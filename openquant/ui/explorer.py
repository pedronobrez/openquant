"""Explorer workspace: the qualitative review of raw samples."""

from __future__ import annotations

import csv
import os

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from ..chemistry import (
    ADDUCTS_BY_NAME,
    find_formulas,
    has_isotope_satellites,
    isotope_pattern,
    rank_by_isotope_pattern,
)
from ..components import Component
from ..infusion import InfusionVerdict, run_range, verdict_for
from ..matching import match_channel
from .settings import settings
from ..processing import (centroid_spectrum, detect_peaks, integrate,
                          signal_to_noise)
from ..samples import SampleEntry
from ..session import Session
from ..wiff import Channel
from .chrom_area import ChromatogramArea
from .component_list import ComponentListPanel
from .formula_panel import FormulaPanel
from .lipid_panel import LipidPanel
from .mass_calc_panel import MassCalcPanel
from ..contour import Contour, build_contour
from .contour_view import ContourView
from . import plots
from .plots import SpectrumView, Trace, colour
from .. import labels as label_rule
from .results_panel import Result, ResultsPanel
from .sample_info import SampleInfoPanel

ROLE_REF = QtCore.Qt.ItemDataRole.UserRole

#: bumped whenever the toolbars are rearranged, so Qt throws away a layout
#: saved by a version that had them somewhere else
LAYOUT_VERSION = 2


def _first_line(error: BaseException) -> str:
    """A .NET exception is a page; the first line is the message."""
    text = str(error).strip()
    return text.splitlines()[0] if text else type(error).__name__


class ChannelRef:
    """A tree node: either the sample TIC or one specific channel."""

    def __init__(self, entry: SampleEntry, channel: Channel | None):
        self.entry = entry
        self.channel = channel

    @property
    def sample(self):
        return self.entry.sample

    @property
    def alias(self) -> str:
        return self.entry.name

    @property
    def filename(self) -> str:
        return self.entry.filename

    @property
    def key(self) -> str:
        idx = "TIC" if self.channel is None else str(self.channel.index)
        return f"{self.entry.key}|{idx}"

    @property
    def label(self) -> str:
        if self.channel is None:
            return f"{self.alias} · TIC"
        return f"{self.alias} · {self.channel.info.short_label}"

    @property
    def full_label(self) -> str:
        base = os.path.splitext(self.filename)[0]
        if self.channel is None:
            return f"{base} · sample TIC"
        return f"{base} · {self.channel.info.label}"


VIEW_CHROMATOGRAM = "Chromatogram"
VIEW_CONTOUR = "Contour"

#: how many built surfaces to keep. Each is a grid of some ten megabytes, and
#: a file of eighty-one channels would otherwise fill memory with pictures
#: nobody is looking at any more.
CONTOUR_CACHE = 6


class _Cancelled(Exception):
    """The reader asked to stop, from inside the writer's progress callback."""


