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

#: the tolerance the mass-axis paragraph counts its before and after at. Not
#: the 20 ppm the ladder is *matched* in — that window is wide enough to
#: absorb the error being measured, so counting in it would show nothing —
#: but the 5 ppm the LIPID MAPS tab's own-structure box defaults to, which is
#: the tolerance somebody would actually judge an identification at.
LADDER_CHECK_PPM = 5.0

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
    #: the experiment's own name — `TOF PI`, `TOF MS` — where `channel` is
    #: the whole label with the precursor and the range in it. A table of
    #: many needs the short one and the document's header the long one.
    channel_name: str = ""
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
    # -- the mass axis ------------------------------------------------------- #
    #: the correction fitted from this infusion's own precursor ladder, or
    #: the refusal that says why there is none. Held whether or not it was
    #: applied: a vial that was looked at and left alone is a finding.
    correction: object | None = None
    #: whether the spectrum above is on the corrected axis. False with a
    #: correction present means the switch was off — the fit stands and the
    #: masses printed are the instrument's own.
    recalibrated: bool = False
    #: the same explanation run on the axis as measured, for the before and
    #: after. Only where a correction was applied; None otherwise.
    raw_explanation: Explanation | None = None
    #: the formula and adduct the ladder was predicted from, and where they
    #: came from. Kept so the paragraph can count the ladder's own ions
    #: before and after without asking the session a second time.
    axis_subject: "AxisSubject | None" = None
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
               measure_precursor: bool = True,
               session=None, recalibrated: bool = False) -> InfusionReport:
    """
    A report for one open infusion, reading the file for what it needs.

    `spectrum` is `(mz, intensity)` when the caller already has the averaged
    spectrum on screen — the Explorer does, conditioned the way the pane
    conditions it — and None to read and average it here. `others` are the
    infusions to compare against, each an `(entry, channel)` pair.

    `session`, where it is given, is what the mass correction lives on: the
    axis is fitted from this infusion's own precursor ladder (`fit_axis`) and
    applied when the session's switch is on. `recalibrated` says the caller
    has already applied it to the `spectrum` handed in — the Explorer draws
    the corrected axis, so its report would otherwise correct it twice.
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
        report.channel_name = str(getattr(info, "name", "") or "")
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
    # the mass axis, before anything reads a mass off it. Fitted from the
    # uncorrected average, which is why this comes before the correction is
    # applied and why a caller that has already applied one says so.
    if session is not None:
        report.axis_subject = axis_subject(
            session, report.compound, report.written_precursor,
            report.polarity)
        if recalibrated:
            report.correction = getattr(session, "mass_corrections", {}).get(
                getattr(entry, "key", ""))
        else:
            report.correction = fit_axis(session, entry, channel,
                                         spectrum=(mz, intensity))
        applied = None
        try:
            applied = session.correction_for(getattr(entry, "key", ""))
        except Exception:
            applied = None
        if applied is not None:
            report.recalibrated = True
            if not recalibrated:
                mz = np.asarray(applied.apply(mz), dtype=float)
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
            # what it was actually scored as, which the own-structure path
            # reads off the written precursor rather than off the box
            adduct = str(getattr(lipids, "explanation_adduct", "")
                         or lipids.explain_adduct.currentText())
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
    # the pane's axis is already corrected exactly when a correction is in
    # force for this sample, so that — and not the switch alone — is what
    # says whether the report would be correcting it a second time. Only
    # where the pane actually handed a spectrum over: with none, the report
    # reads its own average and has to correct that itself.
    session = getattr(explorer, "session", None)
    corrected = False
    if session is not None and spectrum is not None:
        try:
            corrected = session.correction_for(ref.entry.key) is not None
        except Exception:
            corrected = False
    return report_for(
        ref.entry, ref.channel, compound=compound, explanation=explanation,
        basis=basis, deuterium=deuterium, hit=hit, library=library,
        adduct=adduct, others=others, label_floor=float(floor),
        centroid=centroid, spectrum=spectrum,
        measure_precursor=measure_precursor,
        session=session, recalibrated=corrected)


def infusions_open(source) -> "list[tuple[SampleEntry, object]]":
    """
    Every open sample read as an infusion, with the channel to show it from.

    `source` is a session, or anything holding one — the Explorer does.
    Read from the session's entries rather than from a tree, so it is the
    same list whether a tree is filtered or not, and so the Analytics side
    can ask the same question without a widget in it.
    """
    session = getattr(source, "session", None)
    if session is None or not hasattr(session, "entries"):
        session = source
    found = []
    for entry in getattr(session, "entries", []):
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
# every open infusion, one row each
# --------------------------------------------------------------------------- #
#: how far a measured precursor may sit from the written one and still be
#: counted in the summary line. `precursor.CONSENSUS_SPREAD_PPM` is the limit
#: the consensus and the mass drift already use to say two measurements are
#: of the same ion; a fourth number for the same question would be one too
#: many. It counts a row for a sentence — nothing is decided on it.
CONFIRMED_PPM = _precursor.CONSENSUS_SPREAD_PPM

#: the library score the summary line counts a record at. Again a figure the
#: sentence is written with and not a threshold anything passes: a record of
#: one's own made from another activation of the same vial scored 6 to 61 on
#: the nine real infusions, and calling 6 a failure would be calling the
#: collision energy a failure.
COUNTED_SCORE = 0.60

#: the columns of the summary, in the order they are shown and exported.
#: One definition for the table, the CSV and the row's own sort keys.
SUMMARY_COLUMNS = (
    "Compound", "Sample", "Mode", "CE (eV)", "Scans", "Base peak m/z",
    "Precursor written", "Found m/z", "Δ ppm", "Height", "Ions found",
    "Library record", "Score", "Reverse", "Matched", "Record Δ ppm",
    "Record CE", "Other infusions", "Mass axis", "File")

#: what goes in the report's table. A4 does not hold nineteen columns and a
#: table squeezed into it is a table nobody reads, so the precursor and the
#: record are each written as one cell there — the panel and the CSV carry
#: the parts.
REPORT_COLUMNS = ("Compound", "Sample", "Mode", "Scans", "Base peak m/z",
                  "Precursor", "Ions found", "Library record", "Score",
                  "Other infusions", "Mass axis")

_NOT_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _flat(text) -> str:
    return _NOT_ALPHANUMERIC.sub("", str(text or "").lower())


def component_for(method, compound: str):
    """
    The component of the method that is this compound, or None.

    Matched on the name with case, spaces and punctuation set aside, because
    a file called `CA-d4_TOFMSMS_Mix1` and a component called `CA d4` are the
    same standard written by two people. Nothing else is guessed: a component
    that merely has a similar name is not this compound.
    """
    want = _flat(compound)
    if not want:
        return None
    for component in getattr(method, "components", []):
        if _flat(getattr(component, "name", "")) == want:
            return component
    return None


def _sticks(report: InfusionReport):
    """The averaged spectrum as centroids: what a search and a score read."""
    trace = report.trace
    if trace is None or trace.mz.size == 0:
        return None
    if report.spectrum is not None and report.spectrum.centroid:
        return trace.mz, trace.intensity
    from .processing import centroid_spectrum

    return centroid_spectrum(trace.mz, trace.intensity)


def raw_sticks(report: InfusionReport):
    """
    The report's centroids put back on the axis the instrument read.

    `MassCorrection.undo` rather than a second copy of the spectrum: an
    offset inverts exactly, so this is the measured masses to the last
    digit and costs one multiplication per peak instead of holding a
    quarter of a million points twice. None when there is nothing to undo.
    """
    sticks = _sticks(report)
    if sticks is None or not report.recalibrated or report.correction is None:
        return None
    return (np.asarray(report.correction.undo(sticks[0]), dtype=float),
            sticks[1])


def _report_note(report: InfusionReport) -> str:
    """How an infusion was acquired, in one cell — `_channel_note`'s words
    from the report rather than from a channel, since a report holds both."""
    bits = [f"{report.scans:,} scans"] if report.scans else []
    if report.collision_energy:
        bits.append(f"CE {report.collision_energy:g} eV")
    return ", ".join(bits)


@dataclass
class InfusionRow:
    """One infusion in the summary: what was measured, and why not."""

    report: InfusionReport
    #: the peaks this infusion is scored on, at `SCORE_SHARE`, kept because
    #: picking them walks a quarter of a million points and every other
    #: infusion of the same compound needs them
    peaks: list = field(default_factory=list)
    #: the other infusions of the same compound: label, score, reverse,
    #: matched, of the other
    others: list = field(default_factory=list)
    #: why a cell is empty, one per column that can be. Short enough for a
    #: cell; the long form of the precursor's is on the report itself.
    precursor_note: str = ""
    explanation_note: str = ""
    library_note: str = ""
    others_note: str = ""

    # -- what it is ---------------------------------------------------------- #
    @property
    def compound(self) -> str:
        return self.report.compound

    @property
    def sample(self) -> str:
        return self.report.sample

    @property
    def mode(self) -> str:
        """Polarity and experiment, and not the whole channel label: the
        precursor and the mass range are columns of their own here, and a
        cell that repeats two other cells is width spent twice."""
        parts = [p for p in (self.report.polarity,
                             self.report.channel_name or self.report.channel)
                 if p]
        return " · ".join(parts)

    # -- what was measured --------------------------------------------------- #
    @property
    def confirmed(self) -> bool:
        """Measured, and within `CONFIRMED_PPM` of what was written."""
        error = self.report.error_ppm()
        return error is not None and abs(error) <= CONFIRMED_PPM

    @property
    def found(self) -> tuple[float, float] | None:
        """The precursor's measured mass and height, wherever it was read."""
        measurement = self.report.measurement
        if measurement is not None and measurement.found:
            return float(measurement.measured), float(measurement.intensity)
        return self.report.survivor

    @property
    def score(self) -> float | None:
        return None if self.report.hit is None else self.report.hit.score

    @property
    def mass_axis(self) -> str:
        """
        What the recalibration did to this vial, in one cell.

        Says whether it was *applied* as well as what it was: a fit that
        stands with the switch off is a measurement of the axis and not a
        change to the numbers beside it, and a cell that read
        "−5.2 ppm, 4 rungs" either way would make the two look the same.
        """
        correction = self.report.correction
        if correction is None:
            return "not fitted"
        if not correction.usable:
            return correction.note.split(" \u00b7 ")[0] or "no lock mass"
        return correction.short + ("" if self.report.recalibrated
                                   else ", not applied")

    # -- the row ------------------------------------------------------------- #
    def cells(self) -> list[str]:
        report = self.report
        found = self.found
        error = report.error_ppm()
        explanation = report.explanation
        hit = report.hit
        base = report.base_peak()
        gap = report.energy_gap()
        return [
            report.compound,
            report.sample,
            self.mode,
            "—" if report.collision_energy is None
            else f"{report.collision_energy:g}",
            f"{report.scans:,}" if report.scans else "—",
            f"{base[0]:,.4f}" if base else "no spectrum",
            f"{report.written_precursor:g}" if report.written_precursor
            else "none written",
            f"{found[0]:,.4f}" if found else (self.precursor_note
                                              or "not measurable"),
            f"{error:+.1f}" if error is not None else "—",
            f"{found[1]:,.0f}" if found else "—",
            (f"{explanation.matched} of {explanation.predicted}"
             if explanation is not None and explanation.predicted
             else f"{explanation.matched}" if explanation is not None
             else self.explanation_note or "nothing run"),
            hit.entry.name if hit is not None
            else self.library_note or "no record",
            f"{hit.score * 100:.0f}" if hit is not None else "—",
            f"{hit.reverse * 100:.0f}" if hit is not None else "—",
            f"{hit.matched} of {hit.of_library}" if hit is not None else "—",
            (f"{hit.delta_ppm:+.1f}"
             if hit is not None and hit.delta_ppm is not None else "—"),
            (f"{gap[1]:g} vs {gap[0]:g}" if gap is not None
             else "same" if hit is not None and report.collision_energy
             else "—"),
            (", ".join(f"{label} {score * 100:.0f}/{reverse * 100:.0f}"
                       for label, score, reverse, _m, _o in self.others)
             if self.others else self.others_note or "—"),
            self.mass_axis,
            report.file,
        ]

    def keys(self) -> list:
        """
        What each cell sorts on: the number where there is one.

        A table sorted on its text puts 9 after 100 and "not measurable"
        wherever the alphabet says, which on a column of measurements is
        worse than not sorting at all.
        """
        report = self.report
        found = self.found
        error = report.error_ppm()
        explanation = report.explanation
        hit = report.hit
        base = report.base_peak()
        cells = self.cells()
        numbers = {
            3: report.collision_energy,
            4: float(report.scans) if report.scans else None,
            5: base[0] if base else None,
            6: report.written_precursor,
            7: found[0] if found else None,
            8: error,
            9: found[1] if found else None,
            10: float(explanation.matched) if explanation is not None else None,
            12: hit.score if hit is not None else None,
            13: hit.reverse if hit is not None else None,
            14: float(hit.matched) if hit is not None else None,
            15: hit.delta_ppm if hit is not None else None,
            18: (self.report.correction.offset_ppm
                 if self.report.correction is not None
                 and self.report.correction.usable else None),
        }
        keys: list = list(cells)
        for column, value in numbers.items():
            # a cell with no number sorts to the end either way round, which
            # is where a reason belongs in a column of measurements
            keys[column] = float("inf") if value is None else float(value)
        return keys

    def report_cells(self) -> list[str]:
        """The same row, narrow enough for A4."""
        report = self.report
        found = self.found
        error = report.error_ppm()
        explanation = report.explanation
        hit = report.hit
        base = report.base_peak()
        gap = report.energy_gap()
        precursor = (f"{found[0]:,.4f} ({error:+.1f} ppm)"
                     if found and error is not None
                     else f"{found[0]:,.4f}" if found
                     else self.precursor_note or "not measurable")
        record = hit.entry.name if hit is not None else (
            self.library_note or "no record")
        if gap is not None:
            record += f" — {gap[1]:g} eV against this run’s {gap[0]:g}"
        return [
            report.compound, report.sample,
            self.mode + (f", {report.collision_energy:g} eV"
                         if report.collision_energy is not None else ""),
            f"{report.scans:,}" if report.scans else "—",
            f"{base[0]:,.4f}" if base else "no spectrum",
            precursor,
            (f"{explanation.matched} of {explanation.predicted}"
             if explanation is not None and explanation.predicted
             else self.explanation_note or "nothing run"),
            record,
            f"{hit.score * 100:.0f}" if hit is not None else "—",
            (", ".join(f"{label} {score * 100:.0f}"
                       for label, score, _r, _m, _o in self.others)
             if self.others else self.others_note or "—"),
            self.mass_axis,
        ]


