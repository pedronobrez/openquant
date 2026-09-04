"""
The application shell: one window holding the workspaces.

Modelled on how SCIEX OS is laid out — the window owns the file handling, the
menus and the status bar, and each workspace is a tab that reads from the same
session.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtGui, QtWidgets

from ..session import PROJECT_SUFFIX, Session
from .analytics import AnalyticsWorkspace
from .explorer import ExplorerWorkspace
from .method_workspace import MethodWorkspace
from .samples_workspace import SamplesWorkspace


class MainShell(QtWidgets.QMainWindow):
    """Holds the session and switches between workspaces."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenPeakView")
        self.resize(1650, 1000)
        self.settings = QtCore.QSettings("OpenPeakView", "OpenPeakView")

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
        self.statusBar().showMessage("Open a .wiff file to start.")

        for workspace in (self.explorer, self.analytics, self.method, self.samples):
            workspace.sigStatus.connect(self.statusBar().showMessage)
        self.explorer.component_list.sigEditRequested.connect(
            lambda: self.tabs.setCurrentWidget(self.method))
        self.session.sigSamplesChanged.connect(self._samples_changed)
        self.tabs.currentChanged.connect(self._tab_changed)

        geometry = self.settings.value("shell/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    # -- menus --------------------------------------------------------------- #
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.act_open = file_menu.addAction("Open .wiff…")
        self.act_open.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        self.act_close = file_menu.addAction("Close all")
        file_menu.addSeparator()
        self.act_open_project = file_menu.addAction("Open project…")
        self.act_save_project = file_menu.addAction("Save project…")
        self.act_save_project.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        file_menu.addSeparator()
        for action in self.explorer.build_actions()["File"]:
            file_menu.addAction(action)
        file_menu.addSeparator()
        file_menu.addAction("Quit").triggered.connect(self.close)

        actions = self.explorer.build_actions()
        for name in ("View", "Process"):
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
        help_menu.addAction("How to use…").triggered.connect(self.explorer._show_help)

        self.act_open.triggered.connect(self.open_files)
        self.act_close.triggered.connect(self.close_all)
        self.act_open_project.triggered.connect(self.open_project)
        self.act_save_project.triggered.connect(self.save_project)
        self.samples.btn_open.clicked.connect(self.open_files)

    # -- files --------------------------------------------------------------- #
    def _last_dir(self) -> str:
        return self.settings.value("io/last_dir", "", type=str)

    def open_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Open SCIEX files", self._last_dir(),
            "wiff files (*.wiff);;All files (*)")
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
    def open_project(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open project", self._last_dir(),
            f"OpenPeakView project (*{PROJECT_SUFFIX});;All files (*)")
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

    def save_project(self) -> None:
        suggestion = self.session.project_path or os.path.join(
            self._last_dir(), f"project{PROJECT_SUFFIX}")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save project", suggestion,
            f"OpenPeakView project (*{PROJECT_SUFFIX})")
        if not path:
            return
        self.session.save_project(path)
        self.settings.setValue("io/last_dir", os.path.dirname(path))
        self.statusBar().showMessage(f"Project saved to {self.session.project_path}")

    # -- lifecycle ------------------------------------------------------------- #
    def closeEvent(self, event):  # noqa: N802 (Qt API)
        self.settings.setValue("shell/geometry", self.saveGeometry())
        self.explorer.save_settings()
        self.session.close_all()
        super().closeEvent(event)
