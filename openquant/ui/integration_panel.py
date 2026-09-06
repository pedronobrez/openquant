"""Integration parameters for the component under review."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..components import IntegrationParams
from ..processing import SNR_MODES
from .collapsible import CollapsibleGroup


class IntegrationPanel(CollapsibleGroup):
    """
    Edits the settings of the selected component and pushes them where the
    operator wants: this component, its whole group, or back to the defaults.
    """

    sigApplyComponent = QtCore.pyqtSignal(object)   # IntegrationParams
    sigApplyGroup = QtCore.pyqtSignal(object)
    sigResetComponent = QtCore.pyqtSignal()
    sigChanged = QtCore.pyqtSignal(object)          # live preview

    def __init__(self, parent=None):
        super().__init__("Integration", parent)
        self._loading = False

        form = QtWidgets.QFormLayout(self.body)
        form.setContentsMargins(8, 6, 8, 6)
        form.setVerticalSpacing(4)

        self.smooth = QtWidgets.QDoubleSpinBox()
        self.smooth.setRange(0.0, 25.0)
        self.smooth.setSingleStep(0.5)
        self.smooth.setDecimals(1)
        self.smooth.setToolTip("Gaussian smoothing, in scans; 0 turns it off")
        form.addRow("Smooth σ", self.smooth)

        self.baseline = QtWidgets.QDoubleSpinBox()
        self.baseline.setRange(0.0, 60.0)
        self.baseline.setSingleStep(0.5)
        self.baseline.setDecimals(1)
        self.baseline.setToolTip(
            "Window used to estimate the baseline, in minutes; 0 turns it off")
        form.addRow("Baseline (min)", self.baseline)

        self.min_height = QtWidgets.QDoubleSpinBox()
        self.min_height.setRange(0.0, 1.0)
        self.min_height.setSingleStep(0.01)
        self.min_height.setDecimals(3)
        self.min_height.setToolTip(
            "Smallest peak kept, as a fraction of the tallest in the window")
        form.addRow("Min. height", self.min_height)

        self.min_snr = QtWidgets.QDoubleSpinBox()
        self.min_snr.setRange(0.0, 1000.0)
        self.min_snr.setDecimals(1)
        form.addRow("Min. S/N", self.min_snr)

        self.snr_mode = QtWidgets.QComboBox()
        self.snr_mode.addItems(list(SNR_MODES))
        self.snr_mode.setToolTip(
            "How the noise behind S/N is measured inside the noise region")
        form.addRow("Noise as", self.snr_mode)

        noise_row = QtWidgets.QHBoxLayout()
        self.noise_label = QtWidgets.QLabel("—")
        self.noise_label.setProperty("role", "caption")
        self.btn_clear_noise = QtWidgets.QToolButton()
        self.btn_clear_noise.setText("✕")
        self.btn_clear_noise.setToolTip("Forget the noise region")
        noise_row.addWidget(self.noise_label, 1)
        noise_row.addWidget(self.btn_clear_noise)
        form.addRow("Noise region", noise_row)

        buttons = QtWidgets.QVBoxLayout()
        self.btn_component = QtWidgets.QPushButton("Update method for component")
        self.btn_group = QtWidgets.QPushButton("Update method for group")
        self.btn_reset = QtWidgets.QPushButton("Back to method defaults")
        for widget in (self.btn_component, self.btn_group, self.btn_reset):
            buttons.addWidget(widget)
        form.addRow(buttons)

        copy_row = QtWidgets.QHBoxLayout()
        self.btn_copy = QtWidgets.QPushButton("Copy")
        self.btn_paste = QtWidgets.QPushButton("Paste")
        self.btn_paste.setEnabled(False)
        copy_row.addWidget(self.btn_copy)
        copy_row.addWidget(self.btn_paste)
        form.addRow(copy_row)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "hint")
        form.addRow(self.status)

        self._clipboard: IntegrationParams | None = None
        for widget in (self.smooth, self.baseline, self.min_height, self.min_snr):
            widget.valueChanged.connect(self._emit_changed)
        self.snr_mode.currentTextChanged.connect(self._emit_changed)
        self.btn_component.clicked.connect(
            lambda: self.sigApplyComponent.emit(self.params()))
        self.btn_group.clicked.connect(
            lambda: self.sigApplyGroup.emit(self.params()))
        self.btn_reset.clicked.connect(self.sigResetComponent)
        self.btn_copy.clicked.connect(self._copy)
        self.btn_paste.clicked.connect(self._paste)
        self.btn_clear_noise.clicked.connect(self._clear_noise)

    # -- values ------------------------------------------------------------------ #
    def set_params(self, params: IntegrationParams, overridden: bool) -> None:
        self._loading = True
        self.smooth.setValue(params.smoothing)
        self.baseline.setValue(params.baseline_window)
        self.min_height.setValue(params.min_relative_height)
        self.min_snr.setValue(params.min_snr)
        self.snr_mode.setCurrentText(params.snr_mode)
        region = params.noise_region
        self.noise_label.setText(
            f"{region[0]:.2f}–{region[1]:.2f} min" if region else "automatic")
        self.btn_clear_noise.setEnabled(region is not None)
        self._loading = False
        self.setTitle("Integration — component override" if overridden
                      else "Integration — method defaults")

    def params(self) -> IntegrationParams:
        region = self._region
        return IntegrationParams(
            smoothing=self.smooth.value(),
            baseline_window=self.baseline.value(),
            min_relative_height=self.min_height.value(),
            min_snr=self.min_snr.value(),
            noise_start=region[0] if region else None,
            noise_end=region[1] if region else None,
            snr_mode=self.snr_mode.currentText(),
        )

    @property
    def _region(self) -> tuple[float, float] | None:
        text = self.noise_label.text()
        if "–" not in text:
            return None
        try:
            lo, hi = text.replace(" min", "").split("–")
            return float(lo), float(hi)
        except ValueError:
            return None

    def set_noise_region(self, region: tuple[float, float] | None) -> None:
        self.noise_label.setText(
            f"{region[0]:.2f}–{region[1]:.2f} min" if region else "automatic")
        self.btn_clear_noise.setEnabled(region is not None)
        self._emit_changed()

    def _clear_noise(self) -> None:
        self.set_noise_region(None)

    def _emit_changed(self, *_args) -> None:
        if not self._loading:
            self.sigChanged.emit(self.params())

    # -- clipboard ----------------------------------------------------------------- #
    def _copy(self) -> None:
        self._clipboard = self.params()
        self.btn_paste.setEnabled(True)
        self.status.setText("Parameters copied.")

    def _paste(self) -> None:
        if self._clipboard is None:
            return
        self.set_params(self._clipboard, overridden=True)
        self.status.setText("Parameters pasted — apply them to keep the change.")
        self._emit_changed()

    def report(self, text: str) -> None:
        self.status.setText(text)
