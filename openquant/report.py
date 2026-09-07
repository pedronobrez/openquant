"""
A report of a batch, to print or to hand over.

CSV is what you export to carry on working; a report is what you keep. It has
to answer, on its own and months later, what was measured, against what
method, how the curve was built, which rows passed and which did not — without
the reader having the project open, or this application at all.

The document is HTML because Qt can lay HTML out and print it, and because a
report that also opens in a browser is a report that survives this program.
Nothing here reads a widget: it is built from the session, so it can be
generated with no window on screen, and tested.

Nothing is rounded that a decision depends on. Areas and concentrations keep
the digits the results carry; retention times keep three decimals, which is
better than any chromatography, and percentages two.

The page is A4 portrait, and the styling is deliberately narrow: Qt's rich
text engine understands a small subset of CSS and silently ignores the rest,
so everything here is something that was rendered and looked at. Cell padding
comes from the `cellpadding` attribute and column widths from `width`, because
the CSS spellings of both do nothing.
"""

from __future__ import annotations

import datetime as _dt
import html
import os

from . import __version__
from .calibration import Calibration
from .method import ProcessingMethod
from .quantify import PeakResult, ResultsSet
from .samples import SampleEntry
from .statistics import GROUP_BY_SAMPLE_TYPE, summarise
from .qc import (CV_PERCENT, DRIFT_CORRELATION, DRIFT_PERCENT,
                 MIN_SNR, OUTLIER_SIGMA, OUT_PERCENT, batch_qc)
from .validation import all_detection_limits, carryover

#: the statuses a row can carry. Matched without regard to case: the results
#: capitalise them and an earlier version of this counted them in lower case,
#: so a batch with twenty-eight passes and two failures reported that no
#: acceptance criteria had been set.
STATUSES = ("pass", "marginal", "fail")

#: the sections, in the order they are printed, with the headings they carry.
#: A caller names them by key; the number in front is added here so that
#: leaving one out does not leave a gap in the numbering.
SECTIONS = {
    "summary": "Summary",
    "samples": "Samples",
    "method": "Method",
    "calibration": "Calibration",
    "limits": "Detection and quantitation limits",
    "carryover": "Carryover",
    "quality": "Batch quality",
    "results": "Results",
    "statistics": "Statistics",
}
ALL_SECTIONS = tuple(SECTIONS)

#: A4 portrait, in millimetres: left, top, right, bottom, then the bands kept
#: clear at the top and bottom of every page for the running furniture.
MARGINS_MM = (18.0, 15.0, 15.0, 15.0)
HEADER_MM = 8.0
FOOTER_MM = 10.0

#: how many times the document may be laid out again to pull a stranded
#: heading onto the page of the thing it introduces. Moving one heading can
#: strand another, and this stops that chasing its own tail.
MAX_REFLOWS = 3

#: markers on a sample's name, explained in a legend under the table that
#: uses them. A column of "yes / no / by hand" costs more width than it earns.
EXCLUDED = "†"
BY_HAND = "‡"


def _escape(value) -> str:
    return html.escape("" if value is None else str(value))


def _number(value, decimals: int = 4) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return _escape(value)


def _table(headers: list[str] | None, rows: list[list[str]],
           right: set[int] = frozenset(), empty: str = "Nothing to show.",
           widths: list[str] | None = None) -> str:
    """
    One table, striped, with a heading row that repeats on every printed page.

    Qt takes the width of a column from the `width` attribute of its cells and
    the space inside a cell from `cellpadding`; the CSS properties of the same
    names are parsed and dropped. Both are given here in per cent and in
    pixels, which is what those attributes mean.

    Columns are wide enough for the longest single word in their heading. A
    heading may wrap at a space — two lines of `Internal standard` reads
    fine — but one that wraps inside a word does not, and `Concentratio/n` is
    what a column that is four points too narrow looks like.

    Headings are optional: a table of names against values has nothing to put
    in them, and an empty heading row is a grey band that means nothing.
    """
    if not rows:
        return f'<p class="empty">{_escape(empty)}</p>'
    head = ""
    if headers:
        cells = []
        for index, heading in enumerate(headers):
            width = f' width="{widths[index]}"' if widths else ""
            align = ' class="num"' if index in right else ""
            cells.append(f"<th{width}{align}>{_escape(heading)}</th>")
        head = f'<thead><tr>{"".join(cells)}</tr></thead>'
    body = []
    for number, row in enumerate(rows):
        stripe = ' class="alt"' if number % 2 else ""
        cells = []
        for index, cell in enumerate(row):
            width = (f' width="{widths[index]}"'
                     if widths and not headers else "")
            cells.append(f'<td class="{"num" if index in right else ""}"'
                         f"{width}>{cell}</td>")
        body.append(f'<tr{stripe}>{"".join(cells)}</tr>')
    return (f'<table width="100%" cellpadding="4" cellspacing="0">{head}'
            f'<tbody>{"".join(body)}</tbody></table>')


