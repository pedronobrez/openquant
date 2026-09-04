"""Samples workspace: the batch table."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..samples import SAMPLE_TYPES
from ..session import Session

COLUMNS = ["File", "Sample", "Type", "Actual conc.", "Dilution", "Vial",
           "Acquired", "Comment"]
COL = {name: i for i, name in enumerate(COLUMNS)}
EDITABLE = (COL["Sample"], COL["Actual conc."], COL["Dilution"], COL["Comment"])


class SamplesWorkspace(QtWidgets.QWidget):
    """
    Sample type, expected concentration and dilution live here.

    None of it is recorded in the raw file — every injection comes back as
    `kUnknown` — so it is entered once and saved with the project.
    """

    sigStatus = QtCore.pyqtSignal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self._loading = False

        layout = QtWidgets.QVBoxLayout(self)

        bar = QtWidgets.QHBoxLayout()
        self.btn_open = QtWidgets.QPushButton("Open .wiff…")
        self.btn_close = QtWidgets.QPushButton("Close all")
        bar.addWidget(self.btn_open)
        bar.addWidget(self.btn_close)
        bar.addSpacing(20)
        bar.addWidget(QtWidgets.QLabel("Set type of selected rows:"))
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(SAMPLE_TYPES)
        bar.addWidget(self.type_combo)
        self.btn_apply_type = QtWidgets.QPushButton("Apply")
        bar.addWidget(self.btn_apply_type)
        bar.addSpacing(20)
        self.btn_apply_conc = QtWidgets.QPushButton("Apply concentration to selection")
        bar.addWidget(self.btn_apply_conc)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            COL["Comment"], QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setDefaultSectionSize(24)
        layout.addWidget(self.table, 1)

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color:#666;")
        layout.addWidget(self.status)

        self.btn_close.clicked.connect(self._close_all)
        self.btn_apply_type.clicked.connect(self._apply_type)
        self.btn_apply_conc.clicked.connect(self._apply_concentration)
        self.table.itemChanged.connect(self._on_edit)
        session.sigSamplesChanged.connect(self.reload)
        self.reload()

    # -- table <-> session ------------------------------------------------------- #
    def reload(self) -> None:
        self._loading = True
        entries = self.session.entries
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            meta = entry.sample.metadata() if entry.is_loaded else {}
            values = {
                COL["File"]: entry.filename,
                COL["Sample"]: entry.name,
                COL["Actual conc."]: ("" if entry.actual_concentration is None
                                      else f"{entry.actual_concentration:g}"),
                COL["Dilution"]: f"{entry.dilution_factor:g}",
                COL["Vial"]: meta.get("Vial", ""),
                COL["Acquired"]: meta.get("Acquired", ""),
                COL["Comment"]: entry.comment,
            }
            for column, text in values.items():
                item = QtWidgets.QTableWidgetItem(text)
                if column not in EDITABLE:
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    item.setForeground(QtCore.Qt.GlobalColor.darkGray)
                self.table.setItem(row, column, item)

            combo = QtWidgets.QComboBox()
            combo.addItems(SAMPLE_TYPES)
            combo.setCurrentText(entry.sample_type)
            combo.currentTextChanged.connect(
                lambda text, r=row: self._set_type(r, text))
            self.table.setCellWidget(row, COL["Type"], combo)

            if not entry.is_loaded:
                for column in range(len(COLUMNS)):
                    item = self.table.item(row, column)
                    if item:
                        item.setBackground(QtCore.Qt.GlobalColor.lightGray)
        self.table.resizeColumnsToContents()
        self._loading = False
        self._update_status()

    def _on_edit(self, item) -> None:
        if self._loading:
            return
        row, column = item.row(), item.column()
        if row >= len(self.session.entries):
            return
        entry = self.session.entries[row]
        text = item.text().strip()
        if column == COL["Sample"]:
            entry.name = text or entry.name
        elif column == COL["Comment"]:
            entry.comment = text
        elif column == COL["Actual conc."]:
            entry.actual_concentration = self._number(text)
        elif column == COL["Dilution"]:
            entry.dilution_factor = self._number(text) or 1.0
        self._update_status()

    @staticmethod
    def _number(text: str) -> float | None:
        try:
            return float(text.replace(",", ".")) if text else None
        except ValueError:
            return None

    def _set_type(self, row: int, sample_type: str) -> None:
        if not self._loading and row < len(self.session.entries):
            self.session.entries[row].sample_type = sample_type
            self._update_status()

    # -- actions ------------------------------------------------------------------ #
    def _selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def _apply_type(self) -> None:
        sample_type = self.type_combo.currentText()
        rows = self._selected_rows()
        for row in rows:
            widget = self.table.cellWidget(row, COL["Type"])
            if widget is not None:
                widget.setCurrentText(sample_type)
        self._report(f"{len(rows)} sample(s) set to {sample_type}.")

    def _apply_concentration(self) -> None:
        """
        Copy the concentration of the first selected row onto the rest — the
        usual case is a set of standards injected at the same level.
        """
        rows = self._selected_rows()
        if len(rows) < 2:
            self._report("Select the row to copy from, plus the rows to fill.")
            return
        source = self.session.entries[rows[0]].actual_concentration
        self._loading = True
        for row in rows[1:]:
            self.session.entries[row].actual_concentration = source
            self.table.item(row, COL["Actual conc."]).setText(
                "" if source is None else f"{source:g}")
        self._loading = False
        self._report(f"Concentration copied to {len(rows) - 1} sample(s).")

    def _close_all(self) -> None:
        self.session.close_all()
        self._report("All files closed.")

    def _update_status(self) -> None:
        entries = self.session.entries
        by_type: dict[str, int] = {}
        for entry in entries:
            by_type[entry.sample_type] = by_type.get(entry.sample_type, 0) + 1
        summary = ", ".join(f"{n} {name}" for name, n in by_type.items())
        self.status.setText(f"{len(entries)} sample(s)" + (f" — {summary}" if summary else ""))

    def _report(self, text: str) -> None:
        self.status.setText(text)
        self.sigStatus.emit(text)