@dataclass
class InfusionSummary:
    """Every open infusion, one row each, and what they add up to."""

    rows: list[InfusionRow] = field(default_factory=list)
    #: the library of one's own that was searched, as it was named
    library: str = ""
    #: why there are no rows, when there are none
    note: str = ""
    taken: _dt.datetime = field(default_factory=_dt.datetime.now)
    #: how long the measurement took, in seconds
    seconds: float = 0.0

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def compounds(self) -> list[str]:
        return list(dict.fromkeys(row.compound for row in self.rows))

    @property
    def confirmed(self) -> list[InfusionRow]:
        return [row for row in self.rows if row.confirmed]

    @property
    def counted(self) -> list[InfusionRow]:
        return [row for row in self.rows
                if row.score is not None and row.score >= COUNTED_SCORE]

    def summary(self) -> str:
        """
        What the table says, in one line.

        Counts only, and each with what it was counted against: a line that
        said "3 confirmed" without saying within what would be a verdict
        rather than a measurement.
        """
        if not self.rows:
            return self.note or "No infusion is open."
        said = [f"{len(self.compounds)} compound(s) in "
                f"{len(self.rows)} infusion(s)"]
        written = [row for row in self.rows if row.report.written_precursor]
        if written:
            said.append(f"{len(self.confirmed)} of {len(written)} precursor(s) "
                        f"confirmed within {CONFIRMED_PPM:g} ppm")
        else:
            said.append("no precursor is written in any of their methods")
        explained = [row for row in self.rows
                     if row.report.explanation is not None]
        if explained:
            found = sum(row.report.explanation.matched for row in explained)
            offered = sum(row.report.explanation.predicted for row in explained)
            said.append(f"{found} of {offered} predicted ion(s) found across "
                        f"{len(explained)}")
        if self.library:
            said.append(f"{len(self.counted)} with an own record above "
                        f"{COUNTED_SCORE * 100:.0f} in {self.library}")
        else:
            said.append("no library of your own is set")
        return "; ".join(said)