def _heading(title: str, breaks: set[str] | None = None) -> str:
    css = ' class="break"' if breaks and title in breaks else ""
    return f"<h2{css}>{_escape(title)}</h2>"


# --------------------------------------------------------------------------- #
# the front of the report
# --------------------------------------------------------------------------- #
def _title_block(title: str, project: str | None, entries, method) -> str:
    """
    What the report is of, on the page rather than in a file name.

    A report is read detached from everything that made it, so the batch it
    describes has to be identifiable from the paper alone.
    """
    when = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    where = os.path.basename(project) if project else "unsaved project"
    standards = sum(1 for e in entries if e.sample_type == "Standard")
    internal = sum(1 for c in method.components if c.is_internal_standard)
    return (
        f'<p class="eyebrow">OpenQuant {_escape(__version__)} · batch report</p>'
        f"<h1>{_escape(title)}</h1>"
        f'<table class="ident" width="100%" cellpadding="4" cellspacing="0">'
        f'<tr><td class="label" width="18%">Project</td><td width="32%">{_escape(where)}</td>'
        f'<td class="label" width="18%">Generated</td><td width="32%">{when}</td></tr>'
        f'<tr><td class="label">Samples</td><td>{len(entries):,}'
        f'{f" ({standards:,} standards)" if standards else ""}</td>'
        f'<td class="label">Components</td><td>{len(method.components):,}'
        f'{f" ({internal:,} internal standards)" if internal else ""}</td></tr>'
        f"</table>"
    )


def _contents(titles: list[str], pages: dict[str, int] | None) -> str:
    """
    The sections, and where they are.

    The page numbers are not known until the document has been laid out, so
    this is built twice: once with the column empty to fix the pagination, and
    again with the numbers found by that first pass. The row heights are the
    same either way, which is what makes the second pass agree with the first.
    """
    if len(titles) < 2:
        return ""
    rows = []
    for number, title in enumerate(titles):
        stripe = ' class="alt"' if number % 2 else ""
        page = "" if not pages else str(pages.get(title, ""))
        cell = (f'<td class="num" width="8%">{page}</td>'
                if pages is not None else "")
        rows.append(f'<tr{stripe}><td>{_escape(title)}</td>{cell}</tr>')
    return ('<h2 class="plain">Contents</h2>'
            f'<table class="contents" width="60%" cellpadding="3" cellspacing="0">'
            f'{"".join(rows)}</table>')


# --------------------------------------------------------------------------- #
# the sections
# --------------------------------------------------------------------------- #
def _findings(results: ResultsSet, entries: list[SampleEntry],
              method: ProcessingMethod, calibrations) -> str:
    """
    What a reader should not have to find for themselves.

    A summary that only counts things makes the reader hunt through eight
    sections for the two rows that matter. This says what failed and where,
    and says plainly when nothing did — which is not the same as saying
    everything passed, because a batch with no acceptance criteria fails
    nothing at all.
    """
    notes = []

    failed = [row for row in results
              if str(getattr(row, "status", "") or "").strip().lower() == "fail"]
    if failed:
        components = sorted({row.component for row in failed})
        shown = ", ".join(_escape(name) for name in components[:4])
        if len(components) > 4:
            shown += f" and {len(components) - 4} more"
        notes.append(f"{len(failed):,} result(s) outside their acceptance "
                     f"criteria, in {shown}.")

    try:
        found = carryover(results, entries, method)
    except Exception:                                  # a report must still print
        found = None
    if found is not None and found.failures:
        worst = max(found.failures, key=lambda row: row.percent)
        notes.append(f"{len(found.failures)} component(s) over the carryover "
                     f"limit in {_escape(worst.blank)}, the worst "
                     f"{_escape(worst.component)} at {_number(worst.percent, 2)}%.")

    try:
        quality = batch_qc(results, entries, method)
    except Exception:                                  # a report must still print
        quality = None
    if quality is not None:
        if quality.drifted:
            worst = max(quality.drifted, key=lambda c: abs(c.drift))
            notes.append(f"{len(quality.drifted)} internal standard(s) drifted "
                         f"across the run, the worst {_escape(worst.component)} "
                         f"by {_number(worst.drift, 1)}%.")
        stray = sum(len(chart.out) for chart in quality.out)
        if stray:
            notes.append(f"{stray} injection(s) more than three robust standard "
                         f"deviations from their internal standard's centre.")
        if quality.imprecise:
            worst = max(quality.imprecise, key=lambda r: r.percent_cv)
            notes.append(f"{len(quality.imprecise)} component(s) over "
                         f"{_number(CV_PERCENT, 0)}% CV across the quality "
                         f"controls, the worst {_escape(worst.component)} at "
                         f"{_number(worst.percent_cv, 1)}%.")

    extrapolated = [limits for limits in all_detection_limits(calibrations, method)
                    if limits.extrapolated]
    if extrapolated:
        notes.append(f"{len(extrapolated)} limit(s) of quantitation fall below "
                     f"the lowest standard: extrapolated from the curve, not "
                     f"demonstrated by it.")

    if not notes:
        return ('<p class="empty">Nothing was found outside the limits that '
                'were set. Where no criterion was set, nothing is claimed.</p>')
    items = "".join(f"<li>{note}</li>" for note in notes)
    return f'<ul class="findings">{items}</ul>'


