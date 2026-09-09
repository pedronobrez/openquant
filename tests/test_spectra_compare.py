"""
Compared spectra, off the screen.

The comparison is data — the traces as they were drawn, their labels and
the two switches — and the picture is made from it on demand. What is
tested here is that the picture is a real drawing at the size asked for
rather than an enlargement of a small one, that a mass shared by two
spectra is found and a mass 50 ppm away is not, and that a trace colour
chosen for a dark window is darkened before it is printed on white.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtGui, QtWidgets  # noqa: E402

from openquant import spectra_compare as sc  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def profile(peaks, lo=100.0, hi=800.0, step=0.005, width=0.012):
    """A synthetic profile spectrum, sampled finely enough that a centroid
    across its points means something."""
    mz = np.arange(lo, hi, step)
    y = np.zeros(mz.size)
    for centre, height in peaks:
        y += height * np.exp(-0.5 * ((mz - centre) / width) ** 2)
    return mz, y


def comparison(**kwargs):
    a = profile([(184.0733, 100000), (264.2686, 22000), (703.5749, 41000)])
    b = profile([(184.0733, 61000), (264.2686, 31000), (731.6062, 52000)])
    return sc.SpectrumComparison(
        traces=[sc.SpectrumTrace("A · scan 3", a[0], a[1], "#234b8c"),
                sc.SpectrumTrace("B · scan 9", b[0], b[1], "#e08a1e")],
        title="A against B", **kwargs)


# --------------------------------------------------------------------------- #
# what is held
# --------------------------------------------------------------------------- #
def test_a_comparison_needs_two_spectra_to_stand():
    one = sc.SpectrumComparison(traces=[sc.SpectrumTrace(
        "A", *profile([(184.0733, 100)]), "#234b8c")])
    assert not one.stands
    assert comparison().stands
    empty = sc.SpectrumComparison(traces=[
        sc.SpectrumTrace("A", np.zeros(0), np.zeros(0)),
        sc.SpectrumTrace("B", np.zeros(0), np.zeros(0))])
    assert not empty.stands, "two empty traces are not a comparison"


def test_it_is_built_from_anything_shaped_like_a_trace():
    """The module knows nothing about the widget: that is what lets the
    report be built with no window."""
    class Fake:
        def __init__(self, label, x, y, colour):
            self.label, self.x, self.y, self.colour = label, x, y, colour

    x, y = profile([(184.0733, 10.0)])
    built = sc.from_traces([Fake("live", x, y, "#123456")], title="t",
                           condition=lambda t: (t.x, t.y * 2))
    assert built.traces[0].label == "live"
    assert built.traces[0].intensity.max() == pytest.approx(y.max() * 2)
    # a copy, so the live spectrum moving on does not rewrite the comparison
    y[:] = 0.0
    assert built.traces[0].intensity.max() > 0


def test_the_base_peak_and_the_range_come_off_the_trace():
    trace = comparison().traces[0]
    mz, height = trace.base_peak
    assert mz == pytest.approx(184.0733, abs=0.01)
    assert height == pytest.approx(100000, rel=0.01)
    low, high = trace.mz_range
    assert (low, high) == pytest.approx((100.0, 799.995), abs=0.01)


# --------------------------------------------------------------------------- #
# what they have in common
# --------------------------------------------------------------------------- #
def test_shared_peaks_are_the_masses_every_trace_holds():
    shared = sc.shared_peaks(comparison())
    masses = [peak.mz for peak in shared]
    assert any(abs(m - 184.0733) < 0.01 for m in masses)
    assert any(abs(m - 264.2686) < 0.01 for m in masses)
    # 703.57 is in one and 731.61 in the other: a difference, not a match
    assert not any(abs(m - 703.5749) < 0.05 for m in masses)
    assert not any(abs(m - 731.6062) < 0.05 for m in masses)


def test_a_shared_height_is_a_share_of_each_traces_own_base_peak():
    """Two spectra of different sizes only compare as percentages, and the
    percentages must not depend on whether the pane was normalising."""
    plain = sc.shared_peaks(comparison())
    normalised = sc.shared_peaks(comparison(normalise=True))
    assert [p.heights for p in plain] == [p.heights for p in normalised]
    base = next(p for p in plain if abs(p.mz - 184.0733) < 0.01)
    assert base.heights == pytest.approx([100.0, 100.0], abs=0.5)
    second = next(p for p in plain if abs(p.mz - 264.2686) < 0.01)
    assert second.heights[0] == pytest.approx(22.0, abs=1.0)
    assert second.heights[1] == pytest.approx(51.0, abs=1.0)


def test_a_mass_outside_the_tolerance_is_not_the_same_mass():
    a = profile([(400.0000, 1000.0)])
    # 50 ppm away is 0.02 Da at this mass: a different ion
    b = profile([(400.0200, 1000.0)])
    pair = sc.SpectrumComparison(traces=[
        sc.SpectrumTrace("A", *a), sc.SpectrumTrace("B", *b)])
    assert sc.shared_peaks(pair, tolerance_ppm=10.0) == []
    assert len(sc.shared_peaks(pair, tolerance_ppm=100.0)) == 1


# --------------------------------------------------------------------------- #
# colour
# --------------------------------------------------------------------------- #
def test_a_colour_meant_for_a_dark_window_is_darkened_for_paper(qapp):
    """The dark theme's accent is 2.8:1 on white — a pale line on a page."""
    assert sc.contrast_on_white("#6f9be0") < sc.MIN_CONTRAST
    darkened = sc.for_paper("#6f9be0").name()
    assert sc.contrast_on_white(darkened) >= sc.MIN_CONTRAST
    # the hue is kept, so a trace known by its colour on screen is the same
    # trace on paper; a point of drift is the rounding of value into HSV
    assert abs(QtGui.QColor(darkened).hue() - QtGui.QColor("#6f9be0").hue()) <= 2


