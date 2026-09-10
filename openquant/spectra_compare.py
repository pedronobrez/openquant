"""
Two or more spectra held side by side, off the screen.

The Explorer can pin a spectrum so the next one draws over it, and Mirror
turns one pinned spectrum and the live one into a head-to-tail plot. That
comparison is the whole of a qualitative identification, and until now it
only existed as pixels in a window: it could not be printed, mailed, or put
in a report.

What is held here is the data, not a picture: the traces as they were
conditioned for the screen, their labels, and the two switches that decide
how they are drawn. The picture is made from that on demand, by
`render_png` and `render_svg`, with a QPainter of its own rather than by
grabbing the widget — so the image is the same size and the same sharpness
whatever the window happened to be, and can be made with no window at all.

Three things about the drawing are deliberate:

* **It is always drawn for paper.** White ground, dark axes, whatever the
  application's theme is. A dark-theme trace colour is lightened for a dark
  window and would print as a pale line on white, so a colour too light to
  read on paper is darkened here — see `for_paper`.
* **A mirrored trace is labelled with its magnitude.** It is drawn
  downwards because that is how a head-to-tail comparison is read; the
  number beside it is an intensity, not a negative one.
* **Peaks are labelled from the same picker and the same budget the pane
  uses** — `labels.choose`, which gives each eighth of the mass axis a few
  labels rather than spending them all on the densest stretch — so the
  masses printed are the masses on screen. Measured on a survey scan
  against a product-ion scan: 20 labels drawn where picking by height alone
  drew 12, all 12 of them below m/z 360.
"""

from __future__ import annotations

import base64
import datetime as _dt
import math
from dataclasses import dataclass, field

import numpy as np

from . import labels
from .processing import pick_peaks

#: the drawing's logical size, in points. `render_png` multiplies it by the
#: scale it is given; everything below is expressed in these units, so the
#: image comes out the same shape at any scale.
DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 520

#: PNG for print is rendered at twice the logical size. Every coordinate,
#: pen and font goes through the painter's transform, so this is a genuine
#: re-render and not an enlargement of a small one — measured in
#: `tests/test_spectra_compare.py`.
PRINT_SCALE = 2.0

#: the most labels one trace may carry, how far down its own base peak a
#: peak has to be before it is not worth one, and how many maxima are
#: offered to the region budget. The same rule the spectrum pane uses for
#: its own labels — `labels.choose` gives each eighth of the mass axis a
#: budget of three, and the collision rule below drops whatever will not
#: fit. Six labels picked by height alone put every one of them inside the
#: first eighth of a real survey scan.
LABEL_PEAKS = labels.LABEL_REGIONS * labels.LABEL_BUDGET
LABEL_MIN_RELATIVE = labels.LABEL_MIN_RELATIVE
#: maxima kept as candidates before the budget chooses among them
LABEL_POOL = 200
#: two maxima closer than this in Da are one peak
MIN_DISTANCE = 0.05

#: a peak counts as the same peak in two traces within this much
SHARED_PPM = 10.0
#: peaks per trace considered when looking for the shared ones, and how many
#: of the shared ones are worth printing
SHARED_PER_TRACE = 40
SHARED_MOST = 20

#: the contrast a line has to have against the white page. Three to one is
#: what WCAG asks of a graphic that carries meaning, and it is a measured
#: rule rather than an opinion about a colour: the dark theme's accent,
#: #6f9be0, is 2.8:1 on white and is darkened; the light theme's #234b8c is
#: 9.4:1 and is left alone.
MIN_CONTRAST = 3.0


# --------------------------------------------------------------------------- #
# what is held
# --------------------------------------------------------------------------- #
@dataclass
class SpectrumTrace:
    """One spectrum in the comparison, as it was drawn."""

    label: str
    mz: np.ndarray
    intensity: np.ndarray
    colour: str = "#234b8c"

    @property
    def base_peak(self) -> tuple[float, float] | None:
        """(m/z, intensity) of the tallest point, or None for an empty trace."""
        if self.mz.size == 0 or self.intensity.size == 0:
            return None
        index = int(np.argmax(self.intensity))
        return float(self.mz[index]), float(self.intensity[index])

    @property
    def mz_range(self) -> tuple[float, float] | None:
        if self.mz.size == 0:
            return None
        return float(self.mz.min()), float(self.mz.max())


