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

Four things about the drawing are deliberate:

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
* **A label is never drawn over anything.** Which peaks are offered a label
  is the budget's business; where the label goes is `paint`'s, and it goes
  above the peak — never inside it, never over a trace, never over another
  label. A slot already taken moves it a whole text height further out and
  a thin leader joins it to its apex; past `MAX_LIFT` of those it is
  dropped, and the drop is counted. Room for the stack is taken out of the
  plot before the traces are drawn, the same reservation the pane makes in
  `BasePlot._headroom_px`.

  Measured by rendering four real spectra at 960 by 520, normalised and
  head to tail, and counting the trace-coloured pixels found under every
  label drawn — two averaged product-ion spectra of CA-d4 (CID against
  EAD at 22 eV, 473 and 146 scans averaged) and the apex survey scans of
  two injections:

  | | drawn | over a trace | lifted | dropped |
  |---|---|---|---|---|
  | product ions, before | 28 | **10** | — | — |
  | product ions, after | 30 | **0** | 13 | 1 |
  | survey scans, before | 21 | **13** | — | — |
  | survey scans, after | 17 | **0** | 8 | 8 |

  The old rule placed a label inside the peak when the room above it was
  taken, so a third of what it drew was printed on the ink it described —
  `95.0843` and `101.0589` one text height apart over the same cluster of
  sticks was the complaint. The product-ion drawing gains two labels and
  loses the tangle; the survey loses eight, and they are the eight that
  cannot be placed at all: the isotopes of a base peak that reaches the
  top of the plot, whose labels have nowhere to go that is not on top of
  it. Before, they were drawn on top of it.
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

#: how far out a label may be lifted from the peak it names, in text
#: heights, before it is dropped instead of drawn.
#:
#: Measured on the four real comparisons of the note below, drawn at
#: 960 by 520, labels drawn for 1 / 2 / 4 / 6 / 8 / 12 steps: the two
#: averaged product-ion spectra 18 / 25 / 29 / **30** / 30 / 30, the two
#: survey scans 12 / 15 / 16 / **17** / 17 / 18. Six is where it stops
#: paying: past it the label is following a leader most of the way up the
#: plot, and the one more it draws at twelve is an isotope of a base peak
#: with its own label three rows below.
MAX_LIFT = 6

#: clear space between a label and the apex it names, and between two
#: labels side by side. The vertical rule is a plain intersection: a text
#: box is taller than its glyphs, so two rows that touch still read as two
#: rows, and insisting on a gap as well would waste a whole step.
LABEL_CLEAR = 2.0
LABEL_GAP = 3.0

#: text heights of clear space kept above the tallest trace — and below the
#: lowest, mirrored — for the stack to grow into. Taken out of the plot, not
#: out of the data: the traces are drawn shorter and the labels have
#: somewhere to go.
#:
#: Same four comparisons, at `MAX_LIFT` steps, for 1 / 2 / 3 / 4 / 6 text
#: heights: product ions 28 / 30 / **30** / 30 / 30, surveys 14 / 16 /
#: **17** / 17 / 17. Below three the base peak's own label is against the
#: ceiling and the row above it has nowhere to go; above three nothing more
#: is drawn and the traces are shorter for no gain.
HEADROOM_LIFTS = 3.0

#: the leader that joins a lifted label to its apex
LEADER_WIDTH = 0.6


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


