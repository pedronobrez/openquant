"""
The application shell: one window holding the workspaces.

Modelled on how SCIEX OS is laid out — the window owns the file handling, the
menus and the status bar, and each workspace is a tab that reads from the same
session.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtGui, QtWidgets

from .. import raw
from ..session import LEGACY_PROJECT_SUFFIX, PROJECT_SUFFIX, Session
from . import style, theme
from .analytics import AnalyticsWorkspace
from .explorer import ExplorerWorkspace
from .method_workspace import MethodWorkspace
from .new_project import (METHOD, METHOD_EMPTY, NewProjectWizard,
                          StartDialog)
from .plots import BasePlot
from .samples_workspace import SamplesWorkspace


class MainShell(QtWidgets.QMainWindow):
    """Holds the session and switches between workspaces."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenQuant")
        self.resize(1650, 1000)
        self.settings = QtCore.QSettings("OpenQuant", "OpenQuant")

        self.session = Session(self)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.explorer = ExplorerWorkspace(self.session)
        self.analytics = AnalyticsWorkspace(self.session)
        self.method = MethodWorkspace(self.session)
        self.samples = SamplesWorkspace(self.session)
        self.tabs.addTab(self.explorer, "Explorer")
        self.tabs.addTab(self.analytics, "Analytics")
        self.tabs.addTab(self.method, "Method")
        self.tabs.addTab(self.samples, "Samples")
        self.setCentralWidget(self.tabs)

        self._build_menu()
        self.statusBar().showMessage("Open a .wiff or .mzML file to start.")

        for workspace in (self.explorer, self.analytics, self.method, self.samples):
            workspace.sigStatus.connect(self.statusBar().showMessage)
        self.explorer.component_list.sigEditRequested.connect(
            lambda: self.tabs.setCurrentWidget(self.method))
        self.session.sigSamplesChanged.connect(self._samples_changed)
        self.session.sigProjectChanged.connect(self._update_title)
        self.theme_watcher = style.ThemeWatcher(
            QtWidgets.QApplication.instance(), self)
        self.theme_watcher.sigThemeChanged.connect(self.retheme)
        self.tabs.currentChanged.connect(self._tab_changed)
        self._update_title()

        geometry = self.settings.value("shell/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    # -- start ----------------------------------------------------------------- #
    def offer_start(self) -> None:
        """
        Ask how to begin, unless the analyst has said not to.

        Shown without blocking. exec() runs an event loop of its own, and
        while one is running the application cannot be quit at all — not by
        Cmd-Q, not by the red button, not by the Quit the system sends when
        it is shutting down or logging out. A prompt offering to start some
        work should not be able to trap the application it is offering to
        start; the only way out was to answer it.
        """
        if self.settings.value("shell/skip_start", False, type=bool):
            return
        dialog = StartDialog(self)
        dialog.finished.connect(lambda _code, d=dialog: self._start_chosen(d))
        dialog.open()

    def _start_chosen(self, dialog) -> None:
        if dialog.check_skip.isChecked():
            self.settings.setValue("shell/skip_start", True)
        choice = dialog.choice
        dialog.deleteLater()
        if choice == StartDialog.NEW:
            self.new_project()
        elif choice == StartDialog.OPEN:
            self.open_project()

    def export_report(self) -> None:
        """
        Write the batch out as a document.

        PDF for handing over, HTML for keeping: the second opens in a browser
        long after this application is gone, which is the point of a report as
        against an export.
        """
        from ..report import write_html, write_pdf

        if not self.session.entries:
            self.statusBar().showMessage("Open a batch before reporting on it.")
            return
        stem = (os.path.splitext(os.path.basename(self.session.project_path))[0]
                if self.session.project_path else "batch")
        path, chosen = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export report", os.path.join(self._last_dir(), f"{stem}.pdf"),
            "PDF (*.pdf);;Web page (*.html)")
        if not path:
            return
        self.settings.setValue("io/last_dir", os.path.dirname(path))
        wants_html = path.lower().endswith(".html") or "html" in chosen.lower()
        if not os.path.splitext(path)[1]:
            path += ".html" if wants_html else ".pdf"
        title = f"{stem} — batch report"
        # a hundred-page report is laid out more than once, to number its
        # contents and to keep headings with what they introduce, and that is
        # seconds of work with the window frozen. Say so rather than look hung.
        self.statusBar().showMessage(f"Writing {os.path.basename(path)}…")
        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        QtWidgets.QApplication.processEvents()
        try:
            writer = write_html if wants_html else write_pdf
            writer(self.session, path, title=title)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Report failed", str(exc))
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        size = os.path.getsize(path) / 1024
        self.statusBar().showMessage(f"Report written to {path} ({size:,.0f} KB)")

    # -- help ---------------------------------------------------------------- #
    def show_manual(self, page: str | None = None) -> None:
        """The manual, in its own window; one window, brought back if open."""
        from .help_window import HelpWindow

        window = getattr(self, "_help_window", None)
        if window is None:
            window = HelpWindow(self)
            self._help_window = window
        if page:
            window.show_page(page)
        window.show()
        window.raise_()
        window.activateWindow()

    def export_manual(self) -> None:
        from .help_window import HelpWindow

        window = getattr(self, "_help_window", None) or HelpWindow(self)
        self._help_window = window
        window.export_pdf()

    # -- theme --------------------------------------------------------------- #
    def retheme(self) -> None:
        """
        Follow the system into or out of dark mode.

        The widgets are restyled by the sheet the watcher has already applied.
        The plots are not: pyqtgraph is told its colours once, so every plot
        has to be handed them again, and the traces have to be rebuilt because
        the first series colour is the accent, which has changed.
        """
        theme.apply_defaults()
        for plot in self.findChildren(BasePlot):
            plot.retheme()
        self.explorer.refresh_chromatogram()
        self.analytics.refresh_grid()
        self.analytics.refresh_calibration()
        self.analytics.metrics.reload()
        self.method.reload()
        self.statusBar().showMessage(
            "Dark theme" if style.is_dark() else "Light theme")

    # -- menus --------------------------------------------------------------- #
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.act_new_project = file_menu.addAction("New project…")
        self.act_new_project.setShortcut(QtGui.QKeySequence.StandardKey.New)
        self.act_open_project = file_menu.addAction("Open project…")
        self.act_save_project = file_menu.addAction("Save project")
        self.act_save_project.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        self.act_save_project_as = file_menu.addAction("Save project as…")
        self.act_save_project_as.setShortcut(
            QtGui.QKeySequence.StandardKey.SaveAs)
        file_menu.addSeparator()
        self.act_open = file_menu.addAction("Add data files…")
        self.act_open.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        self.act_close = file_menu.addAction("Close all")
        self.act_report = file_menu.addAction("Export report…")
        self.act_report.setToolTip(
            "A document of the whole batch — method, calibration, results and "
            "statistics — to print or to hand over")
        file_menu.addSeparator()
        for action in self.explorer.build_actions()["File"]:
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction("Quit").triggered.connect(self.close)

        actions = self.explorer.build_actions()
        for name in ("View", "Panels", "Process"):
            menu = self.menuBar().addMenu(f"&{name}")
            for action in actions[name]:
                menu.addAction(action)

        workspace_menu = self.menuBar().addMenu("&Workspace")
        for index, label in enumerate(("Explorer", "Analytics", "Method", "Samples")):
            action = workspace_menu.addAction(label)
            action.setShortcut(QtGui.QKeySequence(f"Ctrl+{index + 1}"))
            action.triggered.connect(
                lambda _checked, i=index: self.tabs.setCurrentIndex(i))

        help_menu = self.menuBar().addMenu("&Help")
        act_manual = help_menu.addAction("Manual")
        act_manual.setShortcut(QtGui.QKeySequence.StandardKey.HelpContents)
        act_manual.triggered.connect(self.show_manual)
        help_menu.addAction("Quick tips…").triggered.connect(self.explorer._show_help)
        help_menu.addAction("Export manual as PDF…").triggered.connect(
            self.export_manual)

        self.act_new_project.triggered.connect(self.new_project)
        self.act_open.triggered.connect(self.open_files)
        self.act_close.triggered.connect(self.close_all)
        self.act_open_project.triggered.connect(self.open_project)
        self.act_save_project.triggered.connect(self.save_project)
        self.act_save_project_as.triggered.connect(self.save_project_as)
        self.act_report.triggered.connect(self.export_report)
        self.samples.btn_open.clicked.connect(self.open_files)

    # -- files --------------------------------------------------------------- #
    def _last_dir(self) -> str:
        return self.settings.value("io/last_dir", "", type=str)

    def open_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Add data files", self._last_dir(),
            raw.FILE_FILTER)
        for path in paths:
            self.load_file(path)
        if paths:
            self.settings.setValue("io/last_dir", os.path.dirname(paths[0]))

    def load_file(self, path: str) -> None:
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            self.session.open_file(path)
        except Exception as exc:  # pragma: no cover - depends on the file
            QtWidgets.QMessageBox.critical(
                self, "Could not open", f"{os.path.basename(path)}\n\n{exc}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def close_all(self) -> None:
        # close_all drops the batch and the project link, so unsaved work would
        # go with it without this
        if not self.confirm_discard("Close everything anyway?"):
            return
        self.explorer.clear_views()
        self.session.close_all()

    def _samples_changed(self) -> None:
        loaded = len(self.session.loaded_entries)
        self.statusBar().showMessage(
            f"{loaded} sample(s) open" if loaded else "No files open.")

    def _tab_changed(self, _index: int) -> None:
        if self.tabs.currentWidget() is self.method and not self.session.entries:
            self.statusBar().showMessage(
                "Open a sample to generate the component list from its "
                "acquisition method.")

    # -- project -------------------------------------------------------------- #
    def _update_title(self) -> None:
        name = (os.path.basename(self.session.project_path)
                if self.session.project_path else "")
        marker = " •" if self.session.dirty else ""
        self.setWindowTitle(f"OpenQuant — {name}{marker}" if name
                            else f"OpenQuant{marker}")

    def confirm_discard(self, action: str) -> bool:
        """
        Ask before throwing away unsaved work. True means carry on.

        Offered on anything that replaces the session, which is the whole point
        of tracking the unsaved state: forgetting to save should cost a click,
        not a batch.
        """
        if not (self.session.dirty and self.session.has_content):
            return True
        answer = QtWidgets.QMessageBox.question(
            self, "Save this project first?",
            f"This project has changes that are not saved. {action}",
            QtWidgets.QMessageBox.StandardButton.Save
            | QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Save)
        if answer == QtWidgets.QMessageBox.StandardButton.Cancel:
            return False
        if answer == QtWidgets.QMessageBox.StandardButton.Save:
            return self.save_project()
        return True

    def new_project(self) -> bool:
        if not self.confirm_discard("Start a new project anyway?"):
            return False
        self.explorer.clear_views()
        self.session.close_all()
        wizard = NewProjectWizard(self.session, self._last_dir(), self)
        if not wizard.exec():
            return False

        page = wizard.page(METHOD)
        page.apply_to(self.session.method)
        self.session.set_components(page.components())
        self.session.save_project(wizard.project_path)
        self.settings.setValue(
            "io/last_dir", os.path.dirname(wizard.project_path))
        self.statusBar().showMessage(
            f"Project created at {self.session.project_path}")
        if wizard.process_now:
            self.tabs.setCurrentWidget(self.analytics)
            self.analytics.process_batch()
        elif page.choice() == METHOD_EMPTY:
            self.tabs.setCurrentWidget(self.method)
        else:
            self.tabs.setCurrentWidget(self.samples)
        return True

    def open_project(self) -> None:
        if not self.confirm_discard("Open another project anyway?"):
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open project", self._last_dir(),
            f"OpenQuant project (*{PROJECT_SUFFIX} *{LEGACY_PROJECT_SUFFIX});;"
            "All files (*)")
        if not path:
            return
        self.explorer.clear_views()
        try:
            missing = self.session.load_project(path)
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.critical(self, "Could not open the project", str(exc))
            return
        if missing:
            QtWidgets.QMessageBox.warning(
                self, "Raw files missing",
                "The batch information was restored, but these files could not "
                "be opened:\n\n" + "\n".join(sorted(set(missing))))
        self.statusBar().showMessage(f"Project loaded from {path}")

    def save_project(self) -> bool:
        """Save without asking once the project has a file of its own."""
        if not self.session.project_path:
            return self.save_project_as()
        self.session.save_project(self.session.project_path)
        self.statusBar().showMessage(f"Project saved to {self.session.project_path}")
        return True

    def save_project_as(self) -> bool:
        suggestion = self.session.project_path or os.path.join(
            self._last_dir(), f"project{PROJECT_SUFFIX}")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save project", suggestion,
            f"OpenQuant project (*{PROJECT_SUFFIX})")
        if not path:
            return False
        self.session.save_project(path)
        self.settings.setValue("io/last_dir", os.path.dirname(path))
        self.statusBar().showMessage(f"Project saved to {self.session.project_path}")
        return True

    # -- lifecycle ------------------------------------------------------------- #
    def closeEvent(self, event):
        if not self.confirm_discard("Quit anyway?"):
            event.ignore()
            return
        self.settings.setValue("shell/geometry", self.saveGeometry())
        self.explorer.save_settings()
        self.session.close_all()
        super().closeEvent(event)