@dataclass
class SpectrumComparison:
    """The spectra the Explorer had on screen, and how it was drawing them."""

    traces: list[SpectrumTrace] = field(default_factory=list)
    title: str = ""
    normalise: bool = False
    mirror: bool = False
    centroid: bool = False
    taken: _dt.datetime = field(default_factory=_dt.datetime.now)

    @property
    def stands(self) -> bool:
        """A comparison needs something to compare with: at least two traces
        with points in them."""
        return len([t for t in self.traces if t.mz.size]) >= 2

    def peaks(self, trace: SpectrumTrace, most: int = LABEL_PEAKS,
              min_relative: float = LABEL_MIN_RELATIVE
              ) -> list[tuple[float, float]]:
        """
        The strongest peaks of one trace, strongest first.

        Centroiding a trace that is already centroids averages a stick with
        its neighbours and moves the mass, so it is asked for only when the
        pane was not in centroid mode — the same rule as the pane's own
        labels.
        """
        return pick_peaks(trace.mz, np.abs(trace.intensity), max_peaks=most,
                          min_relative=min_relative,
                          min_distance=MIN_DISTANCE,
                          centroid=not self.centroid)

    def label_peaks(self, trace: SpectrumTrace, low: float, high: float,
                    most: int = LABEL_PEAKS) -> list[tuple[float, float]]:
        """
        The peaks of one trace worth labelling on a drawing of `low` to
        `high`, in the order they may claim room.

        The mass axis is cut into `labels.LABEL_REGIONS` equal windows and
        each may claim `labels.LABEL_BUDGET` labels; the tallest peak of
        every window asks before any window asks for a second, so a dense
        stretch cannot spend the whole allowance. Whether a label is
        actually drawn is still the caller's collision rule.
        """
        pool = self.peaks(trace, most=LABEL_POOL, min_relative=0.002)
        return labels.choose(pool, low, high, most=most,
                             min_relative=LABEL_MIN_RELATIVE)

    def summary(self) -> str:
        names = ", ".join(t.label for t in self.traces if t.label)
        how = []
        if self.normalise:
            how.append("normalised to each base peak")
        if self.mirror and len(self.traces) > 1:
            how.append("every other one drawn downwards")
        if self.centroid:
            how.append("centroids")
        tail = f" ({'; '.join(how)})" if how else ""
        return f"{len(self.traces)} spectra: {names}{tail}"


def from_traces(traces, title: str = "", normalise: bool = False,
                mirror: bool = False, centroid: bool = False,
                condition=None) -> SpectrumComparison:
    """
    Build a comparison from the pane's traces.

    Anything with `label`, `x`, `y` and `colour` will do: this module knows
    nothing about the widget, which is what lets the report be built with no
    window. `condition` is the pane's own processing — smoothing, centroiding,
    the profile zeros put back — so that what is kept is what was on screen
    rather than what came off the disk.
    """
    kept: list[SpectrumTrace] = []
    for trace in traces:
        if condition is not None:
            x, y = condition(trace)
        else:
            x, y = trace.x, trace.y
        kept.append(SpectrumTrace(
            label=str(getattr(trace, "label", "") or ""),
            mz=np.asarray(x, dtype=np.float64).copy(),
            intensity=np.asarray(y, dtype=np.float64).copy(),
            colour=str(getattr(trace, "colour", "#234b8c"))))
    return SpectrumComparison(traces=kept, title=title, normalise=normalise,
                              mirror=mirror, centroid=centroid)


# --------------------------------------------------------------------------- #
# what the two spectra have in common
# --------------------------------------------------------------------------- #
@dataclass
class SharedPeak:
    """One mass found in every trace, with its height in each."""

    mz: float
    spread_ppm: float
    heights: list[float]          # per trace, per cent of that trace's base peak
    masses: list[float]           # per trace, as measured


