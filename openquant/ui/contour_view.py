"""
The contour: retention time across, m/z up, intensity as colour.

The picture exists to show a neighbourhood — an interference half a dalton
from a target, a second species under the same peak, a contaminant ridge down
the whole run. So the parts that matter are the ones that decide what is
visible: the intensity scale, because chromatographic data spans four or five
decades and a linear ramp shows the base peak and nothing else, and the upper
level, because one saturated scan otherwise sets the scale for the entire
surface.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

from . import theme
from ..contour import Contour

#: how the intensities are compressed before they become colour. Square root
#: is the default because it lifts the minor ions into view without the
#: flattening that makes a log plot of chromatographic data look uniformly
#: grey; linear is there for the rare case of wanting the base peak alone.
LINEAR, SQRT, LOG = "linear", "square root", "logarithmic"
SCALES = (SQRT, LOG, LINEAR)

#: the intensity that becomes the top of the colour scale. Not the maximum:
#: a single saturated or spiking scan would then set the scale for everything
#: else and leave the rest of the surface black.
TOP_PERCENTILE = 99.7

MAPS = ("inferno", "viridis", "magma", "turbo", "CET-L9")


class ContourView(QtWidgets.QWidget):
    """A channel's scans as a surface, with a readout and a picker."""

    #: a point in the surface — retention time, m/z
    sigPointPicked = QtCore.pyqtSignal(float, float)
    #: the visible rectangle — rt low, rt high, m/z low, m/z high
    sigRegionPicked = QtCore.pyqtSignal(float, float, float, float)
    sigRebuildRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._contour = Contour()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Intensity"))
        self.scale = QtWidgets.QComboBox()
        self.scale.addItems(list(SCALES))
        self.scale.setToolTip(
            "Chromatographic intensity spans four or five decades. On a "
            "linear scale everything but the base peak is black")
        bar.addWidget(self.scale)
        bar.addWidget(QtWidgets.QLabel("Colours"))
        self.palette = QtWidgets.QComboBox()
        self.palette.addItems(list(MAPS))
        bar.addWidget(self.palette)
        self.btn_extract = QtWidgets.QPushButton("Extract this view")
        self.btn_extract.setToolTip(
            "Take the chromatogram and spectrum of the rectangle on screen: "
            "zoom to what you want, then press this")
        bar.addWidget(self.btn_extract)
        self.btn_rebuild = QtWidgets.QPushButton("Rebuild")
        self.btn_rebuild.setToolTip(
            "Read the scans again over the times and masses now on screen, "
            "so a region gets the full grid instead of a magnified one")
        bar.addWidget(self.btn_rebuild)
        bar.addStretch(1)
        self.readout = QtWidgets.QLabel("")
        self.readout.setProperty("role", "caption")
        bar.addWidget(self.readout)
        layout.addLayout(bar)

        self.plot = pg.PlotWidget(background=theme.background())
        self.plot.setLabel("bottom", "Retention time", units="min")
        self.plot.setLabel("left", "m/z")
        theme.style_axes(self.plot)
        self.image = pg.ImageItem()
        self.plot.addItem(self.image)
        self.plot.setMenuEnabled(False)

        pen = pg.mkPen(theme.muted(), width=1,
                       style=QtCore.Qt.PenStyle.DashLine)
        self._vline = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._hline = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        for line in (self._vline, self._hline):
            line.setVisible(False)
            line.setZValue(10)
            self.plot.addItem(line, ignoreBounds=True)

        layout.addWidget(self.plot, 1)

        self.status = QtWidgets.QLabel("No contour yet.")
        self.status.setProperty("role", "caption")
        layout.addWidget(self.status)

        self.scale.currentTextChanged.connect(self._redraw)
        self.palette.currentTextChanged.connect(self._redraw)
        self.btn_rebuild.clicked.connect(self.sigRebuildRequested)
        self.btn_extract.clicked.connect(self._emit_region)
        self.plot.scene().sigMouseMoved.connect(self._on_moved)
        self.plot.scene().sigMouseClicked.connect(self._on_clicked)

    # -- content ------------------------------------------------------------- #
    def set_contour(self, contour: Contour, title: str = "") -> None:
        self._contour = contour
        if contour.is_empty:
            self.image.clear()
            self.status.setText(contour.note or "Nothing to draw.")
            return
        self._redraw()
        rt_lo, rt_hi = contour.rt_range
        mz_lo, mz_hi = contour.mz_range
        said = [f"{contour.scans:,} scans", f"{rt_lo:.2f}–{rt_hi:.2f} min",
                f"m/z {mz_lo:.1f}–{mz_hi:.1f}",
                f"{contour.intensity.shape[0]} × {contour.intensity.shape[1]} cells"]
        if contour.note:
            said.append(contour.note)
        self.status.setText(" · ".join(([title] if title else []) + said))
        self.plot.setXRange(rt_lo, rt_hi, padding=0)
        self.plot.setYRange(mz_lo, mz_hi, padding=0)

    def contour(self) -> Contour:
        return self._contour

    def view_ranges(self) -> tuple[float, float, float, float]:
        (x0, x1), (y0, y1) = self.plot.viewRange()
        return float(x0), float(x1), float(y0), float(y1)

    # -- drawing ------------------------------------------------------------- #
    def _redraw(self, *_args) -> None:
        contour = self._contour
        if contour.is_empty:
            return
        values = np.clip(contour.intensity, 0.0, None)
        mode = self.scale.currentText()
        if mode == SQRT:
            shown = np.sqrt(values)
        elif mode == LOG:
            shown = np.log1p(values)
        else:
            shown = values

        above = shown[shown > 0]
        top = (float(np.percentile(above, TOP_PERCENTILE)) if above.size
               else 1.0)
        if top <= 0:
            top = float(shown.max()) or 1.0

        self.image.setImage(shown, autoLevels=False, levels=(0.0, top))
        self.image.setColorMap(pg.colormap.get(self.palette.currentText()))
        left, bottom, width, height = contour.rect
        self.image.setRect(QtCore.QRectF(left, bottom, width, height))

    # -- interaction ---------------------------------------------------------- #
    def _point_at(self, position) -> tuple[float, float] | None:
        if self._contour.is_empty:
            return None
        if not self.plot.sceneBoundingRect().contains(position):
            return None
        point = self.plot.getViewBox().mapSceneToView(position)
        return float(point.x()), float(point.y())

    def _on_moved(self, position) -> None:
        found = self._point_at(position)
        if found is None:
            self._vline.setVisible(False)
            self._hline.setVisible(False)
            self.readout.setText("")
            return
        rt, mz = found
        self._vline.setPos(rt)
        self._hline.setPos(mz)
        self._vline.setVisible(True)
        self._hline.setVisible(True)
        intensity = self._contour.at(rt, mz)
        self.readout.setText(
            f"{rt:.3f} min · m/z {mz:.4f}"
            + (f" · {intensity:,.0f}" if intensity is not None else ""))

    def _on_clicked(self, event) -> None:
        found = self._point_at(event.scenePos())
        if found is not None:
            self.sigPointPicked.emit(*found)

    def _emit_region(self) -> None:
        if not self._contour.is_empty:
            self.sigRegionPicked.emit(*self.view_ranges())