def cross_compare(reports, peaks=None, centroid: bool = False) -> None:
    """
    Every report of one compound drawn and scored against the others.

    Reads no file: both spectra are already held, so this is the picture and
    the cosine and nothing else. It exists because `report_for(others=…)`
    averages the other infusion again for every report that mentions it —
    nine infusions in three compounds would read twenty-seven runs where
    nine were acquired.
    """
    reports = list(reports)
    if peaks is None:
        peaks = [r.spectrum.peaks(r.trace, most=SCORE_PEAKS,
                                  min_relative=SCORE_SHARE)
                 if r.spectrum is not None and r.trace is not None else []
                 for r in reports]
    for index, report in enumerate(reports):
        report.compared = []
        trace = report.trace
        if trace is None:
            continue
        for other_index, other in enumerate(reports):
            other_trace = other.trace
            if other is report or other_trace is None:
                continue
            score, reverse, pairs = score_against(peaks[index],
                                                  peaks[other_index])
            report.compared.append(Compared(
                label=other.sample,
                comparison=head_to_tail(
                    trace.label, trace.mz, trace.intensity,
                    other_trace.label, other_trace.mz, other_trace.intensity,
                    title="", centroid=centroid,
                    label_floor=report.label_floor),
                score=float(score), reverse=float(reverse),
                matched=len(pairs), of_other=len(peaks[other_index]),
                note=_report_note(other)))