def shared_peaks(comparison: SpectrumComparison,
                 tolerance_ppm: float = SHARED_PPM,
                 per_trace: int = SHARED_PER_TRACE,
                 most: int = SHARED_MOST) -> list[SharedPeak]:
    """
    The masses every trace holds, within `tolerance_ppm`, strongest first.

    Shared means shared by all of them, not by two of several: a peak in
    three spectra out of four is a difference, and the point of the table is
    what the spectra agree on. Heights are given as a per cent of each
    trace's own base peak whether or not the pane was normalising, because
    that is the only way two spectra of different sizes can be compared in a
    table.
    """
    traces = [t for t in comparison.traces if t.mz.size]
    if len(traces) < 2:
        return []
    picked = []
    for trace in traces:
        peaks = comparison.peaks(trace, most=per_trace, min_relative=0.01)
        base = max((h for _m, h in peaks), default=0.0) or 1.0
        picked.append(sorted(((m, h / base * 100.0) for m, h in peaks)))

    found: list[SharedPeak] = []
    for anchor, height in picked[0]:
        masses, heights = [anchor], [height]
        for other in picked[1:]:
            best, gap = None, None
            for m, h in other:
                delta = abs(m - anchor) / anchor * 1e6
                if delta <= tolerance_ppm and (gap is None or delta < gap):
                    best, gap = (m, h), delta
            if best is None:
                break
            masses.append(best[0])
            heights.append(best[1])
        if len(masses) != len(picked):
            continue
        mean = float(np.mean(masses))
        spread = (max(masses) - min(masses)) / mean * 1e6 if mean else 0.0
        found.append(SharedPeak(mean, spread, heights, masses))
    found.sort(key=lambda p: -sum(p.heights))
    return found[:most]


# --------------------------------------------------------------------------- #
# colour
# --------------------------------------------------------------------------- #
def luminance(colour: str) -> float:
    """Relative luminance of a colour, 0 for black and 1 for white."""
    from PyQt6 import QtGui

    rgb = QtGui.QColor(colour)

    def channel(value: float) -> float:
        value /= 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return (0.2126 * channel(rgb.red()) + 0.7152 * channel(rgb.green())
            + 0.0722 * channel(rgb.blue()))


def contrast_on_white(colour: str) -> float:
    """Contrast ratio of a colour against a white page."""
    return 1.05 / (luminance(colour) + 0.05)


def for_paper(colour: str, minimum: float = MIN_CONTRAST):
    """
    The same hue, dark enough to read as a thin line on white.

    The plot colours follow the interface theme, and the dark theme lightens
    them so they carry on a dark window. Printed as they are, the dark
    theme's accent (#6f9be0) is a 2.8:1 line on a white page. Value is taken
    down until the contrast clears the minimum; the hue and the saturation
    are left alone, so a reader who knows a trace by its colour on screen
    still knows it on paper.
    """
    from PyQt6 import QtGui

    result = QtGui.QColor(colour)
    for _ in range(16):
        if contrast_on_white(result.name()) >= minimum:
            break
        h, s, v, a = result.getHsv()
        stepped = max(int(v * 0.9), 0)
        if stepped == v:
            break
        result = QtGui.QColor.fromHsv(h, s, stepped, a)
    return result


# --------------------------------------------------------------------------- #
# the drawing
# --------------------------------------------------------------------------- #
#: the space kept round the plot, in logical points: left for the intensity
#: axis and its ticks, bottom for the m/z axis, top for the title and legend.
MARGIN_LEFT = 68.0
MARGIN_RIGHT = 16.0
MARGIN_BOTTOM = 42.0
MARGIN_TOP = 14.0
TITLE_HEIGHT = 20.0
LEGEND_ROW = 16.0


def _nice_ticks(lo: float, hi: float, count: int = 6) -> list[float]:
    """Round numbers covering [lo, hi], about `count` of them."""
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return [lo]
    raw = (hi - lo) / max(count, 1)
    magnitude = 10.0 ** math.floor(math.log10(raw))
    for step in (1.0, 2.0, 2.5, 5.0, 10.0):
        if raw <= step * magnitude:
            step *= magnitude
            break
    else:                                       # pragma: no cover - unreachable
        step = magnitude * 10.0
    first = math.ceil(lo / step) * step
    ticks, value = [], first
    while value <= hi + step * 1e-9:
        ticks.append(round(value, 10))
        value += step
    return ticks


def _tick_labels(ticks: list[float]) -> list[str]:
    """
    Label a set of ticks the same way as each other.

    Formatting each value on its own gives an axis reading 100, 50.0, 0,
    50.0, 100 — which looks like two different scales. The number of
    decimals comes from the step, so every label on the axis has the same
    shape. A mirrored trace is drawn downwards but its intensity is not
    negative, so the magnitude is what is printed.
    """
    if not ticks:
        return []
    steps = [abs(b - a) for a, b in zip(ticks, ticks[1:])]
    step = min(steps) if steps else abs(ticks[0]) or 1.0
    biggest = max(abs(v) for v in ticks) or 1.0
    if biggest >= 1e5:
        return [f"{abs(v):.1e}".replace("e+0", "e").replace("e+", "e")
                for v in ticks]
    decimals = 0 if step >= 1 else min(4, int(math.ceil(-math.log10(step))) + 1)
    return [f"{abs(v):,.{decimals}f}" for v in ticks]


