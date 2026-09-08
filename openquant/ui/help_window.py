"""
The manual, in a window of its own.

A tree of the contents on the left, the page on the right, and a search
box that turns the tree into a list of hits while there is something in
it. Links between pages work the way a browser's do, with back and
forward, and every page ends with the pages that link to it — the manual
can be read from either end of any link.
"""

from __future__ import annotations

import html

from PyQt6 import QtCore, QtGui, QtWidgets

from . import theme
from .. import manual as manual_module
from ..manual import HOME, SCHEME, Manual, Page

ROLE_ID = QtCore.Qt.ItemDataRole.UserRole


def _stylesheet() -> str:
    dark = theme.is_dark()
    text = theme.foreground()
    muted = "#9aa3ad" if dark else "#5b6472"
    accent = "#8ab4f8" if dark else "#234b8c"
    rule = "#3a4048" if dark else "#c3c9d3"
    shade = "#262a30" if dark else "#f2f4f7"
    return f"""
    body {{ color: {text}; font-size: 10.5pt; }}
    h1 {{ font-size: 18pt; font-weight: 600; margin: 0 0 8pt 0; }}
    h2 {{ font-size: 13pt; font-weight: 600; color: {accent}; margin: 16pt 0 4pt 0; }}
    h3 {{ font-size: 11pt; font-weight: 600; margin: 12pt 0 3pt 0; }}
    p {{ margin: 0 0 7pt 0; line-height: 135%; }}
    li {{ margin: 0 0 3pt 0; }}
    a {{ color: {accent}; text-decoration: none; }}
    code {{ font-family: Menlo, Consolas, "DejaVu Sans Mono", monospace;
            font-size: 9.5pt; background: {shade}; }}
    pre {{ font-family: Menlo, Consolas, "DejaVu Sans Mono", monospace;
           font-size: 9pt; background: {shade}; margin: 4pt 0 8pt 0; }}
    blockquote {{ color: {muted}; margin: 4pt 0 8pt 14pt; }}
    th {{ text-align: left; background: {shade}; color: {accent};
          border-bottom: 1.5px solid {accent}; font-weight: 600; }}
    td {{ border-bottom: 1px solid {rule}; vertical-align: top; }}
    tr.alt td {{ background: {shade}; }}
    p.crumb {{ color: {muted}; font-size: 9pt; margin: 0 0 2pt 0; }}
    p.backlinks {{ color: {muted}; font-size: 9.5pt; margin: 14pt 0 0 0;
                   border-top: 1px solid {rule}; padding-top: 6pt; }}
    """


