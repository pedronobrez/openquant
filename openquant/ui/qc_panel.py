"""
The batch as a control chart: what the run did between first and last.

Every other view in this program answers a question about one peak in one
sample. This one answers a question about the run — and it is the only view
where the horizontal axis is time in the sense that matters, the order the
instrument actually injected.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from . import theme
from ..qc import (MIN_SNR, OUTLIER_SIGMA, OUT_PERCENT, WARN_SIGMA,
                  BatchQC, ControlChart, batch_qc)
from ..session import Session

POINT = "#234b8c"
POINT_OUT = "#a4262c"
POINT_WARN = "#c07a00"
CENTRE_PEN = "#4c8c4a"
TREND_PEN = "#a4262c"


class QualityPanel(QtWidgets.QWidget):
    """
    An internal standard's response across the injection sequence.

    The same amount of it went into every vial, so anything the chart shows
    is the batch's own doing: an injection that failed, a source that
    gradually stopped ionising, a column that shifted halfway through.
    """

    sigSampleActivated = QtCore.pyqtSignal(str)        # sample key

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._report: BatchQC | None = None
        self._chart: ControlChart | None = None
        self._keys: list[str] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Component"))
        self.component = QtWidgets.QComboBox()
        self.component.setToolTip(
            "Internal standards first: the same amount goes into every vial, "
            "so their response is the one number whose variation belongs to "
            "the batch rather than to the study")
        bar.addWidget(self.component, 1)
        self.btn_refresh = QtWidgets.QPushButton("Recheck")
        bar.addWidget(self.btn_refresh)
        bar.addStretch(1)
        layout.addLayout(bar)

        body = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "Injection")
        self.plot.setToolTip(
            f"Solid line the median, dotted {WARN_SIGMA:g}\u03c3, dashed "
            f"{OUTLIER_SIGMA:g}\u03c3. An injection is called out only when "
            f"it is past {OUTLIER_SIGMA:g}\u03c3 and at least "
            f"{OUT_PERCENT:g}% from the centre — a batch that repeats itself "
            f"well has a spread too small to flag on alone")
        self.plot.setLabel("left", "Response")
        theme.style_axes(self.plot)
        self._lines: list[pg.InfiniteLine] = []
        self._trend = self.plot.plot([], [], pen=pg.mkPen(TREND_PEN, width=1.2,
                                                          style=QtCore.Qt.PenStyle.DashLine))
        self._scatter = pg.ScatterPlotItem(size=9, pen=pg.mkPen(theme.axis()))
        self._scatter.sigClicked.connect(self._on_point_clicked)
        self.plot.addItem(self._scatter)
        body.addWidget(self.plot)

        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Component", "n", "Centre", "Spread", "S/N", "Drift %", "ρ",
             "Verdict"])
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip("Click a row to chart that component")

        self.precision = QtWidgets.QTableWidget(0, 4)
        self.precision.setHorizontalHeaderLabels(
            ["Component", "n", "Mean", "%CV"])
        self.precision.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.precision.verticalHeader().setDefaultSectionSize(20)
        self.precision.horizontalHeader().setStretchLastSection(True)
        self.precision.setToolTip(
            "Quality controls only: unknowns differ by design and standards "
            "by construction, so neither says anything about precision")

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.table, "Control charts")
        self.tabs.addTab(self.precision, "Precision")
        body.addWidget(self.tabs)
        body.setSizes([520, 260])
        layout.addWidget(body, 1)

        self.status = QtWidgets.QLabel("Nothing measured yet.")
        self.status.setProperty("role", "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.component.currentTextChanged.connect(self._draw_selected)
        self.btn_refresh.clicked.connect(self.reload)
        self.table.cellClicked.connect(self._on_row_clicked)
        session.sigResultsChanged.connect(self.reload)
        session.sigMethodChanged.connect(self.reload)

    # -- content ------------------------------------------------------------ #
    def reload(self, *_args) -> None:
        if not len(self.session.results):
            self._report = None
            self._clear()
            self.status.setText("Process the batch to see how it held up.")
            return
        self._report = batch_qc(self.session.results, self.session.entries,
                                self.session.method)
        self._fill_table()
        self._fill_precision()
        self._reload_components()
        self._describe()

    def _reload_components(self) -> None:
        previous = self.component.currentText()
        self.component.blockSignals(True)
        self.component.clear()
        if self._report:
            self.component.addItems([c.component for c in self._report.charts])
        index = self.component.findText(previous)
        self.component.setCurrentIndex(max(index, 0))
        self.component.blockSignals(False)
        self._draw_selected()

    def _describe(self) -> None:
        report = self._report
        if report is None:
            return
        if report.note:
            self.status.setText(report.note)
            return
        said = [f"{report.injections} injection(s)"]
        said.append("in acquisition order" if report.ordered else
                    f"in the order opened — only {report.timed} of "
                    f"{report.injections} carry an acquisition time, so the "
                    f"sequence is a guess")
        if report.drifted:
            said.append(f"{len(report.drifted)} drifting")
        stray = sum(len(chart.out) for chart in report.out)
        if stray:
            said.append(f"{stray} injection(s) beyond {OUTLIER_SIGMA:g}σ")
        if report.imprecise:
            said.append(f"{len(report.imprecise)} component(s) over the %CV limit")
        quiet = [c for c in report.charts if not c.quantifiable]
        if quiet:
            said.append(f"{len(quiet)} below S/N {MIN_SNR:g}")
        if not report.drifted and not stray and not report.imprecise and not quiet:
            said.append("nothing outside its limits")
        self.status.setText(" · ".join(said))

    def _fill_table(self) -> None:
        charts = self._report.charts if self._report else []
        self.table.setRowCount(len(charts))
        for row, chart in enumerate(charts):
            snr = f"{chart.snr:,.0f}" if chart.snr is not None else "—"
            cells = [chart.component, f"{len(chart.injections):,}"]
            if chart.measurable:
                cells += [f"{chart.centre:,.1f}", f"{chart.sigma:,.1f}", snr,
                          f"{chart.drift:,.1f}" if chart.drift is not None else "—",
                          f"{chart.correlation:.3f}"
                          if chart.correlation is not None else "—",
                          self._verdict(chart)]
            else:
                cells += ["—", "—", snr, "—", "—",
                          chart.note or "not measurable"]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column in (1, 2, 3, 4, 5, 6):
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 7 and (chart.drifted or chart.out):
                    item.setForeground(pg.mkColor(theme.danger()))
                self.table.setItem(row, column, item)
        self.table.setColumnWidth(0, 160)

    def _fill_precision(self) -> None:
        rows = [row for row in (self._report.precision if self._report else [])
                if row.measurable]
        rows.sort(key=lambda r: -(r.percent_cv or 0.0))
        self.precision.setRowCount(len(rows))
        for index, row in enumerate(rows):
            cells = [row.component, f"{row.replicates:,}", f"{row.mean:,.1f}",
                     f"{row.percent_cv:,.2f}"]
            for column, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if column == 3 and row.fails:
                    item.setForeground(pg.mkColor(theme.danger()))
                self.precision.setItem(index, column, item)
        self.precision.setColumnWidth(0, 200)

    @staticmethod
    def _verdict(chart: ControlChart) -> str:
        if not chart.quantifiable:
            return f"below S/N {MIN_SNR:g} — not quantified, so not flagged"
        said = []
        if chart.drifted:
            said.append(f"drift {chart.drift:+,.0f}%")
        if chart.out:
            said.append(f"{len(chart.out)} outside {OUTLIER_SIGMA:g}σ")
        if chart.excess_warnings:
            said.append(f"{len(chart.warned)} beyond {WARN_SIGMA:g}σ")
        if said:
            return "; ".join(said)
        return chart.note or "steady"

    # -- the chart ----------------------------------------------------------- #
    def _clear(self) -> None:
        self._scatter.setData([])
        self._trend.setData([], [])
        for line in self._lines:
            self.plot.removeItem(line)
        self._lines.clear()
        self.table.setRowCount(0)
        self.precision.setRowCount(0)
        self._keys = []

    def _draw_selected(self, *_args) -> None:
        name = self.component.currentText()
        chart = next((c for c in (self._report.charts if self._report else [])
                      if c.component == name), None)
        self._chart = chart
        self._clear()
        self._fill_table()
        if chart is None or not chart.injections:
            return

        self._keys = [point.sample for point in chart.injections]
        spots = []
        for index, point in enumerate(chart.injections):
            brush = POINT
            if point.out:
                brush = POINT_OUT
            elif point.warned:
                brush = POINT_WARN
            spots.append({"pos": (point.order, point.value),
                          "brush": pg.mkBrush(brush), "data": index})
        self._scatter.setData(spots)
        self.plot.setLabel("left", f"{name} response")

        if not chart.measurable or not chart.sigma:
            return
        # the centre and its limits, drawn rather than described: a point
        # three quarters of the way to the line is the thing worth seeing,
        # and no table shows that
        self._line_at(chart.centre, CENTRE_PEN, 1.4, QtCore.Qt.PenStyle.SolidLine)
        # the three-sigma line is the one a decision hangs on, so it is the
        # one drawn to be seen; two sigma is a hint and is drawn like one
        for sigma, pen, width, style in (
                (WARN_SIGMA, theme.muted(), 1.0, QtCore.Qt.PenStyle.DotLine),
                (OUTLIER_SIGMA, POINT_OUT, 1.2, QtCore.Qt.PenStyle.DashLine)):
            for sign in (1, -1):
                self._line_at(chart.centre + sign * sigma * chart.sigma,
                              pen, width, style)
        if chart.drifted:
            order = np.array([p.order for p in chart.injections], dtype=float)
            values = np.array([p.value for p in chart.injections], dtype=float)
            fit = np.polyfit(order, values, 1)
            self._trend.setData(order, np.polyval(fit, order))

    def _line_at(self, y: float, colour: str, width: float, style) -> None:
        line = pg.InfiniteLine(pos=y, angle=0,
                               pen=pg.mkPen(colour, width=width, style=style))
        self.plot.addItem(line)
        self._lines.append(line)

    # -- interaction --------------------------------------------------------- #
    def _on_row_clicked(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            self.component.setCurrentText(item.text())

    def _on_point_clicked(self, _scatter, spots) -> None:
        if not spots or self._chart is None:
            return
        index = spots[0].data()
        if not isinstance(index, int) or not 0 <= index < len(self._chart.injections):
            return
        point = self._chart.injections[index]
        entry = next((e for e in self.session.entries if e.name == point.sample),
                     None)
        if entry is not None:
            self.sigSampleActivated.emit(entry.key)
