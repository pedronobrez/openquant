"""Chromatogram and spectrum panes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme
from ..processing import (
    ChromPeak,
    centroid_spectrum,
    gaussian_smooth,
    pick_peaks,
    subtract_baseline,
)

PALETTE = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
    "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f",
]
ARROW_COLOUR = "#7a3fbf"


def colour(i: int) -> str:
    return PALETTE[i % len(PALETTE)]


@dataclass
class Trace:
    """One curve drawn in a pane."""

    key: str
    label: str
    x: np.ndarray
    y: np.ndarray
    colour: str
    source: object | None = None  # originating Channel, when there is one


def _sticks(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Turn centroids into a single polyline of vertical sticks, split by NaN."""
    xs = np.repeat(x, 3)
    ys = np.empty(xs.size, dtype=np.float64)
    ys[0::3] = 0.0
    ys[1::3] = y
    ys[2::3] = np.nan
    return xs, ys


class _DragViewBox(pg.ViewBox):
    """ViewBox that turns a horizontal drag into a range selection."""

    sigRangeDrag = QtCore.pyqtSignal(float, float, bool)  # x0, x1, finished

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.select_mode = False

    def mouseDragEvent(self, ev, axis=None):
        shift = bool(ev.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier)
        left = ev.button() == QtCore.Qt.MouseButton.LeftButton
        if left and (self.select_mode or shift):
            ev.accept()
            x0 = float(self.mapToView(ev.buttonDownPos()).x())
            x1 = float(self.mapToView(ev.pos()).x())
            self.sigRangeDrag.emit(x0, x1, ev.isFinish())
            return
        super().mouseDragEvent(ev, axis)


