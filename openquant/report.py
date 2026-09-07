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
"""

from __future__ import annotations

import datetime as _dt
import html
import os

from .calibration import Calibration
from .method import ProcessingMethod
from .quantify import PeakResult, ResultsSet
from .samples import SampleEntry
from .statistics import GROUP_BY_SAMPLE_TYPE, summarise
from .validation import all_detection_limits, carryover

#: the statuses a row can carry. Matched without regard to case: the results
#: capitalise them and an earlier version of this counted them in lower case,
#: so a batch with twenty-eight passes and two failures reported that no
#: acceptance criteria had been set.
STATUSES = ("pass", "marginal", "fail")


def _escape(value) -> str:
    return html.escape("" if value is None else str(value))


def _number(value, decimals: int = 4) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return _escape(value)


def _table(headers: list[str], rows: list[list[str]], right: set[int] = frozenset(),
           empty: str = "Nothing to show.") -> str:
    if not rows:
        return f'<p class="empty">{_escape(empty)}</p>'
    head = "".join(f"<th>{_escape(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(
            f'<td class="{"num" if index in right else ""}">{cell}</td>'
            for index, cell in enumerate(row))
        body.append(f"<tr>{cells}</tr>")
    return (f'<table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


# --------------------------------------------------------------------------- #
# the sections
# --------------------------------------------------------------------------- #
def _header(title: str, project: str | None, entries, method) -> str:
    when = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    where = os.path.basename(project) if project else "unsaved project"
    return (
        f"<h1>{_escape(title)}</h1>"
        f'<p class="meta">{_escape(where)} · {len(entries)} sample(s) · '
        f"{len(method.components)} component(s) · generated {when}</p>"
    )


def _summary(results: ResultsSet, entries: list[SampleEntry]) -> str:
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
    return "<h2>Summary</h2>" + _table(["", ""], body, right={1})


def _samples(entries: list[SampleEntry]) -> str:
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
    return "<h2>Samples</h2>" + _table(
        ["Sample", "File", "Type", "Group", "Concentration", "Dilution", "Comment"],
        rows, right={4, 5}, empty="No samples were open.")


def _method(method: ProcessingMethod) -> str:
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
    return "<h2>Method</h2>" + _table(
        ["Component", "Group", "Precursor", "Fragment", "RT", "Window",
         "Tolerance", "Internal standard", "Role"],
        rows, right={2, 3, 4, 5, 6}, empty="The method has no components.")


def _calibrations(calibrations: dict[str, Calibration],
                  method: ProcessingMethod) -> str:
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
    return "<h2>Calibration</h2>" + _table(
        ["Component", "Regression", "Weighting", "Equation", "r²", "r", "Points"],
        rows, right={4, 5, 6},
        empty="No curve was built. Mark samples as Standard and give them a "
              "concentration.")


def _limits(calibrations, method: ProcessingMethod) -> str:
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
    return ("<h2>Detection and quantitation limits</h2>"
            '<p class="meta">3.3&#963;/S and 10&#963;/S, with &#963; the '
            "residual standard deviation of the curve about its own line "
            "(ICH Q2). Internal standards are left out.</p>"
            + _table(["Component", "LOD", "LOQ", "σ", "Slope", "Notes"],
                     rows, right={1, 2, 3, 4},
                     empty="No curve to derive a limit from."))


def _carryover(results: ResultsSet, entries: list[SampleEntry],
               method: ProcessingMethod) -> str:
    found = carryover(results, entries, method)
    if found.note:
        return (f'<h2>Carryover</h2><p class="empty">{_escape(found.note)}</p>')
    rows = []
    for row in sorted(found.rows, key=lambda r: -r.percent):
        rows.append([
            _escape(row.component), _number(row.blank_area, 1),
            _number(row.reference_area, 1), _number(row.percent, 2),
            "FAIL" if row.fails else "ok",
        ])
    first = found.rows[0] if found.rows else None
    heading = ""
    if first is not None:
        heading = (f'<p class="meta">{_escape(first.blank)}, injected after '
                   f"{_escape(first.follows)}, against the response at the "
                   f"lowest calibrated concentration ({_escape(first.reference)}). "
                   f"Limit {_number(first.limit, 0)}%.</p>")
    return ("<h2>Carryover</h2>" + heading
            + _table(["Component", "Blank", "At the lowest standard", "%", ""],
                     rows, right={1, 2, 3},
                     empty="Nothing to compare."))


def _results(results: ResultsSet, method: ProcessingMethod) -> str:
    by_component: dict[str, list[PeakResult]] = {}
    for row in results:
        by_component.setdefault(row.component, []).append(row)

    parts = ["<h2>Results</h2>"]
    if not by_component:
        return parts[0] + '<p class="empty">Nothing was integrated.</p>'

    order = [c.name for c in method.components if c.name in by_component]
    order += [name for name in sorted(by_component) if name not in order]

    for name in order:
        rows = []
        for row in sorted(by_component[name], key=lambda r: r.sample_name):
            flags = "; ".join(row.flags) if row.flags else ""
            rows.append([
                _escape(row.sample_name),
                _number(row.rt, 3), _number(row.expected_rt, 3),
                _number(row.area, 1), _number(row.height, 1),
                _number(row.snr, 1),
                _number(row.area_ratio, 4) if row.area_ratio is not None else "—",
                _number(row.calculated_concentration, 4)
                if row.calculated_concentration is not None else "—",
                _number(row.accuracy, 2) if row.accuracy is not None else "—",
                _escape(row.status or "—"),
                _escape(flags or row.note or ""),
                "no" if not row.used else ("by hand" if row.manual else "yes"),
            ])
        parts.append(f"<h3>{_escape(name)}</h3>")
        parts.append(_table(
            ["Sample", "RT", "Expected", "Area", "Height", "S/N", "Ratio",
             "Concentration", "Accuracy %", "Status", "Flags", "Used"],
            rows, right={1, 2, 3, 4, 5, 6, 7, 8}))
    return "".join(parts)


def _statistics(results: ResultsSet, entries: list[SampleEntry],
                method: ProcessingMethod, grouping: str) -> str:
    try:
        summary = summarise(results, entries, method, grouping, "response")
    except Exception as exc:                      # a report must still print
        return f'<h2>Statistics</h2><p class="empty">Not computed: {_escape(exc)}</p>'
    rows = []
    for row in summary:
        rows.append([
            _escape(row.component), _escape(row.group),
            f"{row.used} of {row.total}",
            _number(row.mean, 4), _number(row.standard_deviation, 4),
            _number(row.percent_cv, 2), _number(row.accuracy, 2),
        ])
    return (f"<h2>Statistics</h2><p class=\"meta\">Response, grouped by "
            f"{_escape(grouping)}.</p>"
            + _table(["Component", "Group", "n", "Mean", "SD", "%CV", "Accuracy %"],
                     rows, right={2, 3, 4, 5, 6},
                     empty="Nothing to summarise."))


_STYLE = """
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
       font-size: 9pt; color: #16181c; }
