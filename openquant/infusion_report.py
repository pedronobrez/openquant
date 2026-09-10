"""
One compound, infused, on two or three pages: the document that goes into the
notebook when a standard is validated.

A batch report answers what a run measured. This answers something smaller and
older: *is this vial what the label says it is?* Somebody sprays a standard,
looks at the average of the whole run, checks that the precursor is where the
formula puts it, that the fragments are the ones the structure allows, and that
the spectrum matches the record they made of the same compound last month —
and then has to put something on paper. Screenshots do not say what the label
floor was, and a bare spectrum does not say what was checked.

What is here, and what is deliberately not
------------------------------------------

The report **sums what was checked and nothing else**. Every sentence of the
verdict comes from a measurement that was actually made in this session:

- the precursor, from `precursor.measure` — the survey scan, with the
  product-ion scan as the same-ion check; and where the acquisition has no
  survey at all, from the averaged product-ion spectrum itself, said so in
  those words. Nine real infusions to hand have **one channel each and no
  survey**, so that is the ordinary case rather than the exception;
- the fragments, from whatever was run in the LIPID MAPS tab — a database
  record, a drawing of one's own, or a formula and its neutral losses. `n of
  m`, where m is how many ions the prediction offered, so the reader can see
  the denominator;
- the library, from whatever `SpectralLibrary.search` returned — score,
  reverse, matched, Δ ppm, and the record's own provenance as it was written;
- the collision energy, where the record carries one and it is not this
  acquisition's. A spectrum measured at another energy has other fragments,
  and a score that is low for that reason is not a compound that failed.

There is **no pass/fail badge**, and there will not be one. Identity is a
judgement made from evidence by a person who knows what the vial was supposed
to hold; a green tick invites nobody to read the rest of the page. Where
nothing was run the verdict says exactly that: the report is then a spectrum
and a peak table, which is a fair description of it.

The unexplained peaks are listed on purpose. An explanation that accounts for
40% of a spectrum has said nothing about the other 60%, and the intense part
of that other 60% is where a co-infused impurity — or a wrong compound —
shows itself.

The picture and the tables
--------------------------

The spectrum is drawn through `spectra_compare`, at the label floor the pane
was left at, so what is named on paper is what was named on screen; it is
embedded as a data URI, so an exported HTML report is one file that can be
mailed. Where other infusions of the same compound are open — the same name
prefix, or the ones the analyst ticked — they are drawn head to tail against
this one on a page of their own, each with its cosine against this spectrum
taken by `library.match`, which is the same arithmetic a library search uses.

Everything above is built from plain values: a `SampleEntry`, a channel, an
`Explanation`, a `LibraryHit`. Nothing here reads a widget, so a report can be
built and checked with no window, which is what `tests/test_infusion_report.py`
does. `from_explorer` is the thin adapter that takes what the Explorer already
holds and calls the same builder.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
from dataclasses import dataclass, field

import numpy as np

from . import precursor as _precursor
from . import spectra_compare
from .components import Component
from .explain import Explanation
from .infusion import InfusionVerdict, run_range, strongest_channel, verdict_for
from .library import PEAK_TOLERANCE_PPM, LibraryHit, match
from .report import (IMAGE_WIDTH, _escape, _heading, _number, _STYLE, _table,
                     print_document)
from .samples import SampleEntry
from .spectra_compare import LABEL_MIN_RELATIVE, SpectrumComparison

#: at most this many peaks in the table under the spectrum. A product scan
#: averaged over a whole run has hundreds above any floor worth setting; a
#: table of hundreds is an appendix, not a page of a notebook.
PEAKS_LISTED = 25

#: how tall a peak has to be, against its own spectrum's base peak, to count
#: towards one infusion's score against another. `library.NOISE_SHARE`, the
#: floor a library search itself applies, rather than the drawing's label
#: floor: the label floor decides what is worth *naming* on a picture and at
#: 2% a spectrum that is nearly all precursor offers three peaks to score on.
SCORE_SHARE = 0.01

#: at most this many peaks of either spectrum are scored against the other.
SCORE_PEAKS = 200

#: how many times the document may be laid out again to pull a heading onto
#: the page of what it introduces. More than the batch report's three: a
#: picture cannot be split, so a page here can be a third empty and moving
#: one figure over strands the next — and a batch of infusions has a figure
#: every few paragraphs. Each pass costs one layout, not a re-render.
REFLOWS = 8

#: at most this many unexplained peaks are named. They are listed strongest
#: first, so the ones that matter are the ones printed.
UNEXPLAINED_LISTED = 10

#: at most this many matched fragments are tabulated, strongest first.
FRAGMENTS_LISTED = 40

#: how wide the head-to-tail pictures are drawn, in the pixels of the ninety-
#: six dots to the inch that Qt's `width` attribute means — the same measure
#: the batch report's compared spectra use.
PICTURE_WIDTH = IMAGE_WIDTH

#: how far apart two energies have to be before the report says they differ.
#: Vendors write a nominal energy and a spread; a difference of a fraction of
#: an electronvolt is the same setting written twice.
ENERGY_TOLERANCE_EV = 0.5

#: the names a library record may carry its collision energy under, matched
#: whole and without regard to case. MassBank, NIST and MoNA each spell it
#: differently, so more than one is needed — but matching on what a name
#: *contains* is worse than useless here: `Ion_source` ends in "ce".
ENERGY_KEYS = frozenset({"ce", "energy", "collision_energy",
                         "collisionenergy", "collision"})

#: where a name stops being the compound and starts being the acquisition.
#: `CA-d4_TOFMSMS_Mix1` and `CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1` are the
#: same compound infused twice, and the part before the first separator is
#: what says so.
_NAME_SPLIT = re.compile(r"[_ ]")


def compound_of(name: str) -> str:
    """
    The compound a sample's name starts with.

    A file name in a folder of infusions is the compound and then the
    conditions: `CA-d4_TOFMSMS_Mix1`. The prefix is what makes two of them
    the same compound, and it is only ever a proposal — the dialog lets the
    analyst pick which infusions are compared, because a naming convention
    is not a measurement.
    """
    stem = os.path.splitext(str(name or "").strip())[0]
    first = _NAME_SPLIT.split(stem, 1)[0]
    return first or stem


def energy_of(hit_or_entry) -> float | None:
    """
    The collision energy a library record carries, or None.

    The value is not always a number: MassBank writes `35 % (nominal)` and
    `40 eV`, so the first number in it is taken and the units around it
    ignored — which is the only thing that can be done without a table of
    every vendor's spelling, and is why the report prints the record's field
    as written beside the figure it compares.
    """
    entry = getattr(hit_or_entry, "entry", hit_or_entry)
    fields = getattr(entry, "fields", None) or {}
    for key, value in fields.items():
        flat = str(key).strip().lower().replace(" ", "_")
        if flat not in ENERGY_KEYS:
            continue
        found = re.search(r"[-+]?\d*\.?\d+", str(value))
        if found:
            try:
                return float(found.group())
            except ValueError:
                continue
    return None


# --------------------------------------------------------------------------- #
# what is held
# --------------------------------------------------------------------------- #
@dataclass
class Compared:
    """Another infusion of the same compound, drawn against this one."""

    label: str
    comparison: SpectrumComparison
    #: cosine over everything both spectra hold
    score: float = 0.0
    #: cosine asking only whether the other spectrum's peaks are in this one
    reverse: float = 0.0
    matched: int = 0
    of_other: int = 0
    #: how it was acquired, where the file says: collision energy, scans
    note: str = ""


@dataclass
class InfusionReport:
    """One compound, one infusion, and everything that was checked about it."""

    compound: str = ""
    # -- the header ---------------------------------------------------------- #
    file: str = ""
    sample: str = ""
    instrument: str = ""
    polarity: str = ""
    channel: str = ""
    #: the precursor as the method wrote it, to the decimals it was typed with
    written_precursor: float | None = None
    collision_energy: float | None = None
    scans: int = 0
    rt_range: tuple[float, float] | None = None
    adduct: str = ""
    verdict: InfusionVerdict | None = None
    # -- the accurate precursor ---------------------------------------------- #
    #: `precursor.measure`, which reads the survey scan
    measurement: _precursor.PrecursorMeasurement | None = None
    #: the precursor read off the averaged product-ion spectrum itself — its
    #: mass and its height — for an acquisition with no survey scan to read it
    #: from. A different measurement, and the verdict names it as one.
    survivor: tuple[float, float] | None = None
    #: why there is no survivor, when there is not: a window that held
    #: nothing, or one that held too little to be a measurement
    survivor_note: str = ""
    # -- the spectrum -------------------------------------------------------- #
    #: the averaged spectrum, drawn for paper; one trace
    spectrum: SpectrumComparison | None = None
    label_floor: float = LABEL_MIN_RELATIVE
    # -- what was run -------------------------------------------------------- #
    explanation: Explanation | None = None
    #: what the prediction was made from, in words — the sentence that says
    #: what the denominator of "n of m" counts
    basis: str = ""
    deuterium: int = 0
    hit: LibraryHit | None = None
    library: str = ""
    compared: list[Compared] = field(default_factory=list)
    taken: _dt.datetime = field(default_factory=_dt.datetime.now)

    # -- derived ------------------------------------------------------------- #
    @property
    def title(self) -> str:
        return self.compound or self.sample or "Infusion"

    @property
    def trace(self) -> spectra_compare.SpectrumTrace | None:
        traces = self.spectrum.traces if self.spectrum is not None else []
        return traces[0] if traces else None

    def peaks(self, most: int = PEAKS_LISTED) -> list[tuple[float, float]]:
        """
        The peaks of the averaged spectrum above the pane's label floor,
        strongest first.

        The floor is the one the drawing used, so the table and the picture
        name the same peaks — which is the whole reason the floor travels
        with the comparison rather than being a constant here.
        """
        trace = self.trace
        if trace is None or self.spectrum is None:
            return []
        return self.spectrum.peaks(trace, most=most,
                                   min_relative=self.label_floor)

    def base_peak(self) -> tuple[float, float] | None:
        trace = self.trace
        return trace.base_peak if trace is not None else None

    def unexplained(self, most: int = UNEXPLAINED_LISTED
                    ) -> list[tuple[float, float]]:
        """The intense peaks the explanation does not account for."""
        if self.explanation is None:
            return []
        return self.explanation.unexplained(self.peaks(most=PEAKS_LISTED))[:most]

    def error_ppm(self) -> float | None:
        """How far the accurate precursor sits from the written one."""
        if self.written_precursor in (None, 0):
            return None
        if self.measurement is not None and self.measurement.found:
            return self.measurement.error_ppm
        if self.survivor is not None:
            return ((self.survivor[0] - self.written_precursor)
                    / self.written_precursor * 1e6)
        return None

    def energy_gap(self) -> tuple[float, float] | None:
        """This acquisition's energy and the record's, when they differ."""
        if self.hit is None or self.collision_energy is None:
            return None
        theirs = energy_of(self.hit)
        if theirs is None:
            return None
        if abs(theirs - float(self.collision_energy)) <= ENERGY_TOLERANCE_EV:
            return None
        return float(self.collision_energy), theirs

    # -- the verdict --------------------------------------------------------- #
    def sentences(self) -> list[str]:
        """
        What was checked, one sentence per check, and nothing else.

        Each sentence is a measurement or it is absent. There is no
        conclusion at the end because the conclusion is not this program's
        to draw: what a spectrum is worth depends on what the vial was
        supposed to hold, which is in somebody's notebook and not in the
        file.
        """
        said: list[str] = []
        said += self._precursor_sentences()
        said += self._fragment_sentences()
        said += self._library_sentences()
        if not said:
            said.append(
                "Nothing was checked: no precursor was measured, no structure "
                "or formula was scored against this spectrum and no library "
                "was searched. What follows is the averaged spectrum and its "
                "peaks, which is all this report claims to be.")
        return said

    def _precursor_sentences(self) -> list[str]:
        written = (f"the written {self.written_precursor:.4f}"
                   if self.written_precursor else "the written precursor")
        measurement = self.measurement
        if measurement is not None and measurement.found:
            said = [f"Precursor confirmed at {measurement.error_ppm:+.1f} ppm: "
                    f"the survey scan puts {written} at "
                    f"{measurement.measured:.4f}."]
            agreement = measurement.agreement_ppm
            if agreement is None:
                said[-1] += (" Nothing survived fragmentation to check it "
                             "against, so the survey is the only measurement.")
            elif measurement.corroborated:
                said[-1] += (f" The product-ion scan agrees to "
                             f"{agreement:+.1f} ppm, so the two are the same "
                             f"ion.")
            else:
                said[-1] += (f" The product-ion scan disagrees by "
                             f"{agreement:+.1f} ppm, past the "
                             f"{_precursor.AGREEMENT_PPM:g} ppm that says the "
                             f"same ion — the survey window may have caught a "
                             f"neighbour.")
            return said
        if self.survivor is not None:
            error = self.error_ppm()
            return [f"Precursor confirmed at {error:+.1f} ppm in the "
                    f"product-ion scan itself: {written} survives "
                    f"fragmentation at {self.survivor[0]:.4f}, "
                    f"{self.survivor[1]:,.0f} counts. This acquisition has no "
                    f"survey scan, so there is nothing independent to check "
                    f"it against."]
        if self.survivor_note:
            return [f"Precursor not confirmed: {self.survivor_note}."]
        if measurement is not None:
            return [f"Precursor not confirmed: {measurement.note or 'not found'}."]
        return []

    def _fragment_sentences(self) -> list[str]:
        explanation = self.explanation
        if explanation is None:
            return []
        labels = (f", carrying up to {self.deuterium} unplaced label(s)"
                  if self.deuterium else "")
        if explanation.predicted:
            head = (f"{explanation.matched} of the {explanation.predicted} "
                    f"ions predicted for {explanation.name} were found")
        else:
            head = (f"{explanation.matched} peak(s) were accounted for by "
                    f"{explanation.name}")
        said = [f"{head}{labels}, {explanation.share * 100:.1f}% of the "
                f"spectrum's intensity."]
        listed = self.peaks()
        left = self.explanation.unexplained(listed)
        if left:
            said[-1] += (f" {len(left)} of the {len(listed)} strongest peaks "
                         f"above the label floor are not accounted for, the "
                         f"strongest at {left[0][0]:.4f}.")
        return said

    def _library_sentences(self) -> list[str]:
        hit = self.hit
        if hit is None:
            return []
        delta = ("" if hit.delta_ppm is None
                 else f", the precursors {hit.delta_ppm:+.1f} ppm apart")
        said = [f"Best library record “{hit.entry.name}” at score "
                f"{hit.score * 100:.0f}, reverse {hit.reverse * 100:.0f}, "
                f"{hit.matched} of its {hit.of_library} peak(s) matched"
                f"{delta}."]
        gap = self.energy_gap()
        if gap is not None:
            said.append(
                f"Collision energy differs from the record's "
                f"({gap[0]:g} against {gap[1]:g} eV): a spectrum taken at "
                f"another energy has other fragments, so a lower score here "
                f"is the energy and not necessarily the compound.")
        return said


# --------------------------------------------------------------------------- #
# building one
# --------------------------------------------------------------------------- #
def average_spectrum(channel):
    """
    Every scan of a channel averaged into one spectrum, with the range.

    An infusion has no chromatography to select over, so this is the whole of
    it — the same view `Explorer.average_whole_run` lands on.
    """
    window = run_range(channel)
    if window is None:
        return None
    mz, intensity = channel.spectrum_rt_range(*window)
    return np.asarray(mz, dtype=float), np.asarray(intensity, dtype=float), window


class _Trace:
    """The little a `spectra_compare` trace needs: label, x, y, colour."""

    def __init__(self, label, x, y, colour):
        self.label, self.x, self.y, self.colour = label, x, y, colour


def one_spectrum(label: str, mz, intensity, title: str = "",
                 centroid: bool = False,
                 label_floor: float = LABEL_MIN_RELATIVE) -> SpectrumComparison:
    """One spectrum, drawn for paper."""
    return spectra_compare.from_traces(
        [_Trace(label, mz, intensity, "#234b8c")],
        title=title or label, centroid=centroid, label_floor=label_floor)


def head_to_tail(label: str, mz, intensity, other_label: str, other_mz,
                 other_intensity, title: str | None = None,
                 centroid: bool = False,
                 label_floor: float = LABEL_MIN_RELATIVE) -> SpectrumComparison:
    """
    Two spectra, the second drawn downwards.

    Normalised, because the two are never the same size — a library record is
    held relative to its base peak and a measured average is in counts — and
    a picture of one flat line under a tall one compares nothing.

    `title` of `""` draws none: in this document the heading above the figure
    already names it, and the same words twice, four lines apart, read as a
    mistake. None takes the default.
    """
    if title is None:
        title = f"{label} against {other_label}"
    return spectra_compare.from_traces(
        [_Trace(label, mz, intensity, "#234b8c"),
         _Trace(other_label, other_mz, other_intensity, "#a4262c")],
        title=title, normalise=True, mirror=True, centroid=centroid,
        label_floor=label_floor)


def _peak_arrays(peaks) -> tuple[np.ndarray, np.ndarray]:
    if not peaks:
        return np.zeros(0), np.zeros(0)
    mz = np.asarray([p[0] for p in peaks], dtype=float)
    intensity = np.asarray([p[1] for p in peaks], dtype=float)
    top = float(intensity.max()) if intensity.size else 0.0
    return mz, (intensity / top if top > 0 else intensity)


def score_against(peaks, other_peaks,
                  tolerance_ppm: float = PEAK_TOLERANCE_PPM):
    """
    Two measured spectra scored against each other.

    The same cosine a library search takes, on the same pairing rule, because
    "how alike are these two spectra" has one answer in this program and it
    should not have two. `reverse` here asks whether the other spectrum's
    peaks are in this one, which is what an infusion at a lower collision
    energy against one at a higher energy actually needs.
    """
    mz, intensity = _peak_arrays(peaks)
    other_mz, other_intensity = _peak_arrays(other_peaks)
    if mz.size == 0 or other_mz.size == 0:
        return 0.0, 0.0, ()
    return match(mz, intensity, other_mz, other_intensity, tolerance_ppm)


def _channel_note(channel) -> str:
    info = getattr(channel, "info", None)
    if info is None:
        return ""
    energy = getattr(info, "collision_energy", None)
    bits = [f"{info.n_scans:,} scans"]
    if energy:
        bits.append(f"CE {energy:g} eV")
    return ", ".join(bits)


def report_for(entry: SampleEntry, channel=None, compound: str = "",
               explanation: Explanation | None = None, basis: str = "",
               deuterium: int = 0, hit: LibraryHit | None = None,
               library: str = "", adduct: str = "",
               others: "list[tuple[SampleEntry, object]]" = (),
               label_floor: float = LABEL_MIN_RELATIVE,
               centroid: bool = False,
               spectrum: tuple | None = None,
               measure_precursor: bool = True) -> InfusionReport:
    """
    A report for one open infusion, reading the file for what it needs.

    `spectrum` is `(mz, intensity)` when the caller already has the averaged
    spectrum on screen — the Explorer does, conditioned the way the pane
    conditions it — and None to read and average it here. `others` are the
    infusions to compare against, each an `(entry, channel)` pair.
    """
    sample = getattr(entry, "sample", None)
    channel = channel if channel is not None else (
        strongest_channel(sample) if sample is not None else None)
    info = getattr(channel, "info", None)

    report = InfusionReport(
        compound=compound or compound_of(getattr(entry, "name", "")),
        file=getattr(entry, "filename", ""),
        sample=getattr(entry, "name", ""),
        instrument=str(getattr(sample, "instrument", "") or ""),
        adduct=adduct,
        explanation=explanation, basis=basis, deuterium=int(deuterium),
        hit=hit, library=library, label_floor=float(label_floor),
    )
    if sample is not None:
        try:
            report.verdict = verdict_for(sample)
        except Exception:                       # a reader that cannot say
            report.verdict = None
    if info is not None:
        report.polarity = str(getattr(info, "polarity", "") or "")
        report.channel = info.label
        report.written_precursor = info.precursor
        report.collision_energy = info.collision_energy
        report.scans = int(info.n_scans)
    if channel is None:
        return report

    if spectrum is not None:
        mz, intensity = (np.asarray(spectrum[0], dtype=float),
                         np.asarray(spectrum[1], dtype=float))
        report.rt_range = run_range(channel)
    else:
        averaged = average_spectrum(channel)
        if averaged is None:
            return report
        mz, intensity, report.rt_range = averaged
    report.spectrum = one_spectrum(
        f"{report.sample} · {report.channel}", mz, intensity,
        title=f"{report.title} — averaged over the whole run",
        centroid=centroid, label_floor=label_floor)

    # the accurate precursor. The survey first, because it is the independent
    # measurement; the averaged product-ion spectrum only where there is no
    # survey to read — nine real infusions to hand have no survey at all.
    if measure_precursor and report.written_precursor:
        component = Component(name=report.compound or "infused",
                              precursor=float(report.written_precursor))
        try:
            report.measurement = _precursor.measure(entry, component)
        except Exception:
            report.measurement = None
        if report.measurement is None or not report.measurement.found:
            _survivor(report, mz, intensity)

    mine = (report.spectrum.peaks(report.trace, most=SCORE_PEAKS,
                                  min_relative=SCORE_SHARE)
            if report.trace is not None else [])
    for other_entry, other_channel in others:
        other = _compared(report, mine, other_entry, other_channel,
                          centroid=centroid, label_floor=label_floor)
        if other is not None:
            report.compared.append(other)
    return report


def _survivor(report: InfusionReport, mz, intensity) -> None:
    """
    The precursor in the averaged product-ion spectrum, where there is one.

    Held to `precursor.MIN_INTENSITY`, the same floor `measure` holds the
    survey scan to. Without it the window is a stretch of axis like any other
    and its tallest point is noise: measured on a real CID infusion of cholic
    acid-d4 at 45 eV, the ±0.25 Da window around the written 430.35 holds 84
    counts — 1.5% of the base peak — and centroiding them reports the
    precursor 70 ppm out of place. A precursor that does not survive its own
    collision energy is an ordinary finding, and saying so is better than
    measuring what is left.
    """
    target = float(report.written_precursor or 0.0)
    if not target:
        return
    found = _precursor.in_spectrum(mz, intensity, target)
    floor = _precursor.MIN_INTENSITY
    if found is None:
        report.survivor_note = (
            f"nothing at all sits within ±{_precursor.SEARCH_WINDOW:g} Da of "
            f"{target:g} in the averaged product-ion spectrum")
        return
    mass, height = found
    if height < floor:
        base = report.base_peak()
        share = (f", {height / base[1] * 100:.2f}% of the base peak"
                 if base and base[1] else "")
        report.survivor_note = (
            f"too little of the precursor survives this collision energy to "
            f"measure a mass — at most {height:,.0f} counts{share} within "
            f"±{_precursor.SEARCH_WINDOW:g} Da of {target:g}, under the "
            f"{floor:,.0f} counts below which a centroid is noise rather "
            f"than a measurement")
        return
    report.survivor = (mass, height)


def _compared(report: InfusionReport, mine, other_entry,
              other_channel=None, centroid: bool = False,
              label_floor: float = LABEL_MIN_RELATIVE) -> Compared | None:
    sample = getattr(other_entry, "sample", None)
    channel = other_channel if other_channel is not None else (
        strongest_channel(sample) if sample is not None else None)
    if channel is None:
        return None
    averaged = average_spectrum(channel)
    if averaged is None:
        return None
    other_mz, other_intensity, _window = averaged
    trace = report.trace
    if trace is None:
        return None
    label = str(getattr(other_entry, "name", "") or "")
    comparison = head_to_tail(
        trace.label, trace.mz, trace.intensity,
        f"{label} · {channel.info.label}", other_mz, other_intensity,
        title="", centroid=centroid, label_floor=label_floor)
    theirs = comparison.peaks(comparison.traces[1], most=SCORE_PEAKS,
                              min_relative=SCORE_SHARE)
    score, reverse, pairs = score_against(mine, theirs)
    return Compared(label=label, comparison=comparison, score=float(score),
                    reverse=float(reverse), matched=len(pairs),
                    of_other=len(theirs), note=_channel_note(channel))


def from_explorer(explorer, compound: str = "", others=(),
                  measure_precursor: bool = True) -> InfusionReport | None:
    """
    A report from what the Explorer has on screen for its active channel.

    The pane's own spectrum rather than a fresh average, so the report shows
    what was looked at — background subtracted, recalibrated, smoothed, at the
    label floor the handle was left at. The explanation and the library hit
    are whichever the two panels last produced; where a panel produced none,
    that block is absent and the verdict does not mention it.

    Duck-typed on purpose: it reaches for attributes and settles for None, so
    the report module still has no import of the UI and can be exercised
    without one.
    """
    ref = getattr(explorer, "active_ref", None)
    if ref is None or getattr(ref, "channel", None) is None:
        return None
    spectrum = None
    try:
        spectrum = explorer._current_spectrum()
    except Exception:
        spectrum = None

    lipids = getattr(explorer, "lipid_panel", None)
    explanation = getattr(lipids, "current_explanation", None)
    if callable(explanation):
        explanation = explanation()
    basis = getattr(lipids, "explanation_basis", "") or ""
    deuterium = 0
    adduct = ""
    if lipids is not None:
        try:
            deuterium = int(lipids.own_deuterium.value())
            adduct = str(lipids.explain_adduct.currentText())
        except Exception:
            deuterium, adduct = 0, adduct

    panel = getattr(explorer, "library_panel", None)
    hit = None
    library = ""
    if panel is not None:
        try:
            hit = panel._current_hit()
            library = os.path.basename(getattr(panel.library, "path", "") or "")
        except Exception:
            hit, library = None, ""

    floor = getattr(getattr(explorer, "spectrum", None), "label_floor",
                    LABEL_MIN_RELATIVE)
    centroid = bool(getattr(getattr(explorer, "spectrum", None), "centroided",
                            False))
    return report_for(
        ref.entry, ref.channel, compound=compound, explanation=explanation,
        basis=basis, deuterium=deuterium, hit=hit, library=library,
        adduct=adduct, others=others, label_floor=float(floor),
        centroid=centroid, spectrum=spectrum,
        measure_precursor=measure_precursor)


def infusions_open(explorer) -> "list[tuple[SampleEntry, object]]":
    """
    Every open sample the Explorer reads as an infusion, with its own channel.

    Read from the session's entries rather than from the tree, so it is the
    same list whether the tree is filtered or not.
    """
    found = []
    for entry in getattr(getattr(explorer, "session", None), "entries", []):
        sample = getattr(entry, "sample", None)
        if sample is None:
            continue
        try:
            if not verdict_for(sample):
                continue
        except Exception:
            continue
        channel = strongest_channel(sample)
        if channel is not None:
            found.append((entry, channel))
    return found


# --------------------------------------------------------------------------- #
# the document
# --------------------------------------------------------------------------- #
def _identity(report: InfusionReport) -> str:
    """What this is, from the file rather than from the file name."""
    def value(text) -> str:
        return _escape(text) if text else "—"

    written = ("—" if report.written_precursor is None
               else f"{report.written_precursor:g}")
    energy = ("—" if report.collision_energy is None
              else f"{report.collision_energy:g} eV")
    span = ("—" if report.rt_range is None
            else f"{report.rt_range[0]:.3f}–{report.rt_range[1]:.3f} min")
    accurate = "not measured"
    error = report.error_ppm()
    if report.measurement is not None and report.measurement.found:
        accurate = (f"{report.measurement.measured:.4f} "
                    f"({error:+.1f} ppm, survey scan)")
    elif report.survivor is not None:
        accurate = (f"{report.survivor[0]:.4f} ({error:+.1f} ppm, "
                    f"product-ion scan)")
    elif report.survivor_note or (report.measurement is not None
                                  and report.measurement.note):
        # the reason is a sentence and this is a cell: the verdict below is
        # where it is written out, and a table row that holds a paragraph
        # holds nothing readable
        accurate = "not confirmed — see below"
    rows = [
        ["File", value(report.file), "Sample", value(report.sample)],
        ["Instrument", value(report.instrument), "Polarity",
         value(report.polarity)],
        ["Channel", value(report.channel), "Collision energy", energy],
        ["Precursor, written", written, "Precursor, measured", accurate],
        ["Scans averaged", f"{report.scans:,}" if report.scans else "—",
         "Over", span],
        ["Adduct", value(report.adduct), "Read as", _read_as(report)],
    ]
    cells = []
    for number, row in enumerate(rows):
        stripe = ' class="alt"' if number % 2 else ""
        cells.append(
            f'<tr{stripe}><td class="label" width="18%">{row[0]}</td>'
            f'<td width="32%">{row[1]}</td>'
            f'<td class="label" width="18%">{row[2]}</td>'
            f'<td width="32%">{row[3]}</td></tr>')
    return (f'<table class="ident" width="100%" cellpadding="4" '
            f'cellspacing="0">{"".join(cells)}</table>')


def _sub(title: str, breaks: set[str] | None = None) -> str:
    """
    A sub-heading, marked to start a fresh page when it was left stranded.

    `report._heading` does this for the h2 of a section; here it has to reach
    the h3s as well, because in this document a sub-heading introduces a
    picture and a picture cannot be split. Without the class the reflow pass
    finds the stranded heading, adds it to `breaks`, and nothing happens —
    which is what left a page a third empty with the figure's title alone at
    the foot of the one before.
    """
    css = ' class="break"' if breaks and title in breaks else ""
    return f"<h3{css}>{_escape(title)}</h3>"


def _read_as(report: InfusionReport) -> str:
    """The infusion verdict's own figures, in one cell."""
    verdict = report.verdict
    if verdict is None:
        return "—"
    if verdict.infusion:
        return (f"infusion — {verdict.channel_above_half * 100:.0f}% of this "
                f"channel above half maximum")
    return _escape(verdict.reason.split(" — ")[0])


