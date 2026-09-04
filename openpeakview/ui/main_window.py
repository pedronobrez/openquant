"""Janela principal do OpenPeakView."""

from __future__ import annotations

import csv
import os

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from ..processing import integrate, signal_to_noise
from ..wiff import Channel, Sample, WiffFile
from .plots import ChromatogramView, SpectrumView, Trace, colour

ROLE_REF = QtCore.Qt.ItemDataRole.UserRole


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
        self.resize(1500, 950)

        self.files: list[WiffFile] = []
        self.refs: dict[str, ChannelRef] = {}
        self.xic_defs: list[dict] = []
        self.active_ref: ChannelRef | None = None
        self.current_scan: int = 0

        self.chrom = ChromatogramView()
        self.spectrum = SpectrumView()

        self._build_ui()
        self._connect()
        self._update_status("Abra um arquivo .wiff para comecar.")

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
        self._build_toolbar()
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
        box.setLayout(layout)
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
        self.btn_next.setToolTip("Proximo scan (seta direita)")
        self.scan_spin = QtWidgets.QSpinBox()
        self.scan_spin.setMinimum(1)
        self.scan_spin.setMaximum(1)
        self.scan_spin.setToolTip("Numero do scan (1 = primeiro ciclo do canal)")
        self.rt_label = QtWidgets.QLabel("—")
        self.rt_label.setMinimumWidth(150)

        bar.addWidget(QtWidgets.QLabel("Scan:"))
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.scan_spin)
        bar.addWidget(self.btn_next)
        bar.addWidget(self.rt_label)
        bar.addStretch(1)
        self.btn_avg = QtWidgets.QPushButton("Media da faixa selecionada")
        self.btn_avg.setToolTip(
            "Espectro medio dos scans dentro da faixa marcada no cromatograma"
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

    def _build_side_dock(self) -> None:
        dock = QtWidgets.QDockWidget("XIC e picos", self)
        dock.setObjectName("dock_side")
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._build_xic_tab(), "XIC")
        tabs.addTab(self._build_peaks_tab(), "Picos do espectro")
        dock.setWidget(tabs)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setMinimumWidth(300)

    def _build_xic_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        form = QtWidgets.QFormLayout()
        self.xic_mz = QtWidgets.QLineEdit()
        self.xic_mz.setPlaceholderText("183.1385, 313.2384")
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

    def _build_toolbar(self) -> None:
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
        self.act_labels = QtGui.QAction("Rótulos m/z", self, checkable=True)
        self.act_labels.setChecked(True)
        bar.addAction(self.act_labels)
        self.act_apex = QtGui.QAction("Rótulos de RT", self, checkable=True)
        self.act_apex.setChecked(True)
        bar.addAction(self.act_apex)
        self.act_legend = QtGui.QAction("Legenda", self, checkable=True)
        self.act_legend.setChecked(True)
        bar.addAction(self.act_legend)

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
        view_menu.addAction(self.act_autoscale)
        view_menu.addAction(self.act_norm)
        view_menu.addAction(self.act_labels)
        view_menu.addAction(self.act_apex)
        view_menu.addAction(self.act_legend)

        help_menu = self.menuBar().addMenu("A&juda")
        help_menu.addAction("Como usar…").triggered.connect(self._show_help)

    # -------------------------------------------------------------- sinais -- #
    def _connect(self) -> None:
        self.act_open.triggered.connect(self.open_files)
        self.act_close.triggered.connect(self.close_all)
        self.act_autoscale.triggered.connect(self._autoscale_both)
        self.act_select.toggled.connect(self._set_select_mode)
        self.act_norm.toggled.connect(self._set_normalised)
        self.act_labels.toggled.connect(self.spectrum.set_labels_enabled)
        self.act_apex.toggled.connect(self.chrom.set_apex_labels)
        self.act_legend.toggled.connect(self.chrom.set_legend_visible)
        self.act_exp_chrom.triggered.connect(lambda: self._export(self.chrom, "cromatogramas"))
        self.act_exp_spec.triggered.connect(lambda: self._export(self.spectrum, "espectro"))

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
        self.spectrum.sigExtractRequested.connect(self._extract_from_range)

        self.btn_prev.clicked.connect(lambda: self._step_scan(-1))
        self.btn_next.clicked.connect(lambda: self._step_scan(+1))
        self.scan_spin.valueChanged.connect(self._on_scan_spin)
        self.btn_avg.clicked.connect(self._average_selection)

        self.btn_xic.clicked.connect(self._extract_from_form)
        self.btn_xic_clear.clicked.connect(self._clear_xics)
        self.peak_table.cellDoubleClicked.connect(self._peak_double_clicked)

        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Left), self,
                        activated=lambda: self._step_scan(-1))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Right), self,
                        activated=lambda: self._step_scan(+1))
        QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.xic_list,
                        activated=self._remove_selected_xic)

    # -------------------------------------------------------------- arquivos - #
    def open_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Abrir arquivos SCIEX", "", "Arquivos wiff (*.wiff);;Todos (*)"
        )
        for path in paths:
            self.load_file(path)

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
            tic_ref = ChannelRef(wiff, sample, None)
            self._add_leaf(sample_item, "TIC da amostra (todos os canais)", tic_ref,
                           checked=True)
            for channel in sample.channels:
                ref = ChannelRef(wiff, sample, channel)
                self._add_leaf(sample_item, channel.info.label, ref, checked=False)
            sample_item.setExpanded(True)
        file_item.setExpanded(True)
        self.tree.blockSignals(False)
        self._recompute_aliases()
        self._rebuild_active_combo()
        self.refresh_chromatogram()

    def _recompute_aliases(self) -> None:
        """
        Encurta os nomes usados na legenda removendo o prefixo comum a todos os
        arquivos abertos: `..._DiHOME001` e `..._S001` viram `DiHOME001` e `S001`.
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
        self.tree.clear()
        self.xic_list.clear()
        self.active_combo.clear()
        self.chrom.clear_traces()
        self.spectrum.clear_traces()
        self.peak_table.setRowCount(0)
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

    def _bulk_check(self, predicate) -> None:
        self.tree.blockSignals(True)
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            key = item.data(0, ROLE_REF)
            if key in self.refs:
                state = (QtCore.Qt.CheckState.Checked if predicate(self.refs[key])
                         else QtCore.Qt.CheckState.Unchecked)
                item.setCheckState(0, state)
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
                    label = f"{ref.label} ({mode if mode == 'TIC' else 'TIC'})"
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
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
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
        stats = integrate(target.x, target.y, rt0, rt1)
        snr = signal_to_noise(target.x, target.y, rt0, rt1)
        self._update_status(
            f"{target.label} · {rt0:.3f}–{rt1:.3f} min · "
            f"área {stats['area']:,.0f} · altura {stats['height']:,.0f} · "
            f"ápice {stats['apex_rt']:.3f} min · S/N ≈ {snr:.0f} · "
            f"{stats['n_points']} scans"
        )

    # -------------------------------------------------------------- espectro - #
    def _show_scan(self, scan: int) -> None:
        channel = self.active_ref.channel if self.active_ref else None
        if channel is None:
            return
        self.current_scan = int(np.clip(scan, 0, max(channel.info.n_scans - 1, 0)))
        mz, intensity = channel.spectrum(self.current_scan)
        rt = channel.rt_at_scan(self.current_scan)
        self.spectrum.set_traces(
            [Trace("spec", "espectro", mz, intensity, "#1f77b4", channel)]
        )
        self.spectrum.autoscale()
        self.spectrum.set_title(
            f"{self.active_ref.label} · scan {self.current_scan + 1}"
            f"/{channel.info.n_scans} · RT {rt:.3f} min"
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
        first, last = channel.scans_in_range(rt0, rt1)
        self.spectrum.set_traces(
            [Trace("spec", "espectro médio", mz, intensity, "#d62728", channel)]
        )
        self.spectrum.autoscale()
        self.spectrum.set_title(
            f"{self.active_ref.label} · média de {last - first + 1} scans "
            f"({first + 1}–{last + 1}) · RT {min(rt0, rt1):.3f}–{max(rt0, rt1):.3f} min"
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

    def _add_xic(self, mz_lo: float, mz_hi: float, label: str) -> None:
        targets = self._xic_targets()
        if not targets:
            self._update_status("Escolha um canal ativo antes de extrair o XIC.")
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for ref in targets:
                x, y = ref.channel.xic_range(mz_lo, mz_hi)
                if x.size == 0:
                    continue
                full = f"{ref.label} · {label}"
                key = f"xic|{ref.key}|{mz_lo:.5f}|{mz_hi:.5f}"
                if any(d["key"] == key for d in self.xic_defs):
                    continue
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

    # ------------------------------------------------------------- utilidades #
    def _set_select_mode(self, enabled: bool) -> None:
        self.chrom.set_select_mode(enabled)
        self.spectrum.set_select_mode(enabled)

    def _set_normalised(self, enabled: bool) -> None:
        self.chrom.set_normalised(enabled)
        self.spectrum.set_normalised(enabled)

    def _autoscale_both(self) -> None:
        self.chrom.autoscale()
        self.spectrum.autoscale()

    def _export(self, view, what: str) -> None:
        traces = view.traces
        if not traces:
            self._update_status(f"Nada para exportar em {what}.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Exportar {what}", f"{what}.csv", "CSV (*.csv)"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for trace in traces:
                writer.writerow([trace.label])
                writer.writerow(["x", "y"])
                writer.writerows(zip(trace.x.tolist(), trace.y.tolist()))
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
            "<b>Canais</b><br>"
            "• marque na árvore à esquerda para sobrepor no cromatograma<br>"
            "• o combo “Canal ativo” define de onde vêm espectros e XICs",
        )

    def closeEvent(self, event):  # noqa: N802 (API Qt)
        for wiff in self.files:
            wiff.close()
        super().closeEvent(event)