def _summary(title: str, results: ResultsSet, entries: list[SampleEntry],
             method: ProcessingMethod, calibrations,
             breaks: set[str] | None = None) -> str:
    rows = list(results)
    counted = {name: 0 for name in STATUSES}
    integrated = 0
    for row in rows:
        status = str(getattr(row, "status", "") or "").strip().lower()
        if status in counted:
            counted[status] += 1
        if row.area is not None:
            integrated += 1
    excluded = sum(1 for row in rows if not row.used)
    manual = sum(1 for row in rows if row.manual)

    body = [
        ["Rows", f"{len(rows):,}"],
        ["Integrated", f"{integrated:,} of {len(rows):,}"],
        ["Integrated by hand", f"{manual:,}"],
        ["Excluded from statistics", f"{excluded:,}"],
    ]
    if any(counted.values()):
        body.append(["Pass / Marginal / Fail",
                     " / ".join(f"{counted[name]:,}" for name in STATUSES)])
    else:
        body.append(["Acceptance", "no criteria set — no status is reported"])
    return (_heading(title, breaks)
            + _table(None, body, right={1}, widths=["70%", "30%"])
            + _findings(results, entries, method, calibrations))


def _samples(title: str, entries: list[SampleEntry],
             breaks: set[str] | None = None) -> str:
    rows = []
    for entry in entries:
        rows.append([
            _escape(entry.name), _escape(entry.filename),
            _escape(entry.sample_type), _escape(entry.sample_group or "—"),
            _number(entry.actual_concentration, 4)
            if entry.actual_concentration is not None else "—",
            _number(entry.dilution_factor, 4),
            _escape(entry.comment or ""),
        ])
    return _heading(title, breaks) + _table(
        ["Sample", "File", "Type", "Group", "Concentration", "Dilution", "Comment"],
        rows, right={4, 5}, empty="No samples were open.",
        widths=["15%", "23%", "12%", "12%", "14%", "9%", "15%"])


def _method(title: str, method: ProcessingMethod,
            breaks: set[str] | None = None) -> str:
    rows = []
    for component in method.components:
        role = "internal standard" if component.is_internal_standard else (
            f"qualifier of {component.qualifier_of}" if component.qualifier_of else "")
        rows.append([
            _escape(component.name), _escape(component.group or "—"),
            _number(component.precursor, 4), _number(component.fragment, 4),
            _number(component.rt, 3) if component.rt else "—",
            f"±{_number(component.rt_halfwidth, 2)}",
            f"{_number(component.tolerance, 3)} {_escape(component.unit)}",
            _escape(component.internal_standard or "—"),
            _escape(role),
        ])
    return _heading(title, breaks) + _table(
        ["Component", "Group", "Precursor", "Fragment", "RT", "Window",
         "Tolerance", "Internal standard", "Role"],
        rows, right={2, 3, 4, 5, 6}, empty="The method has no components.",
        widths=["15%", "13%", "10%", "10%", "7%", "8%", "10%", "15%", "12%"])


