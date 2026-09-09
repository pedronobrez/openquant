"""
The spectrum on screen searched against a spectral library, and written
into one.

A library is loaded once and remembered; the search takes the spectrum the
Explorer is showing, the active channel's precursor, and lists the records
that match with both scores, the matched peaks of the chosen one, and an
overlay of its peaks on the spectrum pane.

The other direction is a library of one's own. A deuterated standard
infused deliberately is in no public library, so the spectrum on screen is
the only record of it there will ever be: *Add spectrum to library…* writes
it into an MSP file of the analyst's choosing, appending, and reloads that
file when it is the one loaded so the record is searchable at once.
"""

from __future__ import annotations

import datetime
import os

from PyQt6 import QtCore, QtWidgets

from ..library import (MIN_MATCHED, OWN_MIN_RELATIVE, PEAK_TOLERANCE_PPM,
                       PRECURSOR_TOLERANCE_DA, LibraryEntry, LibraryHit,
                       SpectralLibrary, count_records, entry_from_spectrum,
                       load_library, write_msp)
from ..lipidmaps import mass_precision
from .help_window import describe
from .library_add_dialog import AddToLibraryDialog, default_adduct
from .settings import settings

SETTING_PATH = "library/path"
#: the MSP the analyst's own records are appended to, chosen once
SETTING_OWN_PATH = "library/own_path"


