"""
Sample entries — the batch table.

Sample type, expected concentration, dilution and the internal-standard link
are not recorded in the .wiff file (every injection comes back as `kUnknown`),
so they are held here and saved with the project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

UNKNOWN = "Unknown"
STANDARD = "Standard"
QC = "Quality Control"
BLANK = "Blank"
DOUBLE_BLANK = "Double Blank"
SOLVENT = "Solvent"

SAMPLE_TYPES = (UNKNOWN, STANDARD, QC, BLANK, DOUBLE_BLANK, SOLVENT)

#: sample types whose points define a calibration curve
CALIBRATION_TYPES = (STANDARD,)


@dataclass
class SampleEntry:
    """One injection, plus the batch information the raw file does not carry."""

    path: str
    sample_index: int
    name: str
    sample_type: str = UNKNOWN
    actual_concentration: float | None = None
    dilution_factor: float = 1.0
    comment: str = ""
    #: the study group this injection belongs to — control, treated, day 7.
    #: Free text, because no vocabulary fits every study. Last in the field
    #: order so positional construction keeps working.
    sample_group: str = ""
    #: live wiff Sample; set when the file is open, never serialised
    sample: object | None = field(default=None, repr=False, compare=False)

    @property
    def key(self) -> str:
        return f"{self.path}|{self.sample_index}"

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def is_loaded(self) -> bool:
        return self.sample is not None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "sample_index": self.sample_index,
            "name": self.name,
            "sample_type": self.sample_type,
            "sample_group": self.sample_group,
            "actual_concentration": self.actual_concentration,
            "dilution_factor": self.dilution_factor,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SampleEntry":
        sample_type = str(data.get("sample_type", UNKNOWN))
        return cls(
            path=str(data.get("path", "")),
            sample_index=int(data.get("sample_index", 0)),
            name=str(data.get("name", "")),
            sample_type=sample_type if sample_type in SAMPLE_TYPES else UNKNOWN,
            sample_group=str(data.get("sample_group", "") or ""),
            actual_concentration=(
                None if data.get("actual_concentration") in (None, "")
                else float(data["actual_concentration"])
            ),
            dilution_factor=float(data.get("dilution_factor", 1.0) or 1.0),
            comment=str(data.get("comment", "")),
        )


def shorten_names(entries: list[SampleEntry]) -> None:
    """
    Give each entry a short display name by dropping the prefix shared by every
    file: `demo_QC01` and `demo_STD_L1` become
    `QC001` and `S001`.
    """
    stems = [os.path.splitext(e.filename)[0] for e in entries]
    prefix = os.path.commonprefix(stems) if len(stems) > 1 else ""
    prefix = prefix[: prefix.rfind("_") + 1] if "_" in prefix else ""
    for entry, stem in zip(entries, stems):
        entry.name = stem[len(prefix):] or stem
