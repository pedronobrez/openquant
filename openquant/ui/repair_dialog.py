"""
The written precursors a formula contradicts, and the repair of them.

`components.fill_formulas` refuses a formula whose mass disagrees with the
precursor the method already carries, and `health.check_method` reports the
disagreement as serious — both of them stop at saying that one of the two
numbers is wrong. On the method this was written against, all sixteen
refusals were the *precursor*: masses typed to one decimal, one dropped
digit, two rows a whole dalton out.

This is the other way out of that stand-off. It lists each disagreement with
both masses, the difference in Da and in ppm, and what the extraction window
does, and writes the formula and the precursor together for the rows that are
ticked — each one an entry in the audit trail. Nothing else is touched,
and a row that is not ticked is not touched at all.

The pre-ticking is the whole argument of the dialog: a sub-dalton difference
is one compound written down two ways and the repair is arithmetic, so it is
offered ready to apply; a whole dalton is two different compounds and no
amount of arithmetic says which one the instrument acquired, so it is offered
unticked and somebody has to say.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..audit import PRECURSOR_REPAIRED
from ..components import WHOLE_DALTON, Component, PrecursorRepair
from ..matching import PRECURSOR_MATCH_DA
from ..session import Session
from .help_window import describe, open_manual

HELP_PAGE = "method-workspace"


def _window(bounds: tuple[float, float]) -> str:
    return f"{bounds[0]:,.4f}–{bounds[1]:,.4f}"


class RepairPrecursorsDialog(QtWidgets.QDialog):
    """Tick the precursors to take from the formula, then apply."""

    COLUMNS = ["Use", "Component", "Written", "From the formula", "Formula",
               "Δ mDa", "Δ ppm", "Window now", "Window after", "Note"]

    def __init__(self, session: Session, repairs: list[PrecursorRepair],
                 components: list[Component] | None = None, parent=None):
        super().__init__(parent)
        self.session = session
        self.repairs = list(repairs)
        #: the table the workspace is holding, written back whole when a
        #: repair is applied; None means the method's own list is already the
        #: one being repaired
        self._components = components
        self.applied: list[PrecursorRepair] = []
        self.setWindowTitle("Repair precursors from formulas")
        self.resize(1080, 480)
        describe(self, HELP_PAGE)

        layout = QtWidgets.QVBoxLayout(self)
        blurb = QtWidgets.QLabel(
            f"Each row's formula gives a mass that its written precursor "
            f"contradicts. Applying a row writes <b>both</b> the formula and "
            f"the precursor, and records the change. Rows under "
            f"{WHOLE_DALTON:g} Da apart are the same compound written to "
            f"fewer places and are ticked; a row a whole dalton or more out "
            f"is a different compound or a mistyped digit — which of the name "
            f"and the mass is wrong is not something arithmetic can settle, "
            f"so it is offered unticked. A precursor is what "
            f"picks the acquisition channel, within ±{PRECURSOR_MATCH_DA:g} Da "
            f"of the channel's own, and — where the row has no fragment — what "
            f"the extraction window is built from: process the batch again "
            f"afterwards.")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        self.table = QtWidgets.QTableWidget(len(self.repairs), len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            len(self.COLUMNS) - 1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        # the Note column holds a sentence: elided it says nothing, so it
        # wraps and the row grows to fit it (see the folder dialog, where the
        # same thing was found by rendering rather than by reading)
        self.table.setWordWrap(True)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
        for row, repair in enumerate(self.repairs):
            tick = QtWidgets.QTableWidgetItem()
            tick.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable
                          | QtCore.Qt.ItemFlag.ItemIsEnabled)
            tick.setCheckState(QtCore.Qt.CheckState.Checked if repair.offered
                               else QtCore.Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, tick)
            ppm = repair.error_ppm
            cells = [
                repair.component.name,
                f"{repair.written:,.4f}",
                f"{repair.theoretical:,.4f}",
                repair.formula,
                f"{repair.difference * 1000:+,.1f}",
                "—" if ppm is None else f"{ppm:+,.1f}",
                _window(repair.window_before),
                _window(repair.window_after),
                repair.note,
            ]
            for column, text in enumerate(cells, start=1):
                item = QtWidgets.QTableWidgetItem(text)
                if column == len(self.COLUMNS) - 1:
                    item.setToolTip(text)
                if column in (2, 3, 5, 6):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                          | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
        for column in range(len(self.COLUMNS) - 1):
            self.table.resizeColumnToContents(column)
        layout.addWidget(self.table, 1)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Help)
        self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Apply
        ).setText("Apply the ticked repairs")
        self.buttons.rejected.connect(self.reject)
        self.buttons.helpRequested.connect(lambda: open_manual(self, HELP_PAGE))
        self.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply
                            ).clicked.connect(self.apply_selected)
        layout.addWidget(self.buttons)

    def showEvent(self, event):
        """
        Fit the rows once the columns have their real width.

        `resizeRowsToContents` measures a wrapped sentence against the width
        the column has *now*, and until the dialog is shown the stretched
        Note column has no width worth measuring against — the rows come out
        one line tall and the sentence is cut off.
        """
        super().showEvent(event)
        self.table.resizeRowsToContents()

    # -- the rows ---------------------------------------------------------------- #
    def selected(self) -> list[PrecursorRepair]:
        chosen = []
        for row, repair in enumerate(self.repairs):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == QtCore.Qt.CheckState.Checked:
                chosen.append(repair)
        return chosen

    def apply_selected(self) -> int:
        """
        Write the ticked repairs, one audit entry each; returns how many.

        The entries are written before the method is replaced, so that a
        trail read afterwards shows the masses in the order they changed
        rather than a single line saying the table moved.
        """
        chosen = self.selected()
        for repair in chosen:
            before, after = repair.audit_before, repair.audit_after
            repair.apply()
            self.session.record(
                PRECURSOR_REPAIRED, f"{repair.component.name} · precursor",
                before=before, after=after, note=repair.audit_note)
        self.applied = chosen
        if chosen:
            if self._components is not None:
                self.session.method.replace_all(self._components)
            # the same call the component table makes when a cell is typed
            # in: it drops the conditioned traces, which were extracted
            # through the windows that have just moved
            self.session.notify_method_changed()
        self.accept()
        return len(chosen)

    # -- what to say afterwards --------------------------------------------------- #
    def summary(self) -> str:
        """One line for the status bar, including what is now out of date."""
        if not self.applied:
            return "No precursor was changed."
        moved = sum(1 for r in self.applied if r.moves_window)
        said = [f"{len(self.applied)} precursor(s) repaired from their formulas"]
        if moved:
            said.append(f"{moved} extraction window(s) moved")
        names = {r.component.name for r in self.applied}
        stale = sum(1 for r in self.session.results if r.component in names)
        if stale:
            said.append(f"{stale} result row(s) were integrated with the old "
                        f"masses — process the batch again")
        return ", ".join(said) + "."