def _headless_explanation(session, report: InfusionReport, sticks=None):
    """
    What the component table alone can say about this spectrum.

    A formula and an adduct are enough for the precursor and its neutral
    losses — `explain.explain_formula`, the same call the LIPID MAPS tab
    makes for a formula of one's own. It is offered only where the compound
    is a component of the method **by name**: guessing a formula for a file
    name would be inventing the denominator of "n of m".

    `sticks` overrides the spectrum this reads, so the same explanation can
    be run twice — once on the corrected axis and once on the axis as
    measured — which is the before and after the mass-axis paragraph prints.
    """
    from .explain import explain_formula, formula_ions, significant_peaks

    method = getattr(session, "method", None)
    component = component_for(method, report.compound)
    if component is None:
        return None, "", (f"{report.compound or 'this compound'} is not a "
                          f"component of the method")
    if not component.formula:
        return None, "", f"{component.name} carries no formula"
    formula, deuterium, labelled = _headless_labels(component, report)
    adduct, why = _headless_adduct(component, report, formula)
    if not adduct:
        return None, "", why
    if not formula_ions(component.formula, adduct):
        return None, "", f"{adduct} is not an adduct this program knows"
    sticks = _sticks(report) if sticks is None else sticks
    if sticks is None:
        return None, "", "no spectrum to explain"
    peaks = significant_peaks(*sticks)
    if not peaks:
        return None, "", "no peak above the noise share to explain"
    explanation = explain_formula(component.formula, adduct, peaks,
                                  name=component.name, deuterium=deuterium)
    basis = f"the formula {formula} as {adduct}, {why}{labelled}"
    return explanation, basis, ""