class ExplorerWorkspace(QtWidgets.QMainWindow):
    """
    Qualitative review of the raw data.

    A QMainWindow so it keeps dock widgets and toolbars while living inside a
    tab of the shell; the shell owns the real window and its menu bar.
    """

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.WindowType.Widget)

        self.session = session
        self.settings = settings()
        self.refs: dict[str, ChannelRef] = {}
        self.xic_defs: list[dict] = []
        self.active_ref: ChannelRef | None = None
        self.current_scan: int = 0
        self._background_cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}

        self.chrom = ChromatogramArea()
        self.contour_view = ContourView()
        self.spectrum = SpectrumView()
        #: built contours, by channel and by the ranges they were built over
        self._contour_cache: dict[tuple, object] = {}

        self._build_ui()
        self._connect()
        self._restore_settings()
        self.session.sigSamplesChanged.connect(self.rebuild_tree)
        self.session.sigMethodChanged.connect(self._refresh_components)
        self._update_status("Open a .wiff or .mzML file to start.")

    # ------------------------------------------------------------------ UI -- #
    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self._wrap_chromatogram())
        splitter.addWidget(self._wrap_spectrum())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        self._build_tree_dock()
        self._build_side_dock()
        self._build_toolbars()

    def _wrap_chromatogram(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("View:"))
        self.view_combo = QtWidgets.QComboBox()
        self.view_combo.addItems([VIEW_CHROMATOGRAM, VIEW_CONTOUR])
        self.view_combo.setToolTip(
            "The contour is the same data with neither axis summed away: "
            "time across, m/z up, intensity as colour")
        bar.addWidget(self.view_combo)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["TIC", "BPC"])
        self.mode_combo.setToolTip("Chromatogram type for the checked channels")
        bar.addWidget(self.mode_combo)
        bar.addSpacing(16)
        bar.addWidget(QtWidgets.QLabel("Active channel (spectra / XIC):"))
        self.active_combo = QtWidgets.QComboBox()
        self.active_combo.setMinimumWidth(320)
        bar.addWidget(self.active_combo, 1)
        layout.addLayout(bar)

        self.top_stack = QtWidgets.QStackedWidget()
        self.top_stack.addWidget(self.chrom)
        self.top_stack.addWidget(self.contour_view)
        layout.addWidget(self.top_stack)
        return box

    def _wrap_spectrum(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 0, 4, 4)
        layout.setSpacing(4)

        bar = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QToolButton()
        self.btn_prev.setText("◀")
        self.btn_prev.setToolTip("Previous scan (left arrow)")
        self.btn_next = QtWidgets.QToolButton()
        self.btn_next.setText("▶")
        self.btn_next.setToolTip("Next scan (right arrow)")
        self.scan_spin = QtWidgets.QSpinBox()
        self.scan_spin.setMinimum(1)
        self.scan_spin.setMaximum(1)
        self.scan_spin.setToolTip("Scan number (1 is the channel's first cycle)")
        self.rt_label = QtWidgets.QLabel("—")
        self.rt_label.setMinimumWidth(170)
        #: says so when the active sample was read as a direct infusion, and
        #: carries the figures that decided it on hover
        self.infusion_label = QtWidgets.QLabel("")
        self.infusion_label.setProperty("role", "warning")

        bar.addWidget(QtWidgets.QLabel("Scan:"))
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.scan_spin)
        bar.addWidget(self.btn_next)
        bar.addWidget(self.rt_label)
        bar.addWidget(self.infusion_label)
        bar.addStretch(1)
        self.bg_label = QtWidgets.QLabel("")
        self.bg_label.setProperty("role", "warning")
        bar.addWidget(self.bg_label)
        self.btn_avg = QtWidgets.QPushButton("Average selected range")
        self.btn_avg.setToolTip(
            "Average spectrum of the scans inside the range marked on the chromatogram"
        )
        bar.addWidget(self.btn_avg)
        layout.addLayout(bar)
        layout.addWidget(self.spectrum)
        return box

    def _build_tree_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Samples and channels", self)
        dock.setObjectName("dock_tree")
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)

        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter channels (e.g. 313.2)")
        self.filter_edit.setClearButtonEnabled(True)
        layout.addWidget(self.filter_edit)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        layout.addWidget(self.tree, 1)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_none = QtWidgets.QPushButton("Uncheck all")
        self.btn_ms1 = QtWidgets.QPushButton("TOF MS only")
        self.btn_collapse = QtWidgets.QPushButton("Collapse all")
        self.btn_collapse.setToolTip(
            "Fold every sample shut. A TripleTOF method is eighty channels per "
            "injection, and a dozen injections buries the list.")
        buttons.addWidget(self.btn_none)
        buttons.addWidget(self.btn_ms1)
        buttons.addWidget(self.btn_collapse)
        layout.addLayout(buttons)

        dock.setWidget(panel)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
                             | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        dock.setMinimumWidth(330)
        self.dock_tree = dock
        self.act_dock_tree = self._reopen_action(
            dock, "Samples and channels", "Ctrl+Shift+S",
            "The tree of open files and their channels, on the left")

    def _build_side_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Panels", self)
        dock.setObjectName("dock_side")
        self.tabs = QtWidgets.QTabWidget()

        self.component_list = ComponentListPanel()
        self.results_panel = ResultsPanel()
        self.mass_calc = MassCalcPanel()
        self.formula_panel = FormulaPanel()
        self.lipid_panel = LipidPanel()
        self.sample_info = SampleInfoPanel()

        from .help_window import describe
        xic_tab, peaks_tab = self._build_xic_tab(), self._build_peaks_tab()
        self.tabs.addTab(self.component_list, "Components")
        self.tabs.addTab(self.results_panel, "Results")
        self.tabs.addTab(xic_tab, "Manual XIC")
        self.tabs.addTab(peaks_tab, "Spectrum peaks")
        self.tabs.addTab(self.mass_calc, "Mass calc")
        self.tabs.addTab(self.formula_panel, "Formula finder")
        self.tabs.addTab(self.lipid_panel, "LIPID MAPS")
        from .library_panel import LibraryPanel
        self.library_panel = LibraryPanel()
        self.library_panel.spectrum_source = self._library_spectrum
        self.tabs.addTab(self.library_panel, "Library")
        for widget, page in ((self.component_list, "explorer-components-and-results"),
                             (self.results_panel, "explorer-components-and-results"),
                             (xic_tab, "manual-xic"),
                             (peaks_tab, "chromatograms-and-spectra"),
                             (self.mass_calc, "mass-calculator"),
                             (self.formula_panel, "formula-finder"),
                             (self.lipid_panel, "lipid-maps"),
                             (self.sample_info, "sample-information"),
                             (self.contour_view, "contour-view"),
                             (self.chrom, "chromatograms-and-spectra"),
                             (self.infusion_label, "direct-infusion"),
                             (self.spectrum, "chromatograms-and-spectra")):
            describe(widget, page)
        # eight tabs in a narrow dock elide into unreadable stubs; scroll
        # buttons keep the full names and let the reader page through them
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self.tabs.addTab(self.sample_info, "Sample")

        # the eight tabs need twice the width the dock has, so five of them sit
        # behind two small arrows and are found by accident or not at all. This
        # lists every panel by name, at the tabs, where you look for them.
        self.panel_menu = QtWidgets.QMenu(self)
        self.btn_panels = QtWidgets.QToolButton()
        self.btn_panels.setText("Panels")
        self.btn_panels.setToolTip("Go to a panel by name")
        self.btn_panels.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_panels.setMenu(self.panel_menu)
        self.tabs.setCornerWidget(self.btn_panels,
                                  QtCore.Qt.Corner.TopRightCorner)
        self._build_panel_actions()

        dock.setWidget(self.tabs)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setMinimumWidth(360)
        self.dock_side = dock
        self.act_dock_side = self._reopen_action(
            dock, "Side panels", "Ctrl+Shift+P",
            "Components, results, XIC and the rest, on the right")

    def _build_xic_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        form = QtWidgets.QFormLayout()
        self.xic_mz = QtWidgets.QLineEdit()
        self.xic_mz.setPlaceholderText("183.1391, 313.2384")
        form.addRow("m/z (comma separated):", self.xic_mz)

        tol_row = QtWidgets.QHBoxLayout()
        self.xic_tol = QtWidgets.QDoubleSpinBox()
        self.xic_tol.setDecimals(4)
        self.xic_tol.setRange(0.0001, 500.0)
        self.xic_tol.setValue(0.02)
        self.xic_unit = QtWidgets.QComboBox()
        self.xic_unit.addItems(["Da", "ppm"])
        tol_row.addWidget(self.xic_tol)
        tol_row.addWidget(self.xic_unit)
        form.addRow("Tolerance (±):", tol_row)
        layout.addLayout(form)

        self.xic_all_channels = QtWidgets.QCheckBox("Extract from every checked channel")
        layout.addWidget(self.xic_all_channels)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_xic = QtWidgets.QPushButton("Extract XIC")
        self.btn_xic_clear = QtWidgets.QPushButton("Clear XICs")
        buttons.addWidget(self.btn_xic)
        buttons.addWidget(self.btn_xic_clear)
        layout.addLayout(buttons)

        layout.addWidget(QtWidgets.QLabel("Active XICs:"))
        self.xic_list = QtWidgets.QListWidget()
        self.xic_list.setToolTip("Delete removes the selected XIC")
        layout.addWidget(self.xic_list, 1)

        hint = QtWidgets.QLabel(
            "Tip: select a range on the spectrum (Shift + drag) and right-click "
            "to extract its XIC."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        layout.addWidget(hint)
        return page

    def _build_peaks_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.peak_table = QtWidgets.QTableWidget(0, 3)
        self.peak_table.setHorizontalHeaderLabels(["m/z", "Intensity", "% base"])
        self.peak_table.horizontalHeader().setStretchLastSection(True)
        self.peak_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.peak_table.setToolTip("Double-click to extract that mass as an XIC")
        layout.addWidget(self.peak_table)
        return page

    def _build_toolbars(self) -> None:
        bar = self.addToolBar("Main")
        bar.setObjectName("toolbar_main")
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.act_select = QtGui.QAction("Select range", self, checkable=True)
        self.act_select.setToolTip(
            "Dragging selects a range instead of zooming "
            "(Shift + drag always does the same)"
        )
        bar.addAction(self.act_select)
        self.act_autoscale = bar.addAction("Fit")
        self.act_marker = bar.addAction("Add marker")
        self.act_marker.setToolTip(
            "Reference marker on the spectrum; other peaks are then labelled "
            "with their distance to it — neutral losses and isotope spacings"
        )
        self.act_marker_clear = bar.addAction("Clear markers")

        view = self.addToolBar("View")
        view.setObjectName("toolbar_view")
        view.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.act_norm = QtGui.QAction("Normalise", self, checkable=True)
        self.act_mirror = QtGui.QAction("Mirror", self, checkable=True)
        self.act_mirror.setToolTip("Flip every other trace — sample against blank")
        self.act_stack = QtGui.QAction("Stack", self, checkable=True)
        self.act_stack.setToolTip(
            "One pane per trace, with the time axes locked together"
        )
        self.act_overview = QtGui.QAction("Overview", self, checkable=True)
        self.act_overview.setToolTip(
            "Navigator showing the full range and the region currently in view"
        )
        self.act_labels = QtGui.QAction("m/z labels", self, checkable=True)
        self.act_labels.setChecked(True)
        self.act_apex = QtGui.QAction("RT labels", self, checkable=True)
        self.act_apex.setChecked(True)
        self.act_relative = QtGui.QAction("Relative labels", self, checkable=True)
        self.act_relative.setChecked(True)
        self.act_relative.setToolTip(
            "With markers present, label peaks by their distance to the marker"
        )
        self.act_legend = QtGui.QAction("Legend", self, checkable=True)
        self.act_legend.setChecked(True)
        for action in (self.act_norm, self.act_mirror, self.act_stack,
                       self.act_overview, self.act_labels, self.act_apex,
                       self.act_relative, self.act_legend):
            view.addAction(action)
        view.addSeparator()
        # beside the label switches, because that is what it belongs to, and
        # ahead of the cascade so it is the cascade that goes into the
        # toolbar's overflow on a narrow window
        view.addWidget(QtWidgets.QLabel(" Label floor (%): "))
        self.floor_spin = QtWidgets.QDoubleSpinBox()
        self.floor_spin.setRange(plots.FLOOR_MIN * 100.0, plots.FLOOR_MAX * 100.0)
        self.floor_spin.setDecimals(2)
        self.floor_spin.setSingleStep(0.25)
        self.floor_spin.setValue(label_rule.LABEL_MIN_RELATIVE * 100.0)
        self.floor_spin.setToolTip(
            "How tall a peak must be, against the tallest one in view, to be "
            "labelled with its m/z.\nThe same as the triangle beside the "
            "spectrum's Y axis; either moves the other."
        )
        view.addWidget(self.floor_spin)
        view.addSeparator()
        view.addWidget(QtWidgets.QLabel(" Cascade x (min): "))
        self.offset_x_spin = QtWidgets.QDoubleSpinBox()
        self.offset_x_spin.setRange(-10.0, 10.0)
        self.offset_x_spin.setSingleStep(0.05)
        self.offset_x_spin.setDecimals(2)
        self.offset_x_spin.setToolTip("Shift each overlaid trace along time")
        view.addWidget(self.offset_x_spin)
        view.addWidget(QtWidgets.QLabel("  y (%): "))
        self.offset_y_spin = QtWidgets.QDoubleSpinBox()
        self.offset_y_spin.setRange(-500.0, 500.0)
        self.offset_y_spin.setSingleStep(5.0)
        self.offset_y_spin.setDecimals(0)
        self.offset_y_spin.setToolTip("Stagger each overlaid trace vertically")
        view.addWidget(self.offset_y_spin)

        # Main and View fill a row on their own; without a break the whole
        # Processing toolbar collapses behind an overflow button
        self.addToolBarBreak()
        proc = self.addToolBar("Processing")
        proc.setObjectName("toolbar_proc")
        proc.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        proc.addWidget(QtWidgets.QLabel(" Smooth (σ, scans): "))
        self.smooth_spin = QtWidgets.QDoubleSpinBox()
        self.smooth_spin.setRange(0.0, 25.0)
        self.smooth_spin.setSingleStep(0.5)
        self.smooth_spin.setDecimals(1)
        self.smooth_spin.setToolTip("Gaussian smoothing; 0 turns it off")
        proc.addWidget(self.smooth_spin)
        proc.addWidget(QtWidgets.QLabel("  Baseline (min): "))
        self.baseline_spin = QtWidgets.QDoubleSpinBox()
        self.baseline_spin.setRange(0.0, 60.0)
        self.baseline_spin.setSingleStep(0.5)
        self.baseline_spin.setDecimals(1)
        self.baseline_spin.setToolTip(
            "Window width used to estimate the baseline; 0 turns it off.\n"
            "It must be wider than the broadest peak you want to keep."
        )
        proc.addWidget(self.baseline_spin)
        proc.addSeparator()
        self.act_centroid = QtGui.QAction("Centroid", self, checkable=True)
        self.act_centroid.setToolTip("Show the spectrum as centroid sticks")
        proc.addAction(self.act_centroid)
        proc.addSeparator()
        self.act_set_bg = proc.addAction("Set background")
        self.act_set_bg.setToolTip(
            "Use the selected chromatogram range as the blank: every spectrum "
            "generated from then on comes out with that background subtracted"
        )
        self.act_clear_bg = proc.addAction("Clear background")
        proc.addSeparator()
        self.act_explain = proc.addAction("Explain spectrum")
        self.act_explain.setToolTip(
            "Score every LIPID MAPS candidate for this precursor by how much "
            "of the spectrum on screen its structure accounts for")
        self.act_detect = proc.addAction("Detect peaks")
        self.act_avg_run = proc.addAction("Average whole run")
        self.act_avg_run.setToolTip(
            "Average every scan of the active channel into one spectrum — "
            "what a direct infusion, which has no chromatography to select "
            "over, is meant to be looked at as")
        self.act_exp_chrom = QtGui.QAction("Export chromatograms (CSV)…", self)
        self.act_exp_spec = QtGui.QAction("Export spectrum (CSV)…", self)
        self.act_exp_cmp = QtGui.QAction("Export comparison (PNG/SVG)…", self)
        self.act_exp_cmp.setEnabled(False)
        self.act_exp_cmp.setToolTip(
            "Write the pinned spectra and the live one as one picture — PNG "
            "at twice the size for print, or SVG to resize. The same drawing "
            "goes in the report")
        self.act_exp_mzml = QtGui.QAction("Export sample as mzML…", self)
        self.act_pin = proc.addAction("Pin spectrum")
        self.act_pin.setToolTip(
            "Keep the spectrum on screen so the next one draws over it — "
            "another sample, scan or channel. Normalise puts them on one scale; "
            "Mirror draws every other one downwards, head to tail")
        self.act_unpin = proc.addAction("Unpin spectra")
        self.act_unpin.setEnabled(False)
        self.act_exp_mzml.setToolTip(
            "Write the selected sample as open-format mzML, spectrum for "
            "spectrum, so it can be read elsewhere"
        )
        self.act_detect.setToolTip(
            "Integrate the peaks of every chromatogram trace and fill the Results tab"
        )

    def _build_panel_actions(self) -> None:
        """One action per panel, for the corner menu and the menu bar."""
        self.panel_actions = []
        for index in range(self.tabs.count()):
            action = QtGui.QAction(self.tabs.tabText(index), self)
            action.setShortcut(QtGui.QKeySequence(f"Ctrl+Shift+{index + 1}"))
            action.triggered.connect(
                lambda _checked, i=index: self.show_panel(i))
            self.panel_menu.addAction(action)
            self.panel_actions.append(action)
            self.addAction(action)

    def show_panel(self, index: int) -> None:
        """Bring a panel to the front, opening the dock if it was closed."""
        self.dock_side.show()
        self.dock_side.raise_()
        self.tabs.setCurrentIndex(index)
        self.tabs.tabBar().setCurrentIndex(index)

    def show_panel_named(self, title: str) -> bool:
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                self.show_panel(index)
                return True
        return False

    def _reopen_action(self, dock, text: str, shortcut: str,
                       tip: str) -> QtGui.QAction:
        """
        The way back after a side panel has been closed.

        A dock has a close button and nothing that undoes it. Qt lists them in
        a context menu on the toolbar, which nobody finds — close the tree of
        samples and channels and the workspace looks broken with no way back.

        The action is made here, where the dock is, rather than when the menu
        asks for it: the shortcut has to work whether or not anything built a
        menu, and it only fires at all if the window itself owns the action.
        """
        action = dock.toggleViewAction()
        action.setText(text)
        action.setShortcut(QtGui.QKeySequence(shortcut))
        action.setShortcutContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        action.setToolTip(tip)
        self.addAction(action)
        return action

    def _dock_actions(self) -> list:
        separator = QtGui.QAction(self)
        separator.setSeparator(True)
        return [separator, self.act_dock_tree, self.act_dock_side]

    def build_actions(self) -> dict:
        """Actions the shell adds to its own menus for this workspace."""
        return {
            "File": [self.act_exp_chrom, self.act_exp_spec, self.act_exp_cmp,
                     self.act_exp_mzml],
            "View": [self.act_autoscale, self.act_norm, self.act_mirror,
                     self.act_stack, self.act_overview, self.act_labels,
                     self.act_apex, self.act_relative, self.act_legend,
                     *self._dock_actions()],
            "Panels": list(self.panel_actions),
            "Process": [self.act_centroid, self.act_marker, self.act_marker_clear,
                        self.act_set_bg, self.act_clear_bg, self.act_explain,
                        self.act_detect, self.act_avg_run, self.act_pin,
                        self.act_unpin],
        }

    # -------------------------------------------------------------- signals -- #
    def _connect(self) -> None:
        self.act_autoscale.triggered.connect(self._autoscale_both)
        self.act_select.toggled.connect(self._set_select_mode)
        self.act_norm.toggled.connect(self._set_normalised)
        self.act_mirror.toggled.connect(self._set_mirror)
        self.act_stack.toggled.connect(self.chrom.set_stacked)
        self.act_overview.toggled.connect(self._set_overview)
        self.act_labels.toggled.connect(self.spectrum.set_labels_enabled)
        self.act_apex.toggled.connect(self.chrom.set_apex_labels)
        self.act_relative.toggled.connect(self._set_relative_labels)
        self.act_legend.toggled.connect(self.chrom.set_legend_visible)
        self.act_centroid.toggled.connect(self._set_centroid)
        self.act_marker.triggered.connect(self._add_marker)
        self.act_marker_clear.triggered.connect(self._clear_markers)
        self.act_pin.triggered.connect(self.pin_spectrum)
        self.act_unpin.triggered.connect(self.unpin_spectra)
        self.spectrum.sigPinRequested.connect(self.pin_spectrum)
        self.spectrum.sigUnpinRequested.connect(self.unpin_spectra)
        self.act_exp_chrom.triggered.connect(
            lambda: self._export(self.chrom, "chromatograms"))
        self.act_exp_spec.triggered.connect(
            lambda: self._export(self.spectrum, "spectrum"))
        self.act_exp_cmp.triggered.connect(self._export_comparison)
        self.act_exp_mzml.triggered.connect(self._export_mzml)
        self.act_set_bg.triggered.connect(self._set_background)
        self.act_clear_bg.triggered.connect(self._clear_background)
        self.act_explain.triggered.connect(self.explain_spectrum)
        self.act_detect.triggered.connect(self._detect_peaks)
        self.act_avg_run.triggered.connect(self.average_whole_run)

        self.smooth_spin.valueChanged.connect(self._set_smoothing)
        self.baseline_spin.valueChanged.connect(self.chrom.set_baseline)
        self.offset_x_spin.valueChanged.connect(self._set_offsets)
        self.offset_y_spin.valueChanged.connect(self._set_offsets)
        self.floor_spin.valueChanged.connect(self._set_label_floor)
        self.spectrum.sigLabelFloorChanged.connect(self._label_floor_moved)

        self.tree.itemChanged.connect(self._on_tree_changed)
        self.tree.currentItemChanged.connect(self._on_tree_selection)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.btn_collapse.clicked.connect(self.collapse_samples)
        self.btn_none.clicked.connect(lambda: self._bulk_check(lambda ref: False))
        self.btn_ms1.clicked.connect(
            lambda: self._bulk_check(
                lambda ref: ref.channel is not None and ref.channel.info.is_ms1
            )
        )

        self.mode_combo.currentTextChanged.connect(lambda _: self.refresh_chromatogram())
        self.active_combo.currentIndexChanged.connect(self._on_active_changed)
        self.view_combo.currentTextChanged.connect(self._on_view_changed)
        self.contour_view.sigPointPicked.connect(self._on_contour_point)
        self.contour_view.sigRegionPicked.connect(self._on_contour_region)
        self.contour_view.sigRebuildRequested.connect(self._rebuild_contour)

        self.chrom.sigClicked.connect(self._on_chrom_click)
        self.chrom.sigRangeSelected.connect(self._on_chrom_range)
        self.chrom.sigRangeDragging.connect(self._on_chrom_dragging)
        self.chrom.sigBackgroundChanged.connect(self._on_background_changed)
        self.spectrum.sigExtractRequested.connect(self._extract_from_range)

        self.btn_prev.clicked.connect(lambda: self._step_scan(-1))
        self.btn_next.clicked.connect(lambda: self._step_scan(+1))
        self.scan_spin.valueChanged.connect(self._on_scan_spin)
        self.btn_avg.clicked.connect(self._average_selection)

        self.btn_xic.clicked.connect(self._extract_from_form)
        self.btn_xic_clear.clicked.connect(self._clear_xics)
        self.peak_table.cellDoubleClicked.connect(self._peak_double_clicked)

        self.component_list.sigExtractAll.connect(self._extract_components)
        self.component_list.sigShowComponent.connect(self._show_component)
        self.results_panel.sigResultActivated.connect(self._go_to_result)

        self.spectrum.sigIdentifyRequested.connect(self._identify_peak)
        self.mass_calc.sigOverlay.connect(self._overlay_pattern)
        self.library_panel.sigOverlay.connect(self._overlay_pattern)
        self.library_panel.sigClearOverlay.connect(self.spectrum.clear_overlay)
        self.mass_calc.sigClearOverlay.connect(self.spectrum.clear_overlay)
        self.mass_calc.sigSendToFinder.connect(self._send_to_finder)
        self.formula_panel.sigSearch.connect(self._run_formula_search)
        self.formula_panel.sigOverlay.connect(self._overlay_hit)
        self.formula_panel.sigSendToCalculator.connect(
            self.mass_calc.formula_edit.setText)
        self.lipid_panel.sigAnnotate.connect(self._lipid_annotation)
        self.lipid_panel.sigPrecursor.connect(self._lipid_precursor)
        self.lipid_panel.sigFragment.connect(self._lipid_fragment)
        self.lipid_panel.sigMatches.connect(self.spectrum.set_matches)

        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Left), self,
                        activated=lambda: self._step_scan(-1))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Right), self,
                        activated=lambda: self._step_scan(+1))
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.xic_list,
                        activated=self._remove_selected_xic)

    # ---------------------------------------------------------- preferences -- #
    def _restore_settings(self) -> None:
        s = self.settings
        state = s.value("explorer/state")
        if state is not None:
            # a saved arrangement from a version with a different toolbar
            # layout is discarded rather than pinning the old one back
            self.restoreState(state, LAYOUT_VERSION)

        def flag(key: str, default: bool) -> bool:
            return s.value(key, default, type=bool)

        self.act_norm.setChecked(flag("view/normalise", False))
        self.act_mirror.setChecked(flag("view/mirror", False))
        self.act_stack.setChecked(flag("view/stacked", False))
        self.act_overview.setChecked(flag("view/overview", False))
        self.act_labels.setChecked(flag("view/labels", True))
        self.act_apex.setChecked(flag("view/apex", True))
        self.act_relative.setChecked(flag("view/relative_labels", True))
        self.act_legend.setChecked(flag("view/legend", True))
        self.act_select.setChecked(flag("view/select_mode", False))
        self.act_centroid.setChecked(flag("view/centroid", False))
        self.offset_x_spin.setValue(s.value("view/offset_x", 0.0, type=float))
        self.offset_y_spin.setValue(s.value("view/offset_y", 0.0, type=float))
        # kept as the per cent the spin box shows, which is what the reader
        # typed; the pane stores it as a fraction
        self.floor_spin.setValue(s.value(
            "view/label_floor", label_rule.LABEL_MIN_RELATIVE * 100.0,
            type=float))
        self.smooth_spin.setValue(s.value("proc/smooth", 0.0, type=float))
        self.baseline_spin.setValue(s.value("proc/baseline", 0.0, type=float))
        self.xic_tol.setValue(s.value("xic/tolerance", 0.02, type=float))
        self.xic_unit.setCurrentText(s.value("xic/unit", "Da", type=str))
        self.xic_all_channels.setChecked(flag("xic/all_channels", False))
        self.mode_combo.setCurrentText(s.value("chrom/mode", "TIC", type=str))
        self.formula_panel.tol_spin.setValue(s.value("formula/tolerance", 10.0, type=float))
        self.formula_panel.unit_combo.setCurrentText(
            s.value("formula/unit", "ppm", type=str))
        self.formula_panel.adduct_combo.setCurrentText(
            s.value("formula/adduct", "[M-H]-", type=str))
        self.mass_calc.adduct_combo.setCurrentText(
            s.value("formula/adduct", "[M-H]-", type=str))
        self.formula_panel.even_electron.setChecked(flag("formula/even_electron", True))
        self.formula_panel.golden_rules.setChecked(flag("formula/golden_rules", True))
        self.formula_panel.use_isotopes.setChecked(flag("formula/use_isotopes", True))
        stored_ranges = s.value("formula/ranges", "", type=str)
        if stored_ranges:
            try:
                import json as _json
                self._apply_element_ranges(_json.loads(stored_ranges))
            except (ValueError, TypeError):
                pass

        # push the restored state through (signals are already connected)
        self._set_select_mode(self.act_select.isChecked())
        self._set_normalised(self.act_norm.isChecked())
        self._set_mirror(self.act_mirror.isChecked())
        self.chrom.set_stacked(self.act_stack.isChecked())
        self._set_overview(self.act_overview.isChecked())
        self.spectrum.set_labels_enabled(self.act_labels.isChecked())
        self.chrom.set_apex_labels(self.act_apex.isChecked())
        self._set_relative_labels(self.act_relative.isChecked())
        self.chrom.set_legend_visible(self.act_legend.isChecked())
        self._set_centroid(self.act_centroid.isChecked())
        self._set_offsets()
        self._set_label_floor(self.floor_spin.value())
        self._set_smoothing(self.smooth_spin.value())
        self.chrom.set_baseline(self.baseline_spin.value())

    def save_settings(self) -> None:
        s = self.settings
        s.setValue("explorer/state", self.saveState(LAYOUT_VERSION))
        s.setValue("view/normalise", self.act_norm.isChecked())
        s.setValue("view/mirror", self.act_mirror.isChecked())
        s.setValue("view/stacked", self.act_stack.isChecked())
        s.setValue("view/overview", self.act_overview.isChecked())
        s.setValue("view/labels", self.act_labels.isChecked())
        s.setValue("view/apex", self.act_apex.isChecked())
        s.setValue("view/relative_labels", self.act_relative.isChecked())
        s.setValue("view/legend", self.act_legend.isChecked())
        s.setValue("view/select_mode", self.act_select.isChecked())
        s.setValue("view/centroid", self.act_centroid.isChecked())
        s.setValue("view/offset_x", self.offset_x_spin.value())
        s.setValue("view/offset_y", self.offset_y_spin.value())
        s.setValue("view/label_floor", self.floor_spin.value())
        s.setValue("proc/smooth", self.smooth_spin.value())
        s.setValue("proc/baseline", self.baseline_spin.value())
        s.setValue("xic/tolerance", self.xic_tol.value())
        s.setValue("xic/unit", self.xic_unit.currentText())
        s.setValue("xic/all_channels", self.xic_all_channels.isChecked())
        s.setValue("chrom/mode", self.mode_combo.currentText())
        s.setValue("formula/tolerance", self.formula_panel.tol_spin.value())
        s.setValue("formula/unit", self.formula_panel.unit_combo.currentText())
        s.setValue("formula/adduct", self.formula_panel.adduct_combo.currentText())
        s.setValue("formula/even_electron", self.formula_panel.even_electron.isChecked())
        s.setValue("formula/golden_rules", self.formula_panel.golden_rules.isChecked())
        s.setValue("formula/use_isotopes", self.formula_panel.use_isotopes.isChecked())
        import json as _json
        s.setValue("formula/ranges", _json.dumps(self.formula_panel.ranges()))

    def _apply_element_ranges(self, ranges: dict) -> None:
        """Write stored element ranges back into the finder's table."""
        table = self.formula_panel.elements
        for row in range(table.rowCount()):
            element = table.item(row, 0).text()
            low, high = ranges.get(element, (0, 0))
            table.item(row, 1).setText(str(int(low)))
            table.item(row, 2).setText(str(int(high)))

    def _last_dir(self) -> str:
        return self.settings.value("io/last_dir", "", type=str)

    def _remember_dir(self, path: str) -> None:
        self.settings.setValue("io/last_dir", os.path.dirname(path))

    # -------------------------------------------------------- samples/tree --- #
    def rebuild_tree(self) -> None:
        """Rebuild the sample and channel tree from the session."""
        # A node keeps whatever the user had set; a node that was never in the
        # tree is new, and a new sample comes in with its TIC shown.
        previous = self._tree_items()
        checked = {k for k, item in previous.items()
                   if item.checkState(0) == QtCore.Qt.CheckState.Checked}
        self.tree.blockSignals(True)
        self.tree.clear()
        self.refs.clear()

        #: the newest infusion opened this time round, to land on afterwards
        arrived: ChannelRef | None = None
        by_file: dict[str, QtWidgets.QTreeWidgetItem] = {}
        for entry in self.session.entries:
            if not entry.is_loaded:
                continue
            file_item = by_file.get(entry.path)
            if file_item is None:
                file_item = QtWidgets.QTreeWidgetItem(self.tree, [entry.filename])
                font = file_item.font(0)
                font.setBold(True)
                file_item.setFont(0, font)
                by_file[entry.path] = file_item

            sample = entry.sample
            verdict = self.verdict(entry)
            instrument = sample.instrument + (", infusion" if verdict else "")
            sample_item = QtWidgets.QTreeWidgetItem(
                file_item, [f"{entry.name}  ({instrument})"]
            )
            if verdict:
                sample_item.setToolTip(0, verdict.reason)
            if entry.problem:
                # in front, where a narrow dock cannot cut it off
                sample_item.setText(0, "⚠ " + sample_item.text(0))
                sample_item.setToolTip(0, entry.problem)
            tic = ChannelRef(entry, None)
            self._add_leaf(sample_item, "Sample TIC (all channels)", tic,
                           checked=tic.key in checked or tic.key not in previous)
            # an infusion's own channel comes in checked and becomes the
            # active one; nothing else about a new sample changes
            wanted = verdict.channel_index if verdict else None
            for channel in sample.channels:
                ref = ChannelRef(entry, channel)
                new = ref.key not in previous
                on_arrival = new and channel.index == wanted
                self._add_leaf(sample_item, channel.info.label, ref,
                               checked=ref.key in checked or on_arrival)
                if on_arrival:
                    arrived = ref
            sample_item.setExpanded(True)
            file_item.setExpanded(True)
        self.tree.blockSignals(False)
        self._rebuild_active_combo()
        self.refresh_chromatogram()
        if arrived is not None:
            self.open_as_infusion(arrived)

    # -------------------------------------------------------------- infusion #
    def verdict(self, entry: SampleEntry) -> InfusionVerdict:
        """
        Whether this sample is a direct infusion.

        The tree asks for every sample it draws and it is rebuilt on every
        file opened, so the measurement is the module's cached one: it reads
        chromatograms only, but on an eighty-one channel sample that is still
        eighty-one of them.
        """
        try:
            return verdict_for(entry.sample)
        except Exception as exc:  # a reader that cannot say is not one
            return InfusionVerdict(
                False, f"the run could not be read: {_first_line(exc)}")

    def open_as_infusion(self, ref: ChannelRef) -> None:
        """
        Land on an infusion's own channel, showing the whole run at once.

        An infusion has no chromatography to pick a range over, so the
        chromatogram — which is still drawn, and is still the TIC over time —
        has nothing to point at. The average of every scan is the spectrum,
        and it is what Explain, the library search and a pin all then work on.
        """
        index = self.active_combo.findData(ref.key)
        if index < 0:
            return
        self.active_combo.blockSignals(True)
        self.active_combo.setCurrentIndex(index)
        self.active_combo.blockSignals(False)
        self._sync_active_ref()
        self.average_whole_run()

    def average_whole_run(self) -> None:
        """Every scan of the active channel, averaged into one spectrum."""
        ref = self.active_ref
        channel = ref.channel if ref else None
        if channel is None:
            self._update_status("Pick an active channel first.")
            return
        window = run_range(channel)
        if window is None:
            self._update_status(f"{ref.label} has no scans to average.")
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            self._show_average(*window,
                               tag=" (infusion)" if self.verdict(ref.entry) else "")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _tree_items(self) -> dict:
        out = {}
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            key = it.value().data(0, ROLE_REF)
            if key:
                out[key] = it.value()
            it += 1
        return out

    def _add_leaf(self, parent, text: str, ref: ChannelRef, checked: bool) -> None:
        item = QtWidgets.QTreeWidgetItem(parent, [text])
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            0,
            QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked,
        )
        item.setData(0, ROLE_REF, ref.key)
        if ref.entry.problem:
            item.setToolTip(0, ref.entry.problem)
        self.refs[ref.key] = ref

    def clear_views(self) -> None:
        """Drop everything that referred to samples that are no longer open."""
        self.refs.clear()
        self.xic_defs.clear()
        self.active_ref = None
        self._background_cache.clear()
        self._contour_cache.clear()
        self.tree.clear()
        self.xic_list.clear()
        self.active_combo.clear()
        self.chrom.clear_traces()
        self.chrom.clear_peak_markers()
        self.chrom.clear_background_range()
        self.spectrum.clear_traces()
        self.peak_table.setRowCount(0)
        self.results_panel.clear()
        self.sample_info.clear()
        self._update_status("No files open.")

    def _refresh_components(self) -> None:
        self.component_list.set_components(self.session.method.components)

    # ----------------------------------------------------------------- tree -- #
    def _checked_refs(self) -> list[ChannelRef]:
        out = []
        it = QtWidgets.QTreeWidgetItemIterator(
            self.tree, QtWidgets.QTreeWidgetItemIterator.IteratorFlag.Checked
        )
        while it.value():
            key = it.value().data(0, ROLE_REF)
            if key in self.refs:
                out.append(self.refs[key])
            it += 1
        return out

    def _checked_samples(self) -> list[ChannelRef]:
        """One reference per checked sample, in tree order."""
        seen, out = set(), []
        for ref in self._checked_refs():
            if ref.entry.key not in seen:
                seen.add(ref.entry.key)
                out.append(ref)
        if out:
            return out
        # nothing checked: fall back to every loaded sample
        return [ChannelRef(e, None) for e in self.session.loaded_entries]

    def collapse_samples(self) -> None:
        """Fold every sample shut, leaving the file names visible."""
        self.tree.collapseAll()
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setExpanded(True)
        self._update_status("Samples collapsed.")

    def _bulk_check(self, predicate) -> None:
        self.tree.blockSignals(True)
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            key = item.data(0, ROLE_REF)
            if key in self.refs:
                item.setCheckState(
                    0,
                    QtCore.Qt.CheckState.Checked if predicate(self.refs[key])
                    else QtCore.Qt.CheckState.Unchecked,
                )
            it += 1
        self.tree.blockSignals(False)
        self._rebuild_active_combo()
        self.refresh_chromatogram()

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, ROLE_REF) is not None:
                item.setHidden(bool(needle) and needle not in item.text(0).lower())
            it += 1

    def _on_tree_changed(self, item, column) -> None:
        self._rebuild_active_combo()
        self.refresh_chromatogram()

    def _on_tree_selection(self, current, previous) -> None:
        if current is None:
            return
        key = current.data(0, ROLE_REF)
        if key in self.refs:
            index = self.active_combo.findData(key)
            if index >= 0:
                self.active_combo.setCurrentIndex(index)

    # -------------------------------------------------------- active channel - #
    def _rebuild_active_combo(self) -> None:
        previous = self.active_combo.currentData()
        self.active_combo.blockSignals(True)
        self.active_combo.clear()
        candidates = [r for r in self._checked_refs() if r.channel is not None]
        if not candidates:
            candidates = [r for r in self.refs.values() if r.channel is not None]
        for ref in candidates:
            self.active_combo.addItem(ref.full_label, ref.key)
        index = self.active_combo.findData(previous)
        self.active_combo.setCurrentIndex(index if index >= 0 else 0)
        self.active_combo.blockSignals(False)
        self._sync_active_ref()

    def _sync_active_ref(self) -> None:
        key = self.active_combo.currentData()
        self.active_ref = self.refs.get(key) if key else None
        channel = self.active_ref.channel if self.active_ref else None
        self.scan_spin.blockSignals(True)
        self.scan_spin.setMaximum(max(channel.info.n_scans if channel else 1, 1))
        self.scan_spin.blockSignals(False)
        verdict = self.verdict(self.active_ref.entry) if self.active_ref else None
        self.infusion_label.setText("infusion" if verdict else "")
        self.infusion_label.setToolTip(verdict.reason if verdict else "")
        if self.active_ref is not None:
            self.sample_info.show_sample(self.active_ref.sample, channel)

    def _on_active_changed(self, _index: int) -> None:
        self._sync_active_ref()
        if self.active_ref and self.active_ref.channel:
            self._show_scan(min(self.current_scan,
                                self.active_ref.channel.info.n_scans - 1))
        if self._contour_showing:
            self._show_contour()

    # ----------------------------------------------------------- contour -- #
    @property
    def _contour_showing(self) -> bool:
        return self.top_stack.currentIndex() == 1

    def _on_view_changed(self, name: str) -> None:
        self.top_stack.setCurrentIndex(1 if name == VIEW_CONTOUR else 0)
        # TIC against BPC is a choice about a chromatogram; on a surface with
        # neither axis summed away it means nothing, so it goes away
        self.mode_combo.setVisible(not self._contour_showing)
        if self._contour_showing and self.contour_view.contour().is_empty:
            self._show_contour()

    def _show_contour(self, rt_range=None, mz_range=None) -> None:
        """
        Build the surface for the active channel, or show the one already
        built for it.

        Reading every scan is the cost, so it is cached against the channel
        and the ranges it was built over, and a second look at the same
        channel is instant. It is also cancellable: a partial surface of the
        first half of a run still shows what is in the first half.
        """
        ref = self.active_ref
        channel = ref.channel if ref else None
        if channel is None:
            self.contour_view.set_contour(Contour(
                note="Pick an active channel to build a contour."))
            return

        key = (ref.key, rt_range, mz_range)
        cached = self._contour_cache.get(key)
        if cached is not None:
            self.contour_view.set_contour(cached, ref.label)
            return

        progress = QtWidgets.QProgressDialog(
            f"Reading {channel.info.n_scans:,} scans…", "Cancel", 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)

        def tick(done: int, total: int):
            progress.setValue(int(done / max(total, 1) * 100))
            QtWidgets.QApplication.processEvents()
            return not progress.wasCanceled()

        try:
            contour = build_contour(channel, rt_range=rt_range,
                                    mz_range=mz_range, progress=tick)
        except Exception as exc:
            progress.close()
            self._update_status(ref.entry.problem or f"Contour failed: {_first_line(exc)}")
            return
        progress.close()
        self._contour_cache[key] = contour
        while len(self._contour_cache) > CONTOUR_CACHE:
            self._contour_cache.pop(next(iter(self._contour_cache)))
        self.contour_view.set_contour(contour, ref.label)
        self._update_status(f"Contour of {ref.label}: {contour.scans:,} scans")

    def _rebuild_contour(self) -> None:
        """Read the scans again over what is on screen, at the full grid."""
        rt_lo, rt_hi, mz_lo, mz_hi = self.contour_view.view_ranges()
        self._show_contour(rt_range=(rt_lo, rt_hi), mz_range=(mz_lo, mz_hi))

    def _on_contour_point(self, rt: float, _mz: float) -> None:
        """A click on the surface shows the spectrum underneath it."""
        channel = self.active_ref.channel if self.active_ref else None
        if channel is not None:
            self._show_scan(channel.scan_at_rt(rt))

    def _on_contour_region(self, rt_lo: float, rt_hi: float,
                           mz_lo: float, mz_hi: float) -> None:
        """
        The rectangle on screen, as a chromatogram and a spectrum.

        Both come from the reader rather than from the grid. The grid is a
        picture: its m/z bins are wider than the instrument's steps and its
        rows may be several scans averaged together, so a number taken off it
        would be neither the instrument's nor reproducible from the file.
        """
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        self._add_xic(mz_lo, mz_hi, f"m/z {mz_lo:.3f}–{mz_hi:.3f}")
        self._show_average(rt_lo, rt_hi)
        self.view_combo.setCurrentText(VIEW_CHROMATOGRAM)

    def _activate_trace_key(self, key: str) -> None:
        """When a stacked pane is clicked, make its channel the active one."""
        if not key:
            return
        index = self.active_combo.findData(key)
        if index >= 0 and index != self.active_combo.currentIndex():
            self.active_combo.setCurrentIndex(index)

    # ---------------------------------------------------------- chromatogram - #
    def refresh_chromatogram(self) -> None:
        refs = self._checked_refs()
        mode = self.mode_combo.currentText()
        traces: list[Trace] = []
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for i, ref in enumerate(refs):
                if ref.channel is None:
                    x, y = ref.sample.tic()
                    label = f"{ref.label} (TIC)"
                elif mode == "BPC":
                    x, y = ref.channel.bpc()
                    label = f"{ref.label} (BPC)"
                else:
                    x, y = ref.channel.tic()
                    label = f"{ref.label} (TIC)"
                traces.append(Trace(ref.key, label, x, y, colour(i), ref.channel))

            for j, xic in enumerate(self.xic_defs):
                traces.append(
                    Trace(xic["key"], xic["label"], xic["x"], xic["y"],
                          colour(len(refs) + j), xic["channel"])
                )
            self.chrom.set_traces(traces)
            self.chrom.autoscale()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._update_status(
            f"{len(traces)} trace(s) on the chromatogram · {mode} mode"
            + (f" · active channel: {self.active_ref.label}" if self.active_ref else "")
        )

    def _on_chrom_click(self, key: str, rt: float) -> None:
        self._activate_trace_key(key)
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            self._update_status("Pick an active channel to see the spectrum.")
            return
        self._show_scan(channel.scan_at_rt(rt))

    def _on_chrom_range(self, key: str, rt0: float, rt1: float) -> None:
        self._activate_trace_key(key)
        if self.active_ref is None or self.active_ref.channel is None:
            return
        self._show_average(rt0, rt1)
        self._report_integration(rt0, rt1)

    def _on_chrom_dragging(self, key: str, rt0: float, rt1: float) -> None:
        """
        Live preview while the selection is being dragged or resized: the
        spectrum follows the highlight instead of waiting for the mouse to be
        released.
        """
        if self.active_ref is None or self.active_ref.channel is None:
            return
        self._show_average(rt0, rt1, live=True)

    def _report_integration(self, rt0: float, rt1: float) -> None:
        traces = [t for t in self.chrom.traces if t.source is not None]
        if not traces:
            return
        target = next(
            (t for t in traces
             if self.active_ref and t.source is self.active_ref.channel),
            traces[0],
        )
        conditioned = self.chrom.conditioned(target.key)
        x, y = conditioned if conditioned else (target.x, target.y)
        stats = integrate(x, y, rt0, rt1)
        snr = signal_to_noise(x, y, rt0, rt1)
        self._update_status(
            f"{target.label} · {rt0:.3f}–{rt1:.3f} min · "
            f"area {stats['area']:,.0f} · height {stats['height']:,.0f} · "
            f"apex {stats['apex_rt']:.3f} min · S/N ≈ {snr:.0f} · "
            f"{stats['n_points']} scans"
        )

    # -------------------------------------------------------------- background #
    def _set_background(self) -> None:
        selection = self.chrom.selected_range()
        if selection is None:
            self._update_status(
                "Select the blank range on the chromatogram (Shift + drag) "
                "before setting the background."
            )
            return
        self.chrom.set_background_range(*selection)

    def _clear_background(self) -> None:
        self.chrom.clear_background_range()

    def _on_background_changed(self) -> None:
        self._background_cache.clear()
        window = self.chrom.background_range()
        if window is None:
            self.bg_label.setText("")
            self._update_status("Background subtraction off.")
        else:
            self.bg_label.setText(f"background {window[0]:.2f}–{window[1]:.2f} min")
            self._update_status(
                f"Background set at {window[0]:.3f}–{window[1]:.3f} min; "
                "new spectra come out with it subtracted."
            )

    def _background_spectrum(self, channel: Channel):
        window = self.chrom.background_range()
        if window is None:
            return None
        key = (id(channel), round(window[0], 5), round(window[1], 5))
        if key not in self._background_cache:
            self._background_cache[key] = channel.spectrum_rt_range(*window)
        return self._background_cache[key]

    def _apply_background(self, channel: Channel, mz: np.ndarray,
                          intensity: np.ndarray) -> tuple[np.ndarray, bool]:
        """
        Subtract the average blank spectrum. In profile data the m/z grids of
        the spectrum and of the blank do not line up, so the blank is
        interpolated onto the spectrum's grid before subtraction.
        """
        background = self._background_spectrum(channel)
        if background is None:
            return intensity, False
        bmz, bi = background
        if bmz.size < 2 or mz.size == 0:
            return intensity, False
        interpolated = np.interp(mz, bmz, bi, left=0.0, right=0.0)
        return np.clip(intensity - interpolated, 0.0, None), True

    # ---------------------------------------------------------------- spectrum #
    def _recalibrate_mz(self, mz):
        """
        The spectrum's m/z axis with this injection's correction applied.

        Returns the axis and the words for the title. The title has to say so:
        a mass axis that has been moved and does not admit it is the one thing
        worse than a mass axis that is wrong.
        """
        entry = self.active_ref.entry if self.active_ref else None
        correction = (self.session.correction_for(entry.key)
                      if entry is not None else None)
        if correction is None or mz.size == 0:
            return mz, ""
        middle = float(np.median(mz))
        return (correction.apply(mz),
                f" · recalibrated {float(correction.ppm_at(middle)):+.1f} ppm")

    def _show_scan(self, scan: int) -> None:
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        self.current_scan = int(np.clip(scan, 0, max(channel.info.n_scans - 1, 0)))
        try:
            mz, intensity = channel.spectrum(self.current_scan)
        except Exception as exc:
            self._spectrum_unreadable(exc)
            return
        intensity, subtracted = self._apply_background(channel, mz, intensity)
        rt = channel.rt_at_scan(self.current_scan)
        mz, recalibrated = self._recalibrate_mz(mz)
        self.spectrum.set_traces(self._with_pins(
            Trace("spec", "spectrum", mz, intensity, "#1f77b4", channel)))
        self.spectrum.autoscale()
        self.spectrum.set_title(
            f"{self.active_ref.label} · scan {self.current_scan + 1}"
            f"/{channel.info.n_scans} · RT {rt:.3f} min"
            + (" · background subtracted" if subtracted else "")
            + recalibrated
        )
        self.scan_spin.blockSignals(True)
        self.scan_spin.setValue(self.current_scan + 1)
        self.scan_spin.blockSignals(False)
        self.rt_label.setText(f"RT {rt:.3f} min")
        self.chrom.mark(rt)
        self.refresh_comparison()
        self._fill_peak_table()

    def _show_average(self, rt0: float, rt1: float, live: bool = False,
                      tag: str = "") -> None:
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        try:
            mz, intensity = channel.spectrum_rt_range(rt0, rt1)
        except Exception as exc:
            self._spectrum_unreadable(exc)
            return
        intensity, subtracted = self._apply_background(channel, mz, intensity)
        first, last = channel.scans_in_range(rt0, rt1)
        mz, recalibrated = self._recalibrate_mz(mz)
        self.spectrum.set_traces(self._with_pins(
            Trace("spec", "average spectrum", mz, intensity, "#d62728", channel)))
        if not live:
            self.spectrum.autoscale()
        # the scan numbers are what says which part of the run was taken;
        # a whole-run average has no other part to be told from, so the tag
        # replaces them rather than sitting beside them
        scans = f" ({first + 1}–{last + 1})" if not tag else ""
        self.spectrum.set_title(
            f"{self.active_ref.label} · average of {last - first + 1} "
            f"scans{tag}{scans} · RT {min(rt0, rt1):.3f}–{max(rt0, rt1):.3f} min"
            + (" · background subtracted" if subtracted else "")
            + recalibrated
        )
        self.rt_label.setText(f"RT {min(rt0, rt1):.3f}–{max(rt0, rt1):.3f} min")
        self.chrom.mark(None)
        if not live:  # too slow to rebuild on every mouse move of a drag
            self.refresh_comparison()
            self._fill_peak_table()

    def _spectrum_unreadable(self, error: Exception) -> None:
        """
        Say, where the spectrum would be, why there is none.

        A .wiff whose .wiff.scan is not beside it opens, draws its
        chromatograms and throws on the first spectrum. Left to Qt the
        exception went to a console nobody has and the pane stayed as it
        was: nothing scan by scan, nothing for a selected range, and no
        word why — found on a folder where one companion had been renamed
        by hand. The title of the pane is where the eye already is, and
        the entry's own diagnosis names the file that is missing.
        """
        problem = self.active_ref.entry.problem if self.active_ref else ""
        if not problem:
            text = str(error).strip()
            problem = ("the spectrum could not be read: "
                       + (text.splitlines()[0] if text else type(error).__name__))
        self.spectrum.set_traces(list(self.pinned_spectra))
        # the pane's title is one line: the diagnosis, not the advice
        self.spectrum.set_title(problem.split(";")[0].split(". ")[0])
        self.spectrum.setToolTip(problem)
        self.rt_label.setText("—")
        self.chrom.mark(None)
        self.refresh_comparison()
        self._fill_peak_table()
        self._update_status(problem)

    def _average_selection(self) -> None:
        selection = self.chrom.selected_range()
        if selection is None:
            self._update_status(
                "Select a range on the chromatogram first (Shift + drag)."
            )
            return
        self._show_average(*selection)
        self._report_integration(*selection)

    def _step_scan(self, delta: int) -> None:
        if self.active_ref and self.active_ref.channel:
            self._show_scan(self.current_scan + delta)

    def _on_scan_spin(self, value: int) -> None:
        self._show_scan(value - 1)

    def _fill_peak_table(self) -> None:
        peaks = self.spectrum.peaks_of_current(max_peaks=60)
        base = peaks[0][1] if peaks else 1.0
        self.peak_table.setRowCount(len(peaks))
        for row, (mz, intensity) in enumerate(peaks):
            for col, text in enumerate(
                (f"{mz:.4f}", f"{intensity:,.0f}", f"{intensity / base * 100:.1f}")
            ):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.peak_table.setItem(row, col, item)

    def _peak_double_clicked(self, row: int, _column: int) -> None:
        item = self.peak_table.item(row, 0)
        if item:
            self.mass_calc.set_measured(float(item.text()))
            self.xic_mz.setText(item.text())
            self._extract_from_form()

    # ------------------------------------------------------------------ XIC -- #
    def _xic_targets(self) -> list[ChannelRef]:
        if self.xic_all_channels.isChecked():
            targets = [r for r in self._checked_refs() if r.channel is not None]
            if targets:
                return targets
        return [self.active_ref] if self.active_ref and self.active_ref.channel else []

    def _extract_from_form(self) -> None:
        text = self.xic_mz.text().replace(";", ",")
        values = []
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(float(part))
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid m/z", f"Not a number: {part}")
                return
        if not values:
            return
        tol = self.xic_tol.value()
        unit = self.xic_unit.currentText()
        for mz in values:
            half = mz * tol * 1e-6 if unit == "ppm" else tol
            self._add_xic(mz - half, mz + half, f"XIC {mz:.4f} ±{tol:g} {unit}")

    def _extract_from_range(self, mz0: float, mz1: float) -> None:
        lo, hi = sorted((mz0, mz1))
        self._add_xic(lo, hi, f"XIC {lo:.4f}–{hi:.4f}")

    def _add_xic(self, mz_lo: float, mz_hi: float, label: str,
                 targets: list[ChannelRef] | None = None) -> None:
        targets = targets if targets is not None else self._xic_targets()
        if not targets:
            self._update_status("Pick an active channel before extracting an XIC.")
            return
        unreadable: list[str] = []
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for ref in targets:
                try:
                    x, y = ref.channel.xic_range(mz_lo, mz_hi)
                except Exception as exc:
                    unreadable.append(ref.entry.problem
                                      or f"{ref.label}: {_first_line(exc)}")
                    continue
                if x.size == 0:
                    continue
                key = f"xic|{ref.key}|{mz_lo:.5f}|{mz_hi:.5f}"
                if any(d["key"] == key for d in self.xic_defs):
                    continue
                full = f"{ref.label} · {label}"
                self.xic_defs.append(
                    {"key": key, "label": full, "x": x, "y": y, "channel": ref.channel}
                )
                self.xic_list.addItem(full)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.refresh_chromatogram()
        if unreadable:
            self._update_status(unreadable[0])

    def _remove_selected_xic(self) -> None:
        row = self.xic_list.currentRow()
        if 0 <= row < len(self.xic_defs):
            self.xic_defs.pop(row)
            self.xic_list.takeItem(row)
            self.refresh_chromatogram()

    def _clear_xics(self) -> None:
        self.xic_defs.clear()
        self.xic_list.clear()
        self.refresh_chromatogram()

    # ------------------------------------------------------------ components -- #
    def _integrate_component(self, ref: ChannelRef, channel: Channel,
                            component: Component) -> Result:
        mz_lo, mz_hi = component.mass_window()
        mz_text = f"{(mz_lo + mz_hi) / 2:.4f}"
        # the window moves, the reader's arithmetic does not — see
        # quantify.extract_xic
        correction = self.session.correction_for(ref.entry.key)
        if correction is not None:
            mz_lo, mz_hi = (float(correction.undo(mz_lo)),
                            float(correction.undo(mz_hi)))

        def empty(note: str) -> Result:
            return Result(
                component=component.name, sample=ref.alias,
                channel=channel.info.short_label, mz=mz_text,
                rt=component.rt or 0.0, area=0.0, height=0.0, width=0.0,
                snr=0.0, note=note,
            )

        try:
            x, y = channel.xic_range(mz_lo, mz_hi)
        except Exception as exc:
            return empty(ref.entry.problem or _first_line(exc))
        if x.size == 0:
            return empty("no data")

        window = component.rt_window()
        if window is None:
            mask = np.ones(x.size, dtype=bool)
        else:
            mask = (x >= window[0]) & (x <= window[1])
            # Do not fall back to scanning the whole run when the window is not
            # covered: returning a peak from another time would be a wrong
            # result, not an approximate one.
            if mask.sum() < 3:
                return empty(f"channel does not cover {window[0]:.2f}–{window[1]:.2f} min")

        peaks = detect_peaks(x[mask], y[mask], min_relative=0.05, min_snr=3.0)
        if not peaks:
            return empty("no peak above noise")

        peak = peaks[0]
        return Result(
            component=component.name, sample=ref.alias,
            channel=channel.info.short_label, mz=mz_text,
            rt=peak.apex_rt, area=peak.area, height=peak.height,
            width=peak.width, snr=peak.snr,
            start_rt=peak.start_rt, end_rt=peak.end_rt,
        )

    def _extract_components(self, components: list[Component]) -> None:
        if not components:
            self._update_status("No valid component in the list.")
            return
        samples = self._checked_samples()
        if not samples:
            self._update_status("Open at least one file before extracting.")
            return

        total = len(components) * len(samples)
        progress = QtWidgets.QProgressDialog(
            "Extracting and integrating…", "Cancel", 0, total, self
        )
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)

        results: list[Result] = []
        done = 0
        for ref in samples:
            for component in components:
                if progress.wasCanceled():
                    break
                channel = match_channel(ref.sample, component)
                if channel is None:
                    results.append(Result(
                        component=component.name, sample=ref.alias, channel="—",
                        mz=f"{component.target_mz:.4f}", rt=component.rt or 0.0,
                        area=0.0, height=0.0, width=0.0, snr=0.0,
                        note="no matching channel",
                    ))
                else:
                    results.append(self._integrate_component(ref, channel, component))
                done += 1
                progress.setValue(done)
                QtWidgets.QApplication.processEvents()
            if progress.wasCanceled():
                break
        progress.setValue(total)

        self.results_panel.set_results(results)
        self.tabs.setCurrentWidget(self.results_panel)
        found = sum(1 for r in results if r.area > 0)
        self._update_status(
            f"{len(results)} extractions across {len(samples)} sample(s); "
            f"{found} with a detected peak."
        )

    def _show_component(self, component: Component) -> None:
        """Plot one component's XIC across every checked sample."""
        samples = self._checked_samples()
        targets = []
        for ref in samples:
            channel = match_channel(ref.sample, component)
            if channel is not None:
                targets.append(ChannelRef(ref.entry, channel))
        if not targets:
            self._update_status(f"No channel matches {component.name}.")
            return
        mz_lo, mz_hi = component.mass_window()
        self._add_xic(mz_lo, mz_hi,
                      f"{component.name} {component.target_mz:.4f}", targets)
        window = component.rt_window()
        if window:
            self.chrom.set_x_range(*window)

    def _go_to_result(self, result: Result) -> None:
        """Bring the chromatogram to the peak of a results row."""
        if result.end_rt > result.start_rt:
            span = max(result.end_rt - result.start_rt, 0.05)
            self.chrom.set_x_range(result.start_rt - span, result.end_rt + span)
            self.chrom.mark(result.rt)
        self._update_status(
            f"{result.component} · {result.sample} · {result.channel} · "
            f"RT {result.rt:.3f} min · area {result.area:,.0f}"
        )

    # ------------------------------------------------------ chromatogram peaks #
    def _detect_peaks(self) -> None:
        traces = self.chrom.traces
        if not traces:
            self._update_status("Nothing on the chromatogram to integrate.")
            return
        results: list[Result] = []
        markers = []
        for trace in traces:
            conditioned = self.chrom.conditioned(trace.key)
            x, y = conditioned if conditioned else (trace.x, trace.y)
            peaks = detect_peaks(x, y, min_relative=0.05, min_snr=3.0)
            markers.extend(peaks)
            ref = self.refs.get(trace.key)
            sample_name = ref.alias if ref else "—"
            channel_name = (
                trace.source.info.short_label if trace.source is not None else "TIC"
            )
            for peak in peaks:
                results.append(
                    Result(
                        component="(detected)", sample=sample_name,
                        channel=channel_name, mz="—", rt=peak.apex_rt,
                        area=peak.area, height=peak.height, width=peak.width,
                        snr=peak.snr, trace_key=trace.key,
                        start_rt=peak.start_rt, end_rt=peak.end_rt,
                    )
                )
        self.chrom.set_peak_markers(markers)
        self.results_panel.set_results(results)
        self.tabs.setCurrentWidget(self.results_panel)
        self._update_status(
            f"{len(results)} peak(s) integrated across {len(traces)} trace(s)."
        )

    # ------------------------------------------------------------- chemistry -- #
    def _identify_peak(self, mz: float) -> None:
        """Right-click on a spectrum peak: send it to every chemistry panel."""
        self.mass_calc.set_measured(mz)
        self.formula_panel.set_target(mz)
        self.lipid_panel.set_target(mz)
        self.tabs.setCurrentWidget(self.formula_panel)
        self._update_status(f"m/z {mz:.4f} sent to the formula finder.")

    def _lipid_annotation(self, name: str, formula: str, lm_id: str) -> None:
        """A structure picked in the LIPID MAPS tab feeds the chemistry panels."""
        self.mass_calc.formula_edit.setText(formula)
        self._update_status(f"{name} · {formula} · {lm_id}")

    def _lipid_precursor(self, name: str, formula: str, lm_id: str,
                         adduct: str, mz: float) -> None:
        """
        An ion picked in the LIPID MAPS tab becomes a component.

        This is the reverse of annotation: the compound is known and what is
        wanted is the channel to extract it on. The component carries the
        formula and the LM_ID, so where the mass came from stays on the record.
        """
        method = self.session.method
        if method.by_name(name) is not None:
            self.xic_mz.setText(f"{mz:.4f}")
            self._update_status(
                f"{name} is already in the method — {mz:.4f} put in the "
                "manual XIC box instead.")
            return
        method.components.append(Component(
            name=name, precursor=mz, formula=formula, adduct=adduct,
            lm_id=lm_id, tolerance=method.tolerance, unit=method.unit,
        ))
        self.session.notify_method_changed()
        self.mass_calc.formula_edit.setText(formula)
        self.xic_mz.setText(f"{mz:.4f}")
        self._update_status(
            f"{name} {adduct} — m/z {mz:.4f} added to the method "
            f"({len(method.components)} component(s)).")

    def explain_spectrum(self) -> None:
        """Send the spectrum on screen to be scored against LIPID MAPS."""
        current = self._current_spectrum()
        if current is None:
            self._update_status("Show a spectrum first.")
            return
        mz, intensity = current
        if not self.act_centroid.isChecked():
            # centroiding what is already sticks merges neighbours and moves
            # the masses, which is worse than not centroiding at all
            mz, intensity = centroid_spectrum(mz, intensity)
        precursor = None
        if self.active_ref is not None and self.active_ref.channel is not None:
            precursor = self.active_ref.channel.info.precursor
        self.lipid_panel.set_spectrum(mz, intensity, precursor)
        self.show_panel_named("LIPID MAPS")
        self.lipid_panel.explain_spectrum()

    def _library_spectrum(self):
        """
        The spectrum on screen as the library panel wants it.

        Centroided sticks, the active channel's precursor, and a mapping of
        where they came from. The last is for the panel's *Add spectrum to
        library…*: a record has to say which file, sample, channel and scans
        it was made from, and the Explorer is the only place that knows. The
        pane's own title already reads "sample · channel · average of n scans
        (a–b) · RT x–y", which is exactly the provenance a record wants, so
        it is passed as written rather than assembled a second time here.
        """
        current = self._current_spectrum()
        if current is None:
            self._update_status("Show a spectrum first.")
            return None
        mz, intensity = current
        if not self.act_centroid.isChecked():
            mz, intensity = centroid_spectrum(mz, intensity)
        precursor = None
        context = {"title": self.spectrum.title}
        if self.active_ref is not None:
            context["file"] = self.active_ref.filename
            context["sample"] = self.active_ref.alias
            channel = self.active_ref.channel
            if channel is not None:
                info = channel.info
                precursor = info.precursor
                context["channel"] = info.label
                context["polarity"] = info.polarity
                context["collision_energy"] = info.collision_energy
        return mz, intensity, precursor, context

    def _lipid_fragment(self, name: str, lm_id: str, route: str,
                        mz: float) -> None:
        """
        A predicted fragment goes to the manual XIC, not into the method.

        A precursor from the database is arithmetic on a known formula; a
        fragment is a candidate. Extracting it against a real sample is how it
        earns a place in a method, so that is what this offers.
        """
        self.xic_mz.setText(f"{mz:.4f}")
        self.show_panel_named("Manual XIC")
        self._update_status(
            f"{name}: candidate fragment {mz:.4f} ({route}) — extract it to "
            "see whether the sample agrees.")

    def _send_to_finder(self, mz: float, adduct: str) -> None:
        self.formula_panel.set_target(mz, adduct)
        self.tabs.setCurrentWidget(self.formula_panel)

    # -- pinned spectra --------------------------------------------------------- #
    #: colours for the spectra held for comparison; the live one stays blue
    PIN_COLOURS = ("#e08a1e", "#2ca02c", "#9467bd", "#8c564b", "#17becf", "#7f7f7f")

    def _with_pins(self, current: Trace) -> list[Trace]:
        """The live spectrum first, then whatever was pinned: the first trace
        is what every panel reads, and Mirror flips the odd ones."""
        return [current] + list(getattr(self, "_pinned", []))

    def pin_spectrum(self) -> None:
        """
        Hold the spectrum on screen so the next one draws over it.

        The comparison a chromatogram overlay gives for free — sample against
        blank, injection against injection — needs the spectrum pane to keep
        one while another is shown. The pinned copy carries the pane's title
        as its legend entry, so the sample, channel and scan it came from
        stay readable after the live spectrum has moved on.
        """
        traces = self.spectrum.traces
        live = next((t for t in traces if t.key == "spec"), None)
        if live is None:
            self._update_status("Show a spectrum first.")
            return
        pinned = getattr(self, "_pinned", [])
        colour = self.PIN_COLOURS[len(pinned) % len(self.PIN_COLOURS)]
        label = self.spectrum.title or live.label
        pinned.append(Trace(f"pin{len(pinned) + 1}", label, live.x.copy(),
                            live.y.copy(), colour, live.source))
        self._pinned = pinned
        self.spectrum.set_traces(self._with_pins(live))
        self.spectrum.set_legend_visible(True)
        self.spectrum.autoscale()
        self.act_unpin.setEnabled(True)
        self.act_exp_cmp.setEnabled(True)
        self.refresh_comparison()
        self._update_status(
            f"{len(pinned)} spectrum(s) pinned. The next spectrum draws over "
            f"them; Normalise puts them on one scale, Mirror draws every other "
            f"one downwards.")

    def unpin_spectra(self) -> None:
        self._pinned = []
        traces = self.spectrum.traces
        live = next((t for t in traces if t.key == "spec"), None)
        self.spectrum.set_traces([live] if live is not None else [])
        self.spectrum.autoscale()
        self.act_unpin.setEnabled(False)
        self.act_exp_cmp.setEnabled(False)
        self.refresh_comparison()
        self._update_status("Pinned spectra cleared.")

    @property
    def pinned_spectra(self) -> list[Trace]:
        return list(getattr(self, "_pinned", []))

    def refresh_comparison(self) -> None:
        """
        Keep the session's comparison of spectra in step with this pane.

        The rule is that the report prints what the pane shows: pinning a
        spectrum starts the comparison, changing the live spectrum or either
        of the two switches refreshes it, and unpinning drops it. The
        alternative — a snapshot taken by a button — means a report that
        disagrees with the window and no way of telling from either which
        one is stale, and the argument for it (that browsing away from the
        pinned spectrum spoils the comparison) is answered by the pane
        showing exactly the same thing.

        A comparison is a copy of the conditioned traces, so it survives the
        live spectrum moving on, and it costs nothing at all while nothing
        is pinned.
        """
        session = getattr(self, "session", None)
        if session is None:
            return
        if not self.pinned_spectra:
            session.spectra_comparison = None
            return
        from ..spectra_compare import from_traces

        traces = self.spectrum.traces
        if not traces:
            session.spectra_comparison = None
            return
        # the live trace is named by the pane's title, the way a pin is
        labelled = []
        for index, trace in enumerate(traces):
            label = (self.spectrum.title or trace.label) if index == 0 else trace.label
            labelled.append(Trace(trace.key, label, trace.x, trace.y,
                                  trace.colour, trace.source))
        session.spectra_comparison = from_traces(
            labelled, title=self._comparison_title(),
            normalise=self.act_norm.isChecked(),
            mirror=self.act_mirror.isChecked(),
            centroid=self.spectrum.centroided,
            condition=self.spectrum.condition,
            label_floor=self.spectrum.label_floor)

    def _comparison_title(self) -> str:
        """What the picture is called: the samples it holds, once each."""
        names = []
        for trace in self.spectrum.traces:
            name = (trace.label or "").split(" · ")[0].strip()
            if name and name not in names:
                names.append(name)
        if len(names) > 1:
            return " against ".join(names[:2]) + (
                f" and {len(names) - 2} more" if len(names) > 2 else "")
        return "Compared spectra"

    def _export_comparison(self) -> None:
        """
        The comparison as an image, at print size rather than screen size.

        PNG is written at twice the drawing's own size, which is what makes
        the type and the sticks come out sharp on paper; SVG is the same
        drawing as vectors for a figure that will be resized.
        """
        self.refresh_comparison()
        comparison = getattr(self.session, "spectra_comparison", None)
        if comparison is None or not comparison.stands:
            self._update_status("Pin a spectrum first: a comparison needs two.")
            return
        from .help_window import describe

        dialog = QtWidgets.QFileDialog(
            self, "Export comparison",
            os.path.join(self._last_dir(), "compared-spectra.png"),
            "PNG image, 2× for print (*.png);;SVG image (*.svg)")
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        describe(dialog, "chromatograms-and-spectra")
        if not dialog.exec() or not dialog.selectedFiles():
            return
        path = dialog.selectedFiles()[0]
        self._write_comparison(
            path, svg="svg" in dialog.selectedNameFilter().lower())

    def _write_comparison(self, path: str, svg: bool = False) -> str | None:
        """Write the current comparison to `path`, as SVG or as a 2× PNG."""
        comparison = getattr(self.session, "spectra_comparison", None)
        if comparison is None:
            return None
        from ..spectra_compare import PRINT_SCALE, render_png, render_svg

        svg = svg or path.lower().endswith(".svg")
        wanted = ".svg" if svg else ".png"
        if not path.lower().endswith(wanted):
            path += wanted
        self._remember_dir(path)
        try:
            if svg:
                render_svg(comparison, path)
            else:
                render_png(comparison, path, scale=PRINT_SCALE)
        except Exception as exc:                       # a full disk, a bad path
            self._update_status(f"Could not write {path}: {exc}")
            return None
        self._update_status(
            f"{len(comparison.traces)} spectra written to {path}"
            + ("" if svg else f", at {PRINT_SCALE:g}× for print"))
        return path

    def _current_spectrum(self) -> tuple[np.ndarray, np.ndarray] | None:
        traces = self.spectrum.traces
        if not traces:
            return None
        return self.spectrum.condition(traces[0])

    def _run_formula_search(self, params: dict) -> None:
        adduct = ADDUCTS_BY_NAME[params["adduct"]]
        neutral = adduct.neutral_mass(params["mz"])
        if neutral <= 0:
            self.formula_panel.set_results([], "That m/z is below the adduct mass.")
            return

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            hits = find_formulas(
                neutral, params["tolerance"], params["unit"],
                ranges=params["ranges"], rdbe_range=params["rdbe_range"],
                even_electron=params["even_electron"],
                golden_rules=params["golden_rules"],
            )
            for hit in hits:
                hit.mz = adduct.mz(hit.neutral_mass)

            note = f"{len(hits)} candidate(s) within ±{params['tolerance']:g} {params['unit']}"
            spectrum = self._current_spectrum()
            if params["use_isotopes"] and hits and spectrum is not None:
                mz, intensity = spectrum
                if has_isotope_satellites(mz, intensity, params["mz"], adduct.charge):
                    hits = rank_by_isotope_pattern(hits, mz, intensity, adduct)
                    note += ", ranked by isotope pattern"
                else:
                    # Nothing to score against: say so rather than showing a
                    # column of meaningless numbers, and point at the scan that
                    # does carry the pattern.
                    note += ("; this spectrum has no isotope satellites for that "
                             "ion, so candidates are ranked by mass error — a "
                             "product-ion scan isolates the monoisotopic "
                             "precursor, so use the TOF MS survey channel to "
                             "bring the pattern into play")
            elif params["use_isotopes"] and spectrum is None:
                note += "; no spectrum on screen, so ranked by mass error only"
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self.formula_panel.set_results(hits, note)
        if hits:
            self._overlay_hit(hits[0])
        self._update_status(note)

    def _overlay_hit(self, hit) -> None:
        adduct = ADDUCTS_BY_NAME[self.formula_panel.adduct_combo.currentText()]
        pattern = isotope_pattern(hit.counts, adduct, min_abundance=0.005,
                                  max_peaks=6)
        self.spectrum.set_overlay(pattern, f"{hit.formula} {adduct.name}")
        self._update_status(
            f"{hit.formula} · m/z {hit.mz:.5f} · {hit.error_ppm:+.2f} ppm · "
            f"RDBE {hit.rdbe:g}"
            + (f" · isotope match {hit.isotope_score * 100:.0f}%"
               if hit.isotope_score else "")
        )

    def _overlay_pattern(self, pattern: list, label: str) -> None:
        self.spectrum.set_overlay(pattern, label)
        self._update_status(f"Theoretical pattern of {label} overlaid.")

    # ------------------------------------------------------------------ misc -- #
    def _set_select_mode(self, enabled: bool) -> None:
        self.chrom.set_select_mode(enabled)
        self.spectrum.set_select_mode(enabled)

    def _set_normalised(self, enabled: bool) -> None:
        self.chrom.set_normalised(enabled)
        self.spectrum.set_normalised(enabled)
        self.refresh_comparison()

    def _set_mirror(self, enabled: bool) -> None:
        self.chrom.set_mirror(enabled)
        self.spectrum.set_mirror(enabled)
        self.refresh_comparison()

    def _set_smoothing(self, sigma: float) -> None:
        self.chrom.set_smoothing(sigma)
        self.spectrum.set_smoothing(sigma)

    def _set_offsets(self, *_args) -> None:
        dx, dy = self.offset_x_spin.value(), self.offset_y_spin.value()
        self.chrom.set_offsets(dx, dy)
        self.spectrum.set_offsets(0.0, dy)  # shifting a spectrum in m/z is misleading

    def _set_overview(self, enabled: bool) -> None:
        self.chrom.set_overview_visible(enabled)
        self.spectrum.set_overview_visible(enabled)

    def _set_label_floor(self, percent: float) -> None:
        """The spin box moved: take the handle with it, and the print."""
        self.spectrum.set_label_floor(float(percent) / 100.0)
        self._floor_into_comparison()

    def _label_floor_moved(self, fraction: float) -> None:
        """The handle moved: take the spin box with it, and the print.

        Blocked while it is set, or the spin box's own signal comes back
        here as a second `set_label_floor` and a drag lands on the rounded
        value rather than where the mouse is.
        """
        self.floor_spin.blockSignals(True)
        try:
            self.floor_spin.setValue(float(fraction) * 100.0)
        finally:
            self.floor_spin.blockSignals(False)
        self._floor_into_comparison()

    def _floor_into_comparison(self) -> None:
        """
        Keep the print's floor in step with the pane's.

        The field is set rather than the comparison rebuilt: `from_traces`
        copies every point of every trace, and this runs on every mouse move
        of a drag. A comparison that does not exist yet is left alone —
        pinning builds one, and it reads the floor as it stands.
        """
        comparison = getattr(getattr(self, "session", None),
                             "spectra_comparison", None)
        if comparison is not None:
            comparison.label_floor = self.spectrum.label_floor

    def _set_relative_labels(self, enabled: bool) -> None:
        self.chrom.set_relative_labels(enabled)
        self.spectrum.set_relative_labels(enabled)

    def _set_centroid(self, enabled: bool) -> None:
        self.spectrum.set_centroid(enabled)
        self.refresh_comparison()
        self._fill_peak_table()

    def _add_marker(self) -> None:
        """Drop a marker at the tallest peak of the current spectrum selection."""
        selection = self.spectrum.selected_range()
        traces = self.spectrum.traces
        if not traces:
            self._update_status("Show a spectrum before adding a marker.")
            return
        if selection is None:
            x, y = self.spectrum.condition(traces[0])
            position = float(x[int(np.argmax(y))]) if x.size else 0.0
        else:
            position = sum(selection) / 2.0
        self.spectrum.add_marker(position)
        self._update_status(
            "Marker added; other peaks are now labelled by their distance to it."
        )

    def _clear_markers(self) -> None:
        self.spectrum.clear_markers()
        self.chrom.clear_markers()

    def _autoscale_both(self) -> None:
        self.chrom.autoscale()
        self.spectrum.autoscale()

    def _export(self, view, what: str) -> None:
        traces = view.traces
        if not traces:
            self._update_status(f"Nothing to export in {what}.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Export {what}", os.path.join(self._last_dir(), f"{what}.csv"),
            "CSV (*.csv)"
        )
        if not path:
            return
        self._remember_dir(path)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for trace in traces:
                conditioned = view.conditioned(trace.key)
                x, y = conditioned if conditioned else (trace.x, trace.y)
                writer.writerow([trace.label])
                writer.writerow(["x", "y"])
                writer.writerows(zip(x.tolist(), y.tolist()))
                writer.writerow([])
        self._update_status(f"Exported to {path}")

    def _export_mzml(self) -> None:
        """
        Write the selected sample out as mzML.

        Every spectrum goes through, as the instrument stored it, along with
        the total ion current the instrument reported rather than a sum taken
        here. A run of this size is tens of thousands of spectra, so the
        window says how far it has got instead of appearing to hang.
        """
        # whichever sample the tree is pointing at, falling back to the first
        # one open — exporting is about a sample, not about a channel
        entry = self.active_ref.entry if self.active_ref else None
        if entry is None or not entry.is_loaded:
            entry = next((e for e in self.session.entries if e.is_loaded), None)
        if entry is None:
            self._update_status("Open a file before exporting it.")
            return

        suggestion = os.path.join(self._last_dir(), f"{entry.name}.mzML")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export as mzML", suggestion, "mzML (*.mzML)")
        if not path:
            return
        self._remember_dir(path)

        progress = QtWidgets.QProgressDialog(
            f"Writing {os.path.basename(path)}…", "Cancel", 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        cancelled = False

        def tick(done: int, total: int) -> None:
            nonlocal cancelled
            progress.setValue(int(done / max(total, 1) * 100))
            QtWidgets.QApplication.processEvents()
            if progress.wasCanceled():
                cancelled = True
                raise _Cancelled()

        from ..mzml import write_mzml

        try:
            write_mzml(entry.sample, path, progress=tick)
        except _Cancelled:
            pass
        except Exception as exc:
            progress.close()
            QtWidgets.QMessageBox.warning(self, "Export failed", str(exc))
            return
        progress.close()
        if cancelled:
            try:
                os.remove(path)
            except OSError:
                pass
            self._update_status("Export cancelled.")
            return
        size = os.path.getsize(path) / 1048576
        self._update_status(f"Exported {entry.name} to {path} ({size:.0f} MB)")

    def _show_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "How to use",
            "<b>Chromatogram</b><br>"
            "• drag = rubber-band zoom; double-click = fit<br>"
            "• single click = spectrum of that scan<br>"
            "• Shift + drag = select a range → average spectrum + integration<br>"
            "• the spectrum follows the highlight while you drag or resize it<br>"
            "• ← → step through the scans<br><br>"
            "<b>Spectrum</b><br>"
            "• Shift + drag selects an m/z range<br>"
            "• right-click → extract an XIC, or drop a marker<br>"
            "• with a marker present, other peaks are labelled by their distance "
            "to it — that is how neutral losses and isotope spacings are read<br>"
            "• double-click a row of the Spectrum peaks tab to extract its XIC<br><br>"
            "<b>Components</b><br>"
            "• the list comes from the Method workspace and is shared<br>"
            "• “Extract and integrate all” runs it over every checked sample<br>"
            "• double-click a row to show that component's XIC<br><br>"
            "<b>View</b><br>"
            "• Stack gives each trace its own pane with the time axes locked<br>"
            "• Overview adds a navigator showing where the current zoom sits<br>"
            "• Mirror flips every other trace; Cascade offsets them in x and y<br><br>"
            "<b>Chemistry</b><br>"
            "• Mass calc: type a formula for its exact masses, RDBE and isotope "
            "pattern, and overlay that pattern on the spectrum<br>"
            "• right-click a spectrum peak → “Find formula for this peak”<br>"
            "• the finder ranks candidates by how well their isotope pattern "
            "matches the spectrum on screen<br><br>"
            "<b>Processing</b><br>"
            "• smoothing and baseline apply to the display, the integration and "
            "the export alike<br>"
            "• select a blank range and click “Set background” to subtract it "
            "from the spectra<br>"
            "• Centroid turns the profile spectrum into sticks",
        )

    def _update_status(self, text: str) -> None:
        """
        Say it once.

        This workspace is a QMainWindow nested in the shell's tab widget, so
        calling statusBar() here creates a second status bar inside the tab,
        directly above the shell's own — and every message was printed in
        both. The shell owns the status bar; this only reports.
        """
        self.sigStatus.emit(text)
