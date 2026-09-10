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

That "maximum" is the **99th percentile** of the scans, not the largest of
them. See *The spike that inverted the two populations* below: the largest
scan is one scan, and on three of nine real infusions it was two to four
times the median and dragged both figures to 0.002 – 0.006, under every
chromatographic run measured.

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

The spike that inverted the two populations
-------------------------------------------

The first version of this module took the largest scan as the maximum, and
was written with only the chromatographic population measured. When the nine
bile-acid infusions were finally read, **three of the nine measured 0.0021,
0.0039 and 0.0063 on both figures** — lower than every one of the thirty-nine
chromatographic runs. The two populations were not merely overlapping, they
were the wrong way round, and no value of `FLAT_FRACTION` separates them.

The cause is one scan. All three carry a transient at scan index 1, 0.0084 min
in, of 2.8 to 4.4 times the run's median total; `DCA-d4_TOFMSMS_Mix1` carries
two more mid-run, at 1.08 and 1.10 min. Half of a spike is above everything
else in the run, so a perfectly flat spray measured as though nothing in it
ever reached half its own height. The statistic was wrong, not the threshold.

So the reference is the **99th percentile** of the scans, `REFERENCE_PERCENTILE`,
rather than the largest of them. The choice is measured, not assumed:

| reference | infusions (9) | chromatographic (39) | margin |
|---|---|---|---|
| the largest scan | 0.0021 – 1.0000 | 0.0041 – 0.0984 | **−0.096**, inverted |
| 99.5th percentile | 0.6385 – 1.0000 | 0.0061 – 0.0984 | +0.540 |
| **99th percentile** | **0.9937 – 1.0000** | **0.0143 – 0.1148** | **+0.879** |
| 95th percentile | 0.9937 – 1.0000 | 0.0714 – 0.2623 | +0.731 |
| 90th percentile | 0.9937 – 1.0000 | 0.1148 – 0.4098 | +0.584 |

(each figure the smaller of the two the verdict reads). 99.5 is not enough
because `DCA-d4_TOFMSMS_Mix1`'s three spiked scans are 0.63% of its 473; the
widest margin measured is 0.895 at the 99.2nd percentile and 99 is the round
number next to it. Going lower costs margin from the other end, because
setting aside a real peak's apex lifts the chromatographic figures too.

**Below about a hundred scans the 99th percentile is the largest scan again**,
so a single spike can still call a short infusion chromatographic. `MIN_SCANS`
is 8, and this is a stated gap rather than a fixed one: the shortest infusion
to hand has 146 scans, and the default whenever anything is unclear is "not an
infusion", which is what the application did before this module existed.

Measured
--------

Forty-eight acquisitions, everything to hand, read through `openquant.raw`,
with the reference at the 99th percentile:

| acquisition set | n | `above_half` | `channel_above_half` |
|---|---|---|---|
| `/Volumes/NOBRE/Cyborg/Bileomics/*` — ZenoTOF 7600, 0.6 – 2.0 min, product-ion infusions of bile-acid standards, negative | 9 | 0.9937 – 1.0000 | 0.9937 – 1.0000 |
| `260904_EICs_Isabela_*` — TripleTOF 5600, 21.4 min, 81 channels, MRM-HR | 5 | 0.019 – 0.057 | 0.029 – 0.097 |
| `20.02.21_Esfing_Zeca_Unicamp_*` — TripleTOF 5600, 14.6 min, 144 channels | 26 | 0.033 – 0.426 | 0.016 – 0.377 |
| `260406-Teste-*` — ZenoTOF 7600, 24.0 min, 25 channels, DIA | 8 | 0.031 – 0.361 | 0.014 – 0.059 |

**Nothing is miscalled: 9 infusions and 39 chromatographic runs, 48 of 48.**
The runs with the least chromatography in them are still caught by the second
figure rather than the first. `260406-Teste-Eq01` is a column equilibration
with no injection at all — solvent spraying for 24 minutes, the nearest thing
in the set to an infusion — and measures 0.361 on the sample total against
0.059 on its strongest channel. `20.02.21_Esfing_Zeca_Unicamp_08`, at 0.377 on
its strongest channel, measures 0.049 on the sample total. Across the
thirty-nine the smaller of the two figures never exceeds **0.1148**, and across
the nine infusions it never falls below **0.9937**. `FLAT_FRACTION = 0.75`
therefore sits 0.635 above the worst chromatographic run and 0.244 below the
worst infusion, inside a gap of 0.879. The maximum-margin cut would be 0.554;
0.75 is kept because it is already inside the gap, it is the figure the manual
states, and moving it would change verdicts on nothing measured.

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

Getting the verdict wrong stays cheap by design: it only decides what the
Explorer shows first, every channel and every range stays reachable by hand,
`Average whole run` gives the same view on any sample, and the default
whenever anything cannot be measured is "not an infusion", which is what the
application did before this module existed.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass

import numpy as np

#: how much of a run has to sit at or above half its maximum total ion current
#: before it is called flat. Measured on both populations: the worst
#: chromatographic acquisition reaches 0.1148 on the smaller of the two
#: figures and the worst infusion 0.9937, so this sits inside a gap of 0.879.
FLAT_FRACTION = 0.75

#: the reference height every figure is taken against, as a percentile of the
#: run's scans. **Not the largest scan**: one spray transient at 2.8–4.4 times
#: the median put three of nine real infusions at 0.002–0.006 and turned the
#: two populations the wrong way round. See the module docstring for the
#: measurement behind this particular percentile.
REFERENCE_PERCENTILE = 99.0

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
    #: own maximum — the `REFERENCE_PERCENTILE`-th scan, not the largest one
    above_half: float = 0.0
    #: the same on the channel the average would be shown from
    channel_above_half: float = 0.0
    #: index of that channel, -1 when there is none
    channel_index: int = -1

    def __bool__(self) -> bool:
        return self.infusion


def above_half_fraction(y, percentile: float = REFERENCE_PERCENTILE) -> float:
    """
    The fraction of a trace sitting at or above half its own maximum.

    The maximum is the `percentile`-th of the scans rather than the largest
    of them, because the largest is one scan and a spray transient is one
    scan. Three of nine real infusions carry one, and read 0.002 – 0.006 when
    the largest scan is the reference against 0.994 – 1.000 when the 99th
    percentile is. Every scan is still counted; only the height they are
    counted against changes.
    """
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return 0.0
    top = float(np.percentile(y, percentile)) if percentile < 100 else float(
        np.max(y))
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
            f"above half the maximum (the {REFERENCE_PERCENTILE:g}th-percentile "
            f"scan), over {length:.2f} min — an infusion",
            **figures)
    if flat < FLAT_FRACTION:
        return InfusionVerdict(
            False,
            f"only {flat * 100:.0f}% of the run is at or above half the "
            f"maximum total ion current (the {REFERENCE_PERCENTILE:g}th-"
            f"percentile scan), where {limit} would make it an infusion "
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
