"""Paineis de cromatograma e de espectro."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from ..processing import ChromPeak, gaussian_smooth, pick_peaks, subtract_baseline

PALETTE = [
    "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
    "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f",
]


def colour(i: int) -> str:
    return PALETTE[i % len(PALETTE)]


@dataclass
class Trace:
    """Uma curva desenhada em um dos paineis."""

    key: str
    label: str
    x: np.ndarray
    y: np.ndarray
    colour: str
    source: object | None = None  # Channel de origem, quando houver


class _DragViewBox(pg.ViewBox):
    """ViewBox que emite arraste horizontal como selecao de faixa."""

    sigRangeDrag = QtCore.pyqtSignal(float, float, bool)  # x0, x1, terminou

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
    """Base comum: grade, crosshair, legenda, processamento e selecao de faixa."""

    sigRangeSelected = QtCore.pyqtSignal(float, float)  # selecao concluida
    sigClicked = QtCore.pyqtSignal(float)               # clique simples em x

    def __init__(self, x_label: str, x_units: str, y_label: str, parent=None):
        super().__init__(parent)
        self._traces: list[Trace] = []
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._normalise = False
        self._smooth_sigma = 0.0
        self._mirror = False

        self.viewbox = _DragViewBox()
        self.plot = pg.PlotWidget(viewBox=self.viewbox, background="w")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", x_label, units=x_units or None)
        self.plot.setLabel("left", y_label)
        for axis in ("bottom", "left"):
            self.plot.getAxis(axis).setPen(pg.mkPen("#444"))
            self.plot.getAxis(axis).setTextPen(pg.mkPen("#222"))
        self.legend = self.plot.addLegend(
            offset=(-10, 10), labelTextColor="#222",
            brush=pg.mkBrush(255, 255, 255, 205),
            pen=pg.mkPen("#ccc"), verSpacing=-4,
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

        self.vline = pg.InfiniteLine(
            angle=90, movable=False,
            pen=pg.mkPen("#999", style=QtCore.Qt.PenStyle.DashLine),
        )
        self.vline.hide()
        self.plot.addItem(self.vline, ignoreBounds=True)

        self.readout = pg.TextItem(color="#333", anchor=(0, 1))
        self.readout.setZValue(100)
        self.plot.addItem(self.readout, ignoreBounds=True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

        self.viewbox.sigRangeDrag.connect(self._on_drag)
        self.plot.scene().sigMouseMoved.connect(self._on_move)
        self.plot.scene().sigMouseClicked.connect(self._on_click)

    # -- modo do mouse ------------------------------------------------------ #
    def set_select_mode(self, enabled: bool) -> None:
        self.viewbox.select_mode = enabled
        self.plot.setCursor(
            QtCore.Qt.CursorShape.SplitHCursor if enabled
            else QtCore.Qt.CursorShape.CrossCursor
        )

    # -- processamento ------------------------------------------------------ #
    def condition(self, trace: Trace) -> np.ndarray:
        """
        Processamento no nivel dos dados (linha de base, suavizacao). E o que a
        integracao usa, para que area e altura correspondam ao que esta na tela.
        """
        y = trace.y
        if self._smooth_sigma > 0:
            y = gaussian_smooth(y, self._smooth_sigma)
        return y

    def _display(self, trace: Trace, index: int) -> np.ndarray:
        """Processamento no nivel da exibicao (normalizacao, espelhamento)."""
        y = self.condition(trace)
        if self._normalise and y.size:
            peak = float(np.max(np.abs(y)))
            if peak > 0:
                y = y / peak * 100.0
        if self._mirror and index % 2 == 1:
            y = -y
        return y

    def conditioned(self, key: str) -> tuple[np.ndarray, np.ndarray] | None:
        for trace in self._traces:
            if trace.key == key:
                return trace.x, self.condition(trace)
        return None

    def set_normalised(self, enabled: bool) -> None:
        self._normalise = enabled
        self.plot.setLabel("left", "Intensidade (%)" if enabled else self._y_label_raw())
        self.redraw()
        self.autoscale()

    def set_smoothing(self, sigma: float) -> None:
        self._smooth_sigma = max(0.0, float(sigma))
        self.redraw()

    def set_mirror(self, enabled: bool) -> None:
        self._mirror = enabled
        self.redraw()
        self.autoscale()

    @property
    def mirrored(self) -> bool:
        return self._mirror

    # -- curvas ------------------------------------------------------------- #
    def set_traces(self, traces: list[Trace]) -> None:
        self._traces = list(traces)
        self.redraw()

    def redraw(self) -> None:
        for curve in self._curves.values():
            self.plot.removeItem(curve)
        self._curves.clear()
        self.legend.clear()
        for i, trace in enumerate(self._traces):
            curve = self.plot.plot(
                trace.x, self._display(trace, i),
                pen=pg.mkPen(trace.colour, width=1.4),
                name=trace.label, antialias=True,
            )
            self._curves[trace.key] = curve
        self._after_traces_changed()

    def clear_traces(self) -> None:
        self.set_traces([])

    @property
    def traces(self) -> list[Trace]:
        return list(self._traces)

    def _y_label_raw(self) -> str:
        return "Intensidade"

    def _after_traces_changed(self) -> None:
        pass

    def autoscale(self) -> None:
        self.plot.enableAutoRange()
        self.plot.autoRange()

    # -- interacao ---------------------------------------------------------- #
    def _on_drag(self, x0: float, x1: float, finished: bool) -> None:
        lo, hi = sorted((x0, x1))
        self.region.show()
        self.region.blockSignals(True)
        self.region.setRegion((lo, hi))
        self.region.blockSignals(False)
        if finished and hi > lo:
            self.sigRangeSelected.emit(lo, hi)

    def _region_finished(self) -> None:
        lo, hi = self.region.getRegion()
        if hi > lo:
            self.sigRangeSelected.emit(float(lo), float(hi))

    def _on_click(self, event) -> None:
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
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
    """Painel superior: TIC, BPC e XIC ao longo do tempo."""

    sigBackgroundChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Tempo", "min", "Intensidade, cps", parent)
        self._apex_labels: list[pg.TextItem] = []
        self._peak_items: list[pg.GraphicsObject] = []
        self._show_apex = True
        self._baseline_window = 0.0

        # regiao usada como branco para subtrair dos espectros gerados
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
        return "Intensidade, cps"

    def _format_readout(self, x: float, y: float) -> str:
        return f"RT {x:.3f} min    {y:,.0f}"

    # -- processamento especifico de cromatograma --------------------------- #
    def condition(self, trace: Trace) -> np.ndarray:
        y = trace.y
        if self._baseline_window > 0:
            y = subtract_baseline(trace.x, y, self._baseline_window)
        if self._smooth_sigma > 0:
            y = gaussian_smooth(y, self._smooth_sigma)
        return y

    def set_baseline(self, window: float) -> None:
        self._baseline_window = max(0.0, float(window))
        self.redraw()
        self.autoscale()

    # -- regiao de background ----------------------------------------------- #
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

    # -- marcacao de picos integrados --------------------------------------- #
    def set_peak_markers(self, peaks: list[ChromPeak], pen_colour: str = "#2ca02c") -> None:
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

    # -- rotulos de apice ---------------------------------------------------- #
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
            y = self._display(trace, n)
            if y.size == 0 or float(np.max(np.abs(y))) <= 0:
                continue
            i = int(np.argmax(np.abs(y)))
            text = pg.TextItem(f"{trace.x[i]:.2f}", color=trace.colour,
                               anchor=(0.5, 1.1 + 1.05 * (n % 2)))
            font = QtGui.QFont()
            font.setPointSize(8)
            text.setFont(font)
            text.setPos(float(trace.x[i]), float(y[i]))
            self.plot.addItem(text, ignoreBounds=True)
            self._apex_labels.append(text)


class SpectrumView(BasePlot):
    """Painel inferior: espectro de massas de um scan ou de uma faixa media."""

    sigExtractRequested = QtCore.pyqtSignal(float, float)  # faixa de m/z p/ XIC

    def __init__(self, parent=None):
        super().__init__("m/z", "", "Intensidade, cps", parent)
        self._labels: list[pg.TextItem] = []
        self._n_labels = 12
        self._show_labels = True
        self._title = ""
        self.legend.setVisible(False)  # o titulo ja identifica o espectro

    def _y_label_raw(self) -> str:
        return "Intensidade, cps"

    def _format_readout(self, x: float, y: float) -> str:
        return f"m/z {x:.4f}    {y:,.0f}"

    def set_title(self, text: str) -> None:
        self._title = text
        self.plot.setTitle(text, color="#222", size="10pt")

    @property
    def title(self) -> str:
        return self._title

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
        t = traces[0]
        return pick_peaks(t.x, self.condition(t), max_peaks=max_peaks,
                          min_relative=0.005, min_distance=0.03)

    def _after_traces_changed(self) -> None:
        for item in self._labels:
            self.plot.removeItem(item)
        self._labels.clear()
        if not self._show_labels or self._n_labels == 0:
            return
        for n, trace in enumerate(self.traces):
            y = self._display(trace, n)
            for mz, intensity in pick_peaks(trace.x, np.abs(y),
                                            max_peaks=self._n_labels,
                                            min_relative=0.02, min_distance=0.05):
                sign = -1.0 if (self._mirror and n % 2 == 1) else 1.0
                text = pg.TextItem(f"{mz:.4f}", color="#333",
                                   anchor=(0.5, 1.0 if sign > 0 else 0.0))
                font = QtGui.QFont()
                font.setPointSize(8)
                text.setFont(font)
                text.setPos(mz, intensity * sign)
                self.plot.addItem(text, ignoreBounds=True)
                self._labels.append(text)

    def contextMenuEvent(self, event):  # noqa: N802 (API Qt)
        selection = self.selected_range()
        menu = QtWidgets.QMenu(self)
        action = menu.addAction("Extrair XIC da faixa selecionada")
        action.setEnabled(selection is not None)
        chosen = menu.exec(event.globalPos())
        if chosen is action and selection:
            self.sigExtractRequested.emit(*selection)