def _picture(comparison: SpectrumComparison,
             width: int = PICTURE_WIDTH) -> str:
    """
    One drawing, and nothing else in the block.

    Qt cannot split an image across a page, so a picture that does not fit
    moves whole and leaves the rest of the page empty. That is why every
    picture here follows its heading immediately and carries its caption
    underneath: `report._orphan_headings` sees the heading separated from
    the block after it and pushes the pair over together, which is the only
    machinery in this program that can move an image and its title as one.
    """
    height = int(round(width * spectra_compare.DEFAULT_HEIGHT
                       / spectra_compare.DEFAULT_WIDTH))
    return (f'<p><img src="{spectra_compare.data_uri(comparison)}" '
            f'width="{width}" height="{height}" /></p>')


def _verdict(report: InfusionReport, breaks: set[str] | None = None) -> str:
    parts = [_sub("What was measured", breaks),
             '<p class="meta">Every sentence below is a measurement that was '
             'made. There is no overall pass or fail: whether this is the '
             'compound the vial should hold is a judgement for the person '
             'who filled it, made from the evidence on these pages.</p>']
    parts.append("<p>" + " ".join(_escape(s) for s in report.sentences())
                 + "</p>")
    return "".join(parts)


def _spectrum_block(report: InfusionReport,
                    breaks: set[str] | None = None) -> str:
    if report.spectrum is None or report.trace is None:
        return (_sub("Averaged spectrum", breaks)
                + '<p class="empty">No spectrum could be read from this '
                'channel.</p>')
    base = report.base_peak()
    peaks = report.peaks()
    parts = [_sub("Averaged spectrum", breaks),
             _picture(report.spectrum),
             f'<p class="foot">Every scan of the channel averaged into one '
             f'spectrum — an infusion has no chromatography to select over, '
             f'so this is the whole of the run. Peaks are labelled at '
             f'{report.label_floor:.2%} of the tallest in view, which is where '
             f'the label floor stood in the Explorer, so the masses printed '
             f'here are the masses that were on screen.</p>']
    rows = []
    top = base[1] if base else 0.0
    for mz, height in peaks:
        rows.append([_number(mz, 4), _number(height, 0),
                     f"{height / top * 100:,.2f}" if top else "—"])
    parts.append(_table(["m/z", "Intensity", "Relative %"], rows,
                        right={0, 1, 2},
                        empty="No peak reaches the label floor.",
                        widths=["34%", "33%", "33%"]))
    if base:
        parts.append(
            f'<p class="foot">Base peak {base[0]:,.4f} at {base[1]:,.0f} '
            f'counts; {len(peaks):,} peak(s) listed of those at or above the '
            f'label floor, strongest first, at most {PEAKS_LISTED}.</p>')
    return "".join(parts)