def _decimate(x: np.ndarray, y: np.ndarray, x0: float, x1: float,
              columns: int) -> tuple[np.ndarray, np.ndarray]:
    """
    A profile trace reduced to what a column of pixels can show.

    A TOF profile spectrum is a hundred thousand points and the plot is a
    thousand columns wide, so all but a hundredth of them land on a pixel
    that already has ink. Taking every hundredth point would lose a peak one
    point wide — the same trap as the contour view's rows — so each column
    keeps its lowest and its highest point, in the order they were measured.
    The picture is identical and the SVG is a hundred times smaller.
    """
    if x.size <= columns * 2 or x1 <= x0 or columns < 1:
        return x, y
    column = np.clip(((x - x0) / (x1 - x0) * columns).astype(np.int64),
                     0, columns - 1)
    edges = np.searchsorted(column, np.arange(columns + 1))
    keep: list[int] = []
    for start, stop in zip(edges, edges[1:]):
        if stop <= start:
            continue
        block = y[start:stop]
        lo = start + int(block.argmin())
        hi = start + int(block.argmax())
        keep.extend(sorted({start, lo, hi, stop - 1}))
    index = np.array(sorted(set(keep)), dtype=np.int64)
    return x[index], y[index]


def _series(comparison: SpectrumComparison):
    """Each trace as it is to be drawn: heights and which way up."""
    out = []
    for index, trace in enumerate(comparison.traces):
        y = np.abs(np.asarray(trace.intensity, dtype=np.float64))
        if comparison.normalise and y.size:
            top = float(y.max())
            y = y / top * 100.0 if top > 0 else y
        sign = -1.0 if (comparison.mirror and index % 2 == 1) else 1.0
        out.append((trace, y, sign))
    return out


