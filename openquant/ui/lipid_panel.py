"""Candidate lipids for a measured mass, from the local LIPID MAPS index."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from .. import lipidmaps
from ..chemistry import ADDUCTS
from ..explain import rank_candidates, significant_peaks
from ..matching import PRECURSOR_MATCH_DA
from ..structure import predict
from .structure_view import StructureView

ROLE_RECORD = QtCore.Qt.ItemDataRole.UserRole
ROLE_MZ = QtCore.Qt.ItemDataRole.UserRole + 1
ROLE_ADDUCT = QtCore.Qt.ItemDataRole.UserRole + 2
ROLE_ION = QtCore.Qt.ItemDataRole.UserRole + 3
ROLE_EXPLANATION = QtCore.Qt.ItemDataRole.UserRole + 4


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
    #: name, lm_id, description, m/z — a predicted fragment sent onward
    sigFragment = QtCore.pyqtSignal(str, str, str, float)
    #: (m/z, label) pairs the spectrum should mark as accounted for
    sigMatches = QtCore.pyqtSignal(list)

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

        by_fragment = QtWidgets.QWidget()
        frag_layout = QtWidgets.QVBoxLayout(by_fragment)
        frag_layout.setContentsMargins(0, 6, 0, 0)
        self.modes.addTab(by_fragment, "Fragments")

        frag_form = QtWidgets.QFormLayout()
        self.frag_name = QtWidgets.QLineEdit()
        self.frag_name.setPlaceholderText("Cer(d18:1/16:0), Cholic acid…")
        frag_form.addRow("Lipid:", self.frag_name)

        limits = QtWidgets.QHBoxLayout()
        self.frag_polarity = QtWidgets.QComboBox()
        self.frag_polarity.addItems(["positive", "negative"])
        limits.addWidget(self.frag_polarity)
        self.frag_cuts = QtWidgets.QSpinBox()
        self.frag_cuts.setRange(1, 2)
        self.frag_cuts.setValue(1)
        self.frag_cuts.setPrefix("cuts ≤ ")
        self.frag_cuts.setToolTip(
            "Two are needed to open a ring, or to free a piece held at both "
            "ends — and produce a great many more candidates")
        limits.addWidget(self.frag_cuts)
        self.frag_losses = QtWidgets.QSpinBox()
        self.frag_losses.setRange(0, 2)
        self.frag_losses.setValue(1)
        self.frag_losses.setPrefix("losses ≤ ")
        self.frag_losses.setToolTip(
            "Small neutrals shed after the bond breaks — water, ammonia, CO, "
            "CO2, formic acid")
        limits.addWidget(self.frag_losses)
        frag_form.addRow("Limits:", limits)

        window = QtWidgets.QHBoxLayout()
        self.frag_target = QtWidgets.QLineEdit()
        self.frag_target.setPlaceholderText("264.2686")
        self.frag_target.setToolTip(
            "Show only ions near this mass — for checking whether a fragment "
            "you already use can be accounted for")
        window.addWidget(self.frag_target, 1)
        self.frag_tolerance = QtWidgets.QDoubleSpinBox()
        self.frag_tolerance.setRange(0.001, 5.0)
        self.frag_tolerance.setDecimals(3)
        self.frag_tolerance.setValue(0.01)
        self.frag_tolerance.setPrefix("± ")
        self.frag_tolerance.setSuffix(" Da")
        window.addWidget(self.frag_tolerance)
        frag_form.addRow("Near m/z:", window)
        frag_layout.addLayout(frag_form)

        self.btn_fragments = QtWidgets.QPushButton("Predict fragments")
        self.btn_fragments.setProperty("primary", True)
        frag_layout.addWidget(self.btn_fragments)

        self.frag_tree = QtWidgets.QTreeWidget()
        self.frag_tree.setHeaderLabels(["m/z", "Piece", "Route", "Cuts"])
        self.frag_tree.setColumnWidth(0, 90)
        self.frag_tree.setColumnWidth(1, 120)
        self.frag_tree.setAlternatingRowColors(True)
        self.frag_tree.setToolTip(
            "Double-click to send the m/z on; the drawing below shows where "
            "the molecule would break")
        frag_layout.addWidget(self.frag_tree, 3)

        self.structure_view = StructureView()
        frag_layout.addWidget(self.structure_view, 2)

        self.frag_note = QtWidgets.QLabel(
            "The mass is arithmetic and exact. The route beside it is only the "
            "simplest one that reaches that mass — not evidence of how the "
            "molecule actually breaks. Confirm against a measured product "
            "spectrum before trusting a fragment.")
        self.frag_note.setWordWrap(True)
        self.frag_note.setProperty("role", "warning")
        frag_layout.addWidget(self.frag_note)

        explain_tab = QtWidgets.QWidget()
        explain_layout = QtWidgets.QVBoxLayout(explain_tab)
        explain_layout.setContentsMargins(0, 6, 0, 0)
        self.modes.addTab(explain_tab, "Explain")

        self.explain_header = QtWidgets.QLabel(
            "Take the spectrum on screen, look its precursor up in LIPID MAPS, "
            "and score each candidate by how much of the spectrum its "
            "structure accounts for.")
        self.explain_header.setWordWrap(True)
        self.explain_header.setProperty("role", "hint")
        explain_layout.addWidget(self.explain_header)

        explain_form = QtWidgets.QFormLayout()
        self.explain_precursor = QtWidgets.QLineEdit()
        self.explain_precursor.setPlaceholderText("703.5749")
        explain_form.addRow("Precursor:", self.explain_precursor)
        self.explain_adduct = QtWidgets.QComboBox()
        self.explain_adduct.addItems([a.name for a in ADDUCTS])
        self.explain_adduct.setCurrentText("[M+H]+")
        explain_form.addRow("Adduct:", self.explain_adduct)
        explain_layout.addLayout(explain_form)

        self.btn_explain = QtWidgets.QPushButton("Explain this spectrum")
        self.btn_explain.setProperty("primary", True)
        explain_layout.addWidget(self.btn_explain)

        self.explain_tree = QtWidgets.QTreeWidget()
        self.explain_tree.setHeaderLabels(["Candidate", "Explains", "Peaks",
                                           "Formula"])
        self.explain_tree.setColumnWidth(0, 190)
        self.explain_tree.setAlternatingRowColors(True)
        self.explain_tree.setToolTip(
            "Select a candidate to mark the peaks it accounts for on the "
            "spectrum")
        explain_layout.addWidget(self.explain_tree, 2)

        self.match_tree = QtWidgets.QTreeWidget()
        self.match_tree.setHeaderLabels(["Measured", "ppm", "Route"])
        self.match_tree.setColumnWidth(0, 95)
        self.match_tree.setAlternatingRowColors(True)
        explain_layout.addWidget(self.match_tree, 2)

        self.explain_note = QtWidgets.QLabel(
            "A share is evidence, not proof. Isomers fragment alike, and a long "
            "enough list of possible masses covers a spectrum by accident — so "
            "read the peaks a candidate leaves unexplained as carefully as the "
            "ones it claims.")
        self.explain_note.setWordWrap(True)
        self.explain_note.setProperty("role", "warning")
        explain_layout.addWidget(self.explain_note)

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
        self.btn_fragments.clicked.connect(self.predict_fragments)
        self.frag_name.returnPressed.connect(self.predict_fragments)
        self.frag_target.returnPressed.connect(self.predict_fragments)
        self.frag_tree.currentItemChanged.connect(self._show_cleavage)
        self.frag_tree.itemDoubleClicked.connect(self._fragment_activated)
        self.btn_explain.clicked.connect(self.explain_spectrum)
        self.explain_precursor.returnPressed.connect(self.explain_spectrum)
        self.explain_tree.currentItemChanged.connect(self._show_explanation)
        self.refresh_availability()

    # -- availability -------------------------------------------------------- #
    def refresh_availability(self) -> None:
        installed = lipidmaps.is_installed()
        self.install_box.setVisible(not installed)
        for widget in (self.btn_search, self.mz_edit, self.adduct_combo,
                       self.tol_spin, self.unit_combo,
                       self.btn_lookup, self.name_edit,
                       self.btn_fragments, self.frag_name,
                       self.btn_explain, self.explain_precursor):
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

    # -- fragments ------------------------------------------------------------ #
    def set_fragment_target(self, name: str, mz: float | None = None) -> None:
        """Ask about a lipid from elsewhere in the app."""
        self.frag_name.setText(name)
        if mz is not None:
            self.frag_target.setText(f"{mz:.4f}")
        self.modes.setCurrentIndex(2)
        self.predict_fragments()

    def predict_fragments(self) -> None:
        database = lipidmaps.database()
        if database is None:
            self._report("Install the database first.")
            return
        text = self.frag_name.text().strip()
        if not text:
            self._report("Type a lipid name, its shorthand or its LM_ID.")
            return
        found = database.find_by_name(text, limit=1)
        if not found:
            self._report(f"Nothing named like {text!r}.")
            return

        record = found[0]
        molecule = record.molecule()
        self.frag_tree.clear()
        self.structure_view.set_structure(molecule)
        if molecule is None:
            self._report(
                f"{record.name} has no structure in the index. Reinstall the "
                "database to add the connection tables.")
            return

        charge = 1 if self.frag_polarity.currentIndex() == 0 else -1
        cuts, losses = self.frag_cuts.value(), self.frag_losses.value()
        ions = self._near_target(predict(molecule, charge=charge,
                                         max_cuts=cuts, max_losses=losses))
        wider = ""
        if not ions and self.frag_target.text().strip():
            # a mass the analyst already uses turning up empty is worth more
            # than silence: say what it would take to reach it
            needed = self._reachable_at(molecule, charge, cuts, losses)
            wider = (f" It is reachable with {needed}." if needed else
                     " No combination of one or two cuts and two losses "
                     "reaches it.")

        for ion in ions:
            row = QtWidgets.QTreeWidgetItem(self.frag_tree, [
                f"{ion.mz:.4f}", ion.formula,
                ion.description.split(" ", 1)[1] if " " in ion.description
                else "as drawn",
                str(ion.fragment.cut_count),
            ])
            row.setData(0, ROLE_ION, ion)
            row.setTextAlignment(0, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            row.setTextAlignment(3, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
        if ions:
            self.frag_tree.setCurrentItem(self.frag_tree.topLevelItem(0))

        if wider:
            self._report(f"{record.name}: nothing within the current limits."
                         + wider)
            return
        warning = "" if molecule.reliable else (
            " Its hydrogen count does not match the published formula, so "
            "these masses are not to be trusted.")
        self._report(f"{record.name}: {len(ions)} ion(s) from "
                     f"{len(molecule.atoms)} atoms." + warning)

    def _reachable_at(self, molecule, charge: int, cuts: int,
                      losses: int) -> str:
        """The smallest limits that would reach the mass being asked about."""
        for more_cuts in range(cuts, 3):
            for more_losses in range(losses, 3):
                if (more_cuts, more_losses) == (cuts, losses):
                    continue
                if self._near_target(predict(molecule, charge=charge,
                                             max_cuts=more_cuts,
                                             max_losses=more_losses)):
                    return f"cuts ≤ {more_cuts} and losses ≤ {more_losses}"
        return ""

    def _near_target(self, ions: list) -> list:
        """Narrow to a mass being checked, when one was given."""
        text = self.frag_target.text().strip().replace(",", ".")
        if not text:
            return ions
        try:
            target = float(text)
        except ValueError:
            return ions
        half = self.frag_tolerance.value()
        return [i for i in ions if abs(i.mz - target) <= half]

    def _show_cleavage(self, item, _previous=None) -> None:
        ion = item.data(0, ROLE_ION) if item is not None else None
        self.structure_view.set_fragment(ion.fragment if ion else None)

    def _fragment_activated(self, item, _column: int) -> None:
        ion = item.data(0, ROLE_ION)
        if ion is None:
            return
        name = self.frag_name.text().strip()
        database = lipidmaps.database()
        found = database.find_by_name(name, limit=1) if database else []
        lm_id = found[0].lm_id if found else ""
        self.sigFragment.emit(found[0].name if found else name, lm_id,
                              ion.description, float(ion.mz))
        self._report(f"{ion.mz:.4f} ({ion.description}) sent on. The route is "
                     "the simplest arithmetic, not a mechanism.")

    # -- explaining a measured spectrum --------------------------------------- #
    def set_spectrum(self, mz, intensity, precursor: float | None = None) -> None:
        """Hand the panel the spectrum on screen, ready to be explained."""
        self._peaks = significant_peaks(mz, intensity)
        if precursor:
            self.explain_precursor.setText(f"{precursor:.4f}")
        self.modes.setCurrentIndex(3)
        self.explain_header.setText(
            f"{len(self._peaks)} peak(s) above 1% of the base peak are on "
            "screen. Give the precursor and score the candidates against them.")

    def explain_spectrum(self) -> None:
        database = lipidmaps.database()
        if database is None:
            self._report("Install the database first.")
            return
        peaks = getattr(self, "_peaks", None)
        if not peaks:
            self._report("Show a spectrum first — Process ▸ Explain spectrum "
                         "takes the one on screen.")
            return
        text = self.explain_precursor.text().strip().replace(",", ".")
        try:
            precursor = float(text)
        except ValueError:
            self._report("Type the precursor m/z of this spectrum.")
            return

        adduct = self.explain_adduct.currentText()
        charge = 1 if "+" in adduct else -1
        # the quadrupole passed a window, not a mass, and the method's own
        # figure is rounded besides — 538.6 for a ceramide whose precursor is
        # 538.52. Anything the isolation let through is a candidate.
        ranked = rank_candidates(database, precursor, peaks, adduct=adduct,
                                 tolerance=PRECURSOR_MATCH_DA, unit="Da",
                                 charge=charge)
        self.explain_tree.clear()
        self.match_tree.clear()
        for explanation in ranked:
            row = QtWidgets.QTreeWidgetItem(self.explain_tree, [
                explanation.name,
                f"{explanation.share * 100:.1f}%",
                str(explanation.matched),
                explanation.record.formula,
            ])
            row.setData(0, ROLE_EXPLANATION, explanation)
            row.setTextAlignment(1, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
            row.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignRight
                                 | QtCore.Qt.AlignmentFlag.AlignVCenter)
        if ranked:
            self.explain_tree.setCurrentItem(self.explain_tree.topLevelItem(0))
            top = ranked[0]
            close = [e for e in ranked[1:] if top.share - e.share < 0.05]
            tie = (f" {len(close)} other(s) explain it about as well."
                   if close else "")
            self._report(f"{len(ranked)} candidate(s) at that precursor."
                         + tie)
        else:
            self.sigMatches.emit([])
            self._report(
                f"No structure in the curated database sits within "
                f"±{PRECURSOR_MATCH_DA:g} Da of {precursor:.4f} as {adduct}. "
                "A theoretical species may still exist in the computed set.")

    def _show_explanation(self, item, _previous=None) -> None:
        explanation = item.data(0, ROLE_EXPLANATION) if item is not None else None
        self.match_tree.clear()
        if explanation is None:
            self.sigMatches.emit([])
            return
        for match in sorted(explanation.matches, key=lambda m: -m.intensity):
            row = QtWidgets.QTreeWidgetItem(self.match_tree, [
                f"{match.mz:.4f}", f"{match.error_ppm:+.1f}",
                match.ion.description,
            ])
            for column in (0, 1):
                row.setTextAlignment(column,
                                     QtCore.Qt.AlignmentFlag.AlignRight
                                     | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.sigMatches.emit(
            [(m.mz, m.ion.formula) for m in explanation.matches])

    def _report(self, text: str) -> None:
        self.status.setText(text)
