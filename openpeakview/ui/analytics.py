"""Analytics workspace: process a batch, review the peaks, read the results."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..components import Component
from ..quantify import PeakResult, extract_xic, process
from ..session import Session
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
        splitter.addWidget(left)

        right = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.grid = PeakReviewGrid()
        self.results = ResultsTable(session)
        right.addWidget(self.grid)
        right.addWidget(self.results)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1200])
        layout.addWidget(splitter, 1)

        self.btn_process.clicked.connect(self.process_batch)
        self.btn_magnify.toggled.connect(self._set_magnified)
        self.component_filter.textChanged.connect(self._filter_components)
        self.component_tree.currentItemChanged.connect(self._on_component_changed)
        self.grid.sigSelected.connect(self._on_panel_selected)
        self.grid.sigMagnified.connect(self._on_panel_magnified)
        self.results.sigSelected.connect(self._on_row_selected)

        session.sigMethodChanged.connect(self.reload_components)
        session.sigSamplesChanged.connect(self.refresh_grid)
        session.sigResultsChanged.connect(self.refresh_grid)
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
        self.refresh_grid()

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
        self.session.set_results(results)
        found = sum(1 for r in results if r.found)
        self._report(f"{len(results)} row(s) across {len(loaded)} sample(s); "
                     f"{found} integrated.")

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