class HelpWindow(QtWidgets.QMainWindow):
    """Contents, search, a page, and the history to move between them."""

    def __init__(self, parent=None, manual: Manual | None = None):
        super().__init__(parent)
        self.manual = manual or manual_module.manual()
        self.setWindowTitle("OpenQuant manual")
        self.setWindowFlag(QtCore.Qt.WindowType.Window, True)
        self.resize(1180, 780)
        self._history: list[str] = []
        self._position = -1
        self._current: str | None = None

        bar = self.addToolBar("Navigation")
        bar.setMovable(False)
        self.act_back = bar.addAction("◀ Back")
        self.act_back.setShortcut(QtGui.QKeySequence.StandardKey.Back)
        self.act_forward = bar.addAction("Forward ▶")
        self.act_forward.setShortcut(QtGui.QKeySequence.StandardKey.Forward)
        self.act_home = bar.addAction("Contents")
        bar.addSeparator()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search the manual…  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(320)
        bar.addWidget(self.search)
        self.act_pdf = bar.addAction("Export as PDF…")
        self.act_pdf.setToolTip("The whole manual as one A4 document")

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.side = QtWidgets.QStackedWidget()
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(240)
        self.hits = QtWidgets.QListWidget()
        self.hits.setWordWrap(True)
        self.side.addWidget(self.tree)
        self.side.addWidget(self.hits)
        splitter.addWidget(self.side)
        self.browser = QtWidgets.QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.document().setDefaultStyleSheet(_stylesheet())
        self.browser.document().setDocumentMargin(18)
        splitter.addWidget(self.browser)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 900])
        self.setCentralWidget(splitter)
        self.statusBar()

        self._fill_tree()
        self.tree.currentItemChanged.connect(self._tree_changed)
        self.hits.currentItemChanged.connect(self._hit_changed)
        self.search.textChanged.connect(self._search)
        self.search.returnPressed.connect(self._open_first_hit)
        self.browser.anchorClicked.connect(self._link_clicked)
        self.act_back.triggered.connect(self.back)
        self.act_forward.triggered.connect(self.forward)
        self.act_home.triggered.connect(lambda: self.show_page(HOME))
        self.act_pdf.triggered.connect(self.export_pdf)
        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Find, self,
                        activated=lambda: (self.search.setFocus(),
                                           self.search.selectAll()))
        self.show_page(HOME)

    # -- contents ---------------------------------------------------------------- #
    def _fill_tree(self) -> None:
        self.tree.clear()
        for section, pages in self.manual.sections():
            node = QtWidgets.QTreeWidgetItem(self.tree, [section])
            font = node.font(0)
            font.setBold(True)
            node.setFont(0, font)
            node.setFlags(node.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable)
            for page in pages:
                item = QtWidgets.QTreeWidgetItem(node, [page.title])
                item.setData(0, ROLE_ID, page.id)
            node.setExpanded(True)

    def _tree_changed(self, current, _previous) -> None:
        if current is None:
            return
        pid = current.data(0, ROLE_ID)
        if pid and pid != self._current:
            self.show_page(pid)

    def _select_in_tree(self, pid: str) -> None:
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, ROLE_ID) == pid:
                self.tree.blockSignals(True)
                self.tree.setCurrentItem(item)
                self.tree.blockSignals(False)
                return
            iterator += 1

    # -- pages ------------------------------------------------------------------- #
    def show_page(self, pid: str, remember: bool = True,
                  anchor: str | None = None) -> None:
        page = self.manual.get(pid)
        if page is None:
            self.statusBar().showMessage(f"No page called “{pid}”.")
            return
        if remember and page.id != self._current:
            del self._history[self._position + 1:]
            self._history.append(page.id)
            self._position = len(self._history) - 1
        self._current = page.id
        self.browser.setHtml(self._page_html(page))
        if anchor:
            self.browser.scrollToAnchor(anchor)
        else:
            self.browser.verticalScrollBar().setValue(0)
        self._select_in_tree(page.id)
        self.setWindowTitle(f"{page.title} — OpenQuant manual")
        self.act_back.setEnabled(self._position > 0)
        self.act_forward.setEnabled(self._position < len(self._history) - 1)
        query = self.search.text().strip()
        if query:
            self.browser.find(query)

    def _page_html(self, page: Page) -> str:
        crumb = html.escape(page.section)
        parts = [f'<p class="crumb">{crumb}</p>',
                 f"<h1>{html.escape(page.title)}</h1>", page.html]
        if page.backlinks:
            links = ", ".join(
                f'<a href="{SCHEME}{pid}">{html.escape(self.manual.pages[pid].title)}</a>'
                for pid in page.backlinks)
            parts.append(f'<p class="backlinks">Linked from: {links}</p>')
        return "".join(parts)

    def _link_clicked(self, url: QtCore.QUrl) -> None:
        text = url.toString()
        if text.startswith(SCHEME):
            target = text[len(SCHEME):]
            pid, _, anchor = target.partition("#")
            self.show_page(pid, anchor=anchor or None)
        elif url.scheme() in ("http", "https", "mailto"):
            QtGui.QDesktopServices.openUrl(url)
        elif text.startswith("#"):
            self.browser.scrollToAnchor(text[1:])

    def back(self) -> None:
        if self._position > 0:
            self._position -= 1
            self.show_page(self._history[self._position], remember=False)

    def forward(self) -> None:
        if self._position < len(self._history) - 1:
            self._position += 1
            self.show_page(self._history[self._position], remember=False)

    @property
    def current_page(self) -> str | None:
        return self._current

    # -- search ------------------------------------------------------------------ #
    def _search(self, text: str) -> None:
        query = text.strip()
        if not query:
            self.side.setCurrentWidget(self.tree)
            self.statusBar().clearMessage()
            return
        hits = self.manual.search(query)
        self.hits.blockSignals(True)
        self.hits.clear()
        for hit in hits:
            item = QtWidgets.QListWidgetItem(f"{hit.page.title}\n{hit.snippet}")
            item.setData(ROLE_ID, hit.page.id)
            item.setToolTip(hit.page.section)
            self.hits.addItem(item)
        self.hits.blockSignals(False)
        self.side.setCurrentWidget(self.hits)
        self.statusBar().showMessage(
            f"{len(hits)} page(s) mention “{query}”" if hits
            else f"Nothing mentions “{query}”")

    def _hit_changed(self, current, _previous) -> None:
        if current is not None:
            self.show_page(current.data(ROLE_ID))

    def _open_first_hit(self) -> None:
        if self.hits.count():
            self.hits.setCurrentRow(0)

    # -- printing ---------------------------------------------------------------- #
    def export_pdf(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export the manual", "OpenQuant-manual.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        try:
            self.manual.write_pdf(path)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"Manual written to {path}")
