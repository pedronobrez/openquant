"""
Every infused compound on one row: the summary that comes before the pages.

The per-compound report answers *is this vial what the label says it is?* one
vial at a time. A folder of infusions is nine of those, and the question asked
of nine is a different one — which of them measured its precursor, which found
its fragments, which matched the record made of the same compound last month,
and which did not. That is a table, and this is it.

Nothing is measured until asked. Averaging a whole run, centroiding a quarter
of a million points, searching a library and scoring every infusion of a
compound against the others is a few seconds per compound, so *Measure* waits
to be pressed and the table stays as it was until it is pressed again. The
summary is held on the session and not saved with the project: it is derived
from the files, and a table stored without the spectra behind it could not be
checked against them.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from .. import audit
from ..infusion_report import (SUMMARY_COLUMNS, InfusionRow, InfusionSummary,
                               prepare_documents, summarise, write_pdf,
                               write_summary_csv)
from ..session import Session
from .settings import settings

HELP_PAGE = "infusion-report"

#: the two columns whose cell is an abbreviation of a sentence, by name
#: rather than by position: a column added in the middle would otherwise
#: move the tooltip onto the wrong cell without anything failing
FOUND_COLUMN = SUMMARY_COLUMNS.index("Found m/z")
OTHERS_COLUMN = SUMMARY_COLUMNS.index("Other infusions")

#: the setting the analyst's own library is remembered under, written by the
#: Explorer's library panel. Read rather than owned: there is one library of
#: one's own and both places mean the same file.
SETTING_OWN_PATH = "library/own_path"


class _Cell(QtWidgets.QTableWidgetItem):
    """A cell that sorts on its number where it has one."""

    def __init__(self, text: str, key):
        super().__init__(text)
        self.key = key

    def __lt__(self, other) -> bool:
        mine, theirs = self.key, getattr(other, "key", other.text())
        if isinstance(mine, float) and isinstance(theirs, float):
            return mine < theirs
        return str(mine).lower() < str(theirs).lower()


class InfusionsPanel(QtWidgets.QWidget):
    """One row per infused compound, measured on request."""

    #: how many rows the table holds, for the tab that shows it
    sigRowsChanged = QtCore.pyqtSignal(int)
    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.settings = settings()
        #: set by the shell: the Explorer, whose LIPID MAPS tab may already
        #: have explained the compound on screen. Duck-typed and optional, so
        #: this panel can be built and exercised with no Explorer at all.
        self.explorer = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = QtWidgets.QHBoxLayout()
        self.btn_measure = QtWidgets.QPushButton("Measure")
        self.btn_measure.setToolTip(
            "Average every open infusion over its whole run, read the "
            "precursor, explain what the method's formula can, search your "
            "own library and score each infusion against the others of the "
            "same compound. A few seconds per compound, which is why it "
            "waits to be asked")
        bar.addWidget(self.btn_measure)
        self.btn_report = QtWidgets.QPushButton("Report…")
        self.btn_report.setToolTip(
            "Write the per-compound document for the selected rows — every "
            "row when none is selected — one section per compound")
        self.btn_report.setEnabled(False)
        bar.addWidget(self.btn_report)
        self.btn_csv = QtWidgets.QPushButton("Export CSV…")
        self.btn_csv.setToolTip("The table as it stands, every column")
        self.btn_csv.setEnabled(False)
        bar.addWidget(self.btn_csv)
        self.btn_quantify = QtWidgets.QPushButton("Quantify…")
        self.btn_quantify.setToolTip(
            "Measure each analyte against the internal standard the method "
            "gives it, in the averaged spectrum of every open infusion: the "
            "two responses, the isotope cross-talk between them and the "
            "ratio. Independent of the table above — it needs a component "
            "table with an internal standard set, not a Measure")
        bar.addWidget(self.btn_quantify)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(SUMMARY_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(SUMMARY_COLUMNS))
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.setToolTip(
            "One row per infused sample. A cell that could not be filled "
            "says why instead of being blank — which check was not run, or "
            "what was not there to measure")
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("Not measured yet — press Measure.")
        self.status.setProperty("role", "caption")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.btn_measure.clicked.connect(self.measure)
        self.btn_report.clicked.connect(self.write_report)
        self.btn_csv.clicked.connect(self.export_csv)
        self.btn_quantify.clicked.connect(self.quantify)
        session.sigSamplesChanged.connect(self._invalidate)

        from .help_window import describe
        describe(self, HELP_PAGE)
        self.reload()

    # -- measuring ------------------------------------------------------------ #
    @property
    def summary(self) -> InfusionSummary | None:
        return getattr(self.session, "infusion_summary", None)

    def own_library(self):
        """The analyst's own library, or None with the reason left to the
        summary — a library that is not set is not an error."""
        from ..library import load_library

        path = self.settings.value(SETTING_OWN_PATH, "", type=str)
        if not path or not os.path.exists(path):
            return None
        try:
            return load_library(path)
        except (OSError, ValueError):
            return None

    def explanations(self) -> dict:
        """
        What the Explorer's LIPID MAPS tab has already produced, by compound.

        One at most: the panel holds the last explanation it made, and it
        belongs to whatever was on screen when it was made. Anything else is
        explained here from the component table.
        """
        from ..infusion_report import compound_of

        explorer = self.explorer
        if explorer is None:
            return {}
        panel = getattr(explorer, "lipid_panel", None)
        explanation = getattr(panel, "current_explanation", None)
        if callable(explanation):
            try:
                explanation = explanation()
            except Exception:
                explanation = None
        ref = getattr(explorer, "active_ref", None)
        name = getattr(getattr(ref, "entry", None), "name", "")
        compound = compound_of(name)
        if explanation is None or not compound:
            return {}
        return {compound: explanation}

    def measure(self) -> None:
        library = self.own_library()
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor)
        try:
            summary = summarise(self.session, library=library,
                                explanations=self.explanations())
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.session.infusion_summary = summary
        self.reload()

    def _invalidate(self) -> None:
        """A file opened or closed makes the table a description of a batch
        that is no longer the open one."""
        self.session.infusion_summary = None
        self.reload()

    # -- content -------------------------------------------------------------- #
    def reload(self) -> None:
        summary = self.summary
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        rows = summary.rows if summary is not None else []
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            cells, keys = row.cells(), row.keys()
            for column, text in enumerate(cells):
                item = _Cell(text, keys[column])
                if isinstance(keys[column], float):
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter)
                item.setToolTip(self._tooltip(row, column, text))
                self.table.setItem(index, column, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.btn_report.setEnabled(bool(rows))
        self.btn_csv.setEnabled(bool(rows))
        self._describe()
        self.sigRowsChanged.emit(len(rows))

    @staticmethod
    def _tooltip(row: InfusionRow, column: int, text: str) -> str:
        """
        The whole sentence where the cell holds an abbreviation of it.

        A cell is a few characters wide and the reason a measurement could
        not be made is a sentence; the short form goes in the table and the
        long one here, rather than the reason being lost to the width.
        """
        if column == FOUND_COLUMN and row.found is None:
            return (row.report.survivor_note
                    or getattr(row.report.measurement, "note", "")
                    or text)
        if column == OTHERS_COLUMN and row.others:
            return "\n".join(
                f"{label}: score {score * 100:.0f}, reverse "
                f"{reverse * 100:.0f}, {matched} of {of_other} peak(s)"
                for label, score, reverse, matched, of_other in row.others)
        return text

    def _describe(self) -> None:
        summary = self.summary
        if summary is None:
            self.status.setText("Not measured yet — press Measure.")
            return
        said = summary.summary()
        if summary.rows:
            said += f" · measured in {summary.seconds:.1f} s"
        self.status.setText(said)
        self.sigStatus.emit(said)

    # -- what comes off it ---------------------------------------------------- #
    def chosen(self) -> list[InfusionRow]:
        """
        The selected rows, or every row when nothing is selected.

        In the table's own order, which is the order it is sorted in: a
        document whose sections are in a different order from the table they
        were chosen in reads as a different set of rows.
        """
        summary = self.summary
        if summary is None or not summary.rows:
            return []
        selected = {index.row() for index in
                    self.table.selectionModel().selectedRows()}
        # the table is sorted, so its rows are not the summary's: the sample
        # name is what identifies one, and it is unique per acquisition
        by_name = {row.sample: row for row in summary.rows}
        picked = []
        for visual in range(self.table.rowCount()):
            if selected and visual not in selected:
                continue
            item = self.table.item(visual, 1)
            row = by_name.get(item.text()) if item is not None else None
            if row is not None:
                picked.append(row)
        return picked

    def write_report(self, path: str = "") -> str:
        """Write the per-compound document for the chosen rows."""
        rows = self.chosen()
        if not rows:
            self.status.setText("Measure first; there is nothing to report.")
            return ""
        if not path:
            start = os.path.join(
                self.settings.value("io/last_dir", "", type=str),
                "infusion-report.pdf")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Write the infusion report", start, "PDF (*.pdf)")
            if not path:
                return ""
            self.settings.setValue("io/last_dir", os.path.dirname(path))
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor)
        try:
            reports = prepare_documents(rows)
            write_pdf(reports, path)
        except (OSError, ValueError) as exc:
            self.status.setText(f"Could not write {path}: {exc}")
            return ""
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        names = ", ".join(dict.fromkeys(row.compound for row in rows))
        self.session.record(
            audit.INFUSION_REPORT, names, after=os.path.basename(path),
            note=f"{len(rows)} infusion(s) from the Infusions tab")
        self._report(f"{len(rows)} infusion(s) written to "
                     f"{os.path.basename(path)}.")
        return path

    def export_csv(self, path: str = "") -> str:
        """The whole table, not the selection: a summary with rows left out
        is not the thing it claims to be."""
        summary = self.summary
        if summary is None or not summary.rows:
            self.status.setText("Measure first; there is nothing to export.")
            return ""
        if not path:
            start = os.path.join(
                self.settings.value("io/last_dir", "", type=str),
                "infusions.csv")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Export the infusion summary", start, "CSV (*.csv)")
            if not path:
                return ""
            self.settings.setValue("io/last_dir", os.path.dirname(path))
        try:
            written = write_summary_csv(summary, path)
        except OSError as exc:
            self.status.setText(f"Could not write {path}: {exc}")
            return ""
        self._report(f"{len(summary.rows)} row(s) written to "
                     f"{os.path.basename(written)}.")
        return written

    # -- quantitation ---------------------------------------------------------- #
    def quantify(self):
        """
        Open the ratio dialog: analyte over internal standard, in the spray.

        Not gated on the summary above having been measured. The two answer
        different questions — that one asks whether a vial is what its label
        says, this one asks how much of one compound there is against
        another — and they read the files independently.
        """
        from .infusion_quant_dialog import InfusionQuantDialog

        dialog = InfusionQuantDialog(self.session, self)
        dialog.measure()
        dialog.exec()
        return dialog

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