def _headless_labels(component, report: InfusionReport):
    """
    The labels a component declares in its name but not in its formula.

    A d4 standard is bought, named and filed as `CA-d4`, and the formula
    beside it is usually the unlabelled one: nothing in the component table
    has a column for four deuteriums. The name has them, and
    `chemistry.split_labels` reads a trailing `-d4` the same way the LIPID
    MAPS tab does. Without this the arithmetic is out by 4.025 Da and no
    adduct fits the written precursor at all — which is a true statement
    about the formula as typed and a useless one about the compound.

    A formula that already spells its labels out is left alone: it has said
    what it is.
    """
    from .chemistry import (FormulaError, format_formula, parse_formula,
                            split_labels)

    try:
        counts = dict(parse_formula(component.formula))
    except (FormulaError, ValueError):
        return component.formula, 0, ""
    if counts.get("D"):
        return component.formula, 0, ""
    for written in (component.name, report.compound):
        _stem, labels = split_labels(written or "")
        if labels and counts.get("H", 0) >= labels:
            counts["D"] = labels
            counts["H"] -= labels
            return (format_formula(counts), labels,
                    f", with the {labels} label(s) {written} is named for")
    return component.formula, 0, ""


def _headless_adduct(component, report: InfusionReport,
                     formula: str = "") -> tuple[str, str]:
    """
    The adduct to explain this infusion's formula with, and where it came from.

    The component table's own is used when it agrees with the channel's
    written precursor, because that is what the analyst declared. When it
    disagrees — or when the component carries none — the precursor is
    asked instead: it is the one number the instrument was actually given,
    and an ammoniated channel explained as [M+H]+ predicts every fragment
    17 Da away from anything in the spectrum. The reason travels with the
    answer, into the basis line under the table.
    """
    from .chemistry import adducts_matching, identify_adduct

    precursor = report.written_precursor or None
    declared = component.adduct or ""
    formula = formula or component.formula
    if precursor:
        choice = identify_adduct(formula, float(precursor),
                                 report.polarity or None)
        if declared:
            fits = [m for m in adducts_matching(formula,
                                                float(precursor),
                                                report.polarity or None)
                    if m.within and m.name == declared]
            if fits:
                return declared, "from the component table"
            if choice.adduct is not None:
                return choice.adduct.name, (
                    f"read off the written precursor — {choice.reason}, "
                    f"not the {declared} the component table carries")
            return "", (f"{component.name} is written {declared}, and "
                        f"{choice.reason}")
        if choice.adduct is not None:
            return choice.adduct.name, f"read off the written precursor — {choice.reason}"
        return "", (f"{component.name} carries no adduct and {choice.reason}")
    if declared:
        return declared, "from the component table"
    return "", f"{component.name} carries no adduct"


# --------------------------------------------------------------------------- #
# the mass axis, from this infusion's own precursor
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AxisSubject:
    """What an infusion's ladder is predicted from, and where it came from."""

    formula: str = ""
    deuterium: int = 0
    adduct: str = ""
    #: the sentence that says which of the two below answered, and how
    why: str = ""

    def __bool__(self) -> bool:
        return bool(self.formula and self.adduct)


def axis_subject(session, compound: str, written_precursor: float | None,
                 polarity: str = "") -> AxisSubject:
    """
    The formula and adduct to build one infusion's lock-mass ladder from.

    The method's component table first, exactly as the explanation reads it,
    because a component the analyst filled in is a declaration. Where the
    method does not hold the compound the **name** is asked —
    `explain.resolve_name`, the standards table then LIPID MAPS then the
    lipid shorthand — which `_headless_explanation` deliberately refuses to
    do, and the difference is worth stating. A guessed formula is a bad
    denominator for "n of m found": it changes the number of ions offered
    and nothing in the answer says the guess was wrong. It is a safe source
    of a *lock mass*, because a lock mass has to be **found**: a wrong
    formula predicts masses that are not in the spectrum, no rung matches,
    and the fit refuses rather than correcting onto a compound that is not
    in the vial. The two questions have different failure modes and get
    different rules.

    The adduct comes from the written precursor either way, since that is
    the one number the instrument was actually given. The nine real
    infusions are named after the bottle — `CA-d4`, `DCA-d4`, `TDCA-d4` —
    and the standards table answers all three; the two isolating 839.56 get
    no adduct at all, which is the correct answer for a channel that is not
    the compound its file is named after.
    """
    from .chemistry import (FormulaError, format_formula, identify_adduct,
                            parse_formula)
    from .explain import resolve_name

    component = component_for(getattr(session, "method", None), compound)
    formula, deuterium, where = "", 0, ""
    if component is not None and component.formula:
        shim = InfusionReport(compound=compound,
                              written_precursor=written_precursor,
                              polarity=polarity)
        formula, deuterium, _labels = _headless_labels(component, shim)
        where = f"the method's formula for {component.name}"
    if not formula:
        resolved = resolve_name(compound)
        if resolved is None:
            return AxisSubject(why=f"“{compound or 'this file'}” is not in the "
                                   f"method, in the standards table, in LIPID "
                                   f"MAPS or in the lipid shorthand, so "
                                   f"nothing says what mass to look for")
        formula, deuterium = resolved.formula, resolved.labels
        where = f"{compound} read from {resolved.source}"
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return AxisSubject(why=f"“{formula}” is not a formula this can read")
    if deuterium:
        if counts.get("H", 0) < deuterium:
            return AxisSubject(why=f"{formula} has fewer than the {deuterium} "
                                   f"hydrogen(s) its name replaces")
        counts["D"] = counts.get("D", 0) + deuterium
        counts["H"] -= deuterium
    labelled = format_formula(counts)
    if not written_precursor:
        return AxisSubject(formula=labelled, why=(
            f"{where}, but the channel writes no precursor, so nothing says "
            f"which adduct it was ionised as"))
    choice = identify_adduct(labelled, float(written_precursor),
                             polarity or None)
    if choice.adduct is None:
        return AxisSubject(formula=labelled,
                           why=f"{where}; {choice.reason}")
    return AxisSubject(formula=labelled, deuterium=0,
                       adduct=choice.adduct.name,
                       why=f"{where}; {choice.reason}")