def paint(comparison: SpectrumComparison, painter, width: float,
          height: float) -> None:
    """
    Draw the comparison into `painter`, in logical points.

    The caller has already scaled the painter, so nothing here knows about
    the scale: a pen of 1.4 is 1.4 points on paper whatever the image's
    pixel size is.
    """
    from PyQt6 import QtCore, QtGui

    ink = QtGui.QColor("#16181c")
    muted = QtGui.QColor("#5b6472")
    grid = QtGui.QColor("#e3e7ee")

    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
    painter.fillRect(QtCore.QRectF(0, 0, width, height), QtGui.QColor("#ffffff"))

    def font(size: float, bold: bool = False):
        f = QtGui.QFont()
        f.setFamily("Helvetica")
        f.setPixelSize(int(round(size)))
        f.setBold(bold)
        return f

    series = _series(comparison)
    drawn = [(t, y, s) for t, y, s in series if t.mz.size and y.size]

    top = MARGIN_TOP
    if comparison.title:
        painter.setFont(font(13, bold=True))
        painter.setPen(ink)
        painter.drawText(QtCore.QRectF(MARGIN_LEFT, top, width - MARGIN_LEFT
                                       - MARGIN_RIGHT, TITLE_HEIGHT),
                         int(QtCore.Qt.AlignmentFlag.AlignLeft
                             | QtCore.Qt.AlignmentFlag.AlignVCenter),
                         comparison.title)
        top += TITLE_HEIGHT

    # -- legend: one row per trace, so a long label is never elided --------- #
    painter.setFont(font(11))
    for trace, _y, sign in series:
        colour = for_paper(trace.colour)
        painter.setPen(QtGui.QPen(colour, 2.4))
        y = top + LEGEND_ROW / 2
        painter.drawLine(QtCore.QPointF(MARGIN_LEFT, y),
                         QtCore.QPointF(MARGIN_LEFT + 18, y))
        painter.setPen(ink)
        text = trace.label or "spectrum"
        if comparison.mirror and sign < 0:
            text += "  (downwards)"
        painter.drawText(QtCore.QRectF(MARGIN_LEFT + 24, top,
                                       width - MARGIN_LEFT - MARGIN_RIGHT - 24,
                                       LEGEND_ROW),
                         int(QtCore.Qt.AlignmentFlag.AlignLeft
                             | QtCore.Qt.AlignmentFlag.AlignVCenter), text)
        top += LEGEND_ROW
    top += 6

    plot = QtCore.QRectF(MARGIN_LEFT, top, width - MARGIN_LEFT - MARGIN_RIGHT,
                         height - top - MARGIN_BOTTOM)
    if plot.width() <= 10 or plot.height() <= 10 or not drawn:
        painter.setPen(muted)
        painter.setFont(font(12))
        painter.drawText(QtCore.QRectF(0, 0, width, height),
                         int(QtCore.Qt.AlignmentFlag.AlignCenter),
                         "Nothing to compare.")
        return

    x0 = min(float(t.mz.min()) for t, _y, _s in drawn)
    x1 = max(float(t.mz.max()) for t, _y, _s in drawn)
    if x1 <= x0:
        x0, x1 = x0 - 0.5, x1 + 0.5
    pad = (x1 - x0) * 0.02
    x0, x1 = x0 - pad, x1 + pad

    ymax = max(float(y.max()) for _t, y, _s in drawn) or 1.0
    down = any(s < 0 for _t, _y, s in drawn)
    ylo, yhi = (-ymax, ymax) if down else (0.0, ymax)

    def px(mz: float) -> float:
        return plot.left() + (mz - x0) / (x1 - x0) * plot.width()

    def py(value: float) -> float:
        return plot.bottom() - (value - ylo) / (yhi - ylo) * plot.height()

    # -- axes ---------------------------------------------------------------- #
    y_ticks = _nice_ticks(ylo, yhi, 5 if down else 4)
    painter.setFont(font(10))
    for value, text in zip(y_ticks, _tick_labels(y_ticks)):
        y = py(value)
        painter.setPen(QtGui.QPen(grid, 1.0))
        painter.drawLine(QtCore.QPointF(plot.left(), y),
                         QtCore.QPointF(plot.right(), y))
        painter.setPen(muted)
        painter.drawText(QtCore.QRectF(0, y - 8, MARGIN_LEFT - 6, 16),
                         int(QtCore.Qt.AlignmentFlag.AlignRight
                             | QtCore.Qt.AlignmentFlag.AlignVCenter), text)
    for value in _nice_ticks(x0, x1, 8):
        x = px(value)
        painter.setPen(muted)
        painter.drawLine(QtCore.QPointF(x, plot.bottom()),
                         QtCore.QPointF(x, plot.bottom() + 4))
        painter.drawText(QtCore.QRectF(x - 40, plot.bottom() + 5, 80, 14),
                         int(QtCore.Qt.AlignmentFlag.AlignCenter),
                         f"{value:g}")
    painter.setPen(QtGui.QPen(muted, 1.2))
    painter.drawLine(QtCore.QPointF(plot.left(), plot.top()),
                     QtCore.QPointF(plot.left(), plot.bottom()))
    painter.drawLine(QtCore.QPointF(plot.left(), py(0.0)),
                     QtCore.QPointF(plot.right(), py(0.0)))

    painter.setFont(font(11))
    painter.setPen(ink)
    painter.drawText(QtCore.QRectF(plot.left(), height - 18, plot.width(), 16),
                     int(QtCore.Qt.AlignmentFlag.AlignCenter), "m/z")
    painter.save()
    painter.translate(13, plot.center().y())
    painter.rotate(-90)
    painter.drawText(QtCore.QRectF(-plot.height() / 2, -8, plot.height(), 16),
                     int(QtCore.Qt.AlignmentFlag.AlignCenter),
                     "Relative intensity (%)" if comparison.normalise
                     else "Intensity, cps")
    painter.restore()

    # -- the traces ---------------------------------------------------------- #
    for trace, y, sign in drawn:
        colour = for_paper(trace.colour)
        painter.setPen(QtGui.QPen(colour, 1.3))
        xs = trace.mz
        if comparison.centroid:
            for mz, value in zip(xs.tolist(), y.tolist()):
                if value <= 0:
                    continue
                painter.drawLine(QtCore.QPointF(px(mz), py(0.0)),
                                 QtCore.QPointF(px(mz), py(value * sign)))
        else:
            # columns of the image, not of the logical drawing: at twice the
            # size there are twice as many pixels to fill
            columns = int(plot.width() * max(painter.transform().m11(), 1.0))
            dx, dy = _decimate(xs, y, x0, x1, columns)
            polygon = QtGui.QPolygonF(
                [QtCore.QPointF(px(mz), py(value * sign))
                 for mz, value in zip(dx.tolist(), dy.tolist())])
            painter.drawPolyline(polygon)

    # -- peak labels --------------------------------------------------------- #
    painter.setFont(font(10))
    metrics = QtGui.QFontMetricsF(painter.font())
    taken: list[QtCore.QRectF] = []
    for trace, y, sign in drawn:
        top_value = float(y.max()) or 1.0
        for mz, _height in comparison.label_peaks(trace, x0, x1):
            index = int(np.argmin(np.abs(trace.mz - mz)))
            value = float(y[index])
            if value < top_value * LABEL_MIN_RELATIVE:
                continue
            text = f"{mz:.4f}"
            w = metrics.horizontalAdvance(text) + 4
            h = metrics.height()
            x = px(mz) - w / 2
            apex = py(value * sign)
            # beyond the apex first, and inside the peak if that would fall
            # off the edge: the base peak of a mirrored trace reaches the
            # bottom of the plot, and it is the one label worth having
            outside = apex - h - 2 if sign > 0 else apex + 2
            inside = apex + 2 if sign > 0 else apex - h - 2
            for placement in (outside, inside):
                rect = QtCore.QRectF(x, placement, w, h)
                if rect.left() < plot.left():
                    rect.moveLeft(plot.left())
                if rect.right() > plot.right():
                    rect.moveRight(plot.right())
                if rect.top() < top or rect.bottom() > plot.bottom() + 2:
                    continue
                if any(rect.intersects(other) for other in taken):
                    continue
                taken.append(rect)
                painter.setPen(ink)
                painter.drawText(rect, int(QtCore.Qt.AlignmentFlag.AlignCenter),
                                 text)
                break


