"""
The spectrum on screen searched against a spectral library.

A library is loaded once and remembered; the search takes the spectrum the
Explorer is showing, the active channel's precursor, and lists the records
that match with both scores, the matched peaks of the chosen one, and an
overlay of its peaks on the spectrum pane.
"""

from __future__ import annotations

import os

from PyQt6 import QtCore, QtWidgets

from ..library import (PEAK_TOLERANCE_PPM, PRECURSOR_TOLERANCE_DA, LibraryHit,
                       SpectralLibrary, load_library)
from .help_window import describe

SETTING_PATH = "library/path"


class LibraryPanel(QtWidgets.QWidget):
    sigOverlay = QtCore.pyqtSignal(list, str)     # [(m/z, share)], label
    sigClearOverlay = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        describe(self, "spectral-library")
        self.library: SpectralLibrary | None = None
        self._hits: list[LibraryHit] = []
        self._spectrum = None
        #: set by the Explorer: returns (mz, intensity, precursor) on screen
        self.spectrum_source = None
        self.settings = QtCore.QSettings("OpenQuant", "OpenQuant")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        top = QtWidgets.QHBoxLayout()
        self.btn_load = QtWidgets.QPushButton("Load library…")
        self.btn_load.setToolTip("An MSP (NIST, MassBank, MoNA, GNPS) or MGF file")
        top.addWidget(self.btn_load)
        self.library_label = QtWidgets.QLabel("No library loaded.")
        self.library_label.setProperty("role", "caption")
        top.addWidget(self.library_label, 1)
        layout.addLayout(top)

        form = QtWidgets.QFormLayout()
        self.precursor_edit = QtWidgets.QLineEdit()
        self.precursor_edit.setPlaceholderText("from the active channel")
        self.precursor_edit.setToolTip(
            "Only records whose precursor sits within the tolerance are "
            "scored; records with no precursor are scored anyway and say so")
        form.addRow("Precursor", self.precursor_edit)
        self.precursor_tol = QtWidgets.QDoubleSpinBox()
        self.precursor_tol.setRange(0.001, 5.0)
        self.precursor_tol.setDecimals(3)
        self.precursor_tol.setValue(PRECURSOR_TOLERANCE_DA)
        self.precursor_tol.setSuffix(" Da")
        self.precursor_tol.setToolTip("Wider for a nominal-mass library")
        form.addRow("Precursor ±", self.precursor_tol)
        self.peak_tol = QtWidgets.QDoubleSpinBox()
        self.peak_tol.setRange(1.0, 500.0)
        self.peak_tol.setDecimals(0)
        self.peak_tol.setValue(PEAK_TOLERANCE_PPM)
        self.peak_tol.setSuffix(" ppm")
        form.addRow("Peaks ±", self.peak_tol)
        layout.addLayout(form)

        self.btn_search = QtWidgets.QPushButton("Search the spectrum on screen")
        self.btn_search.setEnabled(False)
        layout.addWidget(self.btn_search)

        self.hits = QtWidgets.QTreeWidget()
        self.hits.setHeaderLabels(["Record", "Score", "Reverse", "Matched",
                                   "Precursor", "Δ ppm", "Formula"])
        self.hits.setRootIsDecorated(False)
        self.hits.setToolTip(
            "Score: the cosine over everything both spectra hold. Reverse: "
            "only whether the library's peaks are in the measured spectrum, "
            "so a co-eluting impurity does not count against a record. A "
            "high reverse with a low score is a compound present with company")
        layout.addWidget(self.hits, 3)

        self.pairs = QtWidgets.QTreeWidget()
        self.pairs.setHeaderLabels(["Measured", "Library", "ppm", "Measured %",
                                    "Library %"])
        self.pairs.setRootIsDecorated(False)
        layout.addWidget(self.pairs, 2)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_overlay = QtWidgets.QPushButton("Overlay on spectrum")
        self.btn_overlay.setEnabled(False)
        self.btn_clear = QtWidgets.QPushButton("Clear overlay")
        buttons.addWidget(self.btn_overlay)
        buttons.addWidget(self.btn_clear)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "hint")
        layout.addWidget(self.status)

        self.btn_load.clicked.connect(self._choose_library)
        self.btn_search.clicked.connect(self.search)
        self.hits.currentItemChanged.connect(self._show_pairs)
        self.btn_overlay.clicked.connect(self._overlay)
        self.btn_clear.clicked.connect(self.sigClearOverlay)

        remembered = self.settings.value(SETTING_PATH, "", type=str)
        if remembered and os.path.exists(remembered):
            self.load(remembered)

    # -- the library ------------------------------------------------------------ #
    def _choose_library(self) -> None:
        start = os.path.dirname(self.library.path) if self.library else ""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load a spectral library", start,
            "Spectral libraries (*.msp *.mgf *.txt);;All files (*)")
        if path:
            self.load(path)

    def load(self, path: str) -> None:
        try:
            self.library = load_library(path)
        except Exception as exc:
            self.status.setText(f"Could not read {os.path.basename(path)}: {exc}")
            return
        self.settings.setValue(SETTING_PATH, path)
        self.library_label.setText(
            f"{len(self.library):,} records from {os.path.basename(path)}, "
            f"{self.library.with_precursor:,} with a precursor")
        self.btn_search.setEnabled(True)
        self.status.setText("")

    # -- the spectrum ----------------------------------------------------------- #
    def set_spectrum(self, mz, intensity, precursor: float | None = None) -> None:
        self._spectrum = (mz, intensity)
        if precursor:
            self.precursor_edit.setText(f"{precursor:.4f}")

    def _query_precursor(self) -> float | None:
        text = self.precursor_edit.text().strip().replace(",", ".")
        try:
            return float(text) if text else None
        except ValueError:
            return None

    def search(self) -> None:
        if self.library is None:
            self.status.setText("Load a library first.")
            return
        if self.spectrum_source is not None:
            current = self.spectrum_source()
            if current is not None:
                mz, intensity, precursor = current
                self.set_spectrum(mz, intensity, precursor)
        if self._spectrum is None:
            self.status.setText("Show a spectrum first.")
            return
        mz, intensity = self._spectrum
        self._hits = self.library.search(
            mz, intensity, self._query_precursor(),
            tolerance_ppm=self.peak_tol.value(),
            precursor_tolerance=self.precursor_tol.value())
        self.hits.clear()
        self.pairs.clear()
        for hit in self._hits:
            entry = hit.entry
            item = QtWidgets.QTreeWidgetItem([
                entry.name, f"{hit.score * 100:.0f}", f"{hit.reverse * 100:.0f}",
                f"{hit.matched}/{hit.of_library}",
                "—" if entry.precursor is None else f"{entry.precursor:.4f}",
                "—" if hit.delta_ppm is None else f"{hit.delta_ppm:+.1f}",
                entry.formula])
            for column in (1, 2, 3, 4, 5):
                item.setTextAlignment(column, QtCore.Qt.AlignmentFlag.AlignRight)
            item.setToolTip(0, "\n".join(f"{k}: {v}" for k, v in entry.fields.items())
                            or entry.precursor_type)
            self.hits.addTopLevelItem(item)
        for column in range(7):
            self.hits.resizeColumnToContents(column)
        if self._hits:
            self.hits.setCurrentItem(self.hits.topLevelItem(0))
            precursor = self._query_precursor()
            scoped = (f" within ±{self.precursor_tol.value():g} Da of {precursor:.4f}"
                      if precursor is not None else "")
            self.status.setText(f"{len(self._hits)} record(s) matched{scoped}; "
                                f"best {self._hits[0].score * 100:.0f}.")
        else:
            self.status.setText("No record matched. Widen the tolerances, or "
                                "the compound is not in this library.")
        self.btn_overlay.setEnabled(bool(self._hits))

    def _current_hit(self) -> LibraryHit | None:
        item = self.hits.currentItem()
        if item is None:
            return None
        index = self.hits.indexOfTopLevelItem(item)
        return self._hits[index] if 0 <= index < len(self._hits) else None

    def _show_pairs(self, *_args) -> None:
        self.pairs.clear()
        hit = self._current_hit()
        if hit is None:
            return
        for pair in sorted(hit.pairs, key=lambda p: -p.library_share):
            item = QtWidgets.QTreeWidgetItem([
                f"{pair.measured:.4f}", f"{pair.library:.4f}", f"{pair.ppm:+.1f}",
                f"{pair.measured_share * 100:.1f}", f"{pair.library_share * 100:.1f}"])
            for column in range(5):
                item.setTextAlignment(column, QtCore.Qt.AlignmentFlag.AlignRight)
            self.pairs.addTopLevelItem(item)
        for column in range(5):
            self.pairs.resizeColumnToContents(column)

    def _overlay(self) -> None:
        hit = self._current_hit()
        if hit is None:
            return
        pattern = [(float(m), float(i)) for m, i in zip(hit.entry.mz, hit.entry.intensity)]
        self.sigOverlay.emit(pattern, hit.entry.name)