def _explanation_block(report: InfusionReport,
                       breaks: set[str] | None = None) -> str:
    explanation = report.explanation
    if explanation is None:
        return ""
    labelled = (f" Deuterium is unplaced: every ion is offered carrying 0 to "
                f"{report.deuterium} label(s), and the column says how many "
                f"the fragment kept."
                if report.deuterium else "")
    parts = [_sub(f"Structural explanation — {explanation.name}", breaks)]
    basis = report.basis or (
        f"the formula {explanation.record.formula}" if explanation.record.formula
        else "the candidate structure")
    parts.append(
        f'<p class="meta">Predicted from {_escape(basis)}.'
        f'{labelled} A match is a predicted mass within the tolerance of a '
        f'measured peak; it is arithmetic on a formula, not a mechanism.</p>')
    rows = []
    for match_ in sorted(explanation.matches, key=lambda m: -m.intensity)[
            :FRAGMENTS_LISTED]:
        ion = match_.ion
        labels = getattr(ion, "labels", 0)
        rows.append([
            _escape(match_.best_route),
            _number(ion.mz, 4), _number(match_.mz, 4),
            f"{match_.error_ppm:+.1f}",
            f"{labels:d}" if report.deuterium else "—",
            _number(match_.intensity, 0)])
    parts.append(_table(
        ["Ion", "Theoretical m/z", "Measured m/z", "Δ ppm", "D kept",
         "Intensity"],
        rows, right={1, 2, 3, 4, 5},
        empty="No predicted ion landed on a measured peak.",
        widths=["34%", "14%", "14%", "10%", "10%", "18%"]))
    predicted = (f" of the {explanation.predicted:,} the prediction offered"
                 if explanation.predicted else "")
    parts.append(
        f'<p class="foot">{explanation.matched:,} ion(s) matched{predicted}, '
        f'accounting for {explanation.share * 100:.1f}% of the intensity of '
        f'the {explanation.considered:,} peak(s) that were scored.</p>')

    left = report.unexplained()
    parts.append(_sub("Peaks it does not account for", breaks))
    parts.append(
        '<p class="meta">The honest half of the answer. An explanation that '
        'accounts for part of a spectrum has said nothing about the rest, and '
        'a strong peak here is where a co-infused impurity, an adduct nobody '
        'predicted, or the wrong compound shows itself.</p>')
    total = report.base_peak()
    top = total[1] if total else 0.0
    parts.append(_table(
        ["m/z", "Intensity", "Relative %"],
        [[_number(mz, 4), _number(height, 0),
          f"{height / top * 100:,.2f}" if top else "—"]
         for mz, height in left],
        right={0, 1, 2},
        empty="Every peak above the label floor is accounted for.",
        widths=["34%", "33%", "33%"]))
    return "".join(parts)


