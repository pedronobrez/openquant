"""Analytics workspace: process a batch, review the peaks, read the results."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..calibration import fit as fit_curve
from ..calibration import remove_outliers
from ..components import Component, IntegrationParams
from ..quantify import (
    PeakResult,
    apply_calibrations,
    build_calibrations,
    evaluate_acceptance,
    extract_xic,
    integrate_manually,
    process,
)
from ..session import Session
from .acceptance_panel import AcceptancePanel
from .calibration_panel import CalibrationPanel
from .integration_panel import IntegrationPanel
from .metric_plot import MetricPlotPanel
from .statistics_panel import StatisticsPanel
from .peak_review import PeakReviewGrid
from .results_table import ResultsTable

ROLE_NAME = QtCore.Qt.ItemDataRole.UserRole

#: the tree entry that means "do not narrow anything down". Not a component
#: name, and picked so no real one can collide with it.
ALL_COMPONENTS = "\u0000all-components"


class AnalyticsWorkspace(QtWidgets.QWidget):
    """
    The component list drives the review grid, and the grid and the results
    table follow each other's selection.
    """

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._component: Component | None = None
        self._all_components = False
        self._magnified = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = QtWidgets.QHBoxLayout()
        self.btn_process = QtWidgets.QPushButton("Process batch")
        font = self.btn_process.font()
        font.setBold(True)
        self.btn_process.setFont(font)
        self.btn_process.setToolTip(
            "Extract and integrate every component in every open sample")
        bar.addWidget(self.btn_process)
        self.btn_calibrate = QtWidgets.QPushButton("Recalibrate")
        self.btn_calibrate.setToolTip(
            "Refit every curve from the samples marked as standards and read "
            "the unknowns back off them")
        bar.addWidget(self.btn_calibrate)
        self.btn_magnify = QtWidgets.QPushButton("Magnify peak")
        self.btn_magnify.setCheckable(True)
        self.btn_magnify.setToolTip(
            "Expand the selected panel to fill the pane (double-click a panel "
            "does the same)")
        bar.addWidget(self.btn_magnify)
        bar.addStretch(1)
        self.status = QtWidgets.QLabel("")
        self.status.setProperty("role", "caption")
        bar.addWidget(self.status)
        layout.addLayout(bar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.component_filter = QtWidgets.QLineEdit()
        self.component_filter.setPlaceholderText("Filter components…")
        self.component_filter.setClearButtonEnabled(True)
        left_layout.addWidget(self.component_filter)
        self.component_tree = QtWidgets.QTreeWidget()
        self.component_tree.setHeaderHidden(True)
        self.component_tree.setAlternatingRowColors(True)
        # a name wider than the pane scrolls into view rather than being cut;
        # dragging the splitter is the other way to read it
        self.component_tree.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        self.component_tree.header().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.component_tree.header().setStretchLastSection(False)
        self.component_tree.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_layout.addWidget(self.component_tree, 1)
        self.integration = IntegrationPanel()
        left_layout.addWidget(self.integration)
        self.acceptance = AcceptancePanel()
        left_layout.addWidget(self.acceptance)
        # folded to start with: expanded they leave the component list a few
        # rows tall, and they are only wanted while a setting is being changed
        self.settings = QtCore.QSettings("OpenQuant", "OpenQuant")
        self.integration.restore(self.settings, "analytics/integration_open")
        self.acceptance.restore(self.settings, "analytics/acceptance_open")
        self.integration.toggled.connect(self._save_sections)
        self.acceptance.toggled.connect(self._save_sections)
        splitter.addWidget(left)

        right = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.grid = PeakReviewGrid()
        self.results = ResultsTable(session)
        self.calibration = CalibrationPanel()
        self.statistics = StatisticsPanel(session)
        self.metrics = MetricPlotPanel(session)
        self.bottom = QtWidgets.QTabWidget()
        self.bottom.setDocumentMode(True)
        self.bottom.addTab(self.results, "Results")
        self.bottom.addTab(self.calibration, "Calibration")
        self.bottom.addTab(self.statistics, "Statistics")
        self.bottom.addTab(self.metrics, "Metric plot")
        right.addWidget(self.grid)
        right.addWidget(self.bottom)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 1200])
        layout.addWidget(splitter, 1)

        self.btn_process.clicked.connect(self.process_batch)
        self.btn_magnify.toggled.connect(self._set_magnified)
        self.btn_calibrate.clicked.connect(lambda: self._recalibrate())
        self.component_filter.textChanged.connect(self._filter_components)
        self.component_tree.currentItemChanged.connect(self._on_component_changed)
        # queued: the recalculation resets the results model, which must not
        # happen while the table's editor is still closing over the cell
        self.results.sigInternalStandardChanged.connect(
            self._set_internal_standard, QtCore.Qt.ConnectionType.QueuedConnection)
        self.grid.sigSelected.connect(self._on_panel_selected)
        self.grid.sigMagnified.connect(self._on_panel_magnified)
        self.grid.sigManualRange.connect(self._on_manual_range)
        self.grid.sigContextMenu.connect(self._panel_menu)
        self.results.sigSelected.connect(self._on_row_selected)
        self.integration.sigApplyComponent.connect(self._apply_to_component)
        self.integration.sigApplyGroup.connect(self._apply_to_group)
        self.integration.sigResetComponent.connect(self._reset_component)
        self.calibration.sigSettingsChanged.connect(self._set_curve_settings)
        self.calibration.sigPointToggled.connect(self._toggle_point)
        self.calibration.sigAutoOutliers.connect(self._auto_outliers)
        self.acceptance.sigApplyComponent.connect(self._apply_acceptance_component)
        self.acceptance.sigApplyAll.connect(self._apply_acceptance_all)
        self.metrics.sigPointActivated.connect(self._on_row_selected)

        session.sigMethodChanged.connect(self.reload_components)
        session.sigSamplesChanged.connect(self.refresh_grid)
        session.sigResultsChanged.connect(self.refresh_grid)
        session.sigResultsChanged.connect(self.refresh_calibration)
        self.reload_components()

    def _save_sections(self, *_args) -> None:
        self.integration.save(self.settings, "analytics/integration_open")
        self.acceptance.save(self.settings, "analytics/acceptance_open")

    # -- components ---------------------------------------------------------------- #
    def reload_components(self) -> None:
        current = (ALL_COMPONENTS if self._all_components
                   else self._component.name if self._component else None)
        self.component_tree.blockSignals(True)
        self.component_tree.clear()

        groups: dict[str, QtWidgets.QTreeWidgetItem] = {}
        all_item = QtWidgets.QTreeWidgetItem(self.component_tree,
                                             ["All components"])
        all_item.setData(0, ROLE_NAME, ALL_COMPONENTS)
        all_item.setToolTip(0, "Every peak of every component, and the whole "
                               "results table")
        font = all_item.font(0)
        font.setBold(True)
        all_item.setFont(0, font)
        selected_item = all_item if current == ALL_COMPONENTS else None
        for component in self.session.method.components:
            parent = self.component_tree
            if component.group:
                if component.group not in groups:
                    node = QtWidgets.QTreeWidgetItem(self.component_tree,
                                                     [component.group])
                    node.setExpanded(True)
                    font = node.font(0)
                    font.setBold(True)
                    node.setFont(0, font)
                    groups[component.group] = node
                parent = groups[component.group]
            label = component.name + (" (IS)" if component.is_internal_standard else "")
            item = QtWidgets.QTreeWidgetItem(parent, [label])
            item.setData(0, ROLE_NAME, component.name)
            item.setToolTip(0, label)
            if component.name == current:
                selected_item = item
        self.component_tree.blockSignals(False)

        if selected_item is None:
            selected_item = self._first_component_item()
        if selected_item is not None:
            self.component_tree.setCurrentItem(selected_item)
        else:
            self._component = None
            self.grid.clear()

    def _first_component_item(self):
        it = QtWidgets.QTreeWidgetItemIterator(self.component_tree)
        while it.value():
            if it.value().data(0, ROLE_NAME):
                return it.value()
            it += 1
        return None

    def _filter_components(self, text: str) -> None:
        needle = text.strip().lower()
        it = QtWidgets.QTreeWidgetItemIterator(self.component_tree)
        while it.value():
            item = it.value()
            if item.data(0, ROLE_NAME):
                item.setHidden(bool(needle) and needle not in item.text(0).lower())
            it += 1

    def _on_component_changed(self, current, _previous) -> None:
        name = current.data(0, ROLE_NAME) if current is not None else None
        self._all_components = name == ALL_COMPONENTS
        self._component = (None if self._all_components
                           else self.session.method.by_name(name) if name else None)
        # the results table follows the tree: reviewing one component against a
        # table of every other one is what made the table hard to read
        self.results.set_component_filter(
            "" if self._all_components or self._component is None
            else self._component.name)
        self._show_integration_params()
        self.refresh_grid()
        self.refresh_calibration()

    def _show_integration_params(self) -> None:
        component = self._component
        if component is None:
            return
        params = self.session.method.integration_for(component)
        self.integration.set_params(params, component.integration is not None)
        self.grid.set_noise_region(params.noise_region)
        self.acceptance.set_limits(self.session.method.acceptance_for(component),
                                   component.acceptance is not None)

    # -- grid ------------------------------------------------------------------------ #
    def refresh_grid(self) -> None:
        if self._all_components:
            self._refresh_grid_all()
            return
        component = self._component
        if component is None:
            self.grid.clear()
            return
        method = self.session.method
        expected = component.rt_window()
        standard = method.internal_standard_for(component)
        items = []
        for entry in self.session.entries:
            if not entry.is_loaded:
                continue
            result = self.session.results.get(entry.key, component.name)
            if result is None:
                # not processed yet: still show the trace, unintegrated
                result = PeakResult(
                    sample_key=entry.key, sample_name=entry.name,
                    component=component.name, group=component.group,
                    expected_rt=component.rt, note="not processed",
                )
            x, y, _channel = extract_xic(entry, component, method, self.session.cache)
            is_trace = None
            if standard is not None:
                sx, sy, _ = extract_xic(entry, standard, method, self.session.cache)
                if sx.size:
                    is_trace = (sx, sy)
            items.append((result, x, y, expected, is_trace))
        self.grid.set_items(component.label, items)

        found = sum(1 for i in items if i[0].found)
        message = f"{component.name}: {found} of {len(items)} sample(s) integrated"
        if standard is not None:
            message += f" · internal standard {standard.name}"
        quantifier = method.quantifier_for(component)
        if quantifier is not None:
            message += f" · qualifier of {quantifier.name}"
        self._report(message)

    def _refresh_grid_all(self) -> None:
        """
        Every peak of every component, built a page at a time.

        Extracting all of them on a real batch — 141 components across 26
        samples — is around a hundred seconds of work to put nine on screen.
        """
        loaded = [e for e in self.session.entries if e.is_loaded]
        components = [c for c in self.session.method.components if c.is_valid]
        pairs = [(c, e) for c in components for e in loaded]

        def fetch(start: int, stop: int) -> list[tuple]:
            return [self._grid_item(c, e) for c, e in pairs[start:stop]]

        self.grid.set_lazy("All components", len(pairs), fetch)
        self._report(f"{len(components)} component(s) across {len(loaded)} "
                     f"sample(s) — {len(pairs)} peak(s)")

    def _grid_item(self, component: Component, entry) -> tuple:
        """One panel's worth: the result, its trace, and the standard's."""
        method = self.session.method
        result = self.session.results.get(entry.key, component.name)
        if result is None:
            result = PeakResult(
                sample_key=entry.key, sample_name=entry.name,
                component=component.name, group=component.group,
                expected_rt=component.rt, note="not processed",
            )
        x, y, _channel = extract_xic(entry, component, method, self.session.cache)
        standard = method.internal_standard_for(component)
        is_trace = None
        if standard is not None:
            sx, sy, _ = extract_xic(entry, standard, method, self.session.cache)
            if sx.size:
                is_trace = (sx, sy)
        return (result, x, y, component.rt_window(), is_trace)

    # -- acceptance ------------------------------------------------------------------ #
    def _apply_acceptance_component(self, limits) -> None:
        component = self._component
        if component is None:
            return
        component.acceptance = limits.copy()
        self.session.notify_method_changed()
        self._revalidate()
        self._report(f"Acceptance criteria applied to {component.name}.")

    def _apply_acceptance_all(self, limits) -> None:
        method = self.session.method
        method.acceptance = limits.copy()
        for component in method.components:
            component.acceptance = None
        self.session.notify_method_changed()
        self._show_integration_params()
        self._revalidate()
        self._report("Acceptance criteria applied to every component.")

    def _revalidate(self) -> None:
        evaluate_acceptance(self.session.results, self.session.entries,
                            self.session.method)
        self.session.notify_results_changed()

    # -- calibration ---------------------------------------------------------------- #
    def refresh_calibration(self) -> None:
        component = self._component
        if component is None:
            self.calibration.show_curve(None)
            return
        curve = (self.session.calibrations.get(component.name)
                 if component is not None else None)
        self.calibration.show_curve(
            curve, self.session.method.concentration_unit)

    def _recalibrate(self, auto_outliers: bool = False,
                     tolerance: float = 15.0) -> None:
        """Refit every curve and read the unknowns back off them."""
        session = self.session
        curves = build_calibrations(session.results, session.entries,
                                    session.method, auto_outliers, tolerance,
                                    previous=session.calibrations)
        apply_calibrations(session.results, session.entries, session.method,
                           curves)
        session.calibrations = curves
        evaluate_acceptance(session.results, session.entries, session.method)
        session.notify_results_changed()
        fitted = sum(1 for c in curves.values() if c.is_fitted)
        if not curves:
            self._report("No standards found — mark samples as Standard and "
                         "give them a concentration in the Samples workspace.")
        else:
            self._report(f"{fitted} of {len(curves)} curve(s) fitted.")

    def _set_curve_settings(self, regression: str, weighting: str) -> None:
        component = self._component
        if component is None:
            return
        component.regression = regression
        component.weighting = weighting
        self.session.notify_method_changed()
        self._recalibrate()

    def _toggle_point(self, sample_key: str) -> None:
        """Include or exclude one standard, then refit."""
        component = self._component
        curve = (self.session.calibrations.get(component.name)
                 if component is not None else None)
        if curve is None:
            return
        for point in curve.points:
            if point.sample_key == sample_key:
                point.used = not point.used
                break
        refitted = fit_curve(curve.points, curve.regression, curve.weighting,
                             curve.component)
        self.session.calibrations[curve.component] = refitted
        apply_calibrations(self.session.results, self.session.entries,
                           self.session.method, self.session.calibrations)
        evaluate_acceptance(self.session.results, self.session.entries,
                            self.session.method)
        self.session.notify_results_changed()

    def _auto_outliers(self, tolerance: float) -> None:
        component = self._component
        curve = (self.session.calibrations.get(component.name)
                 if component is not None else None)
        if curve is None or not curve.is_fitted:
            return
        cleaned = remove_outliers(curve, tolerance)
        self.session.calibrations[curve.component] = cleaned
        apply_calibrations(self.session.results, self.session.entries,
                           self.session.method, self.session.calibrations)
        evaluate_acceptance(self.session.results, self.session.entries,
                            self.session.method)
        self.session.notify_results_changed()
        dropped = sum(1 for p in cleaned.points if not p.used)
        self._report(f"{curve.component}: {dropped} standard(s) excluded, "
                     f"r² = {cleaned.r2:.5f}")

    # -- integration parameters -------------------------------------------------- #
    def _apply_to_component(self, params: IntegrationParams) -> None:
        component = self._component
        if component is None:
            return
        self.session.method.set_integration(component, params)
        self.session.notify_method_changed()
        self._reprocess([component.name])
        self.integration.report(f"Applied to {component.name}.")

    def _apply_to_group(self, params: IntegrationParams) -> None:
        component = self._component
        if component is None:
            return
        if not component.group:
            self.integration.report(
                "This component has no group; use “update for component”.")
            return
        method = self.session.method
        touched = method.apply_integration_to_group(component.group, params)
        self.session.notify_method_changed()
        names = [c.name for c in method.components if c.group == component.group]
        self._reprocess(names)
        self.integration.report(
            f"Applied to {touched} component(s) of {component.group}.")

    def _reset_component(self) -> None:
        component = self._component
        if component is None:
            return
        self.session.method.set_integration(component, None)
        self.session.notify_method_changed()
        self._show_integration_params()
        self._reprocess([component.name])
        self.integration.report(f"{component.name} back to the method defaults.")

    def _reprocess(self, names: list[str]) -> None:
        """
        Re-integrate only the components that changed, keeping rows the
        operator integrated by hand.
        """
        if not self.session.results.results:
            return
        results = process(self.session.loaded_entries, self.session.method,
                          self.session.cache, previous=self.session.results,
                          keep_manual=True, only=names)
        self.session.results = results
        self._recalibrate()

    # -- manual integration -------------------------------------------------------- #
    def _on_manual_range(self, sample_key: str, start: float, end: float) -> None:
        component = self._component
        entry = self.session.entry_by_key(sample_key)
        if component is None or entry is None:
            return
        previous = self.session.results.get(sample_key, component.name)
        result = integrate_manually(entry, component, self.session.method,
                                    start, end, previous, self.session.cache)
        self.session.results.replace(result)
        self._relink()
        self._recalibrate()
        self.results.select(sample_key, component.name)
        self._report(
            f"{entry.name}: integrated {min(start, end):.3f}–{max(start, end):.3f} min "
            f"by hand — area {result.area:,.0f}")

    def _set_internal_standard(self, component_name: str, standard: str) -> None:
        """
        Point a component at another internal standard from the results table.

        Every ratio, response and calculated concentration that came off the old
        standard is wrong the moment this changes, so they are recomputed here
        rather than left for the analyst to remember to refresh.
        """
        component = self.session.method.by_name(component_name)
        if component is None:
            return
        component.internal_standard = standard
        self.session.notify_method_changed()
        self._relink()
        self._recalibrate()
        self._report(f"{component_name} is now quantified against "
                     + (f"{standard}." if standard else "its own area."))

    def _relink(self) -> None:
        from ..quantify import compute_ion_ratios, link_internal_standards
        link_internal_standards(self.session.results, self.session.method)
        compute_ion_ratios(self.session.results, self.session.method)

    def _panel_menu(self, sample_key: str, position) -> None:
        component = self._component
        if component is None:
            return
        result = self.session.results.get(sample_key, component.name)
        menu = QtWidgets.QMenu(self)
        noise = menu.addAction("Set noise region from the shaded range")
        revert = menu.addAction("Back to automatic integration")
        revert.setEnabled(result is not None and result.manual)
        chosen = menu.exec(position)
        if chosen is noise:
            self._noise_from_panel(sample_key)
        elif chosen is revert:
            self._revert_manual(sample_key)

    def _noise_from_panel(self, sample_key: str) -> None:
        panel = next((p for p in self.grid.views if p.sample_key == sample_key), None)
        if panel is None:
            return
        region = panel.integration_range()
        if region is None:
            self.integration.report("Drag across a stretch of baseline first.")
            return
        self.integration.set_noise_region(region)
        self.grid.set_noise_region(region)
        self.integration.report(
            f"Noise region {region[0]:.2f}–{region[1]:.2f} min — apply to keep it.")

    def _revert_manual(self, sample_key: str) -> None:
        component = self._component
        entry = self.session.entry_by_key(sample_key)
        if component is None or entry is None:
            return
        from ..quantify import integrate_component
        result = integrate_component(entry, component, self.session.method,
                                     self.session.cache)
        self.session.results.replace(result)
        self._relink()
        self._recalibrate()
        self._report(f"{entry.name}: back to automatic integration.")

    def _set_magnified(self, enabled: bool) -> None:
        """One panel filling the pane, or back to the grid."""
        self._magnified = enabled
        if enabled:
            self._saved_layout = (self.grid.col_spin.value(),
                                  self.grid.row_spin.value())
            self.grid.col_spin.setValue(1)
            self.grid.row_spin.setValue(1)
            selected = self.results.current_result()
            if selected is not None:
                self.grid.select(selected.sample_key)
        elif hasattr(self, "_saved_layout"):
            self.grid.col_spin.setValue(self._saved_layout[0])
            self.grid.row_spin.setValue(self._saved_layout[1])

    def _on_panel_magnified(self, sample_key: str) -> None:
        self.btn_magnify.setChecked(not self._magnified)
        self.grid.select(sample_key)

    # -- linking ---------------------------------------------------------------------- #
    def _on_panel_selected(self, sample_key: str) -> None:
        if self._component is not None:
            self.results.select(sample_key, self._component.name)

    def _on_row_selected(self, sample_key: str, component: str) -> None:
        if self._component is None or component != self._component.name:
            item = self._item_for(component)
            if item is not None:
                self.component_tree.setCurrentItem(item)
        self.grid.select(sample_key)

    def _item_for(self, component: str):
        it = QtWidgets.QTreeWidgetItemIterator(self.component_tree)
        while it.value():
            if it.value().data(0, ROLE_NAME) == component:
                return it.value()
            it += 1
        return None

    # -- processing --------------------------------------------------------------- #
    def process_batch(self) -> None:
        method = self.session.method
        components = [c for c in method.components if c.is_valid]
        loaded = self.session.loaded_entries
        if not components:
            self._report("Build the component list in the Method workspace first.")
            return
        if not loaded:
            self._report("Open at least one sample first.")
            return

        total = len(components) * len(loaded)
        dialog = QtWidgets.QProgressDialog("Processing…", "Cancel", 0, total, self)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(300)

        def report(done: int, _total: int) -> bool:
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()
            return not dialog.wasCanceled()

        results = process(loaded, method, self.session.cache, report)
        dialog.setValue(total)
        self.session.results = results
        self._recalibrate()
        found = sum(1 for r in results if r.found)
        self._report(f"{len(results)} row(s) across {len(loaded)} sample(s); "
                     f"{found} integrated.")

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
