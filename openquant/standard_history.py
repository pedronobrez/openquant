"""
One infused standard across the days it was verified: the Batch QC idea
applied to a library of one's own.

A record written by *Add spectrum to library…* is a verification that has
already happened. Every time somebody sprays the standard to check the vial,
one more record of the same compound goes into the same MSP, and after a
few months the file holds the only longitudinal measurement of that standard
anybody has. Nothing was reading it back.

This does. It asks of one compound the three questions a control chart asks
of a batch, with the records in the order they were **acquired** rather than
the order they were typed in:

*Does it still look like itself?* The cosine of each record against the
first — `library.match`, the same arithmetic a library search uses, so
"how alike are two spectra" has one answer in this program and not two.
Both scores are kept: the plain cosine, and the reverse, which asks only
whether the reference's peaks are still there and so forgives an impurity
that has arrived since.

*Is the base peak still where it was?* Its distance from the reference's
base peak, in ppm. This is the one metric that cannot be a percentage of
its own centre — a median of zero ppm has no percentage — which is what
`qc.Limits.absolute` exists for.

*Is it still giving what it gave?* The base peak's absolute height. A
library format holds every peak as a share of the base peak, so this is
lost the moment a record is written unless it is written too; it is, in
`library.BASE_INTENSITY_FIELD`, from the version that added this module
onwards. Records made before that have none and the chart says so rather
than charting the survivors as though they were the whole file.

Three things are deliberate
---------------------------

**The arithmetic is `qc`'s, not a second copy of it.** `qc.chart_from_values`
draws the centre, the spread, the two conditions a point has to meet before
it is out, and the trend that needs both a size and a correlation. A history
differs from a batch in two parameters — how many points are enough, and
whether the scale is a percentage — and in nothing else. Two views that
disagreed about what "out" means would be worse than one view.

**Three records, not six.** A batch is acquired in an afternoon and
`qc.MIN_INJECTIONS` is six because it can be. A history accumulates one
record per verification, and six of them is a year; the floor here is the
fewest points a median and a spread can be taken from at all. Below it
nothing is drawn and the verdict is *too few to chart* — a limit through
two points is a line through two points, which is not a limit.

**A record at 22 eV EAD is not compared with one at 45 eV CID.** A spectrum
measured at another collision energy has other fragments and a different
base peak; scoring across energies measures the method, not the standard.
So the records of one compound are cut into series by energy and
activation, each with its own reference — the first record *of that series*
— and the absolute height, which is only comparable within one method
anyway, is charted inside a series and never across.

What it cannot do
-----------------

The activation is read from the record's own field where an exporter wrote
one and from the record's name otherwise, because no vendor field this
program reads carries it: the nine ZenoTOF infusions this was measured on
say `TOF PI`, `Product`, and the electron energy appears only in the file
name. A record whose name does not say is grouped as unstated, which is
right for a laboratory that runs CID and never says so and wrong for one
that renames its files — and the grouping is shown, so it can be seen.
"""

from __future__ import annotations

import os
import re

import numpy as np

from .infusion_report import ENERGY_TOLERANCE_EV, compound_of, energy_of
from .library import (PEAK_TOLERANCE_PPM, LibraryEntry, SpectralLibrary,
                      acquired_of, base_intensity_of, field_value, load_library,
                      match)
from .qc import (DRIFT_CORRELATION, OUTLIER_SIGMA, WARN_SIGMA, ControlChart,
                 Limits, PERCENT, chart_from_values)

#: the fewest records before a centre and a spread mean anything. Three is
#: the fewest a median absolute deviation can be taken from; below it the
#: history is a list, and says so.
MIN_RECORDS = 3

#: how far the base peak may sit from the reference's before the difference
#: is worth acting on, in ppm — and past which it is out whatever the
#: spread. `library.PEAK_TOLERANCE_PPM` is the figure the library itself
#: pairs peaks within: beyond it a search would not call these the same ion
#: at all, so they are not one ion measured twice.
WARN_PPM = PEAK_TOLERANCE_PPM / 2
OUT_PPM = PEAK_TOLERANCE_PPM
ALWAYS_OUT_PPM = 2 * PEAK_TOLERANCE_PPM

#: the floors the mass chart flags on. Absolute, because the deviation is
#: already a ratio: ppm of ppm is not a quantity.
MASS_LIMITS = Limits(warn=WARN_PPM, out=OUT_PPM, always=ALWAYS_OUT_PPM,
                     drift=OUT_PPM, unit=" ppm", absolute=True)