def _library_block(report: InfusionReport,
                   breaks: set[str] | None = None) -> str:
    hit = report.hit
    if hit is None:
        return ""
    entry = hit.entry
    where = f" in {_escape(report.library)}" if report.library else ""
    parts = [_sub(f"Library — {entry.name}", breaks)]
    comparison = _hit_picture(report)
    if comparison is not None:
        parts.append(_picture(comparison))
        parts.append('<p class="foot">The measured spectrum above, the record '
                     'below, both drawn as centroids on their own base peak. '
                     'A record is already sticks, so nothing here is '
                     'centroided a second time — doing that averages a stick '
                     'with its neighbour and moves the mass.</p>')
    parts.append(
        f'<p class="meta">The best record{where}. The score is the cosine '
        f'over everything both spectra hold; the reverse asks only whether '
        f'the record’s peaks are in the measured one, so a high reverse with '
        f'a low score is this compound with company.</p>')
    delta = "—" if hit.delta_ppm is None else f"{hit.delta_ppm:+.1f}"
    parts.append(_table(
        ["Score", "Reverse", "Matched", "Record precursor", "Δ ppm"],
        [[f"{hit.score * 100:.0f}", f"{hit.reverse * 100:.0f}",
          f"{hit.matched} of {hit.of_library}",
          "—" if entry.precursor is None else _number(entry.precursor, 4),
          delta]],
        right={0, 1, 2, 3, 4},
        widths=["18%", "18%", "20%", "24%", "20%"]))

    provenance = []
    if entry.precursor_type:
        provenance.append(["Precursor type", _escape(entry.precursor_type)])
    if entry.formula:
        provenance.append(["Formula", _escape(entry.formula)])
    for key, value in (entry.fields or {}).items():
        provenance.append([_escape(key), _escape(value)])
    if entry.source:
        provenance.append(["Source", _escape(os.path.basename(entry.source))])
    parts.append(_sub("Where the record came from", breaks))
    parts.append(
        '<p class="meta">The record’s own fields, as they were written. A '
        'record whose provenance is not on the page cannot be checked against '
        'the acquisition it was made from.</p>')
    parts.append(_table(None, provenance,
                        empty="The record carries no fields of its own.",
                        widths=["28%", "72%"]))
    return "".join(parts)


