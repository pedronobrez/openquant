"""
A spectral library, and a measured spectrum searched against it.

Structure-based annotation (`explain.py`) asks what a structure *could*
produce; a library asks what somebody *recorded* from the compound on an
instrument. The two answer different questions and disagree in useful
ways, so this sits beside the other rather than replacing it.

Libraries arrive as text: NIST's MSP, which MassBank, MoNA and GNPS all
export, and MGF. Both are records of a name, a precursor, a few fields and
a peak list; the parsers here read what those files carry and ignore what
they do not know. Matching is the ordinary spectral cosine over
square-rooted intensities — the weighting that keeps one base peak from
deciding everything — with each library peak paired to the nearest
unmatched measured peak inside a ppm tolerance. Two scores are reported:
the plain cosine over everything both spectra hold, and the reverse
cosine, which asks only whether the library's peaks are in the measured
spectrum and so forgives a co-eluting impurity. A hit with a high reverse
score and a low plain one is a compound present with company.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import numpy as np

#: how close a library peak and a measured one have to be, in ppm
PEAK_TOLERANCE_PPM = 20.0
#: how far the recorded precursor may sit from the queried one, in Da; a
#: nominal-mass library wants this wider, and the panel lets it be
PRECURSOR_TOLERANCE_DA = 0.02
#: measured peaks below this share of the base peak are not matched against:
#: the baseline of a product spectrum is full of them
NOISE_SHARE = 0.01

_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


@dataclass
class LibraryEntry:
    """One recorded spectrum."""

    name: str
    precursor: float | None = None
    precursor_type: str = ""
    formula: str = ""
    mz: np.ndarray = field(default_factory=lambda: np.zeros(0))
    #: scaled so the base peak is one
    intensity: np.ndarray = field(default_factory=lambda: np.zeros(0))
    #: the other fields the record carried, as written
    fields: dict = field(default_factory=dict)
    source: str = ""

    @property
    def peaks(self) -> int:
        return int(self.mz.size)


@dataclass(frozen=True)
class Pair:
    """A library peak and the measured peak it landed on."""

    measured: float
    library: float
    measured_share: float
    library_share: float

    @property
    def ppm(self) -> float:
        return (self.measured - self.library) / self.library * 1e6


@dataclass(frozen=True)
class LibraryHit:
    entry: LibraryEntry
    #: cosine over everything both spectra hold, 0 to 1
    score: float
    #: cosine asking only whether the library's peaks are in the measured
    #: spectrum, so an impurity beside the compound does not count against it
    reverse: float
    pairs: tuple[Pair, ...]
    of_library: int
    of_query: int
    #: measured precursor against the recorded one; None when the record has
    #: no precursor or none was queried
    delta_ppm: float | None = None

    @property
    def matched(self) -> int:
        return len(self.pairs)


def _finish(entry: LibraryEntry, mz: list[float], intensity: list[float],
            source: str) -> LibraryEntry | None:
    if not mz or not entry.name:
        return None
    order = np.argsort(mz)
    entry.mz = np.asarray(mz, dtype=float)[order]
    values = np.asarray(intensity, dtype=float)[order]
    top = float(values.max()) if values.size else 0.0
    entry.intensity = values / top if top > 0 else values
    entry.source = source
    return entry


def _peak_line(line: str) -> list[tuple[float, float]]:
    """
    A line of peaks. MSP writes one pair per line or several separated by
    semicolons, sometimes in parentheses or with a quoted annotation after;
    the first two numbers of each pair are the mass and the intensity.
    """
    pairs = []
    for piece in line.replace("(", " ").replace(")", " ").split(";"):
        piece = piece.split('"')[0]
        numbers = _NUMBER.findall(piece)
        if len(numbers) >= 2:
            pairs.append((float(numbers[0]), float(numbers[1])))
    return pairs


def parse_msp(text: str, source: str = "") -> list[LibraryEntry]:
    """
    NIST MSP: `Name:` opens a record, `Num Peaks:` announces the peaks, a
    blank line ends it. Field names vary by exporter — `PrecursorMZ`,
    `PRECURSORMZ`, `Precursor_type`, `PRECURSORTYPE` — and are matched
    without regard to case or underscores.
    """
    entries: list[LibraryEntry] = []
    entry: LibraryEntry | None = None
    mz: list[float] = []
    intensity: list[float] = []
    reading_peaks = False

    def close() -> None:
        nonlocal entry, mz, intensity, reading_peaks
        if entry is not None:
            finished = _finish(entry, mz, intensity, source)
            if finished is not None:
                entries.append(finished)
        entry, mz, intensity, reading_peaks = None, [], [], False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            close()
            continue
        key, sep, value = line.partition(":")
        normalised = key.strip().lower().replace("_", "").replace(" ", "")
        if sep and not reading_peaks and normalised == "name":
            close()
            entry = LibraryEntry(name=value.strip())
            continue
        if entry is None:
            continue
        if sep and not reading_peaks and normalised in ("numpeaks", "npeaks"):
            reading_peaks = True
            continue
        if sep and not reading_peaks and not _NUMBER.fullmatch(key.strip()):
            value = value.strip()
            if normalised in ("precursormz", "precursormass", "parentmass",
                              "precursor"):
                numbers = _NUMBER.findall(value)
                entry.precursor = float(numbers[0]) if numbers else None
            elif normalised in ("precursortype", "adduct", "iontype"):
                entry.precursor_type = value
            elif normalised == "formula":
                entry.formula = value
            else:
                entry.fields[key.strip()] = value
            continue
        for m, i in _peak_line(line):
            mz.append(m)
            intensity.append(i)
    close()
    return entries


def parse_mgf(text: str, source: str = "") -> list[LibraryEntry]:
    """MGF: `BEGIN IONS` to `END IONS`, `KEY=value` lines, then peaks."""
    entries: list[LibraryEntry] = []
    entry: LibraryEntry | None = None
    mz: list[float] = []
    intensity: list[float] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        upper = line.upper()
        if upper == "BEGIN IONS":
            entry, mz, intensity = LibraryEntry(name=""), [], []
            continue
        if upper == "END IONS":
            if entry is not None:
                if not entry.name:
                    entry.name = entry.fields.get("TITLE", "") or "unnamed"
                finished = _finish(entry, mz, intensity, source)
                if finished is not None:
                    entries.append(finished)
            entry = None
            continue
        if entry is None:
            continue
        key, sep, value = line.partition("=")
        if sep and not _NUMBER.fullmatch(key.strip()):
            key, value = key.strip().upper(), value.strip()
            if key == "TITLE":
                entry.name = value
            elif key == "PEPMASS":
                numbers = _NUMBER.findall(value)
                entry.precursor = float(numbers[0]) if numbers else None
            elif key in ("NAME", "COMPOUND"):
                entry.name = value
            elif key == "FORMULA":
                entry.formula = value
            elif key in ("ADDUCT", "PRECURSORTYPE", "PRECURSOR_TYPE", "IONMODE"):
                entry.precursor_type = entry.precursor_type or value
            else:
                entry.fields[key] = value
            continue
        for m, i in _peak_line(line):
            mz.append(m)
            intensity.append(i)
    return entries


class SpectralLibrary:
    """The entries of one or more files, searchable by a spectrum."""

    def __init__(self, entries: list[LibraryEntry] | None = None, path: str = ""):
        self.entries: list[LibraryEntry] = list(entries or [])
        self.path = path

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def with_precursor(self) -> int:
        return sum(1 for entry in self.entries if entry.precursor is not None)

    def search(self, mz: np.ndarray, intensity: np.ndarray,
               precursor: float | None = None,
               tolerance_ppm: float = PEAK_TOLERANCE_PPM,
               precursor_tolerance: float = PRECURSOR_TOLERANCE_DA,
               top: int = 20, noise_share: float = NOISE_SHARE) -> list[LibraryHit]:
        """
        The entries that best match a measured spectrum, best first.

        With a precursor, only records whose precursor sits within the
        tolerance are scored, plus records that carry none — those are kept
        and their `delta_ppm` is None, so the reader knows the filter could
        not apply to them rather than believing it did.
        """
        mz = np.asarray(mz, dtype=float)
        intensity = np.asarray(intensity, dtype=float)
        if mz.size == 0 or intensity.size == 0:
            return []
        top_i = float(intensity.max())
        if top_i <= 0:
            return []
        keep = intensity >= noise_share * top_i
        query_mz, query_i = mz[keep], intensity[keep] / top_i
        hits: list[LibraryHit] = []
        for entry in self.entries:
            delta = None
            if precursor is not None and entry.precursor is not None:
                if abs(entry.precursor - precursor) > precursor_tolerance:
                    continue
                delta = (precursor - entry.precursor) / entry.precursor * 1e6
            score, reverse, pairs = match(query_mz, query_i, entry.mz,
                                          entry.intensity, tolerance_ppm)
            if not pairs:
                continue
            hits.append(LibraryHit(entry, score, reverse, tuple(pairs),
                                   entry.peaks, int(query_mz.size), delta))
        hits.sort(key=lambda hit: (-hit.score, -hit.reverse))
        return hits[:top]


def match(query_mz: np.ndarray, query_i: np.ndarray, lib_mz: np.ndarray,
          lib_i: np.ndarray, tolerance_ppm: float = PEAK_TOLERANCE_PPM
          ) -> tuple[float, float, list[Pair]]:
    """
    Pair library peaks to measured ones and score the pairing.

    Library peaks are taken strongest first, each to the nearest measured
    peak still free within the tolerance, so a strong library ion is never
    robbed of its match by a weak one that happened to be listed earlier.
    Intensities are square-rooted before the cosine, the usual weighting.
    """
    if query_mz.size == 0 or lib_mz.size == 0:
        return 0.0, 0.0, []
    taken = np.zeros(query_mz.size, dtype=bool)
    pairs: list[Pair] = []
    for index in np.argsort(-lib_i):
        centre = float(lib_mz[index])
        window = centre * tolerance_ppm * 1e-6
        candidates = np.flatnonzero((np.abs(query_mz - centre) <= window) & ~taken)
        if candidates.size == 0:
            continue
        nearest = candidates[np.argmin(np.abs(query_mz[candidates] - centre))]
        taken[nearest] = True
        pairs.append(Pair(float(query_mz[nearest]), centre,
                          float(query_i[nearest]), float(lib_i[index])))
    if not pairs:
        return 0.0, 0.0, []
    q = np.sqrt(np.array([p.measured_share for p in pairs]))
    l = np.sqrt(np.array([p.library_share for p in pairs]))
    dot = float((q * l).sum())
    all_query = float(np.sqrt(query_i).__pow__(2).sum())     # = sum of shares
    all_library = float(lib_i.sum())
    score = dot / np.sqrt(all_query * all_library) if all_query and all_library else 0.0
    matched_query = float((q ** 2).sum())
    reverse = dot / np.sqrt(matched_query * all_library) if matched_query and all_library else 0.0
    return min(score, 1.0), min(reverse, 1.0), pairs


def load_library(path: str | os.PathLike) -> SpectralLibrary:
    """A library from an `.msp` or `.mgf` file, by its extension."""
    path = str(path)
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    source = os.path.basename(path)
    if path.lower().endswith(".mgf"):
        entries = parse_mgf(text, source)
    else:
        entries = parse_msp(text, source)
    return SpectralLibrary(entries, path)