def fit_axis(session, entry, channel, spectrum=None, refit: bool = False):
    """
    One infusion's mass correction, fitted once and kept on the session.

    `session.mass_corrections[entry.key]` is where every correction in this
    program lives, so the extraction, the report and the mass-drift panel's
    table need nothing new to see this one. The fit is cached there — the
    refusals too, since a vial that was looked at and left alone is a row
    with a reason on it and not a missing row.

    `spectrum` is the **uncorrected** profile average when the caller has it
    already; the correction cannot be fitted from a corrected axis, which is
    why the Explorer passes what it read before applying anything.

    Returns the correction, or None where this is not an infusion or there is
    no session to keep it on.
    """
    from .processing import centroid_spectrum
    from .recalibrate import fit_infusion

    corrections = getattr(session, "mass_corrections", None)
    if corrections is None or entry is None or channel is None:
        return None
    key = getattr(entry, "key", "")
    if not refit and key in corrections:
        return corrections[key]
    sample = getattr(entry, "sample", None)
    try:
        if sample is None or not verdict_for(sample):
            return None
    except Exception:
        return None

    info = getattr(channel, "info", None)
    compound = compound_of(getattr(entry, "name", ""))
    subject = axis_subject(session, compound,
                           getattr(info, "precursor", None),
                           str(getattr(info, "polarity", "") or ""))
    name = str(getattr(entry, "name", "") or "")
    if not subject:
        from .recalibrate import LADDER_SOURCE, MassCorrection

        correction = MassCorrection(
            sample_key=key, sample_name=name, source=LADDER_SOURCE,
            unit="rung",
            note=f"no lock mass: {subject.why}; the axis stands as measured")
        corrections[key] = correction
        return correction

    if spectrum is None:
        averaged = average_spectrum(channel)
        if averaged is None:
            return None
        spectrum = (averaged[0], averaged[1])
    mz, intensity = centroid_spectrum(np.asarray(spectrum[0], dtype=float),
                                      np.asarray(spectrum[1], dtype=float))
    correction = fit_infusion(mz, intensity, subject.formula, subject.adduct,
                              deuterium=subject.deuterium,
                              sample_key=key, sample_name=name)
    if correction is None:
        return None
    correction.note = " · ".join(p for p in (subject.why, correction.note) if p)
    corrections[key] = correction
    return correction


def _best_record(library, report: InfusionReport):
    """The best record of the analyst's own library for this spectrum."""
    from .library import PRECURSOR_TOLERANCE_DA
    from .lipidmaps import mass_precision

    if library is None or not len(library):
        return None, "no library of your own is set"
    sticks = _sticks(report)
    if sticks is None:
        return None, "no spectrum to search"
    precursor = report.written_precursor or None
    tolerance = PRECURSOR_TOLERANCE_DA
    if precursor:
        # the channel's precursor is good to the decimals it was typed with:
        # `430.35` is known to ±0.005, and a filter tighter than that asks
        # for digits the method never carried
        tolerance = max(tolerance, mass_precision(precursor))
    hits = library.search(sticks[0], sticks[1], precursor,
                          precursor_tolerance=tolerance)
    if not hits:
        where = (f" within ±{tolerance:g} Da of {precursor:g}"
                 if precursor else "")
        return None, f"no record matched{where}"
    return hits[0], ""