def _hit_picture(report: InfusionReport) -> SpectrumComparison | None:
    """
    The measured spectrum against the record it matched, head to tail.

    A library record **is** centroids, and the measured average is profile, so
    the measured one is centroided here and the comparison is told they are
    sticks. Without that the picture is drawn as a polyline through the
    record's sticks and its labels are centroids taken *across* them: the
    first version of this page drew the cholic acid record as one spike
    labelled 359.6428, for a record whose base peak is 359.2870.
    """
    hit, trace = report.hit, report.trace
    if hit is None or trace is None or hit.entry.mz.size == 0:
        return None
    already = bool(report.spectrum.centroid) if report.spectrum else False
    mz, intensity = trace.mz, trace.intensity
    if not already:
        from .processing import centroid_spectrum

        mz, intensity = centroid_spectrum(mz, intensity)
    # no title inside the drawing: the heading above it says the same words,
    # and the legend already names which trace is which
    return head_to_tail(
        trace.label, mz, intensity,
        hit.entry.name, hit.entry.mz, hit.entry.intensity,
        title="", centroid=True, label_floor=report.label_floor)


def _compared_block(report: InfusionReport,
                    breaks: set[str] | None = None) -> str:
    if not report.compared:
        return ""
    parts = [_sub("Other infusions of the same compound", breaks),
             f'<p class="meta">Each one averaged over its own whole run and '
             f'drawn head to tail against this one, both on their own base '
             f'peak. The score is the same cosine a library search takes, '
             f'over the peaks at or above {SCORE_SHARE:.0%} of each '
             f'spectrum’s base peak — the floor a library search itself '
             f'uses, not the drawing’s label floor; the reverse asks whether '
             f'the other spectrum’s peaks are in this one, which is what an '
             f'infusion at a lower collision energy needs.</p>']
    parts.append(_table(
        ["Infusion", "Score", "Reverse", "Matched", "How it was acquired"],
        [[_escape(other.label), f"{other.score * 100:.0f}",
          f"{other.reverse * 100:.0f}",
          f"{other.matched} of {other.of_other}", _escape(other.note)]
         for other in report.compared],
        right={1, 2, 3},
        widths=["38%", "11%", "11%", "16%", "24%"]))
    for other in report.compared:
        parts.append(_sub(f"Against {other.label}", breaks))
        parts.append(_picture(other.comparison))
    return "".join(parts)