h1 { font-size: 17pt; margin: 0 0 2pt 0; }
h2 { font-size: 12pt; margin: 16pt 0 4pt 0; border-bottom: 1px solid #b9bec7;
     padding-bottom: 2pt; }
h3 { font-size: 10pt; margin: 10pt 0 3pt 0; color: #234b8c; }
p.meta { color: #5b6472; margin: 0 0 8pt 0; }
p.empty { color: #5b6472; font-style: italic; }
span.aside { color: #5b6472; font-style: italic; }
table { border-collapse: collapse; width: 100%; margin-bottom: 6pt; }
th { text-align: left; background: #eef1f5; border-bottom: 1px solid #b9bec7;
     padding: 3pt 5pt; font-weight: 600; }
td { padding: 2pt 5pt; border-bottom: 1px solid #e3e6ea; }
td.num { text-align: right; }
"""


# --------------------------------------------------------------------------- #
def build_html(session, title: str = "Batch report",
               grouping: str = GROUP_BY_SAMPLE_TYPE,
               sections: tuple[str, ...] = ("summary", "samples", "method",
                                            "calibration", "limits",
                                            "carryover", "results",
                                            "statistics")) -> str:
    """
    The whole report as one HTML document.

    Sections are named so a caller can leave out what it does not want — a
    hundred-component method makes a results section nobody prints.
    """
    entries = list(session.entries)
    method = session.method
    parts = [f"<html><head><meta charset='utf-8'><style>{_STYLE}</style></head><body>",
             _header(title, session.project_path, entries, method)]
    if "summary" in sections:
        parts.append(_summary(session.results, entries))
    if "samples" in sections:
        parts.append(_samples(entries))
    if "method" in sections:
        parts.append(_method(method))
    if "calibration" in sections:
        parts.append(_calibrations(session.calibrations, method))
    if "limits" in sections:
        parts.append(_limits(session.calibrations, method))
    if "carryover" in sections:
        parts.append(_carryover(session.results, entries, method))
    if "results" in sections:
        parts.append(_results(session.results, method))
    if "statistics" in sections:
        parts.append(_statistics(session.results, entries, method, grouping))
    parts.append("</body></html>")
    return "".join(parts)


def write_html(session, path: str | os.PathLike, **kwargs) -> str:
    path = str(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(build_html(session, **kwargs))
    return path


def write_pdf(session, path: str | os.PathLike, **kwargs) -> str:
    """
    The same document, laid out and paginated by Qt.

    Imported here rather than at the top so that building the HTML — which is
    what the tests exercise — needs no GUI toolkit at all.
    """
    from PyQt6 import QtCore, QtGui

    path = str(path)
    document = QtGui.QTextDocument()
    document.setHtml(build_html(session, **kwargs))

    writer = QtGui.QPdfWriter(path)
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QtGui.QPageLayout.Orientation.Landscape)
    writer.setPageMargins(QtCore.QMarginsF(12, 12, 12, 12),
                          QtGui.QPageLayout.Unit.Millimeter)
    writer.setTitle(kwargs.get("title", "Batch report"))
    document.setPageSize(QtCore.QSizeF(writer.width(), writer.height()))
    document.print(writer)
    return path
