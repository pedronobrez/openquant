"""Candidate lipids for a measured mass, from the local LIPID MAPS index."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from .. import lipidmaps
from ..chemistry import ADDUCTS

ROLE_RECORD = QtCore.Qt.ItemDataRole.UserRole
ROLE_MZ = QtCore.Qt.ItemDataRole.UserRole + 1
ROLE_ADDUCT = QtCore.Qt.ItemDataRole.UserRole + 2


class LipidPanel(QtWidgets.QWidget):
    """
    Looks a mass up in LMSD and lists what it could be.

    Species first, structures underneath: a mass search cannot separate isomers,
    and eleven DiHOMEs listed as eleven answers would imply a precision the
    measurement does not have.
    """

    sigAnnotate = QtCore.pyqtSignal(str, str, str)   # name, formula, lm_id
    #: name, formula, lm_id, adduct, m/z — a lipid resolved to a channel
    sigPrecursor = QtCore.pyqtSignal(str, str, str, str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.modes = QtWidgets.QTabWidget()
        self.modes.setDocumentMode(True)
        layout.addWidget(self.modes)

        by_mass = QtWidgets.QWidget()
        mass_layout = QtWidgets.QVBoxLayout(by_mass)
        mass_layout.setContentsMargins(0, 6, 0, 0)
        self.modes.addTab(by_mass, "Mass → lipid")

        form = QtWidgets.QFormLayout()
        self.mz_edit = QtWidgets.QLineEdit()
        self.mz_edit.setPlaceholderText("313.2384")
        form.addRow("Measured m/z:", self.mz_edit)

        self.adduct_combo = QtWidgets.QComboBox()
        self.adduct_combo.addItems([a.name for a in ADDUCTS])
        self.adduct_combo.setCurrentText("[M-H]-")
        form.addRow("Adduct:", self.adduct_combo)

        tolerance = QtWidgets.QHBoxLayout()
        self.tol_spin = QtWidgets.QDoubleSpinBox()
        self.tol_spin.setDecimals(3)
        self.tol_spin.setRange(0.001, 1000.0)
        self.tol_spin.setValue(10.0)
        self.unit_combo = QtWidgets.QComboBox()
        self.unit_combo.addItems(["ppm", "Da"])
        tolerance.addWidget(self.tol_spin)
        tolerance.addWidget(self.unit_combo)
        form.addRow("Tolerance (±):", tolerance)
        mass_layout.addLayout(form)

        self.btn_search = QtWidgets.QPushButton("Search LIPID MAPS")
        self.btn_search.setProperty("primary", True)
        mass_layout.addWidget(self.btn_search)

        by_name = QtWidgets.QWidget()
        name_layout = QtWidgets.QVBoxLayout(by_name)
        name_layout.setContentsMargins(0, 6, 0, 0)
        self.modes.addTab(by_name, "Lipid → mass")

        name_form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("SM(d18:1/16:0), Cer(d18:1/16:0), LMSP03010003")
        self.name_edit.setToolTip(
            "The LIPID MAPS name, its shorthand or its LM_ID. A method's own "
            "label — C16:0-Ceramide — is not one of these; search the shorthand.")
        name_form.addRow("Lipid:", self.name_edit)
        name_layout.addLayout(name_form)

        self.btn_lookup = QtWidgets.QPushButton("Find the precursor")
        self.btn_lookup.setProperty("primary", True)
        name_layout.addWidget(self.btn_lookup)

        self.name_tree = QtWidgets.QTreeWidget()
        self.name_tree.setHeaderLabels(["Lipid", "Formula", "Neutral", "LM_ID"])
        self.name_tree.setColumnWidth(0, 200)
        self.name_tree.setColumnWidth(1, 110)
        self.name_tree.setAlternatingRowColors(True)
        self.name_tree.setToolTip("Pick the lipid; its ions are listed below")
        name_layout.addWidget(self.name_tree, 1)

        self.ion_tree = QtWidgets.QTreeWidget()
        self.ion_tree.setHeaderLabels(["Adduct", "m/z", "z"])
        self.ion_tree.setColumnWidth(0, 130)
        self.ion_tree.setAlternatingRowColors(True)
        self.ion_tree.setToolTip(
            "Double-click an ion to use its m/z as the precursor")
        name_layout.addWidget(self.ion_tree, 1)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Species / structure", "Formula", "mDa",
                                   "ppm", "n"])
        self.tree.setColumnWidth(0, 210)
        self.tree.setColumnWidth(1, 120)
        self.tree.setAlternatingRowColors(True)
        self.tree.setToolTip(
            "Double-click a structure to name the component after it")
        mass_layout.addWidget(self.tree, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "hint")
        layout.addWidget(self.status)

        self.install_box = QtWidgets.QWidget()
        install_layout = QtWidgets.QVBoxLayout(self.install_box)
        install_layout.setContentsMargins(0, 0, 0, 0)
        message = QtWidgets.QLabel(
            "The LIPID MAPS database is not installed yet. It is a one-off "
            "21 MB download that becomes a 1.3 MB local index — after that, "
            "lookups need no network.")
        message.setWordWrap(True)
        install_layout.addWidget(message)
        self.btn_install = QtWidgets.QPushButton("Download the database")
        install_layout.addWidget(self.btn_install)
        layout.addWidget(self.install_box)

        self.btn_search.clicked.connect(self.search)
        self.mz_edit.returnPressed.connect(self.search)
        self.btn_install.clicked.connect(self.install)
        self.tree.itemDoubleClicked.connect(self._activated)
        self.btn_lookup.clicked.connect(self.look_up_name)
        self.name_edit.returnPressed.connect(self.look_up_name)
        self.name_tree.currentItemChanged.connect(self._show_ions)
        self.ion_tree.itemDoubleClicked.connect(self._ion_activated)
        self.refresh_availability()

    # -- availability -------------------------------------------------------- #
    def refresh_availability(self) -> None:
        installed = lipidmaps.is_installed()
        self.install_box.setVisible(not installed)
        for widget in (self.btn_search, self.mz_edit, self.adduct_combo,
                       self.tol_spin, self.unit_combo,
                       self.btn_lookup, self.name_edit):
            widget.setEnabled(installed)
        if installed:
            database = lipidmaps.database()
            self.status.setText(
                f"{len(database):,} curated structures indexed locally."
                if database else "")

    def install(self) -> None:
        self.btn_install.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            lipidmaps.install(progress=self._report)
            lipidmaps.forget()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Could not install the database",
                f"{exc}\n\nThe download is about 21 MB from lipidmaps.org.")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.btn_install.setEnabled(True)
            self.refresh_availability()

    # -- searching ------------------------------------------------------------ #
    def set_target(self, mz: float, adduct: str | None = None) -> None:
        self.mz_edit.setText(f"{mz:.4f}")
        if adduct:
            self.adduct_combo.setCurrentText(adduct)

    def search(self) -> None:
        database = lipidmaps.database()
        if database is None:
            self._report("Install the database first.")
            return
        text = self.mz_edit.text().strip().replace(",", ".")
        try:
            mz = float(text)
        except ValueError:
            self._report("Type a measured m/z first.")
            return

        matches = database.search_mz(mz, self.adduct_combo.currentText(),
                                     self.tol_spin.value(),
                                     self.unit_combo.currentText())
        groups = lipidmaps.group_by_species(matches)
        self._fill(groups)
        unit = self.unit_combo.currentText()
        if groups:
            self._report(f"{len(groups)} species, {len(matches)} structure(s) "
                         f"within ±{self.tol_spin.value():g} {unit}. "
                         "A mass cannot separate isomers — confirm before using.")
        else:
            self._report(
                f"Nothing within ±{self.tol_spin.value():g} {unit}. The curated "
                "database has no structure at that mass; a theoretical species "
                "may still exist in LIPID MAPS' computed set.")

    def _fill(self, groups) -> None:
        self.tree.clear()
        for group in groups:
            parent = QtWidgets.QTreeWidgetItem(self.tree, [
                group.species, group.formula, f"{group.error_mda:+.2f}",
                f"{group.error_ppm:+.1f}", str(len(group.records)),
            ])
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            parent.setToolTip(0, group.main_class)
            for record in group.records:
                child = QtWidgets.QTreeWidgetItem(
                    parent, [record.name or record.systematic_name,
                             record.lm_id, "", "", ""])
                child.setToolTip(1, record.lm_id)
                child.setData(0, ROLE_RECORD, record.lm_id)
                child.setToolTip(0, record.systematic_name or record.name)
            parent.setExpanded(len(groups) <= 3)

    def _activated(self, item, _column: int) -> None:
        lm_id = item.data(0, ROLE_RECORD)
        if not lm_id:
            item.setExpanded(not item.isExpanded())
            return
        database = lipidmaps.database()
        record = database.by_id(lm_id) if database else None
        if record is None:
            return
        self.sigAnnotate.emit(record.name or record.abbrev, record.formula,
                              record.lm_id)
        self._report(f"{record.name} ({record.lm_id}) sent to the component.")

    # -- the other direction: a lipid, and where it would be seen ------------- #
    def set_name(self, name: str) -> None:
        """Put a name in the box and look it up, from elsewhere in the app."""
        self.name_edit.setText(name)
        self.modes.setCurrentIndex(1)
        self.look_up_name()

    def look_up_name(self) -> None:
        database = lipidmaps.database()
        if database is None:
            self._report("Install the database first.")
            return
        text = self.name_edit.text().strip()
        if not text:
            self._report("Type a lipid name, its shorthand or its LM_ID.")
            return

        records = database.find_by_name(text, limit=40)
        self.name_tree.clear()
        self.ion_tree.clear()
        for record in records:
            item = QtWidgets.QTreeWidgetItem(
                self.name_tree,
                [record.name or record.abbrev, record.formula,
                 f"{record.exact_mass:.4f}", record.lm_id])
            item.setData(0, ROLE_RECORD, record.lm_id)
            item.setToolTip(0, record.systematic_name or record.name)
            item.setToolTip(2, f"{record.exact_mass:.6f} Da, monoisotopic")
            item.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignRight
                                  | QtCore.Qt.AlignmentFlag.AlignVCenter)
        if records:
            self.name_tree.setCurrentItem(self.name_tree.topLevelItem(0))
            self._report(f"{len(records)} match(es). The ions below are exact "
                         "arithmetic on the formula, not rounded values.")
        else:
            self._report(
                f"Nothing named like {text!r}. LIPID MAPS uses its own "
                "shorthand — Cer(d18:1/16:0) rather than C16:0-Ceramide.")

    def _show_ions(self, item, _previous=None) -> None:
        self.ion_tree.clear()
        lm_id = item.data(0, ROLE_RECORD) if item is not None else None
        database = lipidmaps.database()
        record = database.by_id(lm_id) if (database and lm_id) else None
        if record is None:
            return
        for form in lipidmaps.ion_forms(record):
            row = QtWidgets.QTreeWidgetItem(
                self.ion_tree,
                [form.adduct, f"{form.mz:.4f}", f"{form.charge:+d}"])
            row.setData(0, ROLE_MZ, form.mz)
            row.setData(0, ROLE_ADDUCT, form.adduct)
            row.setData(0, ROLE_RECORD, record.lm_id)
            row.setTextAlignment(1, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            row.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            if form.adduct == "[M+H]+":
                font = row.font(0)
                font.setBold(True)
                for column in range(3):
                    row.setFont(column, font)

    def _ion_activated(self, item, _column: int) -> None:
        mz = item.data(0, ROLE_MZ)
        database = lipidmaps.database()
        record = database.by_id(item.data(0, ROLE_RECORD)) if database else None
        if mz is None or record is None:
            return
        adduct = item.data(0, ROLE_ADDUCT)
        self.sigPrecursor.emit(record.name or record.abbrev, record.formula,
                               record.lm_id, adduct, float(mz))
        self._report(f"{record.name} {adduct} — {mz:.4f} sent to the component.")

    def _report(self, text: str) -> None:
        self.status.setText(text)