#: past this the two base peaks are not one ion measured twice, and the
#: difference between them is not a mass error to be charted.
#:
#: This is `mass_drift`'s lesson in another place: a −351 ppm "drift" was a
#: window catching a different neighbour each time, and a measurement that
#: cannot be shown to be of the same ion is not judged. The figure is
#: `recalibrate.MAX_LOCK_ERROR_PPM`, which that module measured as the far
#: edge of the trough between "the ion the formula names" and something
#: else. Measured here it is not a close call: two of the nine bile-acid
#: infusions came back 950,000 and 1,224,000 ppm from their reference,
#: which is 377.30 against 839.23 — a different precursor, not a drift.
SAME_PEAK_PPM = 50.0

#: what the three charts are called, in the order they are offered
SCORE = "score against the first record"
MASS = "base peak, ppm from the first record"
INTENSITY = "base peak intensity"
METRICS = (SCORE, MASS, INTENSITY)

#: the fields an exporter may name the activation in
_ACTIVATION_KEYS = frozenset({"activation", "activationtype",
                              "fragmentation", "fragmentationmode",
                              "fragmentationtype", "dissociation"})

#: activations worth telling apart, matched as whole words in a record's
#: name. Electron-activated dissociation and a collision cell do not produce
#: the same spectrum of the same compound, and a history that mixed them
#: would report the method changing as the standard changing.
ACTIVATIONS = ("EAD", "ECD", "ETD", "EIEIO", "UVPD", "HCD", "CID")

#: how an activation is written in a name: on its own, between separators
_WORD = re.compile(r"(?:^|[^A-Za-z])(%s)(?![A-Za-z])"
                   % "|".join(ACTIVATIONS), re.IGNORECASE)

#: a file name inside a record's comment. The comment is written as the
#: pane's title, the file and the date; this is the piece that names the
#: acquisition, and it is taken by its extension rather than by position
#: because the title itself holds separators.
_FILE = re.compile(r"[^\s·|,;]+\.(?:wiff2?|mzml|mzxml|raw|d)\b", re.IGNORECASE)

#: what a record's kind is called on the chart. `qc.Injection` carries a
#: sample type; a library record has none, and this is what stands there.
RECORD = "record"


# --------------------------------------------------------------------------- #
# reading a record
# --------------------------------------------------------------------------- #
def activation_of(entry: LibraryEntry) -> str:
    """
    How the compound was fragmented: a field where one was written, and the
    record's name otherwise.

    Returned upper case, or `""` when nothing says. Empty is *unstated*, not
    *collision-induced*: guessing the ordinary case would put a record that
    says nothing into the same series as one that says CID, which is the
    comparison this exists to prevent.
    """
    written = field_value(entry, _ACTIVATION_KEYS)
    for text in (written, getattr(entry, "name", "") or "",
                 field_value(entry, {"comment"})):
        found = _WORD.search(str(text))
        if found:
            return found.group(1).upper()
    return ""


def file_of(entry: LibraryEntry) -> str:
    """The acquisition a record was made from, where its comment names one."""
    found = _FILE.search(field_value(entry, {"comment"}) or "")
    return os.path.basename(found.group()) if found else ""


class Record:
    """One record of one compound, with what it is compared against."""

    def __init__(self, entry: LibraryEntry, index: int = 0):
        self.entry = entry
        self.index = index
        self.name = entry.name
        self.compound = compound_of(entry.name)
        self.when = acquired_of(entry)
        self.file = file_of(entry)
        self.energy = energy_of(entry)
        self.activation = activation_of(entry)
        self.precursor = entry.precursor
        self.base_intensity = base_intensity_of(entry)
        top = int(np.argmax(entry.intensity)) if entry.peaks else 0
        self.base_mz = float(entry.mz[top]) if entry.peaks else 0.0
        #: filled in by the series it lands in
        self.order = 0
        self.score: float | None = None
        self.reverse: float | None = None
        self.previous_score: float | None = None
        self.previous_reverse: float | None = None
        #: the base peak's distance from the reference's, always
        self.base_gap_ppm: float | None = None
        #: and the same figure where it can be read as a mass error at all:
        #: None when the two base peaks are not the same ion
        self.ppm: float | None = None

    @property
    def same_base_peak(self) -> bool:
        """
        Whether this record's base peak is the reference's ion at all.

        False is not a large mass error; it is a different ion. Saying which
        is the difference between a standard whose axis has moved and a
        record of something else under the same compound's name.
        """
        return (self.base_gap_ppm is not None
                and abs(self.base_gap_ppm) <= SAME_PEAK_PPM)

    @property
    def day(self) -> str:
        """The date alone, where the record carries a date and a time."""
        return self.when[:10] if len(self.when) >= 10 else self.when

    @property
    def label(self) -> str:
        """What the record is called on a chart: the file, or its name."""
        return self.file or self.name

    def __repr__(self) -> str:                            # pragma: no cover
        return f"<Record {self.name} {self.when or 'undated'}>"