class BasePlot(QtWidgets.QWidget):
    """Shared behaviour: grid, crosshair, legend, processing, markers, overview."""

    sigRangeSelected = QtCore.pyqtSignal(float, float)   # selection finished
    sigRangeDragging = QtCore.pyqtSignal(float, float)   # selection being dragged
    sigClicked = QtCore.pyqtSignal(float)                # single click at x
    sigFocused = QtCore.pyqtSignal()                     # user interacted here

    #: how close a peak must be to a marker to keep its absolute label
    marker_snap = 0.05

    def __init__(self, x_label: str, x_units: str, y_label: str, parent=None):
        super().__init__(parent)
        self._traces: list[Trace] = []
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._normalise = False
        self._smooth_sigma = 0.0
        self._mirror = False
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._stick_mode = False
        self._arrows: list[pg.InfiniteLine] = []
        self._relative_labels = True
        self._syncing_overview = False

        self.viewbox = _DragViewBox()
        self.plot = pg.PlotWidget(viewBox=self.viewbox,
                                  background=theme.background())
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", x_label, units=x_units or None)
        self.plot.setLabel("left", y_label)
        theme.style_axes(self.plot)
        self.legend = self.plot.addLegend(
            offset=(-10, 10), labelTextColor=theme.foreground(),
            brush=theme.legend_brush(), pen=theme.legend_pen(), verSpacing=-4,
        )
        self.legend.setLabelTextSize("8pt")

        self.region = pg.LinearRegionItem(
            brush=pg.mkBrush(60, 110, 200, 45),
            hoverBrush=pg.mkBrush(60, 110, 200, 70),
            pen=pg.mkPen("#3b6ec8", width=1),
        )
        self.region.setZValue(-10)
        self.region.hide()
        self.plot.addItem(self.region, ignoreBounds=True)
        self.region.sigRegionChangeFinished.connect(self._region_finished)
        self.region.sigRegionChanged.connect(self._region_moving)

        self.vline = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#999", style=QtCore.Qt.PenStyle.DashLine),
        )
        self.vline.hide()
        self.plot.addItem(self.vline, ignoreBounds=True)

        self.readout = pg.TextItem(color=theme.foreground(), anchor=(0, 1))
        self.readout.setZValue(100)
        self.plot.addItem(self.readout, ignoreBounds=True)

        # navigator: always shows the full range, with the current view marked
        self.overview = pg.PlotWidget(background=theme.background())
        self.overview.setFixedHeight(64)
        self.overview.setMenuEnabled(False)
        self.overview.hideButtons()
        self.overview.getPlotItem().hideAxis("left")
        self.overview.getAxis("bottom").setPen(pg.mkPen(theme.faint_axis()))
        self.overview.getAxis("bottom").setTextPen(pg.mkPen(theme.muted()))
        self.overview.setMouseEnabled(x=False, y=False)
        self.overview_region = pg.LinearRegionItem(
            brush=pg.mkBrush(200, 120, 200, 55),
            hoverBrush=pg.mkBrush(200, 120, 200, 85),
            pen=pg.mkPen("#a05aa0", width=1),
        )
        self.overview.addItem(self.overview_region)
        self.overview.hide()
        self.overview_region.sigRegionChanged.connect(self._overview_moved)
        self.plot.getViewBox().sigXRangeChanged.connect(self._main_range_changed)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.plot, 1)
        layout.addWidget(self.overview)

        self.viewbox.sigRangeDrag.connect(self._on_drag)
        self.plot.scene().sigMouseMoved.connect(self._on_move)
        self.plot.scene().sigMouseClicked.connect(self._on_click)

    # -- mouse mode ---------------------------------------------------------- #
    def set_select_mode(self, enabled: bool) -> None:
        self.viewbox.select_mode = enabled
        self.plot.setCursor(
            QtCore.Qt.CursorShape.SplitHCursor if enabled
            else QtCore.Qt.CursorShape.CrossCursor
        )

    # -- processing ---------------------------------------------------------- #
    def condition(self, trace: Trace) -> tuple[np.ndarray, np.ndarray]:
        """
        Data-level processing (baseline, smoothing, centroiding). This is what
        integration and export use, so area and height match what is on screen.
        Returns both axes because centroiding shortens the x axis.
        """
        y = trace.y
        if self._smooth_sigma > 0:
            y = gaussian_smooth(y, self._smooth_sigma)
        return trace.x, y

    def _display(self, trace: Trace, index: int) -> tuple[np.ndarray, np.ndarray]:
        """View-level processing (normalisation, mirroring, cascade offsets)."""
        x, y = self.condition(trace)
        if self._normalise and y.size:
            peak = float(np.max(np.abs(y)))
            if peak > 0:
                y = y / peak * 100.0
        if self._mirror and index % 2 == 1:
            y = -y
        if self._offset_x:
            x = x + index * self._offset_x
        if self._offset_y:
            y = y + index * self._offset_y / 100.0 * self._reference_height()
        return x, y

    def _reference_height(self) -> float:
        """Tallest conditioned trace, used as the unit for the Y cascade."""
        best = 0.0
        for trace in self._traces:
            _, y = self.condition(trace)
            if y.size:
                best = max(best, float(np.max(np.abs(y))))
        return best or 1.0

    def conditioned(self, key: str) -> tuple[np.ndarray, np.ndarray] | None:
        for trace in self._traces:
            if trace.key == key:
                return self.condition(trace)
        return None

    def set_normalised(self, enabled: bool) -> None:
        self._normalise = enabled
        self.plot.setLabel("left", "Intensity (%)" if enabled else self._y_label_raw())
        self.redraw()
        self.autoscale()

    def set_smoothing(self, sigma: float) -> None:
        self._smooth_sigma = max(0.0, float(sigma))
        self.redraw()

    def set_mirror(self, enabled: bool) -> None:
        self._mirror = enabled
        self.redraw()
        self.autoscale()

    def set_offsets(self, offset_x: float, offset_y: float) -> None:
        """Cascade the overlaid traces by `offset_x` in x and `offset_y` % in y."""
        self._offset_x = float(offset_x)
        self._offset_y = float(offset_y)
        self.redraw()
        self.autoscale()

    @property
    def mirrored(self) -> bool:
        return self._mirror

    # -- traces -------------------------------------------------------------- #
    def set_traces(self, traces: list[Trace]) -> None:
        self._traces = list(traces)
        self.redraw()

    def redraw(self) -> None:
        for curve in self._curves.values():
            self.plot.removeItem(curve)
        self._curves.clear()
        self.legend.clear()
        for i, trace in enumerate(self._traces):
            x, y = self._display(trace, i)
            if self._stick_mode:
                x, y = _sticks(x, y)
                item = self.plot.plot(x, y, pen=pg.mkPen(trace.colour, width=1.2),
                                      name=trace.label, connect="finite")
            else:
                item = self.plot.plot(x, y, pen=pg.mkPen(trace.colour, width=1.4),
                                      name=trace.label, antialias=True)
            self._curves[trace.key] = item
        self._refresh_overview()
        self._after_traces_changed()

    def clear_traces(self) -> None:
        self.set_traces([])

    @property
    def traces(self) -> list[Trace]:
        return list(self._traces)

    def _y_label_raw(self) -> str:
        return "Intensity"

    def _after_traces_changed(self) -> None:
        pass

    def autoscale(self) -> None:
        self.plot.enableAutoRange()
        self.plot.autoRange()

    # -- overview navigator -------------------------------------------------- #
    def set_overview_visible(self, visible: bool) -> None:
        self.overview.setVisible(visible)
        if visible:
            self._refresh_overview()
            self._main_range_changed()

    def _refresh_overview(self) -> None:
        if not self.overview.isVisible():
            return
        for item in list(self.overview.getPlotItem().listDataItems()):
            self.overview.removeItem(item)
        for i, trace in enumerate(self._traces):
            x, y = self._display(trace, i)
            if self._stick_mode:
                x, y = _sticks(x, y)
                self.overview.plot(x, y, pen=pg.mkPen(trace.colour, width=0.8),
                                   connect="finite")
            else:
                self.overview.plot(x, y, pen=pg.mkPen(trace.colour, width=0.8))
        self.overview.enableAutoRange()
        self.overview.autoRange()

    def _main_range_changed(self, *_args) -> None:
        if not self.overview.isVisible() or self._syncing_overview:
            return
        self._syncing_overview = True
        try:
            lo, hi = self.plot.getViewBox().viewRange()[0]
            self.overview_region.setRegion((lo, hi))
        finally:
            self._syncing_overview = False

    def _overview_moved(self) -> None:
        if not self.overview.isVisible() or self._syncing_overview:
            return
        self._syncing_overview = True
        try:
            lo, hi = self.overview_region.getRegion()
            self.plot.getViewBox().setXRange(lo, hi, padding=0)
        finally:
            self._syncing_overview = False

    # -- markers (mass differences / neutral losses) ------------------------- #
    def add_marker(self, x: float, snap_to_peak: bool = True) -> None:
        """
        Add a reference marker. Other peak labels then read as the distance to
        the nearest marker, which is how neutral losses and isotope spacings
        are read off a spectrum.
        """
        if snap_to_peak:
            x = self._snap_to_peak(x)
        line = pg.InfiniteLine(
            pos=x, angle=90, movable=True,
            pen=pg.mkPen(ARROW_COLOUR, width=1.2),
            label=f"{x:.4f}",
            labelOpts={"color": ARROW_COLOUR, "position": 0.95, "movable": False},
        )
        line.sigPositionChanged.connect(self._marker_moved)
        self.plot.addItem(line, ignoreBounds=True)
        self._arrows.append(line)
        self._after_traces_changed()

    def _snap_to_peak(self, x: float) -> float:
        """Move the marker onto the tallest peak near where the user clicked."""
        if not self._traces:
            return x
        px, py = self.condition(self._traces[0])
        if px.size == 0:
            return x
        span = float(px[-1] - px[0]) or 1.0
        width = span * 0.01
        window = (px >= x - width) & (px <= x + width)
        if not window.any():
            return float(px[int(np.argmin(np.abs(px - x)))])
        local = np.nonzero(window)[0]
        return float(px[local[int(np.argmax(py[local]))]])

    def _marker_moved(self, line) -> None:
        line.label.setText(f"{float(line.value()):.4f}")
        self._after_traces_changed()

    def clear_markers(self) -> None:
        for line in self._arrows:
            self.plot.removeItem(line)
        self._arrows.clear()
        self._after_traces_changed()

    @property
    def markers(self) -> list[float]:
        return [float(line.value()) for line in self._arrows]

    def set_relative_labels(self, enabled: bool) -> None:
        self._relative_labels = enabled
        self._after_traces_changed()

    def _label_for(self, x: float) -> str:
        """
        Absolute value when there is no marker or the peak sits on one;
        otherwise the signed distance to the reference marker.
        """
        markers = self.markers
        if not markers or not self._relative_labels:
            return f"{x:.4f}"
        nearest = min(markers, key=lambda m: abs(m - x))
        if abs(nearest - x) <= self.marker_snap:
            return f"{x:.4f}"
        # prefer the first marker to the right, matching how losses are read
        to_right = [m for m in markers if m >= x]
        reference = min(to_right) if to_right else max(markers)
        return f"{x - reference:+.4f}"

    # -- interaction --------------------------------------------------------- #
    def _on_drag(self, x0: float, x1: float, finished: bool) -> None:
        lo, hi = sorted((x0, x1))
        self.region.show()
        self.region.blockSignals(True)
        self.region.setRegion((lo, hi))
        self.region.blockSignals(False)
        self.sigFocused.emit()
        if hi > lo:
            if finished:
                self.sigRangeSelected.emit(lo, hi)
            else:
                self.sigRangeDragging.emit(lo, hi)

    def _region_moving(self) -> None:
        if not self.region.isVisible():
            return
        lo, hi = self.region.getRegion()
        if hi > lo:
            self.sigRangeDragging.emit(float(lo), float(hi))

    def _region_finished(self) -> None:
        lo, hi = self.region.getRegion()
        if hi > lo:
            self.sigRangeSelected.emit(float(lo), float(hi))

    def _on_click(self, event) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        self.sigFocused.emit()
        if event.double():
            self.autoscale()
            return
        point = self.viewbox.mapSceneToView(event.scenePos())
        self.sigClicked.emit(float(point.x()))

    def _on_move(self, pos) -> None:
        if not self.plot.sceneBoundingRect().contains(pos):
            self.readout.setText("")
            return
        point = self.viewbox.mapSceneToView(pos)
        self.readout.setText(self._format_readout(point.x(), point.y()))
        rect = self.viewbox.viewRect()
        self.readout.setPos(rect.left(), rect.bottom())

    def _format_readout(self, x: float, y: float) -> str:
        return f"x={x:.4f}  y={y:,.0f}"

    def mark(self, x: float | None) -> None:
        if x is None:
            self.vline.hide()
        else:
            self.vline.setPos(x)
            self.vline.show()

    def hide_region(self) -> None:
        self.region.hide()

    def selected_range(self) -> tuple[float, float] | None:
        if not self.region.isVisible():
            return None
        lo, hi = self.region.getRegion()
        return float(lo), float(hi)

    def set_legend_visible(self, visible: bool) -> None:
        self.legend.setVisible(visible)


