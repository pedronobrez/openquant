"""The design tokens, the glyphs they are drawn with, and the sheet itself."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtGui, QtWidgets  # noqa: E402

from openquant.ui import style, theme  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def light(qapp):
    palette = qapp.palette()
    palette.setColor(QtGui.QPalette.ColorRole.Window,
                     QtGui.QColor(style.LIGHT["canvas"]))
    qapp.setPalette(palette)
    yield qapp


@pytest.fixture
def dark(qapp):
    palette = qapp.palette()
    palette.setColor(QtGui.QPalette.ColorRole.Window,
                     QtGui.QColor(style.DARK["canvas"]))
    qapp.setPalette(palette)
    yield qapp
    palette.setColor(QtGui.QPalette.ColorRole.Window,
                     QtGui.QColor(style.LIGHT["canvas"]))
    qapp.setPalette(palette)


def test_both_themes_define_the_same_tokens():
    assert set(style.LIGHT) == set(style.DARK)


def test_the_light_theme_uses_the_project_blue(light):
    assert style.token("accent") == style.ACCENT


def test_the_dark_theme_lightens_it_rather_than_dropping_it(dark):
    assert style.is_dark()
    accent = QtGui.QColor(style.token("accent"))
    original = QtGui.QColor(style.ACCENT)
    # same hue, lifted so it reads on a dark ground
    assert abs(accent.hue() - original.hue()) <= 12
    assert accent.lightness() > original.lightness()


def test_the_accent_carries_enough_contrast_for_its_own_text(light):
    def luminance(colour):
        c = QtGui.QColor(colour)
        parts = []
        for channel in (c.redF(), c.greenF(), c.blueF()):
            parts.append(channel / 12.92 if channel <= 0.03928
                         else ((channel + 0.055) / 1.055) ** 2.4)
        return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

    for tokens in (style.LIGHT, style.DARK):
        a, b = luminance(tokens["accent"]), luminance(tokens["accent_ink"])
        ratio = (max(a, b) + 0.05) / (min(a, b) + 0.05)
        assert ratio >= 4.5, tokens["accent"]


def test_the_sheet_names_no_colour_the_tokens_do_not(light):
    sheet = style.stylesheet()
    known = {v.lower() for v in style.LIGHT.values()}
    literals = {word.lower() for word in sheet.split()
                if word.startswith("#") and len(word) in (4, 7)}
    literals |= {word.rstrip(";").lower() for word in sheet.split()
                 if word.startswith("#") and word.rstrip(";") and len(word) in (5, 8)}
    assert literals <= known, literals - known


def test_the_indicators_are_drawn_as_real_images(light):
    for name, path in style.indicators().items():
        pixmap = QtGui.QPixmap(path)
        assert not pixmap.isNull(), name
        assert pixmap.width() == 14
        # something was actually painted, not just a transparent square
        assert any(pixmap.toImage().pixelColor(x, y).alpha()
                   for x in range(14) for y in range(14)), name


def test_a_retina_copy_is_written_beside_each_glyph(light):
    for path in style.indicators().values():
        retina = path.replace(".png", "@2x.png")
        assert QtGui.QPixmap(retina).width() == 28


def test_applying_the_style_sets_both_palette_and_sheet(light, qapp):
    style.apply(qapp)
    assert qapp.styleSheet()
    assert (qapp.palette().color(QtGui.QPalette.ColorRole.Base).name()
            == style.LIGHT["surface"])


def test_the_plot_colours_come_from_the_same_tokens(dark):
    assert theme.background() == style.DARK["surface"]
    assert theme.foreground() == style.DARK["ink"]
    assert theme.accent() == style.DARK["accent"]


def test_a_cell_widget_is_given_the_padding_it_loses(light, qapp):
    table = QtWidgets.QTableWidget(1, 1)
    combo = QtWidgets.QComboBox()
    combo.addItems(["a name long enough to need the whole column"])
    table.setCellWidget(0, 0, combo)
    table.setColumnWidth(0, 20)
    style.fit_cell_widgets(table)
    assert (table.columnWidth(0)
            >= combo.sizeHint().width() + style.CELL_WIDGET_INSET)