def _precursor_reason(report: InfusionReport) -> str:
    """Why there is no measured precursor, short enough for a cell."""
    if not report.written_precursor:
        return "none written"
    note = report.survivor_note
    if note.startswith("nothing at all"):
        return f"nothing within ±{_precursor.SEARCH_WINDOW:g} Da"
    if note.startswith("too little"):
        # the height it did find is the part that fits, and the part worth
        # seeing: the whole sentence is on the report and in the tooltip
        found = re.search(r"at most ([\d,]+) counts", note)
        return (f"under {_precursor.MIN_INTENSITY:,.0f} counts"
                if found is None else
                f"only {found.group(1)} counts survive")
    measurement = report.measurement
    if measurement is not None and measurement.note:
        return measurement.note
    return "not measurable"


def summarise(session, library=None, explanations=None,
              progress=None) -> InfusionSummary | None:
    """
    Every open infusion as one row: the summary that comes before the pages.

    One row per infused sample, grouped by the compound its name starts
    with. Each row is a whole `InfusionReport` — the same object the document
    is printed from, so the table and the pages cannot disagree — plus the
    two things a table of many has that a page of one does not: the mutual
    scores between infusions of the same compound, and a reason in every cell
    that could not be filled.

    `explanations` is what has already been run elsewhere, keyed by compound
    (the Explorer's LIPID MAPS tab); a compound with none is explained from
    the component table's formula and adduct where it has them. `library` is
    the analyst's own `SpectralLibrary`, or None for no library column.

    `progress(done, total)` is called as each infusion is read and stops the
    measurement by returning False, in which case this returns None.
    """
    import time

    started = time.perf_counter()
    infusions = infusions_open(session)
    if not infusions:
        return InfusionSummary(note="No open sample reads as a direct "
                                    "infusion — see the manual on what makes "
                                    "one.")
    groups: dict[str, list] = {}
    for entry, channel in infusions:
        groups.setdefault(compound_of(getattr(entry, "name", "")),
                          []).append((entry, channel))

    given = {str(k): v for k, v in (explanations or {}).items()}
    name = os.path.basename(getattr(library, "path", "") or "") if library \
        else ""
    rows: list[InfusionRow] = []
    done, total = 0, len(infusions)
    for compound, members in groups.items():
        made: list[InfusionRow] = []
        for entry, channel in members:
            report = report_for(entry, channel, compound=compound,
                                library=name, session=session)
            explanation = given.get(compound)
            note = ""
            if explanation is not None:
                report.explanation = explanation
                report.basis = "what was run in the LIPID MAPS tab"
            else:
                report.explanation, report.basis, note = \
                    _headless_explanation(session, report)
                # the same explanation on the axis as the instrument read it,
                # so the mass-axis paragraph can say what the correction
                # bought rather than only what it was
                raw = raw_sticks(report)
                if report.explanation is not None and raw is not None:
                    report.raw_explanation = _headless_explanation(
                        session, report, sticks=raw)[0]
            hit, library_note = _best_record(library, report)
            report.hit = hit
            row = InfusionRow(
                report=report,
                peaks=(report.spectrum.peaks(report.trace, most=SCORE_PEAKS,
                                             min_relative=SCORE_SHARE)
                       if report.spectrum is not None
                       and report.trace is not None else []),
                explanation_note=note, library_note=library_note,
                precursor_note=_precursor_reason(report))
            made.append(row)
            done += 1
            if progress is not None and not progress(done, total):
                return None
        for row in made:
            for other in made:
                if other is row:
                    continue
                score, reverse, pairs = score_against(row.peaks, other.peaks)
                row.others.append((other.sample, float(score), float(reverse),
                                   len(pairs), len(other.peaks)))
            if not row.others:
                row.others_note = "the only infusion of this compound"
        rows += made
    return InfusionSummary(rows=rows, library=name,
                           seconds=time.perf_counter() - started)


def prepare_documents(rows) -> list[InfusionReport]:
    """
    The chosen rows as reports ready to print.

    Each is compared against the other **chosen** infusions of its own
    compound, and against nothing else: a document of two compounds should
    not draw one against the other, and a row left unticked was left unticked
    on purpose. The comparison is made here rather than in `summarise`
    because it holds a copy of both spectra per pair, which is a price worth
    paying for the handful of rows that are printed and not for every row of
    a table.
    """
    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(row.compound, []).append(row)
    for members in groups.values():
        cross_compare([row.report for row in members],
                      [row.peaks for row in members])
    return [row.report for row in rows]


def write_summary_csv(summary: InfusionSummary, path: str | os.PathLike) -> str:
    """The summary as a CSV, in the order the table holds it."""
    import csv

    path = str(path)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(SUMMARY_COLUMNS)
        for row in summary.rows:
            writer.writerow(row.cells())
    return path


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