def _sort_key(record: Record) -> tuple:
    """
    Acquisition date first, and the order the file holds them in after.

    A record with no date sorts last rather than first: the first record of a
    series is its reference, and an undated record cannot be shown to be the
    earliest one. Where nothing is dated the file's own order stands, which
    is the order the records were appended in.
    """
    return (0, record.when, record.index) if record.when \
        else (1, "", record.index)


# --------------------------------------------------------------------------- #
# one compound at one energy
# --------------------------------------------------------------------------- #
class Series:
    """
    One compound at one collision energy and activation, in date order.

    The reference is the first record of the *series*, not of the compound.
    The two are the same thing wherever a standard is only ever verified one
    way, and where they differ the series is right: a cosine against a
    spectrum measured at another energy is a measurement of the energy.
    """

    def __init__(self, compound: str, energy: float | None, activation: str,
                 records: list[Record]):
        self.compound = compound
        self.energy = energy
        self.activation = activation
        self.records = sorted(records, key=_sort_key)
        for order, record in enumerate(self.records, start=1):
            record.order = order
        self._score()
        self.charts: dict[str, ControlChart] = {
            SCORE: self._chart(SCORE, [(r, None if r.score is None
                                        else r.score * 100.0)
                                       for r in self.records]),
            MASS: self._chart(
                MASS, [(r, r.ppm) for r in self.records], limits=MASS_LIMITS,
                missing=(f"left out: the base peak is more than "
                         f"{SAME_PEAK_PPM:g} ppm from the first record's, "
                         f"which is a different ion and not a mass error")),
            INTENSITY: self._chart(
                INTENSITY, [(r, r.base_intensity) for r in self.records],
                missing="left out: written before the base peak's height was"),
        }

    # -- what it is called ---------------------------------------------------- #
    @property
    def conditions(self) -> str:
        """The energy and activation, as a person would write them."""
        bits = []
        if self.activation:
            bits.append(self.activation)
        bits.append("CE unstated" if self.energy is None
                    else f"{self.energy:g} eV")
        return " ".join(bits)

    @property
    def label(self) -> str:
        return f"{self.compound} · {self.conditions}"

    @property
    def key(self) -> tuple:
        return (self.compound, self.activation,
                float("inf") if self.energy is None else self.energy)

    # -- what it holds --------------------------------------------------------- #
    @property
    def reference(self) -> Record | None:
        return self.records[0] if self.records else None

    @property
    def dated(self) -> int:
        return sum(1 for record in self.records if record.when)

    @property
    def ordered(self) -> bool:
        """Whether every record said when it was acquired."""
        return bool(self.records) and self.dated == len(self.records)

    @property
    def days(self) -> list[str]:
        return sorted({record.day for record in self.records if record.day})

    @property
    def with_intensity(self) -> int:
        return sum(1 for record in self.records
                   if record.base_intensity is not None)

    def summary_line(self) -> str:
        """How many records, over how many days, in a phrase."""
        said = [f"{len(self.records)} record(s)"]
        days = self.days
        if len(days) > 1:
            said.append(f"{len(days)} days, {days[0]} to {days[-1]}")
        elif days:
            said.append(f"one day, {days[0]}")
        else:
            said.append("no acquisition dates")
        return ", ".join(said)

    @property
    def flagged(self) -> dict[str, list[str]]:
        """Which records are out, per record label, and on what."""
        out: dict[str, list[str]] = {}
        for metric, chart in self.charts.items():
            for point in chart.out:
                out.setdefault(point.sample, []).append(metric)
        return out

    # -- the arithmetic, all of it borrowed ------------------------------------ #
    def _score(self) -> None:
        reference = self.reference
        if reference is None:
            return
        for index, record in enumerate(self.records):
            record.score, record.reverse = _cosine(record, reference)
            if reference.base_mz and record.base_mz:
                record.base_gap_ppm = ((record.base_mz - reference.base_mz)
                                       / reference.base_mz * 1e6)
                record.ppm = (record.base_gap_ppm if record.same_base_peak
                              else None)
            if index:
                record.previous_score, record.previous_reverse = _cosine(
                    record, self.records[index - 1])

    def _chart(self, metric: str,
               points: list[tuple[Record, float | None]],
               limits: Limits = PERCENT, missing: str = "") -> ControlChart:
        """
        One metric charted, saying which records could not supply it.

        A record left out is said so on the chart rather than dropped
        quietly: three points out of eight is a different statement from
        three points out of three, and the note is the only place that
        difference appears.
        """
        usable = [(record.label, RECORD, record.when, float(value))
                  for record, value in points if value is not None]
        chart = chart_from_values(metric, usable, limits=limits,
                                  minimum=MIN_RECORDS, unit_word=RECORD,
                                  value_word="value")
        left_out = len(points) - len(usable)
        if left_out:
            said = f"{left_out} of {len(points)} record(s) {missing}".strip()
            chart.note = f"{chart.note}; {said}" if chart.note else said
        return chart