def test_a_colour_that_already_prints_is_left_exactly_as_it_is(qapp):
    assert sc.contrast_on_white("#234b8c") > sc.MIN_CONTRAST
    assert sc.for_paper("#234b8c").name() == "#234b8c"


# --------------------------------------------------------------------------- #
# the drawing
# --------------------------------------------------------------------------- #
def _ink_rows(image, x0, x1, y0, y1):
    """How many rows of a box hold dark ink."""
    rows = 0
    for y in range(y0, min(y1, image.height())):
        for x in range(x0, min(x1, image.width()), 2):
            if image.pixelColor(x, y).lightness() < 128:
                rows += 1
                break
    return rows


def test_the_image_is_the_size_it_was_asked_for(qapp):
    image = sc.render_image(comparison(), 640, 360, 1.0)
    assert (image.width(), image.height()) == (640, 360)
    doubled = sc.render_image(comparison(), 640, 360, 2.0)
    assert (doubled.width(), doubled.height()) == (1280, 720)


def test_twice_the_size_is_a_re_render_and_not_an_enlargement(qapp):
    """
    A picture twice as wide with the same eleven-point type in it is a big
    picture of a small one: printed at one size the letters would be half as
    tall. The title's ink has to scale with the canvas.
    """
    single = sc.render_image(comparison(), 960, 520, 1.0)
    double = sc.render_image(comparison(), 960, 520, 2.0)
    small = _ink_rows(single, 120, 500, 4, 40)
    large = _ink_rows(double, 240, 1000, 8, 80)
    assert small > 4, "no title was drawn"
    assert large >= small * 1.8, (
        f"type did not scale: {small} rows at 1x, {large} at 2x")


def _topmost(image, is_colour, start: int = 100) -> int:
    """The highest row of the plot holding a pixel of one trace's colour.

    The search starts below the legend, whose swatches are drawn in the
    same colours as the traces they name.
    """
    for y in range(start, image.height()):
        for x in range(60, image.width() - 20, 2):
            if is_colour(image.pixelColor(x, y)):
                return y
    return image.height()