def build_section(report: InfusionReport, heading: str = "",
                  breaks: set[str] | None = None) -> str:
    """
    One compound: the heading, the header, the verdict and the blocks.

    An empty `heading` leaves the heading off entirely, which is what a
    document of one compound wants — its title block already names the
    compound, and a page whose first two lines are the same words twice
    reads as a mistake.
    """
    return "".join([
        _heading(heading, breaks) if heading else "",
        _identity(report),
        _verdict(report, breaks),
        _spectrum_block(report, breaks),
        _explanation_block(report, breaks),
        _library_block(report, breaks),
        _compared_block(report, breaks),
    ])


def _title_block(title: str, reports: list[InfusionReport]) -> str:
    """
    What this is, on the page rather than in a file name.

    One compound gets the eyebrow and the title alone: the identity table
    underneath already carries the file, the sample, the instrument and the
    time. Only a document of several needs a count in front of them.
    """
    from . import __version__

    head = (f'<p class="eyebrow">OpenQuant {_escape(__version__)} · direct '
            f'infusion report</p><h1>{_escape(title)}</h1>')
    if len(reports) < 2:
        return head
    when = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    files = len({r.file for r in reports if r.file})
    return (
        head
        + f'<table class="ident" width="100%" cellpadding="4" cellspacing="0">'
        f'<tr><td class="label" width="18%">Compounds</td>'
        f'<td width="32%">{len(reports):,}</td>'
        f'<td class="label" width="18%">Generated</td><td width="32%">{when}</td>'
        f'</tr><tr class="alt"><td class="label">Acquisitions</td>'
        f'<td>{files:,}</td><td class="label">Instrument</td>'
        f'<td>{_escape(reports[0].instrument) if reports else "—"}</td></tr>'
        f"</table>")