def _calibrations(title: str, calibrations: dict[str, Calibration],
                  method: ProcessingMethod,
                  breaks: set[str] | None = None) -> str:
    """
    The curves, with an internal standard's marked as what it is.

    A curve is built for anything with standards behind it, an internal
    standard included — and that one is flat by construction, because the same
    amount is spiked into every sample whatever the analyte's concentration.
    It comes out with an r² near zero, which reads as a failed calibration
    rather than as a meaningless one. Saying which is which costs a word.
    """
    internal = {c.name for c in method.components if c.is_internal_standard}
    fitted = {name: curve for name, curve in calibrations.items()
              if curve is not None and curve.is_fitted}
    rows = []
    for name in sorted(fitted):
        curve = fitted[name]
        label = _escape(name)
        if name in internal:
            label += ' <span class="aside">— internal standard, flat by design</span>'
        rows.append([
            label, _escape(curve.regression), _escape(curve.weighting),
            _escape(curve.equation), _number(curve.r2, 6), _number(curve.r, 6),
            f"{len(curve.used_points)} of {len(curve.points)}",
        ])
    return _heading(title, breaks) + _table(
        ["Component", "Regression", "Weighting", "Equation", "r²", "r", "Points"],
        rows, right={4, 5, 6},
        empty="No curve was built. Mark samples as Standard and give them a "
              "concentration.",
        widths=["19%", "12%", "11%", "26%", "10%", "10%", "12%"])


def _limits(title: str, calibrations, method: ProcessingMethod,
            breaks: set[str] | None = None) -> str:
    rows = []
    for limits in all_detection_limits(calibrations, method):
        if not limits.measurable:
            rows.append([_escape(limits.component), "—", "—", "—", "—",
                         _escape(limits.note or "not derived")])
            continue
        note = limits.note
        if limits.extrapolated:
            warning = (f"below the lowest standard "
                       f"({_number(limits.lowest_standard, 4)}) — extrapolated, "
                       f"not demonstrated")
            note = f"{note}; {warning}" if note else warning
        rows.append([
            _escape(limits.component),
            _number(limits.lod, 4), _number(limits.loq, 4),
            _number(limits.sigma, 6), _number(limits.slope, 6),
            _escape(note),
        ])
    return (_heading(title, breaks)
            + '<p class="meta">3.3&#963;/S and 10&#963;/S, with &#963; the '
              "residual standard deviation of the curve about its own line "
              "(ICH Q2). Internal standards are left out.</p>"
            + _table(["Component", "LOD", "LOQ", "σ", "Slope", "Notes"],
                     rows, right={1, 2, 3, 4},
                     empty="No curve to derive a limit from.",
                     widths=["18%", "11%", "11%", "12%", "12%", "36%"]))


def _carryover(title: str, results: ResultsSet, entries: list[SampleEntry],
               method: ProcessingMethod, breaks: set[str] | None = None) -> str:
    found = carryover(results, entries, method)
    if found.note:
        return (_heading(title, breaks)
                + f'<p class="empty">{_escape(found.note)}</p>')
    rows = []
    for row in sorted(found.rows, key=lambda r: -r.percent):
        verdict = ('<span class="bad">over the limit</span>' if row.fails
                   else "within the limit")
        rows.append([
            _escape(row.component), _number(row.blank_area, 1),
            _number(row.reference_area, 1), _number(row.percent, 2), verdict,
        ])
    first = found.rows[0] if found.rows else None
    heading = ""
    if first is not None:
        heading = (f'<p class="meta">{_escape(first.blank)}, injected after '
                   f"{_escape(first.follows)}, against the response at the "
                   f"lowest calibrated concentration ({_escape(first.reference)}). "
                   f"Limit {_number(first.limit, 0)}%.</p>")
    return (_heading(title, breaks) + heading
            + _table(["Component", "Blank", "At the lowest standard", "%", ""],
                     rows, right={1, 2, 3}, empty="Nothing to compare.",
                     widths=["24%", "16%", "22%", "11%", "27%"]))


