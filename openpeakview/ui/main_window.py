"""Janela principal do OpenPeakView."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from ..compounds import Compound
from ..processing import detect_peaks, integrate, signal_to_noise
from ..wiff import Channel, Sample, WiffFile
from .compound_panel import CompoundPanel
from .plots import ChromatogramView, SpectrumView, Trace, colour
from .results_panel import Result, ResultsPanel
from .sample_info import SampleInfoPanel

ROLE_REF = QtCore.Qt.ItemDataRole.UserRole

# Diferenca maxima, em Da, entre o precursor de um composto e o de um canal do
# metodo para considerar que o canal e o daquele composto.
PRECURSOR_MATCH_DA = 0.7


class ChannelRef:
    """Referencia a um no da arvore: TIC da amostra ou um canal especifico."""

    def __init__(self, wiff: WiffFile, sample: Sample, channel: Channel | None):
        self.wiff = wiff
        self.sample = sample
        self.channel = channel
        self.alias = os.path.splitext(os.path.basename(wiff.path))[0]

    @property
    def key(self) -> str:
        idx = "TIC" if self.channel is None else str(self.channel.index)
        return f"{self.wiff.path}|{self.sample.index}|{idx}"

    @property
    def label(self) -> str:
        if self.channel is None:
            return f"{self.alias} · TIC"
        return f"{self.alias} · {self.channel.info.short_label}"

    @property
    def full_label(self) -> str:
        base = os.path.splitext(self.wiff.filename)[0]
        if self.channel is None:
            return f"{base} · TIC da amostra"
        return f"{base} · {self.channel.info.label}"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenPeakView")
        self.resize(1600, 980)

        self.settings = QtCore.QSettings("OpenPeakView", "OpenPeakView")
        self.files: list[WiffFile] = []
        self.refs: dict[str, ChannelRef] = {}
        self.xic_defs: list[dict] = []
        self.active_ref: ChannelRef | None = None
        self.current_scan: int = 0
        self._background_cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}

        self.chrom = ChromatogramView()
        self.spectrum = SpectrumView()

        self._build_ui()
        self._connect()
        self._restore_settings()
        self._update_status("Abra um arquivo .wiff para começar.")

    # ------------------------------------------------------------------ UI -- #
    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self._wrap_chromatogram())
        splitter.addWidget(self._wrap_spectrum())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

        self._build_tree_dock()
        self._build_side_dock()
        self._build_toolbars()
        self._build_menu()
        self.statusBar().showMessage("")

    def _wrap_chromatogram(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.setSpacing(4)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Cromatograma:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["TIC", "BPC"])
        self.mode_combo.setToolTip("Tipo de cromatograma dos canais marcados")
        bar.addWidget(self.mode_combo)
        bar.addSpacing(16)
        bar.addWidget(QtWidgets.QLabel("Canal ativo (espectros / XIC):"))
        self.active_combo = QtWidgets.QComboBox()
        self.active_combo.setMinimumWidth(320)
        bar.addWidget(self.active_combo, 1)
        layout.addLayout(bar)
        layout.addWidget(self.chrom)
        return box

    def _wrap_spectrum(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 0, 4, 4)
        layout.setSpacing(4)

        bar = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QToolButton()
        self.btn_prev.setText("◀")
        self.btn_prev.setToolTip("Scan anterior (seta esquerda)")
        self.btn_next = QtWidgets.QToolButton()
        self.btn_next.setText("▶")
        self.btn_next.setToolTip("Próximo scan (seta direita)")
        self.scan_spin = QtWidgets.QSpinBox()
        self.scan_spin.setMinimum(1)
        self.scan_spin.setMaximum(1)
        self.scan_spin.setToolTip("Número do scan (1 = primeiro ciclo do canal)")
        self.rt_label = QtWidgets.QLabel("—")
        self.rt_label.setMinimumWidth(170)

        bar.addWidget(QtWidgets.QLabel("Scan:"))
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.scan_spin)
        bar.addWidget(self.btn_next)
        bar.addWidget(self.rt_label)
        bar.addStretch(1)
        self.bg_label = QtWidgets.QLabel("")
        self.bg_label.setStyleSheet("color:#b07800;")
        bar.addWidget(self.bg_label)
        self.btn_avg = QtWidgets.QPushButton("Média da faixa selecionada")
        self.btn_avg.setToolTip(
            "Espectro médio dos scans dentro da faixa marcada no cromatograma"
        )
        bar.addWidget(self.btn_avg)
        layout.addLayout(bar)
        layout.addWidget(self.spectrum)
        return box

    def _build_tree_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Amostras e canais", self)
        dock.setObjectName("dock_tree")
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)

        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filtrar canais (ex.: 313.2)")
        self.filter_edit.setClearButtonEnabled(True)
        layout.addWidget(self.filter_edit)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        layout.addWidget(self.tree, 1)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_none = QtWidgets.QPushButton("Desmarcar tudo")
        self.btn_ms1 = QtWidgets.QPushButton("Só TOF MS")
        buttons.addWidget(self.btn_none)
        buttons.addWidget(self.btn_ms1)
        layout.addLayout(buttons)

        dock.setWidget(panel)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
                             | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        dock.setMinimumWidth(330)
        self.dock_tree = dock

    def _build_side_dock(self) -> None:
        dock = QtWidgets.QDockWidget("Painéis", self)
        dock.setObjectName("dock_side")
        self.tabs = QtWidgets.QTabWidget()

        self.compound_panel = CompoundPanel()
        self.results_panel = ResultsPanel()
        self.sample_info = SampleInfoPanel()

        self.tabs.addTab(self.compound_panel, "Compostos")
        self.tabs.addTab(self.results_panel, "Resultados")
        self.tabs.addTab(self._build_xic_tab(), "XIC manual")
        self.tabs.addTab(self._build_peaks_tab(), "Picos do espectro")
        self.tabs.addTab(self.sample_info, "Amostra")

        dock.setWidget(self.tabs)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setMinimumWidth(360)
        self.dock_side = dock

    def _build_xic_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        form = QtWidgets.QFormLayout()
        self.xic_mz = QtWidgets.QLineEdit()
        self.xic_mz.setPlaceholderText("183.1391, 313.2384")
        form.addRow("m/z (separe por vírgula):", self.xic_mz)

        tol_row = QtWidgets.QHBoxLayout()
        self.xic_tol = QtWidgets.QDoubleSpinBox()
        self.xic_tol.setDecimals(4)
        self.xic_tol.setRange(0.0001, 500.0)
        self.xic_tol.setValue(0.02)
        self.xic_unit = QtWidgets.QComboBox()
        self.xic_unit.addItems(["Da", "ppm"])
        tol_row.addWidget(self.xic_tol)
        tol_row.addWidget(self.xic_unit)
        form.addRow("Tolerância (±):", tol_row)
        layout.addLayout(form)

        self.xic_all_channels = QtWidgets.QCheckBox(
            "Extrair de todos os canais marcados"
        )
        layout.addWidget(self.xic_all_channels)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_xic = QtWidgets.QPushButton("Extrair XIC")
        self.btn_xic_clear = QtWidgets.QPushButton("Limpar XICs")
        buttons.addWidget(self.btn_xic)
        buttons.addWidget(self.btn_xic_clear)
        layout.addLayout(buttons)

        layout.addWidget(QtWidgets.QLabel("XICs ativos:"))
        self.xic_list = QtWidgets.QListWidget()
        self.xic_list.setToolTip("Delete remove o XIC selecionado")
        layout.addWidget(self.xic_list, 1)

        hint = QtWidgets.QLabel(
            "Dica: selecione uma faixa no espectro (Shift + arrastar) e clique "
            "com o botão direito para extrair o XIC dela."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666; font-size:11px;")
        layout.addWidget(hint)
        return page

    def _build_peaks_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self.peak_table = QtWidgets.QTableWidget(0, 3)
        self.peak_table.setHorizontalHeaderLabels(["m/z", "Intensidade", "% base"])
        self.peak_table.horizontalHeader().setStretchLastSection(True)
        self.peak_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.peak_table.setToolTip("Duplo clique extrai o XIC daquela massa")
        layout.addWidget(self.peak_table)
        return page

    def _build_toolbars(self) -> None:
        bar = self.addToolBar("Principal")
        bar.setObjectName("toolbar_main")
        bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self.act_open = bar.addAction("Abrir .wiff")
        bar.addSeparator()
        self.act_select = QtGui.QAction("Selecionar faixa", self, checkable=True)
        self.act_select.setToolTip(
            "Arrastar seleciona faixa em vez de dar zoom "
            "(Shift + arrastar faz o mesmo a qualquer momento)"
        )
        bar.addAction(self.act_select)
        self.act_autoscale = bar.addAction("Ajustar escala")
        bar.addSeparator()
        self.act_norm = QtGui.QAction("Normalizar", self, checkable=True)
        bar.addAction(self.act_norm)
        self.act_mirror = QtGui.QAction("Espelhar", self, checkable=True)
        self.act_mirror.setToolTip(
            "Inverte os traços pares — compara amostra e branco em espelho"
        )
        bar.addAction(self.act_mirror)
        self.act_labels = QtGui.QAction("Rótulos m/z", self, checkable=True)
        self.act_labels.setChecked(True)
        bar.addAction(self.act_labels)
        self.act_apex = QtGui.QAction("Rótulos de RT", self, checkable=True)
        self.act_apex.setChecked(True)
        bar.addAction(self.act_apex)
        self.act_legend = QtGui.QAction("Legenda", self, checkable=True)
        self.act_legend.setChecked(True)
        bar.addAction(self.act_legend)

        proc = self.addToolBar("Processamento")
        proc.setObjectName("toolbar_proc")
        proc.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        proc.addWidget(QtWidgets.QLabel(" Suavizar (σ, scans): "))
        self.smooth_spin = QtWidgets.QDoubleSpinBox()
        self.smooth_spin.setRange(0.0, 25.0)
        self.smooth_spin.setSingleStep(0.5)
        self.smooth_spin.setDecimals(1)
        self.smooth_spin.setToolTip("Suavização gaussiana; 0 desliga")
        proc.addWidget(self.smooth_spin)

        proc.addWidget(QtWidgets.QLabel("  Linha de base (min): "))
        self.baseline_spin = QtWidgets.QDoubleSpinBox()
        self.baseline_spin.setRange(0.0, 60.0)
        self.baseline_spin.setSingleStep(0.5)
        self.baseline_spin.setDecimals(1)
        self.baseline_spin.setToolTip(
            "Largura da janela usada para estimar a linha de base; 0 desliga.\n"
            "Deve ser maior que o pico mais largo que você quer preservar."
        )
        proc.addWidget(self.baseline_spin)
        proc.addSeparator()

        self.act_set_bg = proc.addAction("Definir background")
        self.act_set_bg.setToolTip(
            "Usa a faixa selecionada no cromatograma como branco: todo espectro "
            "gerado a partir daí sai com esse fundo subtraído"
        )
        self.act_clear_bg = proc.addAction("Limpar background")
        proc.addSeparator()
        self.act_detect = proc.addAction("Detectar picos")
        self.act_detect.setToolTip(
            "Integra os picos de todos os traços do cromatograma e "
            "preenche a aba Resultados"
        )

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&Arquivo")
        file_menu.addAction(self.act_open)
        self.act_close = file_menu.addAction("Fechar todos")
        file_menu.addSeparator()
        self.act_exp_chrom = file_menu.addAction("Exportar cromatogramas (CSV)…")
        self.act_exp_spec = file_menu.addAction("Exportar espectro (CSV)…")
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Sair")
        quit_action.triggered.connect(self.close)

        view_menu = self.menuBar().addMenu("&Exibir")
        for action in (self.act_autoscale, self.act_norm, self.act_mirror,
                       self.act_labels, self.act_apex, self.act_legend):
            view_menu.addAction(action)

        proc_menu = self.menuBar().addMenu("&Processar")
        for action in (self.act_set_bg, self.act_clear_bg, self.act_detect):
            proc_menu.addAction(action)

        help_menu = self.menuBar().addMenu("A&juda")
        help_menu.addAction("Como usar…").triggered.connect(self._show_help)

    # -------------------------------------------------------------- sinais -- #
    def _connect(self) -> None:
        self.act_open.triggered.connect(self.open_files)
        self.act_close.triggered.connect(self.close_all)
        self.act_autoscale.triggered.connect(self._autoscale_both)
        self.act_select.toggled.connect(self._set_select_mode)
        self.act_norm.toggled.connect(self._set_normalised)
        self.act_mirror.toggled.connect(self._set_mirror)
        self.act_labels.toggled.connect(self.spectrum.set_labels_enabled)
        self.act_apex.toggled.connect(self.chrom.set_apex_labels)
        self.act_legend.toggled.connect(self.chrom.set_legend_visible)
        self.act_exp_chrom.triggered.connect(
            lambda: self._export(self.chrom, "cromatogramas"))
        self.act_exp_spec.triggered.connect(
            lambda: self._export(self.spectrum, "espectro"))
        self.act_set_bg.triggered.connect(self._set_background)
        self.act_clear_bg.triggered.connect(self._clear_background)
        self.act_detect.triggered.connect(self._detect_peaks)

        self.smooth_spin.valueChanged.connect(self._set_smoothing)
        self.baseline_spin.valueChanged.connect(self.chrom.set_baseline)

        self.tree.itemChanged.connect(self._on_tree_changed)
        self.tree.currentItemChanged.connect(self._on_tree_selection)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.btn_none.clicked.connect(lambda: self._bulk_check(lambda ref: False))
        self.btn_ms1.clicked.connect(
            lambda: self._bulk_check(
                lambda ref: ref.channel is not None and ref.channel.info.is_ms1
            )
        )

        self.mode_combo.currentTextChanged.connect(lambda _: self.refresh_chromatogram())
        self.active_combo.currentIndexChanged.connect(self._on_active_changed)

        self.chrom.sigClicked.connect(self._on_chrom_click)
        self.chrom.sigRangeSelected.connect(self._on_chrom_range)
        self.chrom.sigBackgroundChanged.connect(self._on_background_changed)
        self.spectrum.sigExtractRequested.connect(self._extract_from_range)

        self.btn_prev.clicked.connect(lambda: self._step_scan(-1))
        self.btn_next.clicked.connect(lambda: self._step_scan(+1))
        self.scan_spin.valueChanged.connect(self._on_scan_spin)
        self.btn_avg.clicked.connect(self._average_selection)

        self.btn_xic.clicked.connect(self._extract_from_form)
        self.btn_xic_clear.clicked.connect(self._clear_xics)
        self.peak_table.cellDoubleClicked.connect(self._peak_double_clicked)

        self.compound_panel.sigExtractAll.connect(self._extract_compounds)
        self.compound_panel.sigShowCompound.connect(self._show_compound)
        self.results_panel.sigResultActivated.connect(self._go_to_result)

        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Left), self,
                        activated=lambda: self._step_scan(-1))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Right), self,
                        activated=lambda: self._step_scan(+1))
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.xic_list,
                        activated=self._remove_selected_xic)

    # ---------------------------------------------------------- preferencias - #
    def _restore_settings(self) -> None:
        s = self.settings
        geometry = s.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = s.value("window/state")
        if state is not None:
            self.restoreState(state)

        def flag(key: str, default: bool) -> bool:
            return s.value(key, default, type=bool)

        self.act_norm.setChecked(flag("view/normalise", False))
        self.act_mirror.setChecked(flag("view/mirror", False))
        self.act_labels.setChecked(flag("view/labels", True))
        self.act_apex.setChecked(flag("view/apex", True))
        self.act_legend.setChecked(flag("view/legend", True))
        self.act_select.setChecked(flag("view/select_mode", False))
        self.smooth_spin.setValue(s.value("proc/smooth", 0.0, type=float))
        self.baseline_spin.setValue(s.value("proc/baseline", 0.0, type=float))
        self.xic_tol.setValue(s.value("xic/tolerance", 0.02, type=float))
        self.xic_unit.setCurrentText(s.value("xic/unit", "Da", type=str))
        self.xic_all_channels.setChecked(flag("xic/all_channels", False))
        self.mode_combo.setCurrentText(s.value("chrom/mode", "TIC", type=str))

        stored = s.value("compounds/list", "", type=str)
        if stored:
            try:
                self.compound_panel.set_compounds(
                    [Compound(**row) for row in json.loads(stored)]
                )
            except (ValueError, TypeError):
                pass

        # aplica o que foi restaurado (os sinais ja estao conectados)
        self._set_select_mode(self.act_select.isChecked())
        self._set_normalised(self.act_norm.isChecked())
        self._set_mirror(self.act_mirror.isChecked())
        self.spectrum.set_labels_enabled(self.act_labels.isChecked())
        self.chrom.set_apex_labels(self.act_apex.isChecked())
        self.chrom.set_legend_visible(self.act_legend.isChecked())
        self._set_smoothing(self.smooth_spin.value())
        self.chrom.set_baseline(self.baseline_spin.value())

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/state", self.saveState())
        s.setValue("view/normalise", self.act_norm.isChecked())
        s.setValue("view/mirror", self.act_mirror.isChecked())
        s.setValue("view/labels", self.act_labels.isChecked())
        s.setValue("view/apex", self.act_apex.isChecked())
        s.setValue("view/legend", self.act_legend.isChecked())
        s.setValue("view/select_mode", self.act_select.isChecked())
        s.setValue("proc/smooth", self.smooth_spin.value())
        s.setValue("proc/baseline", self.baseline_spin.value())
        s.setValue("xic/tolerance", self.xic_tol.value())
        s.setValue("xic/unit", self.xic_unit.currentText())
        s.setValue("xic/all_channels", self.xic_all_channels.isChecked())
        s.setValue("chrom/mode", self.mode_combo.currentText())
        s.setValue(
            "compounds/list",
            json.dumps([asdict(c) for c in self.compound_panel.compounds()]),
        )

    def _last_dir(self) -> str:
        return self.settings.value("io/last_dir", "", type=str)

    def _remember_dir(self, path: str) -> None:
        self.settings.setValue("io/last_dir", os.path.dirname(path))

    # -------------------------------------------------------------- arquivos - #
    def open_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Abrir arquivos SCIEX", self._last_dir(),
            "Arquivos wiff (*.wiff);;Todos (*)"
        )
        for path in paths:
            self.load_file(path)
        if paths:
            self._remember_dir(paths[0])

    def load_file(self, path: str) -> None:
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            wiff = WiffFile(path)
            self.files.append(wiff)
            self._add_file_to_tree(wiff)
        except Exception as exc:  # pragma: no cover - depende do arquivo
            QtWidgets.QMessageBox.critical(
                self, "Falha ao abrir", f"{os.path.basename(path)}\n\n{exc}"
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _add_file_to_tree(self, wiff: WiffFile) -> None:
        self.tree.blockSignals(True)
        file_item = QtWidgets.QTreeWidgetItem(self.tree, [wiff.filename])
        font = file_item.font(0)
        font.setBold(True)
        file_item.setFont(0, font)

        for s in range(len(wiff.sample_names)):
            sample = wiff.sample(s)
            sample_item = QtWidgets.QTreeWidgetItem(
                file_item, [f"{sample.name}  ({sample.instrument})"]
            )
            self._add_leaf(sample_item, "TIC da amostra (todos os canais)",
                           ChannelRef(wiff, sample, None), checked=True)
            for channel in sample.channels:
                self._add_leaf(sample_item, channel.info.label,
                               ChannelRef(wiff, sample, channel), checked=False)
            sample_item.setExpanded(True)
        file_item.setExpanded(True)
        self.tree.blockSignals(False)
        self._recompute_aliases()
        self._rebuild_active_combo()
        self.refresh_chromatogram()

    def _recompute_aliases(self) -> None:
        """
        Encurta os nomes usados na legenda removendo o prefixo comum a todos os
        arquivos abertos: `..._demo_QC001` e `..._demo_S001` viram
        `QC001` e `S001`.
        """
        stems = [os.path.splitext(os.path.basename(w.path))[0] for w in self.files]
        prefix = os.path.commonprefix(stems) if len(stems) > 1 else ""
        prefix = prefix[: prefix.rfind("_") + 1] if "_" in prefix else ""
        for ref in self.refs.values():
            stem = os.path.splitext(os.path.basename(ref.wiff.path))[0]
            ref.alias = stem[len(prefix):] or stem

    def _add_leaf(self, parent, text: str, ref: ChannelRef, checked: bool) -> None:
        item = QtWidgets.QTreeWidgetItem(parent, [text])
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            0,
            QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked,
        )
        item.setData(0, ROLE_REF, ref.key)
        self.refs[ref.key] = ref

    def close_all(self) -> None:
        for wiff in self.files:
            wiff.close()
        self.files.clear()
        self.refs.clear()
        self.xic_defs.clear()
        self.active_ref = None
        self._background_cache.clear()
        self.tree.clear()
        self.xic_list.clear()
        self.active_combo.clear()
        self.chrom.clear_traces()
        self.chrom.clear_peak_markers()
        self.chrom.clear_background_range()
        self.spectrum.clear_traces()
        self.peak_table.setRowCount(0)
        self.results_panel.clear()
        self.sample_info.clear()
        self._update_status("Nenhum arquivo aberto.")

    # ------------------------------------------------------------------ arvore #
    def _checked_refs(self) -> list[ChannelRef]:
        out = []
        it = QtWidgets.QTreeWidgetItemIterator(
            self.tree, QtWidgets.QTreeWidgetItemIterator.IteratorFlag.Checked
        )
        while it.value():
            key = it.value().data(0, ROLE_REF)
            if key in self.refs:
                out.append(self.refs[key])
            it += 1
        return out

    def _checked_samples(self) -> list[ChannelRef]:
        """Uma referencia por amostra marcada, preservando a ordem da arvore."""
        seen, out = set(), []
        for ref in self._checked_refs():
            identity = (ref.wiff.path, ref.sample.index)
            if identity not in seen:
                seen.add(identity)
                out.append(ref)
        if out:
            return out
        # nada marcado: usa todas as amostras abertas
        for wiff in self.files:
            for index in range(len(wiff.sample_names)):
                out.append(ChannelRef(wiff, wiff.sample(index), None))
        return out

    def _bulk_check(self, predicate) -> None:
        self.tree.blockSignals(True)
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            key = item.data(0, ROLE_REF)
            if key in self.refs:
                item.setCheckState(
                    0,
                    QtCore.Qt.CheckState.Checked if predicate(self.refs[key])
                    else QtCore.Qt.CheckState.Unchecked,
                )
            it += 1
        self.tree.blockSignals(False)
        self._rebuild_active_combo()
        self.refresh_chromatogram()

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, ROLE_REF) is not None:
                item.setHidden(bool(needle) and needle not in item.text(0).lower())
            it += 1

    def _on_tree_changed(self, item, column) -> None:
        self._rebuild_active_combo()
        self.refresh_chromatogram()

    def _on_tree_selection(self, current, previous) -> None:
        if current is None:
            return
        key = current.data(0, ROLE_REF)
        if key in self.refs:
            index = self.active_combo.findData(key)
            if index >= 0:
                self.active_combo.setCurrentIndex(index)

    # ------------------------------------------------------- canal ativo ----- #
    def _rebuild_active_combo(self) -> None:
        previous = self.active_combo.currentData()
        self.active_combo.blockSignals(True)
        self.active_combo.clear()
        candidates = [r for r in self._checked_refs() if r.channel is not None]
        if not candidates:
            candidates = [r for r in self.refs.values() if r.channel is not None]
        for ref in candidates:
            self.active_combo.addItem(ref.full_label, ref.key)
        index = self.active_combo.findData(previous)
        self.active_combo.setCurrentIndex(index if index >= 0 else 0)
        self.active_combo.blockSignals(False)
        self._sync_active_ref()

    def _sync_active_ref(self) -> None:
        key = self.active_combo.currentData()
        self.active_ref = self.refs.get(key) if key else None
        channel = self.active_ref.channel if self.active_ref else None
        self.scan_spin.blockSignals(True)
        self.scan_spin.setMaximum(max(channel.info.n_scans if channel else 1, 1))
        self.scan_spin.blockSignals(False)
        if self.active_ref is not None:
            self.sample_info.show_sample(self.active_ref.sample, channel)

    def _on_active_changed(self, _index: int) -> None:
        self._sync_active_ref()
        if self.active_ref and self.active_ref.channel:
            self._show_scan(min(self.current_scan,
                                self.active_ref.channel.info.n_scans - 1))

    # ---------------------------------------------------------- cromatograma - #
    def refresh_chromatogram(self) -> None:
        refs = self._checked_refs()
        mode = self.mode_combo.currentText()
        traces: list[Trace] = []
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for i, ref in enumerate(refs):
                if ref.channel is None:
                    x, y = ref.sample.tic()
                    label = f"{ref.label} (TIC)"
                elif mode == "BPC":
                    x, y = ref.channel.bpc()
                    label = f"{ref.label} (BPC)"
                else:
                    x, y = ref.channel.tic()
                    label = f"{ref.label} (TIC)"
                traces.append(Trace(ref.key, label, x, y, colour(i), ref.channel))

            for j, xic in enumerate(self.xic_defs):
                traces.append(
                    Trace(xic["key"], xic["label"], xic["x"], xic["y"],
                          colour(len(refs) + j), xic["channel"])
                )
            self.chrom.set_traces(traces)
            self.chrom.autoscale()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._update_status(
            f"{len(traces)} traço(s) no cromatograma · modo {mode}"
            + (f" · canal ativo: {self.active_ref.label}" if self.active_ref else "")
        )

    def _on_chrom_click(self, rt: float) -> None:
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            self._update_status("Escolha um canal ativo para ver o espectro.")
            return
        self._show_scan(channel.scan_at_rt(rt))

    def _on_chrom_range(self, rt0: float, rt1: float) -> None:
        if self.active_ref is None or self.active_ref.channel is None:
            return
        self._show_average(rt0, rt1)
        self._report_integration(rt0, rt1)

    def _report_integration(self, rt0: float, rt1: float) -> None:
        traces = [t for t in self.chrom.traces if t.source is not None]
        if not traces:
            return
        target = next(
            (t for t in traces
             if self.active_ref and t.source is self.active_ref.channel),
            traces[0],
        )
        conditioned = self.chrom.conditioned(target.key)
        x, y = conditioned if conditioned else (target.x, target.y)
        stats = integrate(x, y, rt0, rt1)
        snr = signal_to_noise(x, y, rt0, rt1)
        self._update_status(
            f"{target.label} · {rt0:.3f}–{rt1:.3f} min · "
            f"área {stats['area']:,.0f} · altura {stats['height']:,.0f} · "
            f"ápice {stats['apex_rt']:.3f} min · S/N ≈ {snr:.0f} · "
            f"{stats['n_points']} scans"
        )

    # ------------------------------------------------------------- background - #
    def _set_background(self) -> None:
        selection = self.chrom.selected_range()
        if selection is None:
            self._update_status(
                "Selecione a faixa de branco no cromatograma (Shift + arrastar) "
                "antes de definir o background."
            )
            return
        self.chrom.set_background_range(*selection)

    def _clear_background(self) -> None:
        self.chrom.clear_background_range()

    def _on_background_changed(self) -> None:
        self._background_cache.clear()
        window = self.chrom.background_range()
        if window is None:
            self.bg_label.setText("")
            self._update_status("Subtração de background desligada.")
        else:
            self.bg_label.setText(
                f"background {window[0]:.2f}–{window[1]:.2f} min"
            )
            self._update_status(
                f"Background definido em {window[0]:.3f}–{window[1]:.3f} min; "
                "novos espectros saem com esse fundo subtraído."
            )

    def _background_spectrum(self, channel: Channel):
        window = self.chrom.background_range()
        if window is None:
            return None
        key = (id(channel), round(window[0], 5), round(window[1], 5))
        if key not in self._background_cache:
            self._background_cache[key] = channel.spectrum_rt_range(*window)
        return self._background_cache[key]

    def _apply_background(self, channel: Channel, mz: np.ndarray,
                          intensity: np.ndarray) -> tuple[np.ndarray, bool]:
        """
        Subtrai o espectro medio do branco. As grades de m/z do espectro e do
        branco nao coincidem em dados de perfil, entao o branco e interpolado
        para a grade do espectro antes da subtracao.
        """
        background = self._background_spectrum(channel)
        if background is None:
            return intensity, False
        bmz, bi = background
        if bmz.size < 2 or mz.size == 0:
            return intensity, False
        interpolated = np.interp(mz, bmz, bi, left=0.0, right=0.0)
        return np.clip(intensity - interpolated, 0.0, None), True

    # -------------------------------------------------------------- espectro - #
    def _show_scan(self, scan: int) -> None:
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        self.current_scan = int(np.clip(scan, 0, max(channel.info.n_scans - 1, 0)))
        mz, intensity = channel.spectrum(self.current_scan)
        intensity, subtracted = self._apply_background(channel, mz, intensity)
        rt = channel.rt_at_scan(self.current_scan)
        self.spectrum.set_traces(
            [Trace("spec", "espectro", mz, intensity, "#1f77b4", channel)]
        )
        self.spectrum.autoscale()
        self.spectrum.set_title(
            f"{self.active_ref.label} · scan {self.current_scan + 1}"
            f"/{channel.info.n_scans} · RT {rt:.3f} min"
            + (" · background subtraído" if subtracted else "")
        )
        self.scan_spin.blockSignals(True)
        self.scan_spin.setValue(self.current_scan + 1)
        self.scan_spin.blockSignals(False)
        self.rt_label.setText(f"RT {rt:.3f} min")
        self.chrom.mark(rt)
        self._fill_peak_table()

    def _show_average(self, rt0: float, rt1: float) -> None:
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        mz, intensity = channel.spectrum_rt_range(rt0, rt1)
        intensity, subtracted = self._apply_background(channel, mz, intensity)
        first, last = channel.scans_in_range(rt0, rt1)
        self.spectrum.set_traces(
            [Trace("spec", "espectro médio", mz, intensity, "#d62728", channel)]
        )
        self.spectrum.autoscale()
        self.spectrum.set_title(
            f"{self.active_ref.label} · média de {last - first + 1} scans "
            f"({first + 1}–{last + 1}) · RT {min(rt0, rt1):.3f}–{max(rt0, rt1):.3f} min"
            + (" · background subtraído" if subtracted else "")
        )
        self.rt_label.setText(f"RT {min(rt0, rt1):.3f}–{max(rt0, rt1):.3f} min")
        self.chrom.mark(None)
        self._fill_peak_table()

    def _average_selection(self) -> None:
        selection = self.chrom.selected_range()
        if selection is None:
            self._update_status(
                "Selecione antes uma faixa no cromatograma (Shift + arrastar)."
            )
            return
        self._show_average(*selection)
        self._report_integration(*selection)

    def _step_scan(self, delta: int) -> None:
        if self.active_ref and self.active_ref.channel:
            self._show_scan(self.current_scan + delta)

    def _on_scan_spin(self, value: int) -> None:
        self._show_scan(value - 1)

    def _fill_peak_table(self) -> None:
        peaks = self.spectrum.peaks_of_current(max_peaks=60)
        base = peaks[0][1] if peaks else 1.0
        self.peak_table.setRowCount(len(peaks))
        for row, (mz, intensity) in enumerate(peaks):
            for col, text in enumerate(
                (f"{mz:.4f}", f"{intensity:,.0f}", f"{intensity / base * 100:.1f}")
            ):
                item = QtWidgets.QTableWidgetItem(text)
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight
                                      | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.peak_table.setItem(row, col, item)

    def _peak_double_clicked(self, row: int, _column: int) -> None:
        item = self.peak_table.item(row, 0)
        if item:
            self.xic_mz.setText(item.text())
            self._extract_from_form()

    # ------------------------------------------------------------------ XIC -- #
    def _xic_targets(self) -> list[ChannelRef]:
        if self.xic_all_channels.isChecked():
            targets = [r for r in self._checked_refs() if r.channel is not None]
            if targets:
                return targets
        return [self.active_ref] if self.active_ref and self.active_ref.channel else []

    def _extract_from_form(self) -> None:
        text = self.xic_mz.text().replace(";", ",")
        values = []
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(float(part))
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "m/z inválido", f"Não entendi: {part}")
                return
        if not values:
            return
        tol = self.xic_tol.value()
        unit = self.xic_unit.currentText()
        for mz in values:
            half = mz * tol * 1e-6 if unit == "ppm" else tol
            self._add_xic(mz - half, mz + half, f"XIC {mz:.4f} ±{tol:g} {unit}")

    def _extract_from_range(self, mz0: float, mz1: float) -> None:
        lo, hi = sorted((mz0, mz1))
        self._add_xic(lo, hi, f"XIC {lo:.4f}–{hi:.4f}")

    def _add_xic(self, mz_lo: float, mz_hi: float, label: str,
                 targets: list[ChannelRef] | None = None) -> None:
        targets = targets if targets is not None else self._xic_targets()
        if not targets:
            self._update_status("Escolha um canal ativo antes de extrair o XIC.")
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for ref in targets:
                x, y = ref.channel.xic_range(mz_lo, mz_hi)
                if x.size == 0:
                    continue
                key = f"xic|{ref.key}|{mz_lo:.5f}|{mz_hi:.5f}"
                if any(d["key"] == key for d in self.xic_defs):
                    continue
                full = f"{ref.label} · {label}"
                self.xic_defs.append(
                    {"key": key, "label": full, "x": x, "y": y, "channel": ref.channel}
                )
                self.xic_list.addItem(full)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.refresh_chromatogram()

    def _remove_selected_xic(self) -> None:
        row = self.xic_list.currentRow()
        if 0 <= row < len(self.xic_defs):
            self.xic_defs.pop(row)
            self.xic_list.takeItem(row)
            self.refresh_chromatogram()

    def _clear_xics(self) -> None:
        self.xic_defs.clear()
        self.xic_list.clear()
        self.refresh_chromatogram()

    # ------------------------------------------------------------ compostos -- #
    @staticmethod
    def _covers_rt(channel: Channel, rt: float | None) -> bool:
        """O canal foi adquirido no tempo pedido? Sem RT informado, aceita qualquer um."""
        if rt is None:
            return True
        times = channel.rt
        return bool(times.size and times[0] <= rt <= times[-1])

    def _match_channel(self, sample: Sample, compound: Compound) -> Channel | None:
        """
        Escolhe o canal do metodo correspondente ao composto.

        Metodos escalonados repetem o mesmo precursor em periodos diferentes —
        neste equipamento, por exemplo, 313.24 aparece em dois experimentos, um
        cobrindo 0–13 min e outro 13–21,5 min. Por isso o tempo de retencao
        esperado entra no criterio: escolher so pelo precursor pegaria o canal
        errado, que nem sequer foi adquirido naquele instante.
        """
        target = compound.target_mz

        def candidates(require_rt: bool):
            found = []
            for channel in sample.channels:
                precursor = channel.info.precursor
                if precursor is None:
                    continue
                delta = abs(precursor - compound.precursor)
                if delta > PRECURSOR_MATCH_DA:
                    continue
                if not (channel.info.start_mass <= target <= channel.info.end_mass):
                    continue
                if require_rt and not self._covers_rt(channel, compound.rt):
                    continue
                found.append((delta, channel.index, channel))
            return sorted(found)

        matches = candidates(require_rt=True) or candidates(require_rt=False)
        if matches:
            return matches[0][2]

        ms1 = [
            c for c in sample.channels
            if c.info.is_ms1 and c.info.start_mass <= target <= c.info.end_mass
        ]
        for channel in ms1:
            if self._covers_rt(channel, compound.rt):
                return channel
        return ms1[0] if ms1 else None

    def _integrate_compound(self, ref: ChannelRef, channel: Channel,
                            compound: Compound) -> Result:
        mz_lo, mz_hi = compound.mass_window()
        mz_text = f"{(mz_lo + mz_hi) / 2:.4f}"

        def empty(note: str) -> Result:
            return Result(
                compound=compound.name, sample=ref.alias,
                channel=channel.info.short_label, mz=mz_text,
                rt=compound.rt or 0.0, area=0.0, height=0.0, width=0.0,
                snr=0.0, note=note,
            )

        x, y = channel.xic_range(mz_lo, mz_hi)
        if x.size == 0:
            return empty("sem dados")

        window = compound.rt_window()
        if window is None:
            mask = np.ones(x.size, dtype=bool)
        else:
            mask = (x >= window[0]) & (x <= window[1])
            # Sem varredura da corrida inteira quando a janela nao é coberta:
            # devolver um pico de outro tempo seria um resultado errado, nao um
            # resultado aproximado.
            if mask.sum() < 3:
                return empty(f"canal não cobre {window[0]:.2f}–{window[1]:.2f} min")

        peaks = detect_peaks(x[mask], y[mask], min_relative=0.05, min_snr=3.0)
        if not peaks:
            return empty("nenhum pico acima do ruído")

        peak = peaks[0]
        return Result(
            compound=compound.name, sample=ref.alias,
            channel=channel.info.short_label, mz=mz_text,
            rt=peak.apex_rt, area=peak.area, height=peak.height,
            width=peak.width, snr=peak.snr,
            start_rt=peak.start_rt, end_rt=peak.end_rt,
        )

    def _extract_compounds(self, compounds: list[Compound]) -> None:
        if not compounds:
            self._update_status("Nenhum composto válido na lista.")
            return
        samples = self._checked_samples()
        if not samples:
            self._update_status("Abra pelo menos um arquivo antes de extrair.")
            return

        total = len(compounds) * len(samples)
        progress = QtWidgets.QProgressDialog(
            "Extraindo e integrando…", "Cancelar", 0, total, self
        )
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)

        results: list[Result] = []
        done = 0
        for ref in samples:
            for compound in compounds:
                if progress.wasCanceled():
                    break
                channel = self._match_channel(ref.sample, compound)
                if channel is None:
                    results.append(Result(
                        compound=compound.name, sample=ref.alias, channel="—",
                        mz=f"{compound.target_mz:.4f}", rt=compound.rt or 0.0,
                        area=0.0, height=0.0, width=0.0, snr=0.0,
                        note="nenhum canal compatível",
                    ))
                else:
                    results.append(self._integrate_compound(ref, channel, compound))
                done += 1
                progress.setValue(done)
                QtWidgets.QApplication.processEvents()
            if progress.wasCanceled():
                break
        progress.setValue(total)

        self.results_panel.set_results(results)
        self.tabs.setCurrentWidget(self.results_panel)
        found = sum(1 for r in results if r.area > 0)
        self._update_status(
            f"{len(results)} extrações em {len(samples)} amostra(s); "
            f"{found} com pico detectado."
        )

    def _show_compound(self, compound: Compound) -> None:
        """Plota o XIC de um composto em todas as amostras marcadas."""
        samples = self._checked_samples()
        targets = []
        for ref in samples:
            channel = self._match_channel(ref.sample, compound)
            if channel is not None:
                targets.append(ChannelRef(ref.wiff, ref.sample, channel))
        if not targets:
            self._update_status(f"Nenhum canal compatível com {compound.name}.")
            return
        for target in targets:
            target.alias = next(
                (r.alias for r in self.refs.values()
                 if r.wiff.path == target.wiff.path), target.alias
            )
        mz_lo, mz_hi = compound.mass_window()
        self._add_xic(mz_lo, mz_hi,
                      f"{compound.name} {compound.target_mz:.4f}", targets)
        window = compound.rt_window()
        if window:
            self.chrom.plot.setXRange(*window)

    def _go_to_result(self, result: Result) -> None:
        """Leva o cromatograma ate o pico de uma linha da tabela de resultados."""
        if result.end_rt > result.start_rt:
            span = max(result.end_rt - result.start_rt, 0.05)
            self.chrom.plot.setXRange(result.start_rt - span, result.end_rt + span)
            self.chrom.mark(result.rt)
        self._update_status(
            f"{result.compound} · {result.sample} · {result.channel} · "
            f"RT {result.rt:.3f} min · área {result.area:,.0f}"
        )

    # ------------------------------------------------------- picos do cromat. #
    def _detect_peaks(self) -> None:
        traces = self.chrom.traces
        if not traces:
            self._update_status("Nada no cromatograma para integrar.")
            return
        results: list[Result] = []
        markers = []
        for trace in traces:
            conditioned = self.chrom.conditioned(trace.key)
            x, y = conditioned if conditioned else (trace.x, trace.y)
            peaks = detect_peaks(x, y, min_relative=0.05, min_snr=3.0)
            markers.extend(peaks)
            ref = self.refs.get(trace.key)
            sample_name = ref.alias if ref else "—"
            channel_name = (
                trace.source.info.short_label if trace.source is not None else "TIC"
            )
            for peak in peaks:
                results.append(
                    Result(
                        compound="(detectado)", sample=sample_name,
                        channel=channel_name, mz="—", rt=peak.apex_rt,
                        area=peak.area, height=peak.height, width=peak.width,
                        snr=peak.snr, trace_key=trace.key,
                        start_rt=peak.start_rt, end_rt=peak.end_rt,
                    )
                )
        self.chrom.set_peak_markers(markers)
        self.results_panel.set_results(results)
        self.tabs.setCurrentWidget(self.results_panel)
        self._update_status(
            f"{len(results)} pico(s) integrado(s) em {len(traces)} traço(s)."
        )

    # ------------------------------------------------------------- utilidades #
    def _set_select_mode(self, enabled: bool) -> None:
        self.chrom.set_select_mode(enabled)
        self.spectrum.set_select_mode(enabled)

    def _set_normalised(self, enabled: bool) -> None:
        self.chrom.set_normalised(enabled)
        self.spectrum.set_normalised(enabled)

    def _set_mirror(self, enabled: bool) -> None:
        self.chrom.set_mirror(enabled)
        self.spectrum.set_mirror(enabled)

    def _set_smoothing(self, sigma: float) -> None:
        self.chrom.set_smoothing(sigma)
        self.spectrum.set_smoothing(sigma)

    def _autoscale_both(self) -> None:
        self.chrom.autoscale()
        self.spectrum.autoscale()

    def _export(self, view, what: str) -> None:
        traces = view.traces
        if not traces:
            self._update_status(f"Nada para exportar em {what}.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Exportar {what}", os.path.join(self._last_dir(), f"{what}.csv"),
            "CSV (*.csv)"
        )
        if not path:
            return
        self._remember_dir(path)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for trace in traces:
                conditioned = view.conditioned(trace.key)
                x, y = conditioned if conditioned else (trace.x, trace.y)
                writer.writerow([trace.label])
                writer.writerow(["x", "y"])
                writer.writerows(zip(x.tolist(), y.tolist()))
                writer.writerow([])
        self._update_status(f"Exportado para {path}")

    def _update_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _show_help(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Como usar",
            "<b>Cromatograma</b><br>"
            "• arrastar = zoom por retângulo; duplo clique = ajustar escala<br>"
            "• clique simples = espectro daquele scan<br>"
            "• Shift + arrastar = seleciona faixa → espectro médio + integração<br>"
            "• setas ← → percorrem os scans<br><br>"
            "<b>Espectro</b><br>"
            "• Shift + arrastar seleciona faixa de m/z<br>"
            "• botão direito na faixa → extrair XIC<br>"
            "• duplo clique na aba “Picos do espectro” extrai o XIC da massa<br><br>"
            "<b>Compostos</b><br>"
            "• monte ou importe a lista na aba “Compostos”<br>"
            "• “Extrair e integrar todos” roda a lista em todas as amostras marcadas<br>"
            "• duplo clique numa linha mostra o XIC daquele composto<br><br>"
            "<b>Processamento</b><br>"
            "• suavização e linha de base valem para o que está na tela e para a "
            "integração<br>"
            "• selecione uma faixa de branco e clique “Definir background” para "
            "subtraí-la dos espectros<br>"
            "• “Espelhar” inverte os traços pares, para comparar amostra e branco",
        )

    def closeEvent(self, event):  # noqa: N802 (API Qt)
        self._save_settings()
        for wiff in self.files:
            wiff.close()
        super().closeEvent(event)