def _contents(headings: list[str], pages: dict[str, int] | None) -> str:
    if len(headings) < 2:
        return ""
    rows = []
    for number, heading in enumerate(headings):
        stripe = ' class="alt"' if number % 2 else ""
        page = "" if not pages else str(pages.get(heading, ""))
        cell = (f'<td class="num" width="8%">{page}</td>'
                if pages is not None else "")
        rows.append(f'<tr{stripe}><td>{_escape(heading)}</td>{cell}</tr>')
    return ('<h2 class="plain">Contents</h2>'
            '<table class="contents" width="60%" cellpadding="3" '
            f'cellspacing="0">{"".join(rows)}</table>')


def _as_list(reports) -> list[InfusionReport]:
    if isinstance(reports, InfusionReport):
        return [reports]
    return list(reports)


def default_title(reports: list[InfusionReport]) -> str:
    if len(reports) == 1:
        return f"{reports[0].title} — direct infusion"
    return "Direct infusion report"


def build_html(reports, title: str = "", contents: dict[str, int] | None = None,
               breaks: set[str] | None = None) -> str:
    """
    One compound, or every one of them, as one HTML document.

    `contents` and `breaks` are what `report.print_document` works out for
    itself — None for no page column, `{}` to reserve one, the mapping on the
    final pass — so the two documents are printed through the same code and
    the heading that ends a page is chased in one place.
    """
    reports = _as_list(reports)
    title = title or default_title(reports)
    headings = ([f"{number}. {r.title}"
                 for number, r in enumerate(reports, start=1)]
                if len(reports) > 1 else [""] * len(reports))
    breaks = set(breaks or ())
    if len(reports) > 1:
        # a compound starts a page of its own: a section that begins half way
        # down the page under the end of another compound reads as one report
        breaks |= set(headings[1:])
    parts = ["<!DOCTYPE html>", "<html><head><meta charset='utf-8'>",
             f"<title>{_escape(title)}</title>",
             f"<style>{_STYLE}</style></head><body>",
             _title_block(title, reports),
             _contents(headings, contents)]
    for heading, report in zip(headings, reports, strict=True):
        parts.append(build_section(report, heading, breaks))
    parts.append("</body></html>")
    return "".join(parts)


def write_html(reports, path: str | os.PathLike, **kwargs) -> str:
    path = str(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_html(reports, **kwargs))
    return path


def write_pdf(reports, path: str | os.PathLike, **kwargs) -> str:
    """
    The report on A4 portrait pages, through the batch report's printer.

    One compound comes to one to three pages, depending on what was run; a
    batch is one section per compound, each starting on a page of its own.
    """
    reports = _as_list(reports)
    title = kwargs.pop("title", "") or default_title(reports)
    return print_document(
        lambda contents, breaks: build_html(reports, title=title,
                                            contents=contents, breaks=breaks),
        path, title, reflows=REFLOWS)