def _quality(title: str, results: ResultsSet, entries: list[SampleEntry],
             method: ProcessingMethod, breaks: set[str] | None = None) -> str:
    """
    What the run did between the first injection and the last.

    Per-sample review cannot see a response that falls away across ninety
    injections: every point is inside its limits and the batch is still not
    the batch it started as.
    """
    report = batch_qc(results, entries, method)
    parts = [_heading(title, breaks)]
    if report.note:
        return "".join(parts) + f'<p class="empty">{_escape(report.note)}</p>'

    order = ("in the order the instrument ran them"
             if report.ordered else
             f"in the order the files were opened — {report.timed} of "
             f"{report.injections} injections carry an acquisition time")
    parts.append(
        f'<p class="meta">Internal-standard response {order}. The centre is '
        f"the median and the spread the median absolute deviation, so that "
        f"one bad injection cannot widen the limits meant to catch it. An "
        f"injection is called out when it is both beyond "
        f"{OUTLIER_SIGMA:g}&#963; and at least {OUT_PERCENT:g}% from the "
        f"centre: a batch that repeats itself well has a spread so small "
        f"that three of them is a difference nobody would act on. Drift is "
        f"the fitted change across the whole run, reported when it is at "
        f"least {DRIFT_PERCENT:g}% and goes one way (Spearman's &#961; "
        f"beyond {DRIFT_CORRELATION:g}). A standard whose median "
        f"signal-to-noise is below {MIN_SNR:g} is charted but not flagged: "
        f"below the limit of quantitation a small absolute change is a large "
        f"relative one, and every flag against it would be arithmetic on "
        f"noise.</p>")

    rows = []
    for chart in report.charts:
        if not chart.measurable:
            rows.append([_escape(chart.component),
                         f"{len(chart.injections):,}", "—", "—",
                         _number(chart.snr, 0) if chart.snr is not None else "—",
                         "—", "—",
                         _escape(chart.note or "not measurable")])
            continue
        verdict = []
        if not chart.quantifiable:
            verdict.append(f"below S/N {MIN_SNR:g} — not quantified, so not "
                           f"flagged")
        if chart.drifted:
            verdict.append('<span class="bad">drift</span>')
        if chart.out:
            verdict.append(f'<span class="bad">{len(chart.out)} outside '
                           f"3&#963;</span>")
        if chart.excess_warnings:
            verdict.append(f"{len(chart.warned)} beyond 2&#963;")
        rows.append([
            _escape(chart.component), f"{len(chart.injections):,}",
            _number(chart.centre, 1), _number(chart.sigma, 1),
            _number(chart.snr, 0) if chart.snr is not None else "—",
            _number(chart.drift, 1), _number(chart.correlation, 3),
            "; ".join(verdict) or (_escape(chart.note) if chart.note
                                   else "steady"),
        ])
    parts.append(_table(
        ["Component", "n", "Centre", "Spread", "S/N", "Drift %", "\u03c1",
         "Verdict"],
        rows, right={1, 2, 3, 4, 5, 6}, empty="Nothing to chart.",
        widths=["20%", "6%", "12%", "12%", "9%", "9%", "8%", "24%"]))

    for chart in report.charts:
        for point in chart.out:
            parts.append(
                f'<p class="foot">{_escape(chart.component)} — injection '
                f"{point.order}, {_escape(point.sample)}: "
                f"{_number(point.percent, 1)}% from the centre "
                f"({_number(point.sigmas, 1)}&#963;)</p>")

    measured = [row for row in report.precision if row.measurable]
    if measured:
        parts.append("<h3>Precision of the quality controls</h3>")
        rows = []
        for row in sorted(measured, key=lambda r: -(r.percent_cv or 0.0)):
            rows.append([
                _escape(row.component), f"{row.replicates:,}",
                _number(row.mean, 1), _number(row.percent_cv, 2),
                ('<span class="bad">over the limit</span>' if row.fails
                 else "within the limit"),
            ])
        parts.append(_table(["Component", "n", "Mean", "%CV", ""], rows,
                            right={1, 2, 3}, empty="Nothing to summarise.",
                            widths=["30%", "9%", "20%", "13%", "28%"]))
    return "".join(parts)


