"""Reviewing LIPID MAPS proposals for a whole component table."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6 import QtCore, QtWidgets

from .. import lipidmaps
from ..components import Component


@dataclass
class Proposal:
    """One component and the species a mass search suggests for it."""

    component: Component
    species: str = ""
    formula: str = ""
    lm_id: str = ""
    error_ppm: float = 0.0
    structures: int = 0
    species_count: int = 0
    window_mda: float = 0.0
    note: str = ""

    @property
    def has_match(self) -> bool:
        """Only an unambiguous species is offered for automatic use."""
        return bool(self.species) and self.species_count == 1


def propose(components: list[Component], adduct: str = "[M-H]-",
            tolerance: float = 10.0, unit: str = "ppm",
            only_unnamed: bool = True) -> list[Proposal]:
    """
    Suggest a species for each component from its precursor mass.

    Two things keep this honest. The search window is never narrower than the
    precursor's own precision — a mass written as 351.20 is known to ±0.005 Da,
    so asking for 10 ppm of it would be inventing digits. And a component is
    only offered for automatic naming when exactly one species falls in that
    window; anything else is reported with its count and left for a person,
    because at nominal precision several species usually fit.
    """
    database = lipidmaps.database()
    if database is None:
        return []
    out: list[Proposal] = []
    for component in components:
        if only_unnamed and not _looks_unnamed(component):
            continue
        requested = (component.precursor * tolerance * 1e-6
                     if unit.lower() == "ppm" else tolerance)
        window = max(requested, lipidmaps.mass_precision(component.precursor))
        groups = lipidmaps.group_by_species(
            database.search_mz(component.precursor, adduct, window, "Da"))

        proposal = Proposal(component=component, window_mda=window * 1000.0,
                            species_count=len(groups))
        if not groups:
            proposal.note = "no lipid at this mass"
            out.append(proposal)
            continue

        best = groups[0]
        proposal.species = best.species
        proposal.formula = best.formula
        proposal.error_ppm = best.error_ppm
        proposal.structures = len(best.records)
        proposal.lm_id = best.records[0].lm_id if len(best.records) == 1 else ""
        if len(groups) > 1:
            proposal.note = f"{len(groups)} species fit — needs an accurate mass"
        elif len(best.records) > 1:
            proposal.note = f"{len(best.records)} isomers share it"
        out.append(proposal)
    return out


def _looks_unnamed(component: Component) -> bool:
    """A component still carrying its generated name is just a number."""
    name = component.name.strip()
    if not name:
        return True
    try:
        float(name)
    except ValueError:
        return False
    return True


class AnnotateDialog(QtWidgets.QDialog):
    """Accept or reject each proposal; nothing is written until OK."""

    COLUMNS = ["Use", "Component", "Best species", "Formula", "ppm",
               "± window", "Note"]

    def __init__(self, proposals: list[Proposal], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Annotate from LIPID MAPS")
        self.resize(720, 460)
        self._proposals = proposals

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            "The search window is widened to each precursor's own precision, so "
            "a mass written to two decimals is searched at ±5 mDa, not at a few "
            "ppm. Only rows where exactly one species fits are ticked; the rest "
            "need an accurate mass from the survey scan. A species is still a "
            "family of isomers, never a compound.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        self.table = QtWidgets.QTableWidget(len(proposals), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        for row, proposal in enumerate(proposals):
            use = QtWidgets.QTableWidgetItem()
            use.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                         | (QtCore.Qt.ItemFlag.ItemIsEnabled
                            if proposal.has_match else QtCore.Qt.ItemFlag.NoItemFlags))
            use.setCheckState(QtCore.Qt.CheckState.Checked if proposal.has_match
                              else QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, use)
            values = [
                proposal.component.name,
                proposal.species or "—",
                proposal.formula or "—",
                f"{proposal.error_ppm:+.1f}" if proposal.has_match else "—",
                str(proposal.structures) if proposal.has_match else "—",
                proposal.lm_id or proposal.note,
            ]
            for column, text in enumerate(values, start=1):
                item = QtWidgets.QTableWidgetItem(text)
                if column in (4, 5):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
        layout.addWidget(self.table, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(
            "Apply the checked rows")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accepted_proposals(self) -> list[Proposal]:
        out = []
        for row, proposal in enumerate(self._proposals):
            item = self.table.item(row, 0)
            if item and item.checkState() == QtCore.Qt.CheckState.Checked:
                out.append(proposal)
        return out