def _cosine(record: Record, other: Record) -> tuple[float, float]:
    """
    One record scored against another: the plain cosine and the reverse.

    `library.match` with the other record as the library, so `reverse` asks
    whether *its* peaks are still in this one — which is the question a
    verification asks, since a standard that has picked up an impurity has
    kept everything it had and gained something.
    """
    score, reverse, _pairs = match(record.entry.mz, record.entry.intensity,
                                   other.entry.mz, other.entry.intensity,
                                   PEAK_TOLERANCE_PPM)
    return float(score), float(reverse)


# --------------------------------------------------------------------------- #
# the whole file
# --------------------------------------------------------------------------- #
class StandardHistory:
    """Every record of a library of one's own, grouped into series."""

    def __init__(self, entries: list[LibraryEntry], path: str = ""):
        self.path = path
        self.records = [Record(entry, index)
                        for index, entry in enumerate(entries)]
        grouped: dict[tuple, list[Record]] = {}
        for record in self.records:
            grouped.setdefault(_group(record), []).append(record)
        self.series = sorted(
            (Series(compound, energy, activation, members)
             for (compound, activation, energy), members in grouped.items()),
            key=lambda series: series.key)

    @property
    def compounds(self) -> list[str]:
        return sorted({series.compound for series in self.series})

    def for_compound(self, compound: str) -> list[Series]:
        return [series for series in self.series if series.compound == compound]

    def summary(self, compound: str = "") -> str:
        """What the file holds, in a sentence."""
        series = self.for_compound(compound) if compound else self.series
        records = sum(len(one.records) for one in series)
        if not records:
            return "no records"
        days = sorted({record.day for one in series for record in one.records
                       if record.day})
        undated = sum(1 for one in series for record in one.records
                      if not record.when)
        said = [f"{records:,} record(s)", f"{len(series)} series"]
        if days:
            said.append(f"{len(days)} day(s), {days[0]} to {days[-1]}"
                        if len(days) > 1 else f"one day, {days[0]}")
        if undated:
            said.append(f"{undated} with no acquisition date — read in the "
                        f"order the file holds them")
        return " · ".join(said)


def _group(record: Record) -> tuple:
    """
    Which series a record belongs to: compound, activation, energy.

    The energy is rounded onto a grid of `ENERGY_TOLERANCE_EV`, the figure
    the infusion report already uses to decide two energies differ: a vendor
    writes a nominal energy and a spread, and a fraction of an electronvolt
    is one setting written twice.
    """
    energy = record.energy
    if energy is not None:
        energy = round(energy / ENERGY_TOLERANCE_EV) * ENERGY_TOLERANCE_EV
    return (record.compound, record.activation, energy)


def read_history(path: str | os.PathLike) -> StandardHistory:
    """A history from an MSP or MGF file of one's own."""
    library = load_library(path)
    return history_of(library)


def history_of(library: SpectralLibrary) -> StandardHistory:
    """A history from a library already read."""
    return StandardHistory(library.entries, getattr(library, "path", ""))


# --------------------------------------------------------------------------- #
# what the charts say, in words
# --------------------------------------------------------------------------- #
def verdict(chart: ControlChart) -> str:
    """
    One chart in a sentence, on the same rules the Batch QC tab prints.

    The wording differs in one place and deliberately: below `MIN_RECORDS`
    the answer is *too few to chart*, because a reader who is shown a median
    and two limits drawn through two points will read them.
    """
    if not chart.injections:
        return "nothing measured"
    if not chart.measurable:
        return f"too few to chart — {chart.note}"
    unit = chart.limits.unit
    if chart.unusable:
        return (f"{len(chart.out)} of {len(chart.injections)} records more "
                f"than {chart.limits.always:g}{unit} from the centre: these "
                f"are not one standard measured repeatedly")
    said = []
    if chart.drifted:
        said.append(f"drift {chart.drift:+,.1f}{unit} across the records")
    if chart.out:
        said.append(f"{len(chart.out)} outside {OUTLIER_SIGMA:g}σ")
    if chart.excess_warnings:
        said.append(f"{len(chart.warned)} beyond {WARN_SIGMA:g}σ")
    if said:
        return "; ".join(said)
    if chart.note:
        return chart.note
    if chart.correlation is not None and abs(chart.correlation) >= DRIFT_CORRELATION:
        return (f"steady: {chart.drift:+,.1f}{unit} across the records, under "
                f"the {chart.limits.drift:g}{unit} a trend needs")
    return "steady"


