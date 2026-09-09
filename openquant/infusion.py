"""
Telling a direct infusion from a chromatographic run, from the sample alone.

In an infusion there is no column. The analyte is sprayed for a minute or two
and every scan is the same spectrum plus noise, so the chromatogram carries no
information and the thing worth looking at is the average of the whole run. In
a chromatographic run the opposite holds: the ion current is concentrated into
peaks, and a spectrum only means something over one of them.

The verdict is two figures of the same shape, and nothing else:

`above_half`
    the fraction of the sample's total ion chromatogram sitting at or above
    half its own maximum.
`channel_above_half`
    the same measure on the one channel the average would be shown from —
    the product-ion channel carrying the most signal, or the survey when the
    method has no product scan.

A peak is by definition narrow against the run it sits in, so a run with a
peak in it spends most of its scans well under half the apex; a spray that
merely drifts stays above it from the first scan to the last. Both have to be
flat. The sample total alone is not enough — a scheduled method acquires each
transition over its own window, and the sum of many peaks at different times
is flatter than any of them — and one channel alone is not enough either,
since a single transition of a blank is flat because it is empty. Neither
statistic reads a spectrum, so the verdict costs one chromatogram per channel,
works on a `.wiff` whose `.wiff.scan` is missing, and says the same thing
about a file and about its mzML.

Measured
--------

Thirty-nine chromatographic acquisitions, everything to hand, read through
`openquant.raw`:

| acquisition set | n | `above_half` | `channel_above_half` |
|---|---|---|---|
| `260904_EICs_Isabela_*` — TripleTOF 5600, 21.4 min, 81 channels, MRM-HR | 5 | 0.016 – 0.043 | 0.025 – 0.088 |
| `20.02.21_Esfing_Zeca_Unicamp_*` — TripleTOF 5600, 14.6 min, 144 channels | 26 | 0.033 – 0.213 | 0.016 – 0.295 |
| `260406-Teste-*` — ZenoTOF 7600, 24.0 min, 25 channels, DIA | 8 | 0.012 – 0.267 | 0.004 – 0.010 |

The two runs with the least chromatography in them are the ones worth naming,
and both are caught by the second figure rather than the first.
`260406-Teste-Eq01` is a column equilibration with no injection at all —
solvent spraying for 24 minutes, the nearest thing in the set to an infusion —
and measures 0.267 on the sample total against 0.006 on its strongest channel.
`20.02.21_Esfing_Zeca_Unicamp_08`, at 0.295 on its strongest channel, measures
0.049 on the sample total. Across all thirty-nine, the smaller of the two
figures never exceeds **0.098**, so `FLAT_FRACTION = 0.75` stands at nearly
eight times the worst chromatographic case; an infusion, where the same ions
enter the source from the first scan to the last, is expected at 0.95–1.00 on
both.

Three other candidate rules were measured and are not used:

*Scan-to-scan spectral correlation.* The cosine between the average spectrum
of the first fifth of a run and that of the last fifth, binned at 0.1 Da, was
expected to be low for chromatography and near one for an infusion. On the
survey channel it behaves: 0.004 – 0.79 over the same thirty-nine files. On
the **product-ion** channel — the channel an infusion is actually shown from —
it does not: the five `260904_EICs_Isabela_*` runs measure 0.847, 0.933,
0.987, 0.990 and 0.992, because a single MRM-HR transition sees the same near
empty background at both ends of a gradient. A rule that would have to be told
which channel to look at, and that answers 0.99 for a chromatographic run on
the channel that matters, is worse than not having it.

*Coefficient of variation of the total ion chromatogram.* 0.398 – 1.493 over
the same files, the low end being a blank. An infusion whose spray falls by a
third over the run — ordinary — lands close enough to 0.4 that there is no
margin to place a threshold in, and the measure punishes drift, which is not
what is being asked.

*Absence of any peak-shaped feature.* `processing.detect_peaks` on a
synthetic flat trace of 1,000 counts with 3% noise returns three peaks, of
106, 93 and 87 counts. That is the documented behaviour rather than a
surprise — a flat trace gives `estimate_noise` nothing to measure, so
detection falls back to `NOISE_FLOOR` and gates on absolute height — but it
makes "no peak was detected" the wrong question to ask of an infusion.

**Not measured: the infusion side.** The acquisitions this was written for
(`/Volumes/NOBRE/Cyborg/Bileomics/*.wiff`, ZenoTOF 7600 product-ion scans of
bile-acid standards) sit on a drive that was not mounted when this was
written, so the figures above are one population and not two. What is claimed
here is the margin on the chromatographic side, which is measured; the
infusion side is reasoned from what an infusion is. Getting it wrong is cheap
by design: the verdict only decides what the Explorer shows first, every
channel and every range stays reachable by hand, `Average whole run` gives the
same view on any sample, and the default whenever anything cannot be measured
is "not an infusion", which is what the application did before this module
existed.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass

import numpy as np

#: how much of a run has to sit at or above half its maximum total ion current
#: before it is called flat. The worst chromatographic acquisition measured
#: reached 0.098 on the smaller of the two figures.
FLAT_FRACTION = 0.75

#: below this there is not enough of a run to say anything about its shape
MIN_SCANS = 8


@dataclass(frozen=True)
class InfusionVerdict:
    """What a sample looks like, and the figures that say so."""

    infusion: bool
    reason: str
    #: scans in the sample's total ion chromatogram
    n_scans: int = 0
    #: the run from its first scan to its last, in minutes
    length_min: float = 0.0
    #: fraction of the sample's total ion chromatogram at or above half its
    #: own maximum
    above_half: float = 0.0
    #: the same on the channel the average would be shown from
    channel_above_half: float = 0.0
    #: index of that channel, -1 when there is none
    channel_index: int = -1

    def __bool__(self) -> bool:
        return self.infusion


def above_half_fraction(y) -> float:
    """The fraction of a trace sitting at or above half its own maximum."""
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return 0.0
    top = float(np.max(y))
    if top <= 0:
        return 0.0
    return float(np.mean(y >= 0.5 * top))


def strongest_channel(sample):
    """
    The channel an infusion should be shown from: the product-ion channel
    carrying the most signal, or the survey when the method has no product
    scan.

    An infusion is nearly always run to look at one compound's fragments, and
    the survey — where the Explorer would otherwise land, it being the first
    channel of the method — is the one channel that does not show them. Total
    signal rather than height picks the channel actually carrying the compound
    among the several a method may declare, without caring where in the run it
    arrived.
    """
    channels = list(getattr(sample, "channels", None) or [])
    if not channels:
        return None

    def total(channel) -> float:
        try:
            y = np.asarray(channel.tic()[1], dtype=float)
        except Exception:
            return -1.0
        return float(np.sum(y)) if y.size else -1.0

    products = [c for c in channels if not c.info.is_ms1]
    return max(products or channels, key=total)


def run_range(channel) -> tuple[float, float] | None:
    """The channel's whole time axis, as a range to average over."""
    try:
        times = np.asarray(channel.rt, dtype=float)
    except Exception:
        return None
    if times.size == 0:
        return None
    return float(times[0]), float(times[-1])


