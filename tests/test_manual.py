"""
The manual: every page present, every link resolving, and the window and
the printed copy built from the same pages.

A manual that names a page which does not exist, or links to one that was
renamed, is the kind of thing nobody notices until a reader does. The
tests here are the reader.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openquant import manual as manual_module  # noqa: E402
from openquant.manual import HOME, INDEX, PAGES_DIR, Manual, load, render_markdown  # noqa: E402


@pytest.fixture(scope="module")
def manual() -> Manual:
    return load()


def test_every_page_in_the_index_exists(manual):
    wanted = [pid for _section, ids in INDEX for pid in ids]
    missing = [pid for pid in wanted if pid not in manual.pages]
    assert missing == [], f"pages named in INDEX but not written: {missing}"
    on_disk = {path.stem for path in PAGES_DIR.glob("*.md")}
    orphans = on_disk - set(wanted)
    assert orphans == set(), f"pages on disk that the index does not list: {orphans}"


def test_every_page_has_a_title_of_its_own(manual):
    titles = [page.title for page in manual.pages.values()]
    assert len(titles) == len(set(titles)), "two pages share a title"
    assert all(title and title[0].isupper() for title in titles)
    assert HOME in manual.pages


def test_every_wiki_link_resolves(manual):
    broken = {pid: page.unresolved for pid, page in manual.pages.items()
              if page.unresolved}
    assert broken == {}, f"links to pages that do not exist: {broken}"


def test_every_page_is_reachable_by_a_link(manual):
    """A page nobody links to can only be found from the contents tree —
    which is fine for the welcome page and a sign of an island otherwise."""
    unlinked = [pid for pid, page in manual.pages.items()
                if not page.backlinks and pid != HOME]
    assert unlinked == [], f"no page links to: {unlinked}"


def test_links_go_both_ways(manual):
    for pid, page in manual.pages.items():
        for target in page.links:
            assert pid in manual.pages[target].backlinks


def test_pages_are_not_stubs(manual):
    """A page a few lines long is a heading with nothing under it."""
    short = [pid for pid, page in manual.pages.items() if len(page.text) < 600]
    assert short == [], f"pages under six hundred characters: {short}"


def test_search_finds_by_prefix_and_ranks_the_title_first(manual):
    hits = manual.search("integr")
    assert hits, "nothing mentions integration"
    assert hits[0].page.title.lower().find("integr") >= 0
    assert manual.search("") == []
    assert manual.search("zqxjwv") == []


def test_search_needs_every_word(manual):
    both = {hit.page.id for hit in manual.search("calibration weighting")}
    either = {hit.page.id for hit in manual.search("calibration")}
    assert both and both <= either


def test_a_wiki_link_can_carry_its_own_text(manual):
    rendered = render_markdown("See [[welcome|the first page]] and [[Welcome]].",
                               lambda m: f"<a>{m.group(2) or m.group(1)}</a>")
    assert "<a>the first page</a>" in rendered and "<a>Welcome</a>" in rendered


def test_markdown_subset_renders_what_the_pages_use():
    source = ("## Head\n\nA *b* **c** `d<e>` [f](http://g).\n\n"
              "| x | y |\n|---|---|\n| 1 | 2 |\n\n- one\n- two\n\n1. first\n2. second\n\n"
              "> quoted\n\n```\ncode & more\n```\n\n---\n")
    out = render_markdown(source)
    for piece in ("<h2>Head</h2>", "<i>b</i>", "<b>c</b>", "<code>d&lt;e&gt;</code>",
                  '<a href="http://g">f</a>', "<th>x</th>", "<td>2</td>",
                  "<ul><li>one</li><li>two</li></ul>", "<ol><li>first</li>",
                  "<blockquote>quoted</blockquote>", "<pre>code &amp; more</pre>", "<hr/>"):
        assert piece in out, piece


# --------------------------------------------------------------------------- #
# the window and the printed copy
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def qapp():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_window_opens_on_the_home_page_and_follows_links(qapp, manual):
    from PyQt6 import QtCore
    from openquant.ui.help_window import HelpWindow

    window = HelpWindow(manual=manual)
    assert window.current_page == HOME
    target = manual.pages[HOME].links[0]
    window._link_clicked(QtCore.QUrl(f"help:{target}"))
    assert window.current_page == target
    window.back()
    assert window.current_page == HOME
    window.forward()
    assert window.current_page == target
    window.search.setText("calibration")
    assert window.hits.count() > 0
    window.hits.setCurrentRow(0)
    assert window.current_page == window.hits.item(0).data(QtCore.Qt.ItemDataRole.UserRole)
    window.close()


def test_the_shell_opens_the_manual_from_its_help_menu(qapp):
    from openquant.ui.shell import MainShell

    shell = MainShell()
    shell.show_manual("peak-review")
    assert shell._help_window.current_page == "peak-review"
    shell._help_window.close()
    shell.close()


def test_the_manual_prints_as_many_pages_with_ink_on_them(qapp, manual, tmp_path):
    pdf = pytest.importorskip("PyQt6.QtPdf")
    from PyQt6 import QtCore

    path = manual.write_pdf(tmp_path / "manual.pdf")
    document = pdf.QPdfDocument(None)
    document.load(path)
    assert document.pageCount() >= 20
    image = document.render(3, QtCore.QSize(600, 848))
    assert not image.isNull()
    lowest = 0
    for y in range(image.height()):
        for x in range(0, image.width(), 3):
            if image.pixelColor(x, y).lightness() < 200:
                lowest = y
                break
    assert lowest > image.height() * 0.6


def test_the_module_level_manual_is_read_once(manual):
    first = manual_module.manual()
    assert manual_module.manual() is first
