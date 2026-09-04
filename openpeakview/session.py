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

from .components import Component
from .matching import components_from_sample, match_channel
from .method import ProcessingMethod
from .samples import SampleEntry, shorten_names
from .wiff import WiffFile

PROJECT_SUFFIX = ".opvproj"


class Session(QtCore.QObject):
    """Owns the data; the workspaces are views onto it."""

    sigSamplesChanged = QtCore.pyqtSignal()
    sigMethodChanged = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files: list[WiffFile] = []
        self.entries: list[SampleEntry] = []
        self.method = ProcessingMethod()
        self.project_path: str | None = None

    # -- files ------------------------------------------------------------------ #
    def open_file(self, path: str) -> WiffFile:
        """Open a .wiff and add each of its samples to the batch."""
        wiff = WiffFile(path)
        self.files.append(wiff)
        for index in range(len(wiff.sample_names)):
            sample = wiff.sample(index)
            self.entries.append(
                SampleEntry(path=wiff.path, sample_index=index,
                            name=sample.name, sample=sample)
            )
        shorten_names(self.entries)
        self.sigSamplesChanged.emit()
        return wiff

    def close_all(self) -> None:
        for wiff in self.files:
            wiff.close()
        self.files.clear()
        self.entries.clear()
        self.project_path = None
        self.sigSamplesChanged.emit()

    @property
    def loaded_entries(self) -> list[SampleEntry]:
        return [e for e in self.entries if e.is_loaded]

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
        self.sigMethodChanged.emit()

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
            "version": 1,
            "method": self.method.to_dict(),
            "samples": [e.to_dict() for e in self.entries],
        }

    def save_project(self, path: str) -> None:
        if not path.endswith(PROJECT_SUFFIX):
            path += PROJECT_SUFFIX
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=False)
        self.project_path = path

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
        opened: dict[str, WiffFile] = {}
        for entry in entries:
            if not os.path.exists(entry.path):
                missing.append(entry.path)
                continue
            wiff = opened.get(entry.path)
            if wiff is None:
                try:
                    wiff = WiffFile(entry.path)
                except Exception:
                    missing.append(entry.path)
                    continue
                opened[entry.path] = wiff
                self.files.append(wiff)
            if entry.sample_index < len(wiff.sample_names):
                entry.sample = wiff.sample(entry.sample_index)
        self.entries = entries
        self.project_path = path
        self.sigMethodChanged.emit()
        self.sigSamplesChanged.emit()
        return missing