def _results(title: str, results: ResultsSet, method: ProcessingMethod,
             breaks: set[str] | None = None) -> str:
    """
    Every integrated row, by component.

    Twelve columns do not fit an A4 page at a size anybody reads, so the two
    that are almost always empty are not columns: a row that carries a flag,
    a note, an exclusion or a manual integration is marked and written out
    underneath its table. That puts the exceptions where they get noticed
    instead of in a column of blanks.
    """
    by_component: dict[str, list[PeakResult]] = {}
    for row in results:
        by_component.setdefault(row.component, []).append(row)

    if not by_component:
        return (_heading(title, breaks)
                + '<p class="empty">Nothing was integrated.</p>')

    order = [c.name for c in method.components if c.name in by_component]
    order += [name for name in sorted(by_component) if name not in order]

    parts = [_heading(title, breaks)]
    for name in order:
        rows, notes, marked = [], [], False
        for row in sorted(by_component[name], key=lambda r: r.sample_name):
            label = _escape(row.sample_name)
            if not row.used:
                label += f' <span class="mark">{EXCLUDED}</span>'
                marked = True
            elif row.manual:
                label += f' <span class="mark">{BY_HAND}</span>'
                marked = True
            drift = (row.rt - row.expected_rt
                     if row.rt is not None and row.expected_rt else None)
            status = _escape(row.status or "—")
            if str(row.status or "").strip().lower() == "fail":
                status = f'<span class="bad">{status}</span>'
            rows.append([
                label,
                _number(row.rt, 3), _number(drift, 3) if drift is not None else "—",
                _number(row.area, 1), _number(row.height, 1), _number(row.snr, 1),
                _number(row.area_ratio, 4) if row.area_ratio is not None else "—",
                _number(row.calculated_concentration, 4)
                if row.calculated_concentration is not None else "—",
                _number(row.accuracy, 2) if row.accuracy is not None else "—",
                status,
            ])
            said = "; ".join(row.flags) if row.flags else (row.note or "")
            if said:
                notes.append(f"{_escape(row.sample_name)} — {_escape(said)}")
        css = ' class="break"' if breaks and name in breaks else ""
        parts.append(f"<h3{css}>{_escape(name)}</h3>")
        parts.append(_table(
            ["Sample", "RT", "Δ RT", "Area", "Height", "S/N", "Ratio",
             "Concentration", "Accuracy %", "Status"],
            rows, right={1, 2, 3, 4, 5, 6, 7, 8},
            widths=["15%", "7%", "7%", "10%", "10%", "8%", "8%", "13%",
                    "11%", "11%"]))
        if marked:
            parts.append(f'<p class="foot">{EXCLUDED} excluded from the '
                         f"statistics&nbsp;&nbsp;&nbsp;{BY_HAND} integrated by "
                         f"hand</p>")
        for note in notes:
            parts.append(f'<p class="foot">{note}</p>')
    return "".join(parts)


def _statistics(title: str, results: ResultsSet, entries: list[SampleEntry],
                method: ProcessingMethod, grouping: str,
                breaks: set[str] | None = None) -> str:
    try:
        summary = summarise(results, entries, method, grouping, "response")
    except Exception as exc:                      # a report must still print
        return (_heading(title, breaks)
                + f'<p class="empty">Not computed: {_escape(exc)}</p>')
    rows = []
    for row in summary:
        rows.append([
            _escape(row.component), _escape(row.group),
            f"{row.used} of {row.total}",
            _number(row.mean, 4), _number(row.standard_deviation, 4),
            _number(row.percent_cv, 2), _number(row.accuracy, 2),
        ])
    return (_heading(title, breaks)
            + f'<p class="meta">Response, grouped by {_escape(grouping)}.</p>'
            + _table(["Component", "Group", "n", "Mean", "SD", "%CV", "Accuracy %"],
                     rows, right={2, 3, 4, 5, 6}, empty="Nothing to summarise.",
                     widths=["22%", "17%", "10%", "14%", "13%", "11%", "13%"]))


# --------------------------------------------------------------------------- #
# how it looks
# --------------------------------------------------------------------------- #
#: Everything here was rendered and looked at. Qt's rich text engine takes a
#: subset of CSS and drops the rest without a word, so `padding` on a cell,
#: `width` on a table and any selector cleverer than `tag.class` are absent
#: on purpose — the attributes in `_table` do that work instead.
_STYLE = """
@page { size: A4 portrait; margin: 15mm 15mm 15mm 18mm; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 9pt; color: #16181c; }
p.eyebrow { color: #234b8c; font-size: 7.5pt; font-weight: 600;
            letter-spacing: 1px; margin: 0 0 2pt 0; }
h1 { font-size: 19pt; font-weight: 600; color: #16181c; margin: 0 0 7pt 0; }
h2 { font-size: 11.5pt; font-weight: 600; color: #234b8c;
     margin: 18pt 0 5pt 0; border-bottom: 2px solid #234b8c;
     padding-bottom: 2pt; }
h2.plain { border-bottom: 1px solid #c3c9d3; }
h3 { font-size: 9.5pt; font-weight: 600; margin: 12pt 0 3pt 0; color: #16181c; }
h2.break, h3.break { page-break-before: always; }
p { margin: 0 0 4pt 0; }
p.meta { color: #5b6472; font-size: 8pt; margin: 0 0 6pt 0; }
p.empty { color: #5b6472; font-style: italic; margin: 2pt 0 6pt 0; }
p.foot { color: #5b6472; font-size: 7.5pt; margin: 2pt 0 0 0; }
ul.findings { margin: 6pt 0 0 0; }
li { margin: 0 0 2pt 0; }
span.aside { color: #5b6472; font-style: italic; }
span.mark { color: #5b6472; }
span.bad { color: #a4262c; font-weight: 600; }
table { border-collapse: collapse; }
th { font-size: 8pt; text-align: left; background: #e8edf4; color: #234b8c;
     border-bottom: 1.5px solid #234b8c; font-weight: 600; }
th.num { text-align: right; }
td { font-size: 8pt; border-bottom: 1px solid #dfe3e9; vertical-align: top; }
td.num { text-align: right; }
td.label { color: #5b6472; background: #f2f4f7; }
tr.alt td { background: #f7f9fb; }
table.ident td { border-bottom: 1px solid #dfe3e9; }
table.contents td { border-bottom: 1px solid #eef1f5; }
"""


