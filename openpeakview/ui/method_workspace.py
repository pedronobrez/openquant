"""Method workspace: the component table of the processing method."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..chemistry import ADDUCTS
from ..components import RESPONSES, Component, load_components, save_components
from ..session import Session

COLUMNS = ["Name", "Group", "Precursor", "Fragment", "RT", "± RT", "Tol.",
           "Unit", "Formula", "Adduct", "IS", "Internal standard", "Response",
           "Conc. unit", "Qualifier of", "Ion ratio %", "± ratio %"]
COL = {name: i for i, name in enumerate(COLUMNS)}

#: columns parsed as numbers, mapped to the dataclass field they fill
_NUMERIC = {
    COL["Precursor"]: "precursor",
    COL["Fragment"]: "fragment",
    COL["RT"]: "rt",
    COL["± RT"]: "rt_halfwidth",
    COL["Tol."]: "tolerance",
    COL["Ion ratio %"]: "ion_ratio",
    COL["± ratio %"]: "ion_ratio_tolerance",
}


class MethodWorkspace(QtWidgets.QWidget):
    """
    Edits the shared component table.

    Writes straight into the session's method, so the Explorer and, later, the
    Analytics workspace always see the same list.
    """

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._loading = False

        layout = QtWidgets.QVBoxLayout(self)

        bar = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add")
        self.btn_remove = QtWidgets.QPushButton("Remove")
        self.btn_generate = QtWidgets.QPushButton("Generate from acquisition method")
        self.btn_generate.setToolTip(
            "Create one component per product-ion channel of the open sample, "
            "so an 80-transition method does not have to be typed in"
        )
        self.btn_import = QtWidgets.QPushButton("Import CSV…")
        self.btn_export = QtWidgets.QPushButton("Export CSV…")
        for widget in (self.btn_add, self.btn_remove, self.btn_generate,
                       self.btn_import, self.btn_export):
            bar.addWidget(widget)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            COL["Name"], QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setDefaultSectionSize(24)
        layout.addWidget(self.table, 1)

        defaults = QtWidgets.QHBoxLayout()
        defaults.addWidget(QtWidgets.QLabel("Default tolerance ±"))
        self.tol_spin = QtWidgets.QDoubleSpinBox()
        self.tol_spin.setDecimals(4)
        self.tol_spin.setRange(0.0001, 500.0)
        self.tol_spin.setValue(session.method.tolerance)
        defaults.addWidget(self.tol_spin)
        self.unit_combo = QtWidgets.QComboBox()
        self.unit_combo.addItems(["Da", "ppm"])
        self.unit_combo.setCurrentText(session.method.unit)
        defaults.addWidget(self.unit_combo)
        defaults.addSpacing(20)
        defaults.addWidget(QtWidgets.QLabel("Concentration unit"))
        self.conc_edit = QtWidgets.QLineEdit(session.method.concentration_unit)
        self.conc_edit.setMaximumWidth(120)
        defaults.addWidget(self.conc_edit)
        defaults.addSpacing(20)
        defaults.addWidget(QtWidgets.QLabel("Ion ratio ±"))
        self.ratio_spin = QtWidgets.QDoubleSpinBox()
        self.ratio_spin.setRange(0.0, 100.0)
        self.ratio_spin.setValue(session.method.ion_ratio_tolerance)
        self.ratio_spin.setSuffix(" %")
        self.ratio_spin.setToolTip("Deviation from the expected ion ratio that passes")
        defaults.addWidget(self.ratio_spin)
        defaults.addWidget(QtWidgets.QLabel("marginal to"))
        self.marginal_spin = QtWidgets.QDoubleSpinBox()
        self.marginal_spin.setRange(0.0, 200.0)
        self.marginal_spin.setValue(session.method.ion_ratio_marginal)
        self.marginal_spin.setSuffix(" %")
        defaults.addWidget(self.marginal_spin)
        defaults.addStretch(1)
        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color:#666;")
        defaults.addWidget(self.status)
        layout.addLayout(defaults)

        self.btn_add.clicked.connect(self._add_row)
        self.btn_remove.clicked.connect(self._remove_rows)
        self.btn_generate.clicked.connect(self._generate)
        self.btn_import.clicked.connect(self._import)
        self.btn_export.clicked.connect(self._export)
        self.table.itemChanged.connect(self._on_edit)
        self.tol_spin.valueChanged.connect(self._defaults_changed)
        self.unit_combo.currentTextChanged.connect(self._defaults_changed)
        self.conc_edit.textChanged.connect(self._defaults_changed)
        self.ratio_spin.valueChanged.connect(self._defaults_changed)
        self.marginal_spin.valueChanged.connect(self._defaults_changed)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.table,
                        activated=self._remove_rows)

        session.sigMethodChanged.connect(self.reload)
        self.reload()

    # -- table <-> method -------------------------------------------------------- #
    def reload(self) -> None:
        self._loading = True
        components = self.session.method.components
        self.table.setRowCount(len(components))
        for row, component in enumerate(components):
            self._write_row(row, component)
        self._loading = False
        self._update_status()

    def _write_row(self, row: int, c: Component) -> None:
        values = {
            COL["Name"]: c.name,
            COL["Group"]: c.group,
            COL["Precursor"]: f"{c.precursor:.4f}" if c.precursor else "",
            COL["Fragment"]: "" if c.fragment is None else f"{c.fragment:.4f}",
            COL["RT"]: "" if c.rt is None else f"{c.rt:.2f}",
            COL["± RT"]: f"{c.rt_halfwidth:g}",
            COL["Tol."]: f"{c.tolerance:g}",
            COL["Formula"]: c.formula,
            COL["Internal standard"]: c.internal_standard,
            COL["Conc. unit"]: c.concentration_unit,
            COL["Qualifier of"]: c.qualifier_of,
            COL["Ion ratio %"]: "" if c.ion_ratio is None else f"{c.ion_ratio:g}",
            COL["± ratio %"]: ("" if not c.ion_ratio_tolerance
                               else f"{c.ion_ratio_tolerance:g}"),
        }
        for column, text in values.items():
            item = QtWidgets.QTableWidgetItem(text)
            if column not in (COL["Name"], COL["Group"], COL["Formula"],
                              COL["Internal standard"], COL["Conc. unit"],
                              COL["Qualifier of"]):
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, item)

        check = QtWidgets.QTableWidgetItem()
        check.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                       | QtCore.Qt.ItemFlag.ItemIsEnabled)
        check.setCheckState(QtCore.Qt.CheckState.Checked if c.is_internal_standard
                            else QtCore.Qt.CheckState.Unchecked)
        self.table.setItem(row, COL["IS"], check)

        self._set_combo(row, COL["Unit"], ["Da", "ppm"], c.unit)
        self._set_combo(row, COL["Adduct"], [""] + [a.name for a in ADDUCTS], c.adduct)
        self._set_combo(row, COL["Response"], list(RESPONSES), c.response)

    def _set_combo(self, row: int, column: int, options: list[str], value: str) -> None:
        combo = QtWidgets.QComboBox()
        combo.addItems(options)
        combo.setCurrentText(value if value in options else options[0])
        combo.currentTextChanged.connect(lambda _t: self._commit())
        self.table.setCellWidget(row, column, combo)

    def _read_row(self, row: int) -> Component | None:
        def text(column: int) -> str:
            widget = self.table.cellWidget(row, column)
            if isinstance(widget, QtWidgets.QComboBox):
                return widget.currentText()
            item = self.table.item(row, column)
            return item.text().strip() if item else ""

        name = text(COL["Name"])
        if not name:
            return None
        numbers: dict[str, float | None] = {}
        for column, field in _NUMERIC.items():
            raw = text(column).replace(",", ".")
            try:
                numbers[field] = float(raw) if raw else None
            except ValueError:
                numbers[field] = None

        is_item = self.table.item(row, COL["IS"])
        component = Component(
            name=name,
            precursor=numbers.get("precursor") or 0.0,
            fragment=numbers.get("fragment"),
            rt=numbers.get("rt"),
            rt_halfwidth=numbers.get("rt_halfwidth") or 0.5,
            tolerance=numbers.get("tolerance") or self.session.method.tolerance,
            unit=text(COL["Unit"]) or "Da",
            group=text(COL["Group"]),
            formula=text(COL["Formula"]),
            adduct=text(COL["Adduct"]),
            is_internal_standard=bool(
                is_item and is_item.checkState() == QtCore.Qt.CheckState.Checked
            ),
            internal_standard=text(COL["Internal standard"]),
            response=text(COL["Response"]) or "area",
            concentration_unit=text(COL["Conc. unit"]),
            qualifier_of=text(COL["Qualifier of"]),
            ion_ratio=numbers.get("ion_ratio"),
            ion_ratio_tolerance=numbers.get("ion_ratio_tolerance") or 0.0,
        )
        return component if component.is_valid else None

    def components(self) -> list[Component]:
        rows = (self._read_row(row) for row in range(self.table.rowCount()))
        return [c for c in rows if c is not None]

    def _commit(self) -> None:
        if self._loading:
            return
        self.session.method.replace_all(self.components())
        self.session.notify_method_changed()
        self._update_status()

    def _on_edit(self, item) -> None:
        if self._loading:
            return
        row = item.row()
        # A formula plus an adduct can stand in for the precursor mass, which is
        # how a labelled internal standard is entered: C18H30D4O4 instead of a
        # hand-computed 317.26.
        if item.column() in (COL["Formula"], COL["Adduct"]):
            component = self._read_row(row)
            if component is not None:
                computed = component.precursor_from_formula()
                if computed:
                    self._loading = True
                    self.table.item(row, COL["Precursor"]).setText(f"{computed:.4f}")
                    self._loading = False
        self._commit()

    # -- actions ------------------------------------------------------------------ #
    def _add_row(self) -> None:
        row = self.table.rowCount()
        self._loading = True
        self.table.insertRow(row)
        self._write_row(row, Component(name="new", precursor=0.0))
        self._loading = False
        self.table.editItem(self.table.item(row, COL["Name"]))

    def _remove_rows(self) -> None:
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
        self._commit()

    def _generate(self) -> None:
        components = self.session.generate_components()
        if not components:
            self._report("Open a sample first — the list is built from its "
                         "acquisition method.")
            return
        if self.session.method.components:
            answer = QtWidgets.QMessageBox.question(
                self, "Replace the component list?",
                f"This replaces the current {len(self.session.method.components)} "
                f"component(s) with {len(components)} taken from the acquisition "
                "method. Continue?",
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.session.set_components(components)
        self._report(f"{len(components)} component(s) from the acquisition method. "
                     "Set names, fragments and retention times before processing.")

    def _import(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import components", "", "CSV (*.csv *.txt);;All files (*)")
        if not path:
            return
        try:
            components = load_components(path)
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Could not read the CSV", str(exc))
            return
        if not components:
            self._report("The file had no valid rows.")
            return
        self.session.set_components(components)
        self._report(f"{len(components)} component(s) imported.")

    def _export(self) -> None:
        components = self.components()
        if not components:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export components", "components.csv", "CSV (*.csv)")
        if path:
            save_components(path, components)
            self._report(f"Exported to {path}")

    def _defaults_changed(self, *_args) -> None:
        method = self.session.method
        method.tolerance = self.tol_spin.value()
        method.unit = self.unit_combo.currentText()
        method.concentration_unit = self.conc_edit.text().strip()
        method.ion_ratio_tolerance = self.ratio_spin.value()
        method.ion_ratio_marginal = self.marginal_spin.value()
        self.session.notify_method_changed()

    def _update_status(self) -> None:
        method = self.session.method
        internal = len(method.internal_standards)
        self.status.setText(
            f"{len(method.components)} component(s)"
            + (f", {internal} internal standard(s)" if internal else "")
        )

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