class ChromatogramView(BasePlot):
    """Top pane: TIC, BPC and XIC over time."""

    sigBackgroundChanged = QtCore.pyqtSignal()

    marker_snap = 0.02

    def __init__(self, parent=None):
        super().__init__("Time", "min", "Intensity, cps", parent)
        self._apex_labels: list[pg.TextItem] = []
        self._peak_items: list[pg.GraphicsObject] = []
        self._show_apex = True
        self._baseline_window = 0.0

        # range used as the blank to subtract from generated spectra
        self.background = pg.LinearRegionItem(
            brush=pg.mkBrush(230, 170, 40, 55),
            hoverBrush=pg.mkBrush(230, 170, 40, 80),
            pen=pg.mkPen("#c98a10", width=1, style=QtCore.Qt.PenStyle.DashLine),
        )
        self.background.setZValue(-20)
        self.background.hide()
        self.plot.addItem(self.background, ignoreBounds=True)
        self.background.sigRegionChangeFinished.connect(self.sigBackgroundChanged)

    def _y_label_raw(self) -> str:
        return "Intensity, cps"

    def _format_readout(self, x: float, y: float) -> str:
        return f"RT {x:.3f} min    {y:,.0f}"

    # -- chromatogram-specific processing ------------------------------------ #
    def condition(self, trace: Trace) -> tuple[np.ndarray, np.ndarray]:
        y = trace.y
        if self._baseline_window > 0:
            y = subtract_baseline(trace.x, y, self._baseline_window)
        if self._smooth_sigma > 0:
            y = gaussian_smooth(y, self._smooth_sigma)
        return trace.x, y

    def set_baseline(self, window: float) -> None:
        self._baseline_window = max(0.0, float(window))
        self.redraw()
        self.autoscale()

    # -- background range ----------------------------------------------------- #
    def set_background_range(self, rt0: float, rt1: float) -> None:
        self.background.setRegion(tuple(sorted((float(rt0), float(rt1)))))
        self.background.show()
        self.sigBackgroundChanged.emit()

    def clear_background_range(self) -> None:
        self.background.hide()
        self.sigBackgroundChanged.emit()

    def background_range(self) -> tuple[float, float] | None:
        if not self.background.isVisible():
            return None
        lo, hi = self.background.getRegion()
        return float(lo), float(hi)

    # -- integrated peak shading ---------------------------------------------- #
    def set_peak_markers(self, peaks: list[ChromPeak],
                         pen_colour: str = "#2ca02c") -> None:
        for item in self._peak_items:
            self.plot.removeItem(item)
        self._peak_items.clear()
        for peak in peaks:
            band = pg.LinearRegionItem(
                values=(peak.start_rt, peak.end_rt),
                brush=pg.mkBrush(44, 160, 44, 40),
                pen=pg.mkPen(pen_colour, width=1),
                movable=False,
            )
            band.setZValue(-15)
            self.plot.addItem(band, ignoreBounds=True)
            self._peak_items.append(band)

    def clear_peak_markers(self) -> None:
        self.set_peak_markers([])

    # -- apex labels ----------------------------------------------------------- #
    def set_apex_labels(self, enabled: bool) -> None:
        self._show_apex = enabled
        self._after_traces_changed()

    def _after_traces_changed(self) -> None:
        for item in self._apex_labels:
            self.plot.removeItem(item)
        self._apex_labels.clear()
        traces = self.traces
        if not self._show_apex or len(traces) > 8:
            return
        for n, trace in enumerate(traces):
            x, y = self._display(trace, n)
            if y.size == 0 or float(np.max(np.abs(y))) <= 0:
                continue
            i = int(np.argmax(np.abs(y)))
            text = pg.TextItem(self._label_for(float(x[i])), color=trace.colour,
                               anchor=(0.5, 1.1 + 1.05 * (n % 2)))
            font = QtGui.QFont()
            font.setPointSize(8)
            text.setFont(font)
            text.setPos(float(x[i]), float(y[i]))
            self.plot.addItem(text, ignoreBounds=True)
            self._apex_labels.append(text)


