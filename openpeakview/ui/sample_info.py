"""Painel de informacoes da amostra e do canal ativo."""

from __future__ import annotations

from PyQt6 import QtWidgets


class SampleInfoPanel(QtWidgets.QWidget):
    """Mostra metadados da injecao e os parametros do experimento selecionado."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Campo", "Valor"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        layout.addWidget(self.tree)

        self.copy_button = QtWidgets.QPushButton("Copiar tudo")
        self.copy_button.clicked.connect(self._copy)
        layout.addWidget(self.copy_button)

        self.clear()

    def clear(self) -> None:
        self.tree.clear()
        placeholder = QtWidgets.QTreeWidgetItem(self.tree, ["—", "nenhuma amostra"])
        placeholder.setDisabled(True)

    def show_sample(self, sample, channel=None) -> None:
        """Preenche o painel com os dados da amostra e, se houver, do canal."""
        self.tree.clear()

        group = QtWidgets.QTreeWidgetItem(self.tree, ["Amostra", ""])
        for key, value in sample.metadata().items():
            QtWidgets.QTreeWidgetItem(group, [key, value])
        group.setExpanded(True)

        if channel is not None:
            info = channel.info
            group = QtWidgets.QTreeWidgetItem(self.tree, ["Canal ativo", ""])
            rows = [
                ("Indice", str(info.index)),
                ("Nome", info.name),
                ("Tipo", info.experiment_type),
                ("Polaridade", info.polarity),
                ("Precursor", "—" if info.precursor is None else f"{info.precursor:.4f}"),
                ("Faixa de massa", f"{info.start_mass:.1f} – {info.end_mass:.1f}"),
                ("Scans", str(info.n_scans)),
            ]
            rt = channel.rt
            if rt.size:
                rows.append(("Faixa de tempo", f"{rt[0]:.3f} – {rt[-1]:.3f} min"))
            for key, value in rows:
                QtWidgets.QTreeWidgetItem(group, [key, value])
            group.setExpanded(True)

            parameters = channel.parameters()
            if parameters:
                group = QtWidgets.QTreeWidgetItem(self.tree, ["Parâmetros do método", ""])
                for key, value in parameters.items():
                    QtWidgets.QTreeWidgetItem(group, [key, value])
                group.setExpanded(False)

        self.tree.resizeColumnToContents(0)

    def _copy(self) -> None:
        lines = []

        def walk(item, depth=0):
            lines.append("  " * depth + f"{item.text(0)}\t{item.text(1)}".rstrip())
            for i in range(item.childCount()):
                walk(item.child(i), depth + 1)

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))
