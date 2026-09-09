"""
Opening a raw file without caring which format it is.

Everything above this line — the session, the workspaces, the quantitation —
asks a file for its samples and a sample for its channels. Which vendor wrote
it is a detail of how those arrive, and the only place that detail belongs is
here.
"""

from __future__ import annotations

import os

#: what can be opened, by extension. A .wiff needs its .wiff.scan beside it;
#: without it the file still opens — the chromatograms are in the .wiff —
#: and the sample's `problem` says why its spectra cannot be read.
FORMATS = {
    ".wiff": "SCIEX",
    ".mzml": "mzML",
}

#: for a file dialog, in the order they should be offered
FILE_FILTER = (
    "Mass spectrometry data (*.wiff *.mzML *.mzml);;"
    "SCIEX (*.wiff);;"
    "mzML (*.mzML *.mzml);;"
    "All files (*)"
)


class UnsupportedFormat(ValueError):
    pass


def format_of(path: str | os.PathLike) -> str:
    """The name of the format, or a refusal that says what was offered."""
    extension = os.path.splitext(str(path))[1].lower()
    if extension not in FORMATS:
        known = ", ".join(sorted(FORMATS))
        raise UnsupportedFormat(
            f"{os.path.basename(str(path))}: no reader for '{extension}' "
            f"(this build reads {known})"
        )
    return FORMATS[extension]


def is_supported(path: str | os.PathLike) -> bool:
    return os.path.splitext(str(path))[1].lower() in FORMATS


def open_raw(path: str | os.PathLike):
    """
    Open a raw file with whichever reader its extension calls for.

    The readers are imported here rather than at the top because the SCIEX one
    starts a .NET runtime on the way in. Someone working with mzML alone
    should not have to have .NET installed, and until this was deferred they
    did.
    """
    kind = format_of(path)
    if kind == "SCIEX":
        from .wiff import WiffFile

        return WiffFile(path)
    from .mzml import MzmlFile

    return MzmlFile(path)