def verdicts(series: Series) -> list[tuple[str, str]]:
    """Each metric of a series and what it says."""
    return [(metric, verdict(series.charts[metric])) for metric in METRICS]


def caveat(series: Series) -> str:
    """
    What has to be said beside this series' figures, or "".

    Two of the three go on every chart because they are properties of the
    data rather than findings in it: an absolute height compares only inside
    one method and energy, and records that did not say when they were
    acquired are in the order the file holds them and not in the order they
    were measured.
    """
    said = [f"{series.conditions}: an absolute intensity is comparable only "
            f"within one method and energy"]
    if not series.ordered:
        said.append(f"{len(series.records) - series.dated} of "
                    f"{len(series.records)} record(s) carry no acquisition "
                    f"date; those are left in the order the file holds them")
    if len(series.days) == 1 and len(series.records) > 1:
        said.append(f"every record was acquired on {series.days[0]} — this is "
                    f"a history of one day, not of a standard over months")
    if series.with_intensity < len(series.records):
        said.append(f"{len(series.records) - series.with_intensity} record(s) "
                    f"were written before the base peak's height was, so the "
                    f"intensity chart is not the whole series")
    return " · ".join(said)


# --------------------------------------------------------------------------- #
# out of the program
# --------------------------------------------------------------------------- #
CSV_HEADER = ("Compound", "Activation", "Collision energy", "Record",
              "Acquired", "File", "Precursor", "Base peak m/z",
              "ppm from first", "Base peak intensity", "Score vs first",
              "Reverse vs first", "Score vs previous", "Reverse vs previous",
              "Out on")


def ppm_text(record: Record) -> str:
    """
    The base peak against the reference's, for a table.

    A record whose base peak is a different ion is written as that rather
    than as a mass error of a million parts per million, which is a number
    that invites the reader to divide it by anything.
    """
    if record.ppm is not None:
        return f"{record.ppm:+.1f}"
    if record.base_gap_ppm is None:
        return ""
    return "not the same ion"


def _cell(value, decimals: int = 2) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def csv_rows(history: StandardHistory, compound: str = "") -> list[list[str]]:
    """The table under the charts, one row per record."""
    rows = [list(CSV_HEADER)]
    series_list = history.for_compound(compound) if compound else history.series
    for series in series_list:
        flagged = series.flagged
        for record in series.records:
            rows.append([
                series.compound, series.activation,
                _cell(series.energy, 1), record.name, record.when, record.file,
                _cell(record.precursor, 4), _cell(record.base_mz, 4),
                ppm_text(record), _cell(record.base_intensity, 0),
                _cell(None if record.score is None else record.score * 100, 1),
                _cell(None if record.reverse is None else record.reverse * 100, 1),
                _cell(None if record.previous_score is None
                      else record.previous_score * 100, 1),
                _cell(None if record.previous_reverse is None
                      else record.previous_reverse * 100, 1),
                "; ".join(flagged.get(record.label, [])),
            ])
    return rows


def csv_text(history: StandardHistory, compound: str = "") -> str:
    """
    The rows as CSV, with the verdicts above them as commented lines.

    The verdicts are what the charts say and the rows are what they say it
    about; a file that carried only the rows would be a table somebody has
    to draw the charts from again.
    """
    lines = [f"# standard history from {os.path.basename(history.path)}"
             if history.path else "# standard history"]
    for series in (history.for_compound(compound) if compound
                   else history.series):
        lines.append(f"# {series.label}: {series.summary_line()}")
        for metric, said in verdicts(series):
            lines.append(f"#   {metric}: {said}")
        note = caveat(series)
        if note:
            lines.append(f"#   {note}")
    for row in csv_rows(history, compound):
        lines.append(",".join(_escape(cell) for cell in row))
    return "\n".join(lines) + "\n"


def _escape(cell: str) -> str:
    text = str(cell)
    if any(character in text for character in ',"\n'):
        return '"' + text.replace('"', '""') + '"'
    return text


def write_csv(history: StandardHistory, path: str | os.PathLike,
              compound: str = "") -> str:
    """Write the table and return the path written."""
    path = str(path)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(csv_text(history, compound))
    return path
