"""
Plot colours taken from the application palette.

The widgets follow the system light or dark setting on their own; the plots do
not, because pyqtgraph is told its colours explicitly. Deriving them from the
palette keeps a white chromatogram from being pasted into a dark window.
"""

from __future__ import annotations

import pyqtgraph as pg
from PyQt6 import QtGui, QtWidgets


def is_dark() -> bool:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return False
    window = app.palette().color(QtGui.QPalette.ColorRole.Window)
    return window.lightness() < 128


def background() -> str:
    return "#1e1e1e" if is_dark() else "w"


def foreground() -> str:
    return "#dddddd" if is_dark() else "#222222"


def axis() -> str:
    return "#777777" if is_dark() else "#444444"


def faint_axis() -> str:
    return "#555555" if is_dark() else "#bbbbbb"


def muted() -> str:
    return "#999999" if is_dark() else "#666666"


def legend_brush():
    return (pg.mkBrush(30, 30, 30, 205) if is_dark()
            else pg.mkBrush(255, 255, 255, 205))


def legend_pen():
    return pg.mkPen("#555" if is_dark() else "#ccc")


def apply_defaults() -> None:
    """Set pyqtgraph's global colours; call once the application exists."""
    pg.setConfigOptions(antialias=True, background=background(),
                        foreground=foreground())


def style_axes(plot, faint: bool = False, tick_points: int | None = None) -> None:
    """Give a plot widget the palette's axis and label colours."""
    pen = pg.mkPen(faint_axis() if faint else axis())
    text = pg.mkPen(muted() if faint else foreground())
    for name in ("bottom", "left"):
        item = plot.getAxis(name)
        item.setPen(pen)
        item.setTextPen(text)
        if tick_points is not None:
            # a QFont built from an empty family name crashes Qt when the axis
            # measures its tick labels, so start from the default font
            font = QtGui.QFont()
            font.setPointSize(tick_points)
            item.setStyle(tickFont=font)