def is_infusion(sample) -> InfusionVerdict:
    """
    Whether this sample is a direct infusion, with the figures behind it.

    Reads chromatograms only; never a spectrum. A sample that cannot be read
    at all is not an infusion, and says why.
    """
    try:
        x, y = sample.tic()
    except Exception as exc:
        first = str(exc).strip().splitlines()
        return InfusionVerdict(
            False, f"the run could not be read: "
                   f"{first[0] if first else type(exc).__name__}")
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.size < MIN_SCANS:
        return InfusionVerdict(
            False, f"only {x.size} scan(s) — too short a run to tell",
            n_scans=int(x.size))

    length = float(x[-1] - x[0])
    flat = above_half_fraction(y)
    channel = strongest_channel(sample)
    if channel is None:
        return InfusionVerdict(False, "the sample has no channels",
                               n_scans=int(x.size), length_min=length,
                               above_half=flat)
    try:
        channel_flat = above_half_fraction(channel.tic()[1])
    except Exception:
        channel_flat = 0.0
    figures = dict(n_scans=int(x.size), length_min=length, above_half=flat,
                   channel_above_half=channel_flat,
                   channel_index=int(channel.index))

    limit = f"{FLAT_FRACTION * 100:.0f}%"
    if flat >= FLAT_FRACTION and channel_flat >= FLAT_FRACTION:
        return InfusionVerdict(
            True,
            f"the signal never falls away: {flat * 100:.0f}% of the run and "
            f"{channel_flat * 100:.0f}% of its strongest channel sit at or "
            f"above half the maximum, over {length:.2f} min — an infusion",
            **figures)
    if flat < FLAT_FRACTION:
        return InfusionVerdict(
            False,
            f"only {flat * 100:.0f}% of the run is at or above half the "
            f"maximum total ion current ({limit} would make it an infusion) "
            f"— chromatographic",
            **figures)
    return InfusionVerdict(
        False,
        f"the run as a whole is flat ({flat * 100:.0f}% above half maximum) "
        f"but its strongest channel is not ({channel_flat * 100:.0f}%, {limit} "
        f"needed) — peaks at different times, not an infusion",
        **figures)


#: verdicts already reached, by sample, so that the tree — rebuilt on every
#: file opened — and the precursor measurement — run once per component —
#: each pay for the chromatograms once. Weak, so it holds nothing open.
_REACHED: "weakref.WeakKeyDictionary[object, InfusionVerdict]" = (
    weakref.WeakKeyDictionary())


def verdict_for(sample) -> InfusionVerdict:
    """`is_infusion`, measured once per sample and remembered."""
    if sample is None:
        return InfusionVerdict(False, "no sample")
    try:
        verdict = _REACHED.get(sample)
    except TypeError:  # a sample that cannot be weakly referenced or hashed
        return is_infusion(sample)
    if verdict is None:
        verdict = is_infusion(sample)
        try:
            _REACHED[sample] = verdict
        except TypeError:
            pass
    return verdict