def _mass_axis_block(report: InfusionReport,
                     breaks: set[str] | None = None) -> str:
    """
    What the mass axis was doing, and what was done about it.

    Printed above the spectrum because it governs every mass printed below
    it, and printed even where nothing was corrected: "no lock mass" is a
    statement about this vial, and a page that simply omitted the paragraph
    would leave a reader unable to tell a corrected axis from an
    uncorrected one.
    """
    from .recalibrate import CONSENSUS_SPREAD_PPM, MIN_LADDER_RUNGS

    correction = report.correction
    if correction is None:
        return ""
    parts = [_sub("Mass axis", breaks),
             f'<p class="meta">A direct infusion has no second injection to '
             f'be read against, so it is recalibrated against itself: the '
             f'precursor and every rung of its own ladder — the core ion a '
             f'labile adduct leaves behind, the cumulative waters, and the '
             f'−1D rungs a labelled standard sheds — each of which is a mass '
             f'the formula already knows, measured here. The correction is '
             f'the intensity-weighted median of their errors, sign flipped, '
             f'and an offset only: the rungs of one precursor span the '
             f'waters it can lose, which is far short of the range they '
             f'would be used over. A rung disagreeing with the rest by more '
             f'than {CONSENSUS_SPREAD_PPM:g} ppm is a different ion in the '
             f'window and is dropped; under {MIN_LADDER_RUNGS} rungs, '
             f'nothing is corrected.</p>']
    # the note only where it is not the verdict already: a refusal's verdict
    # *is* its note, and printing it twice reads as two findings
    aside = ("" if correction.note == correction.verdict
             else f' <span class="meta">{_escape(correction.note)}</span>')
    parts.append(f'<p>{_escape(correction.verdict)}'
                 + (" It <b>is</b> applied to every mass on these pages."
                    if report.recalibrated else
                    " It is <b>not</b> applied: the masses on these pages "
                    "are the ones the instrument read.")
                 + aside + "</p>")
    before, after = correction.before_ppm, correction.after_ppm
    order = sorted(range(len(correction.lock_masses)),
                   key=lambda i: -correction.lock_masses[i].intensity)
    rows = []
    for index in order:
        rung = correction.lock_masses[index]
        rows.append([_escape(rung.component), _number(rung.theoretical, 4),
                     _number(rung.measured, 4), f"{before[index]:+.1f}",
                     f"{after[index]:+.1f}", _number(rung.intensity, 0)])
    parts.append(_table(
        ["Rung", "Theoretical m/z", "Measured m/z", "Δ ppm before",
         "Δ ppm after", "Intensity"], rows, right={1, 2, 3, 4, 5},
        empty="No rung of the ladder was found in this spectrum.",
        widths=["26%", "16%", "16%", "14%", "14%", "14%"]))
    parts.append(_ladder_before_after(report))
    parts.append(_ions_before_after(report))
    return "".join(parts)


def _ladder_before_after(report: InfusionReport) -> str:
    """
    How many of the ladder's own ions land on a peak, before and after.

    Counted at `LADDER_CHECK_PPM` and not at the window the rungs were
    *matched* in: that window has to be wide enough to hold the error being
    measured, so counting inside it would show nothing moving. This is the
    one before-and-after that can always be printed — its denominator is the
    precursor's own formula, which is what the paragraph is about — where
    the explanation's, below, needs an explanation to have been run.
    """
    from .explain import match_peaks, precursor_ions, significant_peaks

    subject, correction = report.axis_subject, report.correction
    if not subject or correction is None or not correction.usable:
        return ""
    now = _sticks(report)
    before = raw_sticks(report)
    if now is None or before is None:
        return ""
    ions = precursor_ions(subject.formula, subject.adduct, subject.deuterium)
    if not ions:
        return ""

    def found(sticks) -> int:
        # `significant_peaks` and not every stick in the window: a product
        # scan averaged over a whole run has thousands of baseline centroids
        # and a 5 ppm window somewhere in the middle of one will always hold
        # something. This is the same floor the explanation is scored on, so
        # the two sentences count the same peaks.
        return len(match_peaks(significant_peaks(*sticks), ions,
                               LADDER_CHECK_PPM))

    return (f'<p class="foot">Of the {len(ions):,} ion(s) '
            f'{_escape(subject.formula)} as {_escape(subject.adduct)} can '
            f'give without cutting a bond, {found(before)} landed on a peak '
            f'within {LADDER_CHECK_PPM:g} ppm on the axis as measured and '
            f'{found(now)} once corrected — counted over the peaks above '
            f'the noise share, which is the floor an explanation is scored '
            f'on.</p>')


def _ions_before_after(report: InfusionReport) -> str:
    """
    What the correction bought the explanation, in one sentence.

    The figure that matters is not the residual — the correction was fitted
    to make that small — but how many of the *other* predicted ions land on
    a peak once the axis has moved, at the tolerance the explanation was
    run at. Absent where the same explanation was not run both ways.
    """
    now, before = report.explanation, report.raw_explanation
    if now is None or before is None:
        return ""
    return (f'<p class="foot">At the tolerance this explanation was run at, '
            f'the axis as measured accounted for {before.matched} of '
            f'{before.predicted} predicted ion(s) and '
            f'{before.share * 100:.1f}% of the intensity; corrected, '
            f'{now.matched} of {now.predicted} and '
            f'{now.share * 100:.1f}%.</p>')


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
        _mass_axis_block(report, breaks),
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