def render_image(comparison: SpectrumComparison, width: int = DEFAULT_WIDTH,
                 height: int = DEFAULT_HEIGHT, scale: float = 1.0):
    """The comparison as a QImage of `width * scale` by `height * scale`."""
    from PyQt6 import QtGui

    pixels_w = max(int(round(width * scale)), 1)
    pixels_h = max(int(round(height * scale)), 1)
    image = QtGui.QImage(pixels_w, pixels_h, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor("#ffffff"))
    painter = QtGui.QPainter(image)
    try:
        painter.scale(scale, scale)
        paint(comparison, painter, width, height)
    finally:
        painter.end()
    return image


def render_png(comparison: SpectrumComparison, path, width: int = DEFAULT_WIDTH,
               height: int = DEFAULT_HEIGHT, scale: float = PRINT_SCALE) -> str:
    """Write the comparison as a PNG, by default at twice the logical size."""
    path = str(path)
    image = render_image(comparison, width, height, scale)
    if not image.save(path, "PNG"):
        raise OSError(f"could not write {path}")
    return path


def png_bytes(comparison: SpectrumComparison, width: int = DEFAULT_WIDTH,
              height: int = DEFAULT_HEIGHT,
              scale: float = PRINT_SCALE) -> bytes:
    """The PNG as bytes, for embedding rather than for a file."""
    from PyQt6 import QtCore

    image = render_image(comparison, width, height, scale)
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def data_uri(comparison: SpectrumComparison, width: int = DEFAULT_WIDTH,
             height: int = DEFAULT_HEIGHT, scale: float = PRINT_SCALE) -> str:
    """
    The PNG as a `data:` URI.

    QTextDocument renders one of these as readily as a file path — measured,
    both draw — and a report that carries its picture inside itself is a
    report that survives being mailed as one file.
    """
    encoded = base64.b64encode(png_bytes(comparison, width, height, scale))
    return "data:image/png;base64," + encoded.decode("ascii")


def render_svg(comparison: SpectrumComparison, path,
               width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> str:
    """
    The same drawing as vectors, for a figure that will be resized.

    QSvgGenerator is a paint device like any other, so this is the same
    `paint` at scale 1 — there is no second renderer to keep in step.
    """
    from PyQt6 import QtCore, QtGui
    from PyQt6.QtSvg import QSvgGenerator

    path = str(path)
    generator = QSvgGenerator()
    generator.setFileName(path)
    generator.setSize(QtCore.QSize(int(width), int(height)))
    generator.setViewBox(QtCore.QRect(0, 0, int(width), int(height)))
    generator.setTitle(comparison.title or "Compared spectra")
    generator.setDescription(comparison.summary())
    painter = QtGui.QPainter()
    painter.begin(generator)
    try:
        paint(comparison, painter, float(width), float(height))
    finally:
        painter.end()
    return path