class SpectrumView(BasePlot):
    """Bottom pane: mass spectrum of one scan or of an averaged range."""

    sigExtractRequested = QtCore.pyqtSignal(float, float)  # m/z range for an XIC
    sigIdentifyRequested = QtCore.pyqtSignal(float)        # send an m/z to the finder

    def __init__(self, parent=None):
        super().__init__("m/z", "", "Intensity, cps", parent)
        self._labels: list[pg.TextItem] = []
        self._n_labels = 12
        self._show_labels = True
        self._centroid = False
        self._title = ""
        self._overlay: tuple[list[tuple[float, float]], str, str] | None = None
        self._overlay_items: list[pg.GraphicsObject] = []
        self.legend.setVisible(False)  # the title already names the spectrum

    def _y_label_raw(self) -> str:
        return "Intensity, cps"

    def _format_readout(self, x: float, y: float) -> str:
        return f"m/z {x:.4f}    {y:,.0f}"

    def set_title(self, text: str) -> None:
        self._title = text
        self.plot.setTitle(text, color=theme.foreground(), size="10pt")

    @property
    def title(self) -> str:
        return self._title

    # -- centroiding ----------------------------------------------------------- #
    def condition(self, trace: Trace) -> tuple[np.ndarray, np.ndarray]:
        x, y = super().condition(trace)
        if self._centroid:
            return centroid_spectrum(x, y)
        return x, y

    def set_centroid(self, enabled: bool) -> None:
        self._centroid = enabled
        self._stick_mode = enabled
        self.redraw()
        self.autoscale()

    @property
    def centroided(self) -> bool:
        return self._centroid

    # -- labels ---------------------------------------------------------------- #
    def set_labels_enabled(self, enabled: bool) -> None:
        self._show_labels = enabled
        self._after_traces_changed()

    def set_label_count(self, n: int) -> None:
        self._n_labels = max(0, int(n))
        self._after_traces_changed()

    def peaks_of_current(self, max_peaks: int = 50) -> list[tuple[float, float]]:
        traces = self.traces
        if not traces:
            return []
        x, y = self.condition(traces[0])
        return pick_peaks(x, y, max_peaks=max_peaks, min_relative=0.005,
                          min_distance=0.03)

    # -- theoretical overlay ---------------------------------------------------- #
    def set_overlay(self, peaks: list[tuple[float, float]], label: str = "",
                    colour: str = "#7a3fbf") -> None:
        """
        Draw a theoretical isotope pattern over the measured spectrum, scaled to
        its base peak so the two can be compared by eye.
        """
        self._overlay = (list(peaks), label, colour) if peaks else None
        self._draw_overlay()

    def clear_overlay(self) -> None:
        self._overlay = None
        self._draw_overlay()

    @property
    def has_overlay(self) -> bool:
        return self._overlay is not None

    def _draw_overlay(self) -> None:
        for item in self._overlay_items:
            self.plot.removeItem(item)
        self._overlay_items.clear()
        if self._overlay is None:
            return
        peaks, label, colour = self._overlay
        scale = self._overlay_scale(peaks)
        xs, ys = [], []
        for mz, abundance in peaks:
            xs.extend([mz, mz, np.nan])
            ys.extend([0.0, abundance * scale, np.nan])
        curve = self.plot.plot(
            np.array(xs), np.array(ys), connect="finite",
            pen=pg.mkPen(colour, width=1.6, style=QtCore.Qt.PenStyle.DashLine),
        )
        curve.setZValue(-5)
        self._overlay_items.append(curve)
        if label:
            text = pg.TextItem(label, color=colour, anchor=(0, 0))
            font = QtGui.QFont()
            font.setPointSize(9)
            text.setFont(font)
            rect = self.viewbox.viewRect()
            text.setPos(rect.left(), rect.top())
            self.plot.addItem(text, ignoreBounds=True)
            self._overlay_items.append(text)

    def _overlay_scale(self, peaks: list[tuple[float, float]],
                       tolerance: float = 0.02) -> float:
        """
        Height for the theoretical pattern.

        It is anchored on the measured monoisotopic peak, not on the base peak
        of the spectrum: the ion being identified is often a minor one, and
        scaling to the tallest peak in the scan would either bury the overlay
        or make it tower over the data, in both cases making the satellite
        heights impossible to compare by eye.
        """
        traces = self.traces
        if not traces or not peaks:
            return 1.0
        x, y = self.condition(traces[0])
        if y.size == 0:
            return 1.0
        if self._normalise:
            peak = float(np.max(np.abs(y)))
            y = y / peak * 100.0 if peak > 0 else y
        target = peaks[0][0]
        window = (x >= target - tolerance) & (x <= target + tolerance)
        if window.any() and float(y[window].max()) > 0:
            return float(y[window].max()) / max(peaks[0][1], 1e-12)
        return float(np.max(y))

    def _after_traces_changed(self) -> None:
        self._draw_overlay()
        for item in self._labels:
            self.plot.removeItem(item)
        self._labels.clear()
        if not self._show_labels or self._n_labels == 0:
            return
        for n, trace in enumerate(self.traces):
            x, y = self._display(trace, n)
            for mz, intensity in pick_peaks(x, np.abs(y),
                                            max_peaks=self._n_labels,
                                            min_relative=0.02, min_distance=0.05):
                below = self._mirror and n % 2 == 1
                sign = -1.0 if below else 1.0
                text = pg.TextItem(self._label_for(mz), color=theme.foreground(),
                                   anchor=(0.5, 0.0 if below else 1.0))
                font = QtGui.QFont()
                font.setPointSize(8)
                text.setFont(font)
                text.setPos(mz, intensity * sign)
                self.plot.addItem(text, ignoreBounds=True)
                self._labels.append(text)

    def contextMenuEvent(self, event):  # noqa: N802 (Qt API)
        selection = self.selected_range()
        menu = QtWidgets.QMenu(self)
        local = self.plot.mapFromGlobal(event.globalPos())
        position = float(self.viewbox.mapSceneToView(self.plot.mapToScene(local)).x())

        extract = menu.addAction("Extract XIC from selection")
        extract.setEnabled(selection is not None)
        identify = menu.addAction("Find formula for this peak")
        menu.addSeparator()
        add_marker = menu.addAction("Add marker here")
        clear_markers = menu.addAction("Clear markers")
        clear_markers.setEnabled(bool(self._arrows))
        clear_overlay = menu.addAction("Clear theoretical overlay")
        clear_overlay.setEnabled(self.has_overlay)

        chosen = menu.exec(event.globalPos())
        if chosen is extract and selection:
            self.sigExtractRequested.emit(*selection)
        elif chosen is identify:
            self.sigIdentifyRequested.emit(self._snap_to_peak(position))
        elif chosen is add_marker:
            self.add_marker(position)
        elif chosen is clear_markers:
            self.clear_markers()
        elif chosen is clear_overlay:
            self.clear_overlay()
