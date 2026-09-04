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
    extract_xic,
    integrate_manually,
    process,
)
from ..session import Session
from .calibration_panel import CalibrationPanel
from .integration_panel import IntegrationPanel
from .peak_review import PeakReviewGrid
from .results_table import ResultsTable

ROLE_NAME = QtCore.Qt.ItemDataRole.UserRole


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
        self.status.setStyleSheet("color:#666;")
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
        left_layout.addWidget(self.component_tree, 1)
        self.integration = IntegrationPanel()
        left_layout.addWidget(self.integration)
        splitter.addWidget(left)

        right = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.grid = PeakReviewGrid()
        self.results = ResultsTable(session)
        self.calibration = CalibrationPanel()
        self.bottom = QtWidgets.QTabWidget()
        self.bottom.setDocumentMode(True)
        self.bottom.addTab(self.results, "Results")
        self.bottom.addTab(self.calibration, "Calibration")
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

        session.sigMethodChanged.connect(self.reload_components)
        session.sigSamplesChanged.connect(self.refresh_grid)
        session.sigResultsChanged.connect(self.refresh_grid)
        session.sigResultsChanged.connect(self.refresh_calibration)
        self.reload_components()

    # -- components ---------------------------------------------------------------- #
    def reload_components(self) -> None:
        current = self._component.name if self._component else None
        self.component_tree.blockSignals(True)
        self.component_tree.clear()

        groups: dict[str, QtWidgets.QTreeWidgetItem] = {}
        selected_item = None
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
        self._component = self.session.method.by_name(name) if name else None
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

    # -- grid ------------------------------------------------------------------------ #
    def refresh_grid(self) -> None:
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

    # -- calibration ---------------------------------------------------------------- #
    def refresh_calibration(self) -> None:
        component = self._component
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
