"""Method workspace: the component table of the processing method."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from .. import lipidmaps, precursor
from ..chemistry import ADDUCTS
from ..components import RESPONSES, Component, load_components, save_components
from ..session import Session
from . import style, theme
from .annotate_dialog import AnnotateDialog, _looks_unnamed, propose

COLUMNS = ["Name", "Group", "Precursor", "Fragment", "RT", "± RT", "Tol.",
           "Unit", "Formula", "Adduct", "IS", "Internal standard", "Response",
           "Conc. unit", "Qualifier of", "Ion ratio %", "± ratio %"]
COL = {name: i for i, name in enumerate(COLUMNS)}

#: widest a column is made when fitted to its contents; past this the
#: analyst widens it themselves rather than losing the rest of the table
MAX_AUTO_WIDTH = 320

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
        #: columns the analyst has dragged; those keep the width they were given
        self._manual_widths: set[int] = set()

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
        self.btn_suggest = QtWidgets.QPushButton("Suggest from data…")
        self.btn_suggest.setToolTip(
            "Retention times from agreement between the open injections, and "
            "window widths from their sampling. Every proposal says what it "
            "rests on and nothing is applied without being ticked")
        self.btn_check = QtWidgets.QPushButton("Check method")
        self.btn_check.setToolTip(
            "Read the method against itself, and against the files that are "
            "open: components that share a transition, internal standards "
            "with no retention time, windows the sampling cannot resolve")
        self.btn_annotate = QtWidgets.QPushButton("Annotate from LIPID MAPS…")
        self.btn_annotate.setToolTip(
            "Propose a lipid species for every component still named after its "
            "precursor mass")
        for widget in (self.btn_add, self.btn_remove, self.btn_generate,
                       self.btn_import, self.btn_export, self.btn_check,
                       self.btn_suggest, self.btn_annotate):
            bar.addWidget(widget)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(60)
        header.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        header.sectionResized.connect(self._section_resized)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setDefaultSectionSize(30)
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
        self.status.setProperty("role", "caption")
        defaults.addWidget(self.status)
        layout.addLayout(defaults)

        self.btn_add.clicked.connect(self._add_row)
        self.btn_remove.clicked.connect(self._remove_rows)
        self.btn_generate.clicked.connect(self._generate)
        self.btn_import.clicked.connect(self._import)
        self.btn_export.clicked.connect(self._export)
        self.btn_check.clicked.connect(self.check_method)
        self.btn_suggest.clicked.connect(self.suggest_from_data)
        self.btn_annotate.clicked.connect(self._annotate)
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
        self._refresh_is_choices()
        self._fit_columns()
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
            COL["Conc. unit"]: c.concentration_unit,
            COL["Qualifier of"]: c.qualifier_of,
            COL["Ion ratio %"]: "" if c.ion_ratio is None else f"{c.ion_ratio:g}",
            COL["± ratio %"]: ("" if not c.ion_ratio_tolerance
                               else f"{c.ion_ratio_tolerance:g}"),
        }
        for column, text in values.items():
            item = QtWidgets.QTableWidgetItem(text)
            if column not in (COL["Name"], COL["Group"], COL["Formula"],
                              COL["Conc. unit"], COL["Qualifier of"]):
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
            elif text:
                # names outrun any sensible column width; keep the full one
                # readable without making the analyst widen the column
                item.setToolTip(text)
            self.table.setItem(row, column, item)

        check = QtWidgets.QTableWidgetItem()
        check.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                       | QtCore.Qt.ItemFlag.ItemIsEnabled)
        check.setCheckState(QtCore.Qt.CheckState.Checked if c.is_internal_standard
                            else QtCore.Qt.CheckState.Unchecked)
        self.table.setItem(row, COL["IS"], check)

        self._set_is_combo(row, c.internal_standard)
        self._set_combo(row, COL["Unit"], ["Da", "ppm"], c.unit)
        self._set_combo(row, COL["Adduct"], [""] + [a.name for a in ADDUCTS], c.adduct)
        self._set_combo(row, COL["Response"], list(RESPONSES), c.response)

    def _set_is_combo(self, row: int, value: str) -> None:
        """The internal standard is picked from a list, never typed."""
        combo = QtWidgets.QComboBox()
        combo.addItem("")
        if value:
            combo.addItem(value)
            combo.setCurrentText(value)
        combo.currentTextChanged.connect(lambda _t: self._commit())
        self.table.setCellWidget(row, COL["Internal standard"], combo)

    def _refresh_is_choices(self) -> None:
        """
        Offer every row ticked IS as a choice, and nothing else.

        A method can still arrive naming a standard that has no row of its own —
        converting someone's spreadsheet usually produces a few. That name stays
        in the list and is marked, because dropping it silently would lose the
        one clue that the reference is broken.
        """
        pool = []
        for row in range(self.table.rowCount()):
            check = self.table.item(row, COL["IS"])
            name = self.table.item(row, COL["Name"])
            if (check is not None and name is not None
                    and check.checkState() == QtCore.Qt.CheckState.Checked
                    and name.text().strip()):
                pool.append(name.text().strip())
        pool.sort(key=str.lower)

        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, COL["Internal standard"])
            if not isinstance(combo, QtWidgets.QComboBox):
                continue
            own = self.table.item(row, COL["Name"])
            own_name = own.text().strip() if own else ""
            options = [""] + [n for n in pool if n != own_name]
            current = combo.currentText()
            unknown = bool(current) and current not in options
            if unknown:
                options.insert(1, current)
            blocked = combo.blockSignals(True)
            combo.clear()
            combo.addItems(options)
            combo.setCurrentIndex(options.index(current) if current in options else 0)
            combo.blockSignals(blocked)
            combo.setStyleSheet(f"color:{theme.warning()};" if unknown else "")
            combo.setToolTip(
                f"nothing is ticked IS under the name \u201c{current}\u201d"
                if unknown else current or "Rows ticked IS appear here")

    def _section_resized(self, index: int, _old: int, _new: int) -> None:
        """A column the analyst sized by hand keeps that width from then on."""
        if not self._loading:
            self._manual_widths.add(index)

    def _fit_columns(self) -> None:
        """Size the columns to what they hold, leaving dragged ones alone."""
        kept = {c: self.table.columnWidth(c) for c in self._manual_widths}
        self.table.resizeColumnsToContents()
        for column in range(self.table.columnCount()):
            if column in kept:
                self.table.setColumnWidth(column, kept[column])
            else:
                self.table.setColumnWidth(
                    column, min(self.table.columnWidth(column), MAX_AUTO_WIDTH))
        style.fit_cell_widgets(self.table)
        for column in kept:
            self.table.setColumnWidth(column, kept[column])

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
        # renaming a row, or ticking it IS, changes what the other rows may point at
        if item.column() in (COL["Name"], COL["IS"]):
            self._refresh_is_choices()
        self._commit()

    # -- actions ------------------------------------------------------------------ #
    def _add_row(self) -> None:
        row = self.table.rowCount()
        self._loading = True
        self.table.insertRow(row)
        self._write_row(row, Component(name="new", precursor=0.0))
        self._refresh_is_choices()
        self._loading = False
        self.table.editItem(self.table.item(row, COL["Name"]))

    def _remove_rows(self) -> None:
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)
        self._refresh_is_choices()
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

    def suggest_from_data(self) -> None:
        """Offer what the open files can say about times and windows."""
        from .suggest_dialog import SuggestDialog

        if not self.session.method.components:
            QtWidgets.QMessageBox.information(
                self, "Suggest from data",
                "Build the component list first — there is nothing to look "
                "for.")
            return
        dialog = SuggestDialog(self.session, self)
        if dialog.load():
            dialog.exec()
        dialog.deleteLater()

    def check_method(self) -> None:
        """
        Say what the method will fail at, before a batch is processed.

        Everything here would otherwise be learned from the results, which is
        both later and harder: a component that shares a transition with
        another reports a number that is not wrong so much as not its own.
        """
        from ..health import SERIOUS, check_method

        health = check_method(self.session.method, self.session.entries)
        if health.sound and not health.skipped:
            QtWidgets.QMessageBox.information(
                self, "Check method",
                f"Nothing in the {health.components} components contradicts "
                f"itself.")
            return

        lines = []
        for finding in health.findings:
            names = ", ".join(finding.components[:8])
            if finding.count > 8:
                names += f", and {finding.count - 8} more"
            mark = "SERIOUS" if finding.severity == SERIOUS else "warning"
            lines.append(f"{mark} — {finding.summary}\n    {finding.detail}"
                         f"\n    {names}")
        for note in health.skipped:
            lines.append(f"not checked — {note}")

        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Check method")
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning if health.serious
                    else QtWidgets.QMessageBox.Icon.Information)
        box.setText(f"{len(health.serious)} serious, {len(health.warnings)} "
                    f"warning(s) over {health.components} components.")
        box.setDetailedText("\n\n".join(lines))
        box.exec()

    def _export(self) -> None:
        components = self.components()
        if not components:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export components", "components.csv", "CSV (*.csv)")
        if path:
            save_components(path, components)
            self._report(f"Exported to {path}")

    def _annotate(self) -> None:
        """Name the unnamed components from their precursor masses."""
        if lipidmaps.database() is None:
            QtWidgets.QMessageBox.information(
                self, "LIPID MAPS not installed",
                "Open the Explorer's LIPID MAPS tab and download the database "
                "first. It is a one-off 21 MB download.")
            return
        components = self.components()
        if not components:
            self._report("Build the component list first.")
            return

        wanted = [c for c in components if _looks_unnamed(c)]
        if not wanted:
            self._report("Every component already has a name.")
            return

        measured = self._measure_precursors(wanted)
        proposals = propose(components, adduct="[M-H]-", tolerance=10.0,
                            unit="ppm", only_unnamed=True, measured=measured)
        if not proposals:
            self._report("Every component already has a name.")
            return

        dialog = AnnotateDialog(proposals, self)
        if not dialog.exec():
            return
        accepted = dialog.accepted_proposals()
        for proposal in accepted:
            proposal.component.name = proposal.species
            proposal.component.formula = proposal.formula
            proposal.component.lm_id = proposal.lm_id
            if not proposal.component.adduct:
                proposal.component.adduct = "[M-H]-"
        self.session.set_components(components)
        self._report(f"{len(accepted)} component(s) annotated.")

    def _measure_precursors(self, components: list) -> dict:
        """
        Read each precursor's real mass off the survey scan before searching.

        The method's own list is only good to the decimals it was typed with,
        which at these masses is around fifteen parts per million — enough for
        a database search to return a confident, wrong answer.
        """
        loaded = self.session.loaded_entries
        if not loaded:
            self._report("Open the samples first — the accurate mass is "
                         "measured from their survey scans.")
            return {}

        dialog = QtWidgets.QProgressDialog(
            "Measuring precursor masses from the survey scan…", "Cancel",
            0, len(components), self)
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(300)

        def report(done: int, _total: int) -> bool:
            dialog.setValue(done)
            QtWidgets.QApplication.processEvents()
            return not dialog.wasCanceled()

        measured = precursor.measure_all(loaded, components,
                                         self.session.method, progress=report)
        dialog.setValue(len(components))
        reliable = sum(1 for c in measured.values() if c.is_reliable)
        self._report(f"{reliable} of {len(measured)} precursor(s) measured "
                     "from the survey scan.")
        return measured

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
