"""
The session shared by every workspace: open files, the batch, and the method.

Both the Explorer and the Analytics workspaces read from here, so that the
component table, the sample list and the loaded files exist once instead of
once per workspace.
"""

from __future__ import annotations

import json
import os

from PyQt6 import QtCore

from .audit import PROJECT_SAVED, RECALIBRATION, AuditTrail
from .components import Component
from .matching import components_from_sample, match_channel
from .calibration import Calibration
from .method import ProcessingMethod
from .quantify import ResultsSet, XicCache
from .samples import SampleEntry, shorten_names
from .raw import open_raw

PROJECT_SUFFIX = ".oqproj"
#: the suffix used before the software was renamed; still opened, never written
LEGACY_PROJECT_SUFFIX = ".opvproj"
PROJECT_SUFFIXES = (PROJECT_SUFFIX, LEGACY_PROJECT_SUFFIX)


class Session(QtCore.QObject):
    """Owns the data; the workspaces are views onto it."""

    sigSamplesChanged = QtCore.pyqtSignal()
    sigMethodChanged = QtCore.pyqtSignal()
    sigResultsChanged = QtCore.pyqtSignal()
    #: the project path or the unsaved state changed
    sigProjectChanged = QtCore.pyqtSignal()
    #: something was written into the audit trail
    sigAuditChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files: list = []
        self.entries: list[SampleEntry] = []
        self.method = ProcessingMethod()
        self.results = ResultsSet()
        self.calibrations: dict[str, Calibration] = {}
        self.cache = XicCache()
        #: the last run of compare_algorithms, for the dialog and the report.
        #: Derived from the batch and not saved with it: it is three
        #: integrations of the whole batch and is rebuilt on request.
        self.comparison = None
        #: the last mass-drift measurement, likewise derived and not saved
        self.mass_drift = None
        #: the mass recalibration fitted from the internal standards, keyed by
        #: sample key. Derived from the drift measurement and not saved: a few
        #: seconds to repeat, and a correction stored without the measurement
        #: behind it could not be reviewed.
        self.mass_corrections: dict = {}
        #: whether that correction is applied. Saved with the project, because
        #: it changes the numbers and a project has to reopen as it was left.
        self.recalibrate = False
        #: the last comparison against a reference batch, likewise
        self.batch_comparison = None
        #: the spectra the Explorer is holding together — a
        #: spectra_compare.SpectrumComparison, kept in step with its spectrum
        #: pane and dropped when the pins are cleared. Derived and not saved:
        #: it is a copy of two traces that came off the files, and the report
        #: prints it only while it stands.
        self.spectra_comparison = None
        #: what was changed by hand in this project, in the order it was
        #: changed. Saved with the project and appended to only — see audit.py
        self.audit = AuditTrail()
        self.project_path: str | None = None
        #: something changed since the last save. Tracked here rather than in
        #: the window, because every workspace can change the session and none
        #: of them should have to remember to say so.
        self.dirty = False
        for signal in (self.sigSamplesChanged, self.sigMethodChanged,
                       self.sigResultsChanged):
            signal.connect(self._mark_dirty)

    # -- the audit trail --------------------------------------------------------- #
    def record(self, what: str, target="", before="", after="", note="",
               when: str | None = None):
        """
        Note one change made by hand.

        Called from wherever the change is actually made, once per user
        action. A change worth recording is a change worth saving, so this
        marks the project unsaved as well — which is also how an edit that
        touches nothing else, retyping a sample's comment, comes to be
        remembered at all.
        """
        entry = self.audit.record(what, target, before, after, note, when)
        self.sigAuditChanged.emit()
        self._mark_dirty()
        return entry

    # -- unsaved state ------------------------------------------------------------ #
    def _mark_dirty(self) -> None:
        if not self.dirty:
            self.dirty = True
            self.sigProjectChanged.emit()

    def _mark_clean(self) -> None:
        self.dirty = False
        self.sigProjectChanged.emit()

    @property
    def has_content(self) -> bool:
        """Is there anything here that would be lost?"""
        return bool(self.entries or self.method.components or len(self.results))

    # -- files ------------------------------------------------------------------ #
    def open_file(self, path: str):
        """Open a raw file of any supported format and add its samples."""
        wiff = open_raw(path)
        self.files.append(wiff)
        for index in range(len(wiff.sample_names)):
            sample = wiff.sample(index)
            self.entries.append(
                SampleEntry(path=wiff.path, sample_index=index,
                            name=sample.name, sample=sample,
                            problem=sample.problem or "")
            )
        shorten_names(self.entries)
        self.sigSamplesChanged.emit()
        return wiff

    def close_all(self) -> None:
        for wiff in self.files:
            wiff.close()
        self.files.clear()
        self.comparison = None
        self.mass_drift = None
        self.mass_corrections = {}
        self.batch_comparison = None
        self.spectra_comparison = None
        self.entries.clear()
        self.results.clear()
        self.calibrations.clear()
        self.cache.clear()
        # a new trail rather than an emptied one: nothing removes an entry
        self.audit = AuditTrail()
        self.project_path = None
        self.sigSamplesChanged.emit()
        self.sigResultsChanged.emit()
        self._mark_clean()

    @property
    def loaded_entries(self) -> list[SampleEntry]:
        return [e for e in self.entries if e.is_loaded]

    # -- mass recalibration ------------------------------------------------------ #
    def correction_for(self, sample_key: str):
        """
        The mass correction to apply in one injection, or None.

        None whenever the switch is off, nothing has been fitted, or that
        injection had no lock mass — three different reasons for the same
        answer, which is that the masses stand as the instrument read them.
        """
        if not self.recalibrate:
            return None
        correction = self.mass_corrections.get(sample_key)
        if correction is None or not correction.usable:
            return None
        return correction

    def corrections_in_force(self) -> dict:
        """Every correction that would be applied right now, keyed by sample."""
        if not self.recalibrate:
            return {}
        return {key: correction
                for key, correction in self.mass_corrections.items()
                if correction.usable}

    def set_recalibrate(self, on: bool) -> None:
        """Turn the correction on or off; conditioned traces are cached."""
        on = bool(on)
        if on == self.recalibrate:
            return
        self.recalibrate = on
        self.cache.clear()
        self.record(RECALIBRATION, "the batch",
                    before="off" if on else "on",
                    after="on" if on else "off",
                    note=f"{len(self.corrections_in_force())} injection(s) "
                         f"corrected" if on else "masses as the instrument "
                                                 "read them")
        self._mark_dirty()

    def entry_by_key(self, key: str) -> SampleEntry | None:
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None

    # -- method ------------------------------------------------------------------ #
    def set_components(self, components: list[Component]) -> None:
        self.method.replace_all(components)
        self.sigMethodChanged.emit()

    def notify_method_changed(self) -> None:
        # Conditioning is baked into the cached traces, so a method change
        # invalidates them.
        self.cache.clear()
        self.sigMethodChanged.emit()

    # -- results ------------------------------------------------------------------ #
    def set_results(self, results: ResultsSet) -> None:
        self.results = results
        self.sigResultsChanged.emit()

    def set_calibrations(self, curves: dict[str, Calibration]) -> None:
        self.calibrations = curves
        self.sigResultsChanged.emit()

    def notify_results_changed(self) -> None:
        self.sigResultsChanged.emit()

    def generate_components(self) -> list[Component]:
        """
        Derive a component table from the acquisition method of the first
        loaded sample, so an 80-transition method does not have to be typed in.
        """
        for entry in self.entries:
            if entry.is_loaded:
                return components_from_sample(entry.sample)
        return []

    def channel_for(self, entry: SampleEntry, component: Component):
        """The acquisition channel that carries a component in one sample."""
        if not entry.is_loaded:
            return None
        return match_channel(entry.sample, component)

    # -- project ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "version": 4,
            "method": self.method.to_dict(),
            "samples": [e.to_dict() for e in self.entries],
            "results": self.results.to_list(),
            "calibrations": {name: curve.to_dict()
                             for name, curve in self.calibrations.items()},
            "recalibrate": self.recalibrate,
            "audit": self.audit.to_dict(),
        }

    def save_project(self, path: str) -> None:
        if not path.endswith(PROJECT_SUFFIXES):
            path += PROJECT_SUFFIX
        # recorded before the file is written, so that the saved project
        # holds the record of its own saving rather than of the one before
        self.audit.record(PROJECT_SAVED, os.path.basename(path),
                          after=path,
                          note=f"{len(self.results)} row(s), "
                               f"{len(self.entries)} sample(s)")
        self.sigAuditChanged.emit()
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)
        self.project_path = path
        self._mark_clean()

    def load_project(self, path: str) -> list[str]:
        """
        Restore a project. Returns the paths of raw files that could not be
        reopened, so the caller can tell the user which ones are missing rather
        than silently dropping their batch information.
        """
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)

        self.close_all()
        self.method = ProcessingMethod.from_dict(data.get("method", {}))

        entries = [SampleEntry.from_dict(row) for row in data.get("samples", [])]
        missing: list[str] = []
        opened: dict[str, object] = {}
        for entry in entries:
            if not os.path.exists(entry.path):
                missing.append(entry.path)
                continue
            wiff = opened.get(entry.path)
            if wiff is None:
                try:
                    wiff = open_raw(entry.path)
                except Exception:
                    missing.append(entry.path)
                    continue
                opened[entry.path] = wiff
                self.files.append(wiff)
            if entry.sample_index < len(wiff.sample_names):
                entry.sample = wiff.sample(entry.sample_index)
        self.entries = entries
        self.results = ResultsSet.from_list(data.get("results", []))
        self.calibrations = {
            name: Calibration.from_dict(row)
            for name, row in (data.get("calibrations") or {}).items()
        }
        # absent in every project written before this existed, which is
        # exactly the answer those projects want
        self.recalibrate = bool(data.get("recalibrate", False))
        # likewise absent from every project written before this existed,
        # which loads with an empty trail rather than an invented one
        self.audit = AuditTrail.from_dict(data.get("audit"))
        self.project_path = path
        self.sigMethodChanged.emit()
        self.sigSamplesChanged.emit()
        self.sigResultsChanged.emit()
        self.sigAuditChanged.emit()
        self._mark_clean()
        return missing