@dataclass
class PlacedLabel:
    """One peak label, and where it ended up.

    In logical points, `y` downwards like the painter's. `lift` is how many
    text heights it had to be moved away from its peak to find room — zero
    is where a label goes when nothing is in the way.
    """

    text: str
    x: float
    y: float
    width: float
    height: float
    apex_x: float
    apex_y: float
    lift: int = 0
    down: bool = False

    @property
    def leader(self) -> bool:
        """A lifted label is more than one text height from its apex, and is
        joined to it by a line: at that distance nothing else says which
        peak it belongs to."""
        return self.lift > 0

    @property
    def box(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.x + self.width, self.y + self.height

    def overlaps(self, other: "PlacedLabel", gap: float = 0.0) -> bool:
        """Would the two labels touch? `gap` is clear space asked for
        sideways only — see `LABEL_GAP`."""
        return (self.x < other.x + other.width + gap
                and other.x < self.x + self.width + gap
                and self.y < other.y + other.height
                and other.y < self.y + self.height)


@dataclass
class LabelLayout:
    """What became of the labels of one drawing."""

    placed: list[PlacedLabel] = field(default_factory=list)
    dropped: int = 0
    #: the ink of the traces, one box per column of the drawing, as the
    #: placement saw it
    ink: list[tuple[float, float, float, float]] = field(default_factory=list)

    @property
    def drawn(self) -> int:
        return len(self.placed)

    @property
    def lifted(self) -> int:
        return sum(1 for label in self.placed if label.lift)

    @property
    def with_leader(self) -> int:
        return sum(1 for label in self.placed if label.leader)

    def summary(self) -> str:
        return (f"{self.drawn} drawn, {self.lifted} lifted, "
                f"{self.with_leader} with a leader, {self.dropped} dropped")


def _spans(x_pixels: np.ndarray, y_pixels: np.ndarray, columns: int,
           left: float) -> tuple[np.ndarray, np.ndarray]:
    """
    The topmost and the bottommost ink of one trace, per column of the
    drawing one point wide.

    One box per trace is the whole plot and forbids every label; a column
    is as fine as the question needs to be, since a label is tens of
    columns wide. A column with no point of the trace in it keeps `inf` and
    `-inf`, which no comparison can be inside. A segment between two points
    crosses the columns between them, so each column takes its neighbours'
    extremes as well rather than leaving a steep flank as a gap in the ink.
    """
    top = np.full(columns, np.inf)
    bottom = np.full(columns, -np.inf)
    if x_pixels.size:
        index = np.clip((x_pixels - left).astype(np.int64), 0, columns - 1)
        np.minimum.at(top, index, y_pixels)
        np.maximum.at(bottom, index, y_pixels)
        padded_top = np.concatenate(([np.inf], top, [np.inf]))
        padded_bottom = np.concatenate(([-np.inf], bottom, [-np.inf]))
        top = np.minimum(top, np.minimum(padded_top[:-2], padded_top[2:]))
        bottom = np.maximum(bottom,
                            np.maximum(padded_bottom[:-2], padded_bottom[2:]))
    return top, bottom


def _ink_boxes(spans, left: float) -> list[tuple[float, float, float, float]]:
    """The per-column ink as boxes, for anything that wants to check it."""
    boxes: list[tuple[float, float, float, float]] = []
    for top, bottom in spans:
        for column in np.nonzero(np.isfinite(top) & np.isfinite(bottom))[0]:
            boxes.append((left + float(column), float(top[column]),
                          left + float(column) + 1.0, float(bottom[column])))
    return boxes


def paint(comparison: SpectrumComparison, painter, width: float,
          height: float) -> LabelLayout:
    """
    Draw the comparison into `painter`, in logical points, and say where the
    labels went.

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

    # the labels' own font, measured before the geometry: how tall one label
    # is decides how much room is kept above the tallest trace
    painter.setFont(font(10))
    label_metrics = QtGui.QFontMetricsF(painter.font())
    text_h = float(label_metrics.height())

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
        return LabelLayout()

    x0 = min(float(t.mz.min()) for t, _y, _s in drawn)
    x1 = max(float(t.mz.max()) for t, _y, _s in drawn)
    if x1 <= x0:
        x0, x1 = x0 - 0.5, x1 + 0.5
    pad = (x1 - x0) * 0.02
    x0, x1 = x0 - pad, x1 + pad

    ymax = max(float(y.max()) for _t, y, _s in drawn) or 1.0
    down = any(s < 0 for _t, _y, s in drawn)
    # room for the stack of labels, taken out of the plot rather than out of
    # the data: the traces are drawn shorter and the labels have somewhere
    # to go. Mirrored, both ends need it — a mirrored base peak reaches the
    # end of its own half. The floor stops a very short drawing from being
    # all headroom and no trace.
    headroom = text_h * HEADROOM_LIFTS * (2.0 if down else 1.0)
    stretch = plot.height() / max(plot.height() - headroom,
                                  plot.height() * 0.5)
    ymax_drawn = ymax * stretch
    ylo, yhi = (-ymax_drawn, ymax_drawn) if down else (0.0, ymax_drawn)

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

    # -- the traces, and the ink a label may not be drawn over ---------------- #
    slots = max(int(math.ceil(plot.width())), 1)

    def column_of(x: float) -> int:
        return int(min(max(x - plot.left(), 0.0), slots - 1))

    ink_spans: list[tuple[np.ndarray, np.ndarray]] = []
    for trace, y, sign in drawn:
        colour = for_paper(trace.colour)
        painter.setPen(QtGui.QPen(colour, 1.3))
        xs = trace.mz
        if comparison.centroid:
            keep = y > 0
            dx, dy = xs[keep], y[keep]
            for mz, value in zip(dx.tolist(), dy.tolist()):
                painter.drawLine(QtCore.QPointF(px(mz), py(0.0)),
                                 QtCore.QPointF(px(mz), py(value * sign)))
            # a stick is ink from the baseline to its apex, so both ends go in
            xp = np.array([px(float(mz)) for mz in dx])
            yp = np.array([py(float(v) * sign) for v in dy])
            base = np.full(xp.shape, py(0.0))
            ink_spans.append(_spans(np.concatenate([xp, xp]),
                                    np.concatenate([yp, base]),
                                    slots, plot.left()))
        else:
            # columns of the image, not of the logical drawing: at twice the
            # size there are twice as many pixels to fill
            columns = int(plot.width() * max(painter.transform().m11(), 1.0))
            dx, dy = _decimate(xs, y, x0, x1, columns)
            xp = np.array([px(float(mz)) for mz in dx])
            yp = np.array([py(float(v) * sign) for v in dy])
            polygon = QtGui.QPolygonF(
                [QtCore.QPointF(a, b) for a, b in zip(xp.tolist(), yp.tolist())])
            painter.drawPolyline(polygon)
            ink_spans.append(_spans(xp, yp, slots, plot.left()))

    # -- peak labels --------------------------------------------------------- #
    painter.setFont(font(10))
    placed: list[PlacedLabel] = []
    dropped = 0

    def slot(text: str, wide: float, apex_x: float, apex_y: float,
             sign: float) -> PlacedLabel | None:
        """
        Where one label goes: the first free step beyond its own peak.

        Beyond it, never inside it — a number printed on the trace it
        describes is read as part of the picture — and never over another
        label. A step taken moves the label one whole text height further
        out, so a crowd stacks into rows; `MAX_LIFT` steps out is as far as
        a leader is worth following, and past that the label is dropped.
        A mirrored trace does all of this downwards.
        """
        left = apex_x - wide / 2
        left = min(max(left, plot.left()), max(plot.right() - wide, plot.left()))
        first, last = column_of(left), column_of(left + wide) + 1
        for lift in range(MAX_LIFT + 1):
            clear = LABEL_CLEAR + lift * text_h
            y_top = apex_y - text_h - clear if sign > 0 else apex_y + clear
            if y_top < plot.top() or y_top + text_h > plot.bottom():
                return None                 # and no further step is any better
            candidate = PlacedLabel(text=text, x=left, y=y_top, width=wide,
                                    height=text_h, apex_x=apex_x,
                                    apex_y=apex_y, lift=lift, down=sign < 0)
            if any(candidate.overlaps(other, LABEL_GAP) for other in placed):
                continue
            if any(bool(np.any((y_top < bottom[first:last])
                               & (y_top + text_h > edge[first:last])))
                   for edge, bottom in ink_spans):
                continue
            return candidate
        return None

    for trace, y, sign in drawn:
        top_value = float(y.max()) or 1.0
        for mz, _height in comparison.label_peaks(trace, x0, x1):
            index = int(np.argmin(np.abs(trace.mz - mz)))
            value = float(y[index])
            if value < top_value * LABEL_MIN_RELATIVE:
                continue
            text = f"{mz:.4f}"
            spot = slot(text, label_metrics.horizontalAdvance(text) + 4.0,
                        px(mz), py(value * sign), sign)
            if spot is None:
                dropped += 1
                continue
            placed.append(spot)

    painter.setPen(QtGui.QPen(muted, LEADER_WIDTH))
    for label in placed:                       # leaders first, under the text
        if not label.leader:
            continue
        painter.drawLine(
            QtCore.QPointF(label.x + label.width / 2,
                           label.y if label.down else label.y + label.height),
            QtCore.QPointF(label.apex_x,
                           label.apex_y + 1.0 if label.down
                           else label.apex_y - 1.0))
    painter.setPen(ink)
    for label in placed:
        painter.drawText(
            QtCore.QRectF(label.x, label.y, label.width, label.height),
            int(QtCore.Qt.AlignmentFlag.AlignCenter), label.text)
    return LabelLayout(placed=placed, dropped=dropped,
                       ink=_ink_boxes(ink_spans, plot.left()))


def _draw(comparison: SpectrumComparison, width: int, height: int,
          scale: float):
    """The drawing and its label layout, in one pass."""
    from PyQt6 import QtGui

    pixels_w = max(int(round(width * scale)), 1)
    pixels_h = max(int(round(height * scale)), 1)
    image = QtGui.QImage(pixels_w, pixels_h, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor("#ffffff"))
    painter = QtGui.QPainter(image)
    try:
        painter.scale(scale, scale)
        layout = paint(comparison, painter, width, height)
    finally:
        painter.end()
    return image, layout


def render_image(comparison: SpectrumComparison, width: int = DEFAULT_WIDTH,
                 height: int = DEFAULT_HEIGHT, scale: float = 1.0):
    """The comparison as a QImage of `width * scale` by `height * scale`."""
    return _draw(comparison, width, height, scale)[0]


def label_layout(comparison: SpectrumComparison, width: int = DEFAULT_WIDTH,
                 height: int = DEFAULT_HEIGHT,
                 scale: float = 1.0) -> LabelLayout:
    """
    Where the labels of this comparison went, by drawing it.

    The drawing is the only thing that knows: the placement follows the
    font, the geometry and the ink of the traces, so it is measured by
    rendering rather than by predicting. Logical points, whatever `scale`
    the image was made at.
    """
    return _draw(comparison, width, height, scale)[1]


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