# --------------------------------------------------------------------------- #
def build_html(session, title: str = "Batch report",
               grouping: str = GROUP_BY_SAMPLE_TYPE,
               sections: tuple[str, ...] = ALL_SECTIONS,
               contents: dict[str, int] | None = None,
               breaks: set[str] | None = None) -> str:
    """
    The whole report as one HTML document.

    Sections are named so a caller can leave out what it does not want — a
    hundred-component method makes a results section nobody prints — and are
    numbered here rather than in the section functions, so that leaving one
    out closes the gap instead of leaving one.

    `contents` is how the printed version puts page numbers in its table of
    contents: `None` for no page column at all, an empty mapping to reserve
    the column while the numbers are still unknown, and the mapping itself on
    the second pass. `breaks` names the headings that are to start a fresh
    page. Both are worked out by `write_pdf`, which has to lay the document
    out before it can know either.
    """
    entries = list(session.entries)
    method = session.method
    order = [key for key in ALL_SECTIONS if key in sections]
    titles = {key: f"{number}. {SECTIONS[key]}"
              for number, key in enumerate(order, start=1)}

    parts = ["<!DOCTYPE html>",
             "<html><head><meta charset='utf-8'>",
             f"<title>{_escape(title)}</title>",
             f"<style>{_STYLE}</style></head><body>",
             _title_block(title, session.project_path, entries, method),
             _contents(list(titles.values()), contents)]
    for key in order:
        name = titles[key]
        if key == "summary":
            parts.append(_summary(name, session.results, entries, method,
                                  session.calibrations, breaks))
        elif key == "samples":
            parts.append(_samples(name, entries, breaks))
        elif key == "method":
            parts.append(_method(name, method, breaks))
        elif key == "calibration":
            parts.append(_calibrations(name, session.calibrations, method, breaks))
        elif key == "limits":
            parts.append(_limits(name, session.calibrations, method, breaks))
        elif key == "carryover":
            parts.append(_carryover(name, session.results, entries, method,
                                    breaks))
        elif key == "quality":
            parts.append(_quality(name, session.results, entries, method,
                                  breaks))
        elif key == "results":
            parts.append(_results(name, session.results, method, breaks))
        elif key == "statistics":
            parts.append(_statistics(name, session.results, entries, method,
                                     grouping, breaks))
    parts.append("</body></html>")
    return "".join(parts)


def write_html(session, path: str | os.PathLike, **kwargs) -> str:
    path = str(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_html(session, **kwargs))
    return path


