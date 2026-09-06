"""Metric plots: any results column against the row order or another column."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from . import theme
from ..session import Session
from .plots import colour
from .results_table import COLUMNS

#: only numeric columns can be plotted
NUMERIC = [c for c in COLUMNS if c.decimals is not None]
ROW_ORDER = "row order"

NO_COLOUR = "nothing"
BY_SAMPLE_GROUP = "sample group"
BY_SAMPLE_TYPE = "sample type"
COLOURINGS = (BY_SAMPLE_GROUP, BY_SAMPLE_TYPE, NO_COLOUR)

#: what a sample with no group is called in the legend
UNGROUPED = "no group"
#: the colour it is drawn in, kept out of the palette so a real group never
#: shares it
UNGROUPED_COLOUR = "#9a9a9a"


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
        bar.addWidget(QtWidgets.QLabel("Colour by"))
        self.colour_combo = QtWidgets.QComboBox()
        self.colour_combo.addItems(list(COLOURINGS))
        self.colour_combo.setToolTip(
            "Draw each study group in its own colour, so a treated batch "
            "separating from its controls is visible rather than inferred")
        bar.addWidget(self.colour_combo)
        layout.addLayout(bar)

        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        theme.style_axes(self.plot)
        self.legend = self.plot.addLegend(
            offset=(-10, 10), labelTextColor=theme.foreground(),
            brush=theme.legend_brush(), pen=theme.legend_pen(), verSpacing=-4)
        self.legend.setLabelTextSize("8pt")
        #: one scatter per colour group; a single item with per-spot brushes
        #: would draw the same picture but could not be put in a legend
        self._scatters: list[pg.ScatterPlotItem] = []
        layout.addWidget(self.plot, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        for widget in (self.x_combo, self.y_combo, self.component_combo,
                       self.colour_combo):
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

        # entry_by_key scans the batch, and this runs once per point
        entries = {e.key: e for e in self.session.entries}
        by_group: dict[str, list[dict]] = {}
        order: list[str] = []
        self._points = []
        for index, result in enumerate(rows):
            y = self._value(result, y_column)
            x = float(index + 1) if x_column is None else self._value(result, x_column)
            if x is None or y is None:
                continue
            key = self._colour_key(result, entries)
            if key not in by_group:
                by_group[key] = []
                order.append(key)
            by_group[key].append({"pos": (x, y), "data": len(self._points)})
            self._points.append((result.sample_key, result.component))

        self._draw(by_group, order)
        self.plot.setLabel("bottom", x_title)
        self.plot.setLabel("left", self.y_combo.currentText())
        self.plot.enableAutoRange()
        self.plot.autoRange()
        total = sum(len(spots) for spots in by_group.values())
        self.status.setText(
            f"{total} point(s)"
            + (f" · {len(order)} group(s)" if self._colouring() else ""))

    def _colouring(self) -> str:
        choice = self.colour_combo.currentText()
        return "" if choice == NO_COLOUR else choice

    def _colour_key(self, result, entries: dict) -> str:
        """Which colour bucket a point belongs to, by the current choice."""
        choice = self._colouring()
        if not choice:
            return ""
        entry = entries.get(result.sample_key)
        if entry is None:
            return UNGROUPED
        if choice == BY_SAMPLE_TYPE:
            return entry.sample_type
        return entry.sample_group or UNGROUPED

    def _draw(self, by_group: dict[str, list[dict]], order: list[str]) -> None:
        for scatter in self._scatters:
            self.plot.removeItem(scatter)
        self._scatters.clear()
        self.legend.clear()

        # the palette index skips the ungrouped bucket so adding one unlabelled
        # sample does not recolour every real group
        palette_index = 0
        for key in order:
            if key == UNGROUPED or not key:
                pen_colour = UNGROUPED_COLOUR
            else:
                pen_colour = colour(palette_index)
                palette_index += 1
            scatter = pg.ScatterPlotItem(size=9, pen=pg.mkPen(theme.axis()),
                                         brush=pg.mkBrush(pen_colour))
            scatter.setData(by_group[key])
            scatter.sigClicked.connect(self._on_clicked)
            self.plot.addItem(scatter)
            self._scatters.append(scatter)
            if self._colouring():
                self.legend.addItem(scatter, key)
        self.legend.setVisible(bool(self._colouring()) and len(order) > 1)

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
