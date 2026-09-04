"""Gerenciador de compostos alvo — equivalente ao XIC Manager do PeakView."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ..compounds import Compound, load_compounds, save_compounds

COLUMNS = ["Nome", "Precursor", "Fragmento", "RT", "± RT", "Tol.", "Un."]
_NUMERIC = {1: "precursor", 2: "fragment", 3: "rt", 4: "rt_halfwidth", 5: "tolerance"}


class CompoundPanel(QtWidgets.QWidget):
    """
    Tabela editavel de compostos, com importacao/exportacao em CSV e disparo da
    extracao em lote sobre as amostras abertas.
    """

    sigExtractAll = QtCore.pyqtSignal(list)   # list[Compound]
    sigShowCompound = QtCore.pyqtSignal(object)  # Compound

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setToolTip(
            "Duplo clique numa linha mostra o XIC daquele composto.\n"
            "Colunas em branco são opcionais: sem fragmento usa-se o precursor;\n"
            "sem RT a busca cobre a corrida inteira."
        )
        layout.addWidget(self.table, 1)

        buttons = QtWidgets.QGridLayout()
        self.btn_add = QtWidgets.QPushButton("Adicionar")
        self.btn_remove = QtWidgets.QPushButton("Remover")
        self.btn_load = QtWidgets.QPushButton("Importar CSV…")
        self.btn_save = QtWidgets.QPushButton("Exportar CSV…")
        buttons.addWidget(self.btn_add, 0, 0)
        buttons.addWidget(self.btn_remove, 0, 1)
        buttons.addWidget(self.btn_load, 1, 0)
        buttons.addWidget(self.btn_save, 1, 1)
        layout.addLayout(buttons)

        self.btn_extract = QtWidgets.QPushButton("Extrair e integrar todos")
        self.btn_extract.setToolTip(
            "Gera o XIC de cada composto em cada amostra marcada e integra o pico"
        )
        font = self.btn_extract.font()
        font.setBold(True)
        self.btn_extract.setFont(font)
        layout.addWidget(self.btn_extract)

        self.btn_add.clicked.connect(lambda: self.add_compound(Compound("novo", 0.0)))
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_load.clicked.connect(self._load)
        self.btn_save.clicked.connect(self._save)
        self.btn_extract.clicked.connect(
            lambda: self.sigExtractAll.emit(self.compounds())
        )
        self.table.cellDoubleClicked.connect(self._double_clicked)
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.table,
                        activated=self._remove_selected)

    # -- dados --------------------------------------------------------------- #
    def add_compound(self, compound: Compound) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            compound.name,
            f"{compound.precursor:.4f}",
            "" if compound.fragment is None else f"{compound.fragment:.4f}",
            "" if compound.rt is None else f"{compound.rt:.2f}",
            f"{compound.rt_halfwidth:g}",
            f"{compound.tolerance:g}",
            compound.unit,
        ]
        for column, text in enumerate(values):
            item = QtWidgets.QTableWidgetItem(text)
            if column:
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, item)

    def set_compounds(self, compounds: list[Compound]) -> None:
        self.table.setRowCount(0)
        for compound in compounds:
            self.add_compound(compound)

    def compounds(self) -> list[Compound]:
        """Le a tabela; linhas invalidas (sem nome ou sem precursor) sao ignoradas."""
        out: list[Compound] = []
        for row in range(self.table.rowCount()):
            compound = self._compound_at(row)
            if compound is not None:
                out.append(compound)
        return out

    def _compound_at(self, row: int) -> Compound | None:
        def text(column: int) -> str:
            item = self.table.item(row, column)
            return item.text().strip() if item else ""

        name = text(0)
        if not name:
            return None
        numbers: dict[str, float | None] = {}
        for column, field in _NUMERIC.items():
            raw = text(column).replace(",", ".")
            try:
                numbers[field] = float(raw) if raw else None
            except ValueError:
                numbers[field] = None
        if not numbers.get("precursor"):
            return None
        unit = text(6) or "Da"
        return Compound(
            name=name,
            precursor=numbers["precursor"],
            fragment=numbers.get("fragment"),
            rt=numbers.get("rt"),
            rt_halfwidth=numbers.get("rt_halfwidth") or 0.5,
            tolerance=numbers.get("tolerance") or 0.02,
            unit="ppm" if unit.lower() == "ppm" else "Da",
        )

    # -- acoes --------------------------------------------------------------- #
    def _remove_selected(self) -> None:
        for index in sorted({i.row() for i in self.table.selectedIndexes()},
                            reverse=True):
            self.table.removeRow(index)

    def _double_clicked(self, row: int, _column: int) -> None:
        compound = self._compound_at(row)
        if compound is not None:
            self.sigShowCompound.emit(compound)

    def _load(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Importar lista de compostos", "", "CSV (*.csv *.txt);;Todos (*)"
        )
        if not path:
            return
        try:
            compounds = load_compounds(path)
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Não consegui ler o CSV", str(exc))
            return
        if not compounds:
            QtWidgets.QMessageBox.information(
                self, "Lista vazia", "O arquivo não tinha nenhuma linha válida."
            )
            return
        self.set_compounds(compounds)

    def _save(self) -> None:
        compounds = self.compounds()
        if not compounds:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar lista de compostos", "compostos.csv", "CSV (*.csv)"
        )
        if path:
            save_compounds(path, compounds)