def _orange(c) -> bool:
    return c.red() > 150 and 90 < c.green() < 170 and c.blue() < 90


def _blue(c) -> bool:
    return c.blue() > 110 and c.red() < 120 and c.lightness() < 190


def test_the_mirrored_trace_is_drawn_below_the_line(qapp):
    """Head to tail: the second spectrum hangs under the zero line, which
    with Mirror off it does not — both then rise from the foot of the plot."""
    mirrored = sc.render_image(comparison(mirror=True), 960, 520, 1.0)
    middle = mirrored.height() // 2
    assert _topmost(mirrored, _blue) < middle, "the first trace goes up"
    assert _topmost(mirrored, _orange) >= middle - 8, (
        "the second trace should start at the zero line and hang below it")

    plain = sc.render_image(comparison(mirror=False), 960, 520, 1.0)
    assert _topmost(plain, _orange) < middle, (
        "with Mirror off the second trace rises like the first")


def test_an_empty_comparison_says_so_rather_than_throwing(qapp):
    empty = sc.SpectrumComparison(traces=[
        sc.SpectrumTrace("A", np.zeros(0), np.zeros(0))], title="nothing")
    image = sc.render_image(empty, 400, 200, 1.0)
    assert not image.isNull()
    assert _ink_rows(image, 0, 400, 0, 200) > 0     # the words, and nothing else


def test_a_profile_is_thinned_to_the_pixels_without_losing_a_lone_point():
    """
    The contour view's lesson: taking every kth point is faster and loses a
    peak one point wide. Each column keeps its highest and its lowest.
    """
    x = np.linspace(100.0, 200.0, 20_000)
    y = np.zeros(x.size)
    y[7_777] = 5000.0                              # one point, nothing round it
    dx, dy = sc._decimate(x, y, 100.0, 200.0, 800)
    assert dx.size < x.size / 5
    assert dy.max() == 5000.0
    assert abs(dx[int(dy.argmax())] - x[7_777]) < 1e-9


def test_png_and_svg_are_written_and_the_svg_carries_the_labels(qapp, tmp_path):
    png = sc.render_png(comparison(mirror=True), tmp_path / "cmp.png")
    assert os.path.getsize(png) > 5_000
    image = QtGui.QImage(png)
    assert (image.width(), image.height()) == (
        int(sc.DEFAULT_WIDTH * sc.PRINT_SCALE),
        int(sc.DEFAULT_HEIGHT * sc.PRINT_SCALE))

    svg = sc.render_svg(comparison(mirror=True), tmp_path / "cmp.svg")
    text = open(svg, encoding="utf-8").read()
    assert text.startswith("<?xml")
    assert "A against B" in text                    # title, as SVG metadata
    # a vector drawing of a hundred thousand points is only reasonable
    # because the profile is thinned to the pixels first
    assert os.path.getsize(svg) < 1_500_000


def test_the_data_uri_is_something_qt_actually_draws(qapp):
    """
    The report embeds the picture as a data URI so that an exported HTML
    report is one file. QTextDocument draws a file path, a file:// URL, a
    registered resource and a data URI alike — measured, and this is the
    one the report depends on.
    """
    uri = sc.data_uri(comparison(mirror=True), 320, 180, 1.0)
    assert uri.startswith("data:image/png;base64,")
    document = QtGui.QTextDocument()
    document.setHtml(f"<p>before</p><img src='{uri}'><p>after</p>")
    document.setPageSize(QtCore.QSizeF(400, 400))
    canvas = QtGui.QImage(400, 400, QtGui.QImage.Format.Format_RGB32)
    canvas.fill(QtGui.QColor("white"))
    painter = QtGui.QPainter(canvas)
    document.drawContents(painter, QtCore.QRectF(0, 0, 400, 400))
    painter.end()
    coloured = sum(1 for y in range(0, 400, 2) for x in range(0, 400, 2)
                   if abs(canvas.pixelColor(x, y).red()
                          - canvas.pixelColor(x, y).blue()) > 40)
    assert coloured > 20, "the image did not draw inside the document"