# --------------------------------------------------------------------------- #
# printing
# --------------------------------------------------------------------------- #
def _section_pages(document, page_height: float) -> dict[str, int]:
    """
    Which page each heading landed on, once the document has been laid out.

    Qt records the heading level of a block, so the sections can be found
    without matching their text against anything.
    """
    layout = document.documentLayout()
    pages: dict[str, int] = {}
    block = document.begin()
    while block.isValid():
        if block.blockFormat().headingLevel() == 2:
            top = layout.blockBoundingRect(block).top()
            pages.setdefault(block.text().strip(), int(top // page_height) + 1)
        block = block.next()
    return pages


def _orphan_headings(document, page_height: float) -> set[str]:
    """
    Headings left stranded at the foot of a page, their content overleaf.

    Qt has no `keep-with-next`, so the only way to hold a heading to what it
    introduces is to lay the document out, see which headings were separated
    from it, and lay it out again with those pushed to the next page. A
    heading is stranded when the block that follows it starts on a later
    page — which is precisely the test, and says nothing about how much space
    was left underneath.
    """
    layout = document.documentLayout()
    stranded: set[str] = set()
    block = document.begin()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        following = block.next()
        if level in (2, 3) and following.isValid() and block.text().strip():
            here = int(layout.blockBoundingRect(block).top() // page_height)
            there = int(layout.blockBoundingRect(following).top() // page_height)
            if there > here:
                stranded.add(block.text().strip())
        block = block.next()
    return stranded


def _furniture(painter, writer, page: int, total: int, title: str,
               header: float, footer: float, body) -> None:
    """
    The running header and footer: what this is, and where the reader is in it.

    Page one carries the title block, so the running header starts on page two;
    the footer is on every page, because a page that comes loose from the
    others has to say what it belongs to.
    """
    from PyQt6 import QtCore, QtGui

    rule = QtGui.QColor("#c3c9d3")
    muted = QtGui.QColor("#5b6472")
    font = QtGui.QFont()
    font.setFamilies(["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"])
    font.setPointSizeF(7.0)
    painter.save()
    painter.setFont(font)
    painter.setPen(muted)

    width = body.width()
    if page > 1:
        band = QtCore.QRectF(0, 0, width, header * 0.62)
        painter.drawText(band, int(QtCore.Qt.AlignmentFlag.AlignLeft
                                   | QtCore.Qt.AlignmentFlag.AlignVCenter), title)
        painter.setPen(QtGui.QPen(rule, writer.resolution() / 1200.0))
        painter.drawLine(QtCore.QPointF(0, header * 0.72),
                         QtCore.QPointF(width, header * 0.72))
        painter.setPen(muted)

    top = header + body.height()
    painter.setPen(QtGui.QPen(rule, writer.resolution() / 1200.0))
    painter.drawLine(QtCore.QPointF(0, top + footer * 0.28),
                     QtCore.QPointF(width, top + footer * 0.28))
    painter.setPen(muted)
    band = QtCore.QRectF(0, top + footer * 0.34, width, footer * 0.66)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    painter.drawText(band, int(QtCore.Qt.AlignmentFlag.AlignLeft
                               | QtCore.Qt.AlignmentFlag.AlignTop),
                     f"OpenQuant {__version__} · generated {stamp}")
    painter.drawText(band, int(QtCore.Qt.AlignmentFlag.AlignRight
                               | QtCore.Qt.AlignmentFlag.AlignTop),
                     f"Page {page} of {total}")
    painter.restore()


def write_pdf(session, path: str | os.PathLike, **kwargs) -> str:
    """
    The same document, on A4 portrait pages, with page numbers.

    Two things here are not obvious and both were bugs. The layout is given
    the writer as its paint device: without one it measures type at the
    screen's ninety-six dots to the inch while the page is sized in the
    writer's twelve hundred, so every point size comes out at a twelfth of
    itself and the whole report collapses into a corner of page one. And it
    is laid out twice, because the table of contents cannot know a page
    number until the pages exist; the first pass reserves the column so that
    the second paginates identically.

    Qt is imported here rather than at the top so that building the HTML —
    which is what the tests exercise — needs no GUI toolkit at all.
    """
    from PyQt6 import QtCore, QtGui

    path = str(path)
    title = kwargs.get("title", "Batch report")
    writer = QtGui.QPdfWriter(path)
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QtGui.QPageLayout.Orientation.Portrait)
    left, top, right, bottom = MARGINS_MM
    writer.setPageMargins(QtCore.QMarginsF(left, top, right, bottom),
                          QtGui.QPageLayout.Unit.Millimeter)
    writer.setTitle(title)
    writer.setCreator(f"OpenQuant {__version__}")

    def millimetres(value: float) -> float:
        return value / 25.4 * writer.resolution()

    header, footer = millimetres(HEADER_MM), millimetres(FOOTER_MM)
    body = QtCore.QSizeF(writer.width(), writer.height() - header - footer)

    def lay_out(contents, breaks=None):
        document = QtGui.QTextDocument()
        document.documentLayout().setPaintDevice(writer)
        document.setHtml(build_html(session, contents=contents, breaks=breaks,
                                    **kwargs))
        document.setPageSize(body)
        return document

    breaks: set[str] = set()
    document = lay_out({})
    for _ in range(MAX_REFLOWS):                  # a break can strand another
        stranded = _orphan_headings(document, body.height()) - breaks
        if not stranded:
            break
        breaks |= stranded
        document = lay_out({}, breaks)
    document = lay_out(_section_pages(document, body.height()), breaks)

    painter = QtGui.QPainter(writer)
    try:
        total = document.pageCount()
        for index in range(total):
            if index:
                writer.newPage()
            painter.save()
            painter.translate(0.0, header - index * body.height())
            document.drawContents(painter, QtCore.QRectF(
                0.0, index * body.height(), body.width(), body.height()))
            painter.restore()
            _furniture(painter, writer, index + 1, total, title, header, footer,
                       body)
    finally:
        painter.end()
    return path