class LibraryPanel(QtWidgets.QWidget):
    sigOverlay = QtCore.pyqtSignal(list, str)     # [(m/z, share)], label
    sigClearOverlay = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        describe(self, "spectral-library")
        self.library: SpectralLibrary | None = None
        self._hits: list[LibraryHit] = []
        self._spectrum = None
        #: set by the Explorer: returns (mz, intensity, precursor) on screen,
        #: optionally with a fourth element — a mapping describing where the
        #: spectrum came from, which is what a record of one's own has to say
        self.spectrum_source = None
        self._context: dict = {}
        self.settings = settings()

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

        own = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add spectrum to library…")
        self.btn_add.setToolTip(
            "Write the spectrum on screen into a library of your own — an "
            "MSP file chosen once and appended to. An infused standard is in "
            "no public library, and this is the only record of it there is")
        own.addWidget(self.btn_add)
        self.own_label = QtWidgets.QLabel("")
        self.own_label.setProperty("role", "caption")
        own.addWidget(self.own_label, 1)
        layout.addLayout(own)

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
        self.min_matched = QtWidgets.QSpinBox()
        self.min_matched.setRange(1, 50)
        self.min_matched.setValue(MIN_MATCHED)
        self.min_matched.setToolTip(
            "A record has to land this many of its peaks to be listed. One "
            "peak in common is a coincidence: a phosphocholine ion at 184.07 "
            "scored 83 against a laxative whose fragment sits 13 ppm away")
        form.addRow("Matched peaks ≥", self.min_matched)
        self.unknown_precursor = QtWidgets.QCheckBox("Also records with no precursor")
        self.unknown_precursor.setToolTip(
            "A filtered search leaves out records that carry no precursor "
            "mass — 24,000 of MassBank's 139,000 — since a filter that admits "
            "them is not one. Tick to score them anyway; their Δ ppm is blank")
        form.addRow("", self.unknown_precursor)
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
        self.btn_add.clicked.connect(self.add_spectrum)
        self.btn_search.clicked.connect(self.search)
        self.hits.currentItemChanged.connect(self._show_pairs)
        self.btn_overlay.clicked.connect(self._overlay)
        self.btn_clear.clicked.connect(self.sigClearOverlay)

        remembered = self.settings.value(SETTING_PATH, "", type=str)
        if remembered and os.path.exists(remembered):
            self.load(remembered)
        self._refresh_own_label()

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
    def set_spectrum(self, mz, intensity, precursor: float | None = None,
                     context: dict | None = None) -> None:
        self._spectrum = (mz, intensity)
        if context is not None:
            self._context = dict(context)
        if precursor:
            # the channel's precursor is what the instrument was told, to
            # the decimals it was typed with: 647.5 is known to ±0.05, and
            # a filter of ±0.02 around it is asking for digits it lacks
            self.precursor_edit.setText(f"{precursor:g}")
            self.precursor_tol.setValue(max(self.precursor_tol.value(),
                                            mass_precision(precursor)))

    def _pull_spectrum(self) -> None:
        """
        Ask the Explorer for what is on screen now.

        The hook returns the spectrum, the active channel's precursor and —
        where the caller can supply one — a mapping saying which sample,
        channel and scans it came from. Older callers return three values
        and are read as carrying no such mapping, which is why the fourth
        element is taken by length rather than unpacked.
        """
        if self.spectrum_source is None:
            return
        current = self.spectrum_source()
        if current is None:
            return
        mz, intensity, precursor = current[0], current[1], current[2]
        context = current[3] if len(current) > 3 else None
        self.set_spectrum(mz, intensity, precursor, context)

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
        self._pull_spectrum()
        if self._spectrum is None:
            self.status.setText("Show a spectrum first.")
            return
        mz, intensity = self._spectrum
        self._hits = self.library.search(
            mz, intensity, self._query_precursor(),
            tolerance_ppm=self.peak_tol.value(),
            precursor_tolerance=self.precursor_tol.value(),
            min_matched=self.min_matched.value(),
            include_unknown_precursor=self.unknown_precursor.isChecked())
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

    # -- a library of one's own ------------------------------------------------- #
    @property
    def own_path(self) -> str:
        return self.settings.value(SETTING_OWN_PATH, "", type=str)

    def set_own_path(self, path: str) -> None:
        self.settings.setValue(SETTING_OWN_PATH, path)
        self._refresh_own_label()

    def _refresh_own_label(self) -> None:
        path = self.own_path
        if not path:
            self.own_label.setText("No library of your own yet.")
            return
        name = os.path.basename(path)
        if not os.path.exists(path):
            self.own_label.setText(f"Your library: {name}, not written yet")
            return
        records = count_records(path)
        self.own_label.setText(f"Your library: {records:,} record(s) in {name}")

    def _choose_own_path(self) -> str:
        """
        Where the analyst's own records go, asked for once and remembered.

        A save dialog, since the file usually does not exist yet, but with
        the overwrite warning off: picking the library that is already there
        is the ordinary case and the record is appended, not written over.
        """
        start = self.own_path or os.path.expanduser("~/my-library.msp")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Your own spectral library", start, "MSP (*.msp);;All files (*)",
            options=QtWidgets.QFileDialog.Option.DontConfirmOverwrite)
        if path:
            if not os.path.splitext(path)[1]:
                path += ".msp"
            self.set_own_path(path)
        return path

    def own_prefill(self) -> dict:
        """
        What the acquisition already knows about the spectrum on screen.

        Everything here comes from the file or from what is typed in the
        panel; only the name, the formula and the adduct are the analyst's
        to give. The comment is the pane's own title — sample, channel and
        the scans the average was taken over — with the file and the date,
        because a record whose provenance is not written down cannot be
        checked against the acquisition later.
        """
        context = self._context
        parts = [str(p) for p in (context.get("title"), context.get("file")) if p]
        parts.append(f"added {datetime.date.today().isoformat()}")
        return {
            "name": str(context.get("name", "")),
            "precursor": self._query_precursor(),
            "precursor_type": default_adduct(context.get("polarity", "")),
            "formula": str(context.get("formula", "")),
            "collision_energy": context.get("collision_energy"),
            "comment": " · ".join(parts),
        }

    def add_spectrum(self) -> None:
        """The button: the spectrum on screen, named, into the analyst's file."""
        self._pull_spectrum()
        if self._spectrum is None:
            self.status.setText("Show a spectrum first.")
            return
        path = self.own_path or self._choose_own_path()
        if not path:
            return
        mz, intensity = self._spectrum
        try:
            preview = entry_from_spectrum("preview", mz, intensity)
        except ValueError as exc:
            self.status.setText(f"Nothing to write: {exc}.")
            return
        dialog = AddToLibraryDialog(self.own_prefill(), preview.peaks,
                                    os.path.basename(path), self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.add_to_own_library(**dialog.values())
        dialog.deleteLater()

    def add_to_own_library(self, name: str, precursor: float | None = None,
                           precursor_type: str = "", formula: str = "",
                           collision_energy: float | None = None,
                           comment: str = "", path: str = "") -> LibraryEntry | None:
        """
        Append the spectrum on screen to the analyst's own MSP, and say so.

        Separate from the dialog on purpose: the dialog collects values and
        this writes them, so the flow can be exercised without a modal loop.
        Where the library that is loaded *is* the file written to, it is read
        again, so the record can be searched for the moment it exists — which
        is the check that it was written in a form the parser reads.
        """
        path = path or self.own_path
        if not path:
            self.status.setText("Choose a file for your own library first.")
            return None
        if self._spectrum is None:
            self.status.setText("Show a spectrum first.")
            return None
        mz, intensity = self._spectrum
        try:
            entry = entry_from_spectrum(
                name, mz, intensity, precursor=precursor,
                precursor_type=precursor_type, formula=formula,
                collision_energy=collision_energy, comment=comment)
            write_msp([entry], path, append=True)
        except (ValueError, OSError) as exc:
            self.status.setText(f"Could not write the record: {exc}")
            return None
        if self.library is not None and self.library.path and \
                os.path.abspath(self.library.path) == os.path.abspath(path):
            self.load(path)                  # searchable at once
        self._refresh_own_label()
        self.status.setText(
            f"{entry.name} written to {os.path.basename(path)}: {entry.peaks} "
            f"peak(s) at or above {OWN_MIN_RELATIVE:.0%} of the base peak.")
        return entry
