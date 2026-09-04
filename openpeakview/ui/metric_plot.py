"""Metric plots: any results column against the row order or another column."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from ..session import Session
from .results_table import COLUMNS

#: only numeric columns can be plotted
NUMERIC = [c for c in COLUMNS if c.decimals is not None]
ROW_ORDER = "row order"


class MetricPlotPanel(QtWidgets.QWidget):
    """
    Plots one results column against another, or against the row order.

    A batch is easiest to judge as a picture: an internal standard drifting
    across an injection sequence, or a response that stops tracking
    concentration, shows up here long before it does in a table of numbers.
    """

    sigPointActivated = QtCore.pyqtSignal(str, str)   # sample key, component

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._points: list[tuple[str, str]] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("X"))
        self.x_combo = QtWidgets.QComboBox()
        self.x_combo.addItem(ROW_ORDER)
        self.x_combo.addItems([c.title for c in NUMERIC])
        bar.addWidget(self.x_combo)
        bar.addWidget(QtWidgets.QLabel("Y"))
        self.y_combo = QtWidgets.QComboBox()
        self.y_combo.addItems([c.title for c in NUMERIC])
        self.y_combo.setCurrentText("Area")
        bar.addWidget(self.y_combo)
        bar.addWidget(QtWidgets.QLabel("Component"))
        self.component_combo = QtWidgets.QComboBox()
        bar.addWidget(self.component_combo, 1)
        layout.addLayout(bar)

        self.plot = pg.PlotWidget(background="w")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        for axis in ("bottom", "left"):
            self.plot.getAxis(axis).setPen(pg.mkPen("#444"))
            self.plot.getAxis(axis).setTextPen(pg.mkPen("#222"))
        self.scatter = pg.ScatterPlotItem(size=9, pen=pg.mkPen("#333"),
                                          brush=pg.mkBrush("#1f77b4"))
        self.scatter.sigClicked.connect(self._on_clicked)
        self.plot.addItem(self.scatter)
        layout.addWidget(self.plot, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color:#666;")
        layout.addWidget(self.status)

        for widget in (self.x_combo, self.y_combo, self.component_combo):
            widget.currentTextChanged.connect(self.reload)
        session.sigResultsChanged.connect(self.reload)
        session.sigMethodChanged.connect(self._reload_components)
        self._reload_components()

    def _reload_components(self, *_args) -> None:
        previous = self.component_combo.currentText()
        self.component_combo.blockSignals(True)
        self.component_combo.clear()
        self.component_combo.addItem("all")
        self.component_combo.addItems(
            [c.name for c in self.session.method.components])
        index = self.component_combo.findText(previous)
        self.component_combo.setCurrentIndex(max(index, 0))
        self.component_combo.blockSignals(False)
        self.reload()

    def reload(self, *_args) -> None:
        wanted = self.component_combo.currentText()
        rows = [r for r in self.session.results
                if wanted in ("all", "") or r.component == wanted]
        y_column = next((c for c in NUMERIC if c.title == self.y_combo.currentText()),
                        None)
        x_title = self.x_combo.currentText()
        x_column = next((c for c in NUMERIC if c.title == x_title), None)

        spots, self._points = [], []
        for index, result in enumerate(rows):
            y = self._value(result, y_column)
            x = float(index + 1) if x_column is None else self._value(result, x_column)
            if x is None or y is None:
                continue
            spots.append({"pos": (x, y), "data": len(self._points)})
            self._points.append((result.sample_key, result.component))

        self.scatter.setData(spots)
        self.plot.setLabel("bottom", x_title)
        self.plot.setLabel("left", self.y_combo.currentText())
        self.plot.enableAutoRange()
        self.plot.autoRange()
        self.status.setText(f"{len(spots)} point(s)")

    @staticmethod
    def _value(result, column) -> float | None:
        if column is None:
            return None
        if column.field == "rt_delta":
            value = result.rt_delta
        else:
            value = getattr(result, column.field, None)
        return float(value) if isinstance(value, (int, float)) else None

    def _on_clicked(self, _scatter, spots) -> None:
        if not spots:
            return
        index = spots[0].data()
        if isinstance(index, int) and 0 <= index < len(self._points):
            self.sigPointActivated.emit(*self._points[index])
