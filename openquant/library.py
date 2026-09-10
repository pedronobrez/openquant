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

A record's `Formula` and `Precursor_type` are not decoration. Together they
give the m/z the record's ion actually has, to as many decimals as the
elements do, where `PrecursorMZ` is whatever its author typed — often two
places, sometimes truncated, occasionally of a different ion altogether. So
the search computes that mass where it can (`LibraryEntry.exact_precursor`),
measures Δ ppm against it and says so, matches a record whose written mass
*or* whose formula mass is in the window, flags a record whose two numbers
disagree by more than the written one's own precision, and — since an
adduct also declares a charge sign — refuses records of the other polarity.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import numpy as np

from . import chemistry
from .components import WRITTEN_UNITS
from .lipidmaps import mass_precision

#: how close a library peak and a measured one have to be, in ppm
PEAK_TOLERANCE_PPM = 20.0
#: how far the recorded precursor may sit from the queried one, in Da; a
#: nominal-mass library wants this wider, and the panel lets it be
PRECURSOR_TOLERANCE_DA = 0.02
#: measured peaks below this share of the base peak are not matched against:
#: the baseline of a product spectrum is full of them
NOISE_SHARE = 0.01
#: a record has to land this many of its peaks before it is a hit. Measured
#: on MassBank against a real product spectrum: with one, a spectrum that is
#: mostly one phosphocholine ion at 184.07 scored 83 against bisacodyl,
#: whose fragment at 184.0757 is 13 ppm away — one peak in common is a
#: coincidence, not a match, and a one-peak record matched on it is a
#: perfect score for nothing.
MIN_MATCHED = 2
#: the bins of the peak index, in daltons: wide enough that a tolerance of
#: PEAK_TOLERANCE_PPM at m/z 2000 fits inside one bin either side
INDEX_BIN = 0.05
#: under this, a record's written precursor and the mass its own formula and
#: adduct give are not called a disagreement however many decimals were
#: written. A library that writes five decimals is claiming ±0.000005 Da and
#: is not good to it: measured over 449,525 records of a lipid MSP that
#: writes exactly that, 96.8% sit inside 0.5 ppm of their own formula, 3.1%
#: inside 1 ppm, 309 inside 2 ppm — the exporter's own rounding — and then
#: **nothing at all** until one record at 116,411 ppm, a precursor typed
#: 101 Da wrong. So the floor is the far side of an empty trough twelve
#: times wider than the noise, and it is the number `precursor` already uses
#: for two measurements of one ion that ought to agree
DISAGREE_FLOOR_PPM = 25.0

_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


#: the field names an exporter may write the ion mode under, normalised the
#: way `parse_msp` normalises a key. A record with no adduct may still say
#: which polarity it was measured in, and that is enough for the gate
_ION_MODE_FIELDS = ("ionmode", "ionisationmode", "ionizationmode",
                    "polarity", "mode")


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
    #: the precursor exactly as the record wrote it. `430.35` and `430.3500`
    #: are the same float and not the same claim; only the text says how
    #: many decimals were meant, and `written_precision` needs to know
    precursor_text: str = ""

    #: worked out once, on demand: a library of 450,000 records pays for
    #: this only where a search reaches the record
    _derived: tuple | None = field(default=None, init=False, repr=False,
                                   compare=False)

    @property
    def peaks(self) -> int:
        return int(self.mz.size)

    def _derive(self) -> tuple:
        if self._derived is None:
            adduct = chemistry.adduct_from_name(self.precursor_type)
            exact = chemistry.mass_from_formula(self.formula, self.precursor_type)
            sign = chemistry.polarity_sign(self.precursor_type)
            if sign is None:
                for key, value in self.fields.items():
                    plain = str(key).lower().replace("_", "").replace(" ", "")
                    if plain in _ION_MODE_FIELDS:
                        sign = chemistry.polarity_sign(value)
                        if sign is not None:
                            break
            self._derived = (adduct, exact, sign)
        return self._derived

    @property
    def adduct(self) -> "chemistry.Adduct | None":
        """The adduct `Precursor_type` names, where it is one we model."""
        return self._derive()[0]

    @property
    def exact_precursor(self) -> float | None:
        """
        The m/z the record's own formula and adduct give, or None when
        either is missing or unreadable. This is the number the ion has;
        `precursor` is the number somebody typed.
        """
        return self._derive()[1]

    @property
    def polarity(self) -> int | None:
        """
        +1, -1 or None — the sign the record's adduct declares, falling back
        to an ion-mode field where the adduct says nothing. None means the
        record does not say, and a record that does not say is never
        filtered out on polarity.
        """
        return self._derive()[2]

    @property
    def written_precision(self) -> float:
        """
        What the precursor as written is actually good to, in Da.

        A whole unit in its last decimal, not half of one:
        `components.written_tolerance` measured that on 141 real components,
        because a written mass is as often truncated as rounded — a method
        writes `286.2` for 286.2741 — and half a unit rejects the compound
        over the way its own precursor was typed. Never tighter than
        `DISAGREE_FLOOR_PPM`, since a library that writes five decimals is
        claiming a precision its own arithmetic does not have.
        """
        if self.precursor is None:
            return 0.5
        written = WRITTEN_UNITS * mass_precision(self.precursor,
                                                 self.precursor_text or None)
        return max(written, abs(self.precursor) * DISAGREE_FLOOR_PPM * 1e-6)

    @property
    def precursor_disagrees(self) -> bool:
        """
        Whether the record's two accounts of its own precursor differ by
        more than the written one is good to. Either the formula, the
        adduct or the typed mass is wrong, and which cannot be told from
        here — so this is reported, never repaired.
        """
        exact = self.exact_precursor
        if exact is None or self.precursor is None:
            return False
        return abs(self.precursor - exact) > self.written_precision


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
    #: measured precursor against the record's own; None when the record
    #: gives no precursor of either kind, or none was queried
    delta_ppm: float | None = None
    #: which of the record's two precursors `delta_ppm` was measured
    #: against: "formula" (its formula and adduct), "written" (its
    #: `PrecursorMZ`), or "" when there is no delta to measure
    delta_basis: str = ""
    #: the record's written precursor and its formula's disagree by more
    #: than the written one's precision — see `LibraryEntry`
    precursor_disagrees: bool = False

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
                entry.precursor_text = numbers[0] if numbers else ""
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
                entry.precursor_text = numbers[0] if numbers else ""
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
        # the precursors as one array, so a precursor filter is a vector
        # comparison over the library rather than a Python loop over it
        self._precursors = np.array(
            [e.precursor if e.precursor is not None else np.nan for e in self.entries],
            dtype=float)
        # which records hold a peak in which bin, built on first use: a
        # search with no precursor filter has 139,000 records to consider,
        # and only the ones that share a peak with the query can score
        self._index: dict[int, np.ndarray] | None = None
        # the mass each record's formula and adduct give, and the sign that
        # adduct declares. Both are built on first use for the same reason
        # as the peak index: reading formulas for every record of a large
        # library at load time would double the wait for a search that may
        # never need them
        self._exact: np.ndarray | None = None
        self._polarities: np.ndarray | None = None

    def _formula_masses(self) -> np.ndarray:
        if self._exact is None:
            self._exact = np.array(
                [e.exact_precursor if e.exact_precursor is not None else np.nan
                 for e in self.entries], dtype=float)
        return self._exact

    def _signs(self) -> np.ndarray:
        """+1, -1, or 0 where the record does not say."""
        if self._polarities is None:
            self._polarities = np.array([e.polarity or 0 for e in self.entries],
                                        dtype=np.int8)
        return self._polarities

    def _build_index(self) -> dict[int, np.ndarray]:
        bins: dict[int, list[int]] = {}
        for number, entry in enumerate(self.entries):
            for b in np.unique(np.floor(entry.mz / INDEX_BIN).astype(np.int64)):
                bins.setdefault(int(b), []).append(number)
        return {b: np.array(members, dtype=np.int64) for b, members in bins.items()}

    def _candidates(self, query_mz: np.ndarray, precursor: float | None,
                    precursor_tolerance: float, include_unknown: bool,
                    min_matched: int, polarity: int | None = None,
                    include_other_polarity: bool = False) -> np.ndarray:
        """
        The records worth scoring.

        With a precursor: the records whose written precursor **or** whose
        formula mass is within the tolerance — a record states its ion
        twice and either statement may be the one that matches, so nothing
        is lost because the two disagree. A record carrying neither is
        left out unless asked for. Measured on MassBank, 24,000 of 139,000
        records carry no written precursor, and a filter that admits them
        all is not a filter: every search came back dominated by them.
        Without a precursor: the records sharing at least `min_matched`
        query peaks' bins, counted one per query peak, which is what a hit
        needs before it can be one.

        Either way, a query polarity leaves out the records whose adduct
        declares the other sign. A record that declares no sign is kept:
        the gate refuses what contradicts the query, not what is silent.
        """
        if precursor is not None:
            exact = self._formula_masses()
            with np.errstate(invalid="ignore"):
                close = np.abs(self._precursors - precursor) <= precursor_tolerance
                close |= np.abs(exact - precursor) <= precursor_tolerance
                if include_unknown:
                    close |= np.isnan(self._precursors) & np.isnan(exact)
            found = np.flatnonzero(close)
        else:
            if self._index is None:
                self._index = self._build_index()
            per_peak: list[np.ndarray] = []
            for b in np.unique(np.floor(query_mz / INDEX_BIN).astype(np.int64)):
                members = [self._index[n] for n in (int(b) - 1, int(b), int(b) + 1)
                           if n in self._index]
                if members:
                    per_peak.append(np.unique(np.concatenate(members)))
            if not per_peak:
                return np.zeros(0, dtype=np.int64)
            records, counts = np.unique(np.concatenate(per_peak),
                                        return_counts=True)
            found = records[counts >= max(min_matched, 1)]
        if polarity and not include_other_polarity and found.size:
            signs = self._signs()[found]
            found = found[(signs == 0) | (signs == polarity)]
        return found

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def with_precursor(self) -> int:
        return sum(1 for entry in self.entries if entry.precursor is not None)

    @property
    def with_formula_mass(self) -> int:
        """Records whose formula and adduct both read, so their ion's mass
        is known to the elements rather than to whatever was typed."""
        return int(np.count_nonzero(~np.isnan(self._formula_masses())))

    @property
    def disagreeing(self) -> list[LibraryEntry]:
        """The records whose written precursor and whose formula's differ by
        more than the written one's own precision."""
        return [e for e in self.entries if e.precursor_disagrees]

    def search(self, mz: np.ndarray, intensity: np.ndarray,
               precursor: float | None = None,
               tolerance_ppm: float = PEAK_TOLERANCE_PPM,
               precursor_tolerance: float = PRECURSOR_TOLERANCE_DA,
               top: int = 20, noise_share: float = NOISE_SHARE,
               min_matched: int = MIN_MATCHED,
               include_unknown_precursor: bool = False,
               polarity=None,
               include_other_polarity: bool = False) -> list[LibraryHit]:
        """
        The entries that best match a measured spectrum, best first.

        With a precursor, only records whose precursor sits within the
        tolerance are scored — the written one or the one the record's
        formula and adduct give, whichever fits. Records that state neither
        are left out unless `include_unknown_precursor` asks for them, and
        then their `delta_ppm` is None so the reader knows the filter could
        not apply to them rather than believing it did. Δ ppm is measured
        against the formula's mass wherever there is one, since that is the
        mass the ion has; `LibraryHit.delta_basis` says which was used.

        `polarity` is the query's — a sign, or the word a channel writes
        (`Positive`). Records whose adduct declares the other sign are left
        out unless `include_other_polarity`; records that declare no sign
        are always kept. A record has to land `min_matched` peaks to be
        listed at all.
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
        sign = chemistry.polarity_sign(polarity)
        hits: list[LibraryHit] = []
        for number in self._candidates(query_mz, precursor, precursor_tolerance,
                                       include_unknown_precursor, min_matched,
                                       sign, include_other_polarity):
            entry = self.entries[int(number)]
            reference, basis = entry.exact_precursor, "formula"
            if reference is None:
                reference, basis = entry.precursor, "written"
            delta = None
            if precursor is not None and reference is not None:
                delta = (precursor - reference) / reference * 1e6
            else:
                basis = ""
            score, reverse, pairs = match(query_mz, query_i, entry.mz,
                                          entry.intensity, tolerance_ppm)
            if len(pairs) < max(min_matched, 1):
                continue
            hits.append(LibraryHit(entry, score, reverse, tuple(pairs),
                                   entry.peaks, int(query_mz.size), delta,
                                   basis, entry.precursor_disagrees))
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


# --------------------------------------------------------------------------- #
# a library of one's own
# --------------------------------------------------------------------------- #
#: peaks under this share of the base peak are not written into a record of
#: one's own. A product spectrum on a TOF carries hundreds of baseline points
#: for every fragment, and a record made of them matches everything
OWN_MIN_RELATIVE = 0.01
#: at most this many peaks, strongest first. A record is a fingerprint, not
#: an archive of the scan
OWN_MAX_PEAKS = 200
#: the fields written before the peaks, in the order NIST and MassBank write
#: them. `Num Peaks` is last because `parse_msp` reads what follows as peaks
_HEAD_FIELDS = ("PrecursorMZ", "Precursor_type", "Formula")

#: when the spectrum was acquired, as the file records it — not when the
#: record was made. The comment already carried "added <today>", and a
#: library of one's own read back as a history needs the day the instrument
#: measured on: records written on one afternoon from a folder acquired over
#: three months are three months of history, and the day they were typed in
#: says nothing about the standard.
ACQUIRED_FIELD = "Acquired"

#: the base peak's height in the counts the instrument reported. Every
#: library format holds intensities relative to the base peak, so the
#: absolute size of the spectrum is lost the moment a record is written —
#: and it is the one number that says whether the standard is still giving
#: what it gave. It is written here, once, where the measurement is still to
#: hand; a record made before this existed has none and says so.
BASE_INTENSITY_FIELD = "Base_peak_intensity"

#: the isotopic purity of a labelled standard, as `purity.Purity.field`
#: writes it: the species distribution, the atom % D and the ion it was read
#: from. A record of a d4 standard says what it fragments to and nothing at
#: all about what the material was; this is the missing half, and it can only
#: be written here because the measurement needs the profile spectrum the
#: record does not keep.
PURITY_FIELD = "Isotopic_purity"

#: what another exporter may spell those two under, matched whole and
#: without regard to case, underscores or spaces
_ACQUIRED_KEYS = frozenset({"acquired", "acquisitiondate", "acquisitiontime",
                            "acquisitiondatetime", "date", "datetime",
                            "creationdate"})
_BASE_INTENSITY_KEYS = frozenset({"basepeakintensity", "baseintensity",
                                  "basepeakheight"})


def field_value(entry: LibraryEntry, keys) -> str:
    """
    The first of a record's fields whose name is one of `keys`, as written.

    Field names vary by exporter exactly as they do in `parse_msp`, so the
    comparison is on the name with its case, spaces and underscores taken
    out — and on the whole name, never on what it contains: matching a
    fragment of a name is how `Ion_source` comes back as a collision energy.
    """
    for key, value in (getattr(entry, "fields", None) or {}).items():
        if str(key).strip().lower().replace("_", "").replace(" ", "") in keys:
            text = str(value).strip()
            if text:
                return text
    return ""


def acquired_of(entry: LibraryEntry) -> str:
    """When the spectrum was acquired, as the record carries it, or ""."""
    return field_value(entry, _ACQUIRED_KEYS)


def base_intensity_of(entry: LibraryEntry) -> float | None:
    """
    The base peak's absolute height, where the record carries one.

    None means it was not recorded, which is not the same as zero: a record
    written before the field existed, or by somebody else's exporter, cannot
    say how big the spectrum was.
    """
    text = field_value(entry, _BASE_INTENSITY_KEYS)
    found = _NUMBER.search(text)
    if not found:
        return None
    try:
        return float(found.group())
    except ValueError:
        return None


def _one_line(value: str) -> str:
    """A field is one line: a newline inside it would end the record."""
    return " ".join(str(value).split())


def _write_mass(value: float) -> str:
    """
    A precursor written with the precision it was given, not more.

    The shortest text that reads back as the same float: `430.35` stays
    `430.35` and `411.3054` stays `411.3054`. Padding to four decimals
    instead would write `430.3500`, and a record that claims four decimals
    is one that `precursor_disagrees` measures to ±0.00005 — so a method
    value typed to two places would be called wrong by its own formula.
    """
    return repr(float(value))


def entry_from_spectrum(name: str, mz, intensity, precursor: float | None = None,
                        precursor_type: str = "", formula: str = "",
                        collision_energy: float | None = None,
                        comment: str = "", acquired: str = "",
                        isotopic_purity: str = "",
                        min_relative: float = OWN_MIN_RELATIVE,
                        max_peaks: int = OWN_MAX_PEAKS) -> LibraryEntry:
    """
    A record built from a measured spectrum.

    The peaks are taken as given and must already be **centroids**: a profile
    spectrum has some tens of points across every ion, and a record made of
    them describes the instrument's peak shape rather than the compound. The
    Explorer centroids before it hands the spectrum over
    (`processing.centroid_spectrum`), which is where that happens.

    What is left is a floor and a ceiling. Peaks under `min_relative` of the
    base peak are dropped — the baseline of a product scan is thousands of
    them, and a record carrying them matches anything — and at most
    `max_peaks` of what survives is kept, strongest first. Intensities are
    stored relative to the base peak, as every library format holds them and
    as `parse_msp` reads them back.

    Two fields go in beyond what the analyst types, because a record read
    back later as a history of one standard needs them and nothing can
    recover them afterwards: `Acquired`, the day the instrument measured on
    rather than the day the record was made, and `Base_peak_intensity`, the
    absolute height the relative peaks are shares of. See
    `standard_history.py`, which reads both.

    `isotopic_purity` is a third of the same kind and it is why this
    parameter exists rather than being folded into the comment: the purity is
    measured from the **profile** spectrum, whose isotope envelope sits at
    tenths of a per cent of the base peak — under `min_relative`, and so
    thrown away by the very next line of this function. A record cannot be
    asked afterwards what the material's purity was, so it is written when it
    is still known. `purity.Purity.field` is the text.
    """
    name = _one_line(name)
    if not name:
        raise ValueError("a record needs a name")
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if mz.size != intensity.size:
        raise ValueError("the mass and intensity arrays differ in length")
    finite = np.isfinite(mz) & np.isfinite(intensity) & (intensity > 0)
    mz, intensity = mz[finite], intensity[finite]
    top = float(intensity.max()) if intensity.size else 0.0
    if top <= 0:
        raise ValueError("the spectrum has no peaks to write")
    keep = np.flatnonzero(intensity >= min_relative * top)
    if keep.size > max_peaks:
        keep = keep[np.argsort(-intensity[keep])[:max_peaks]]
    keep = keep[np.argsort(mz[keep])]
    fields: dict[str, str] = {}
    if collision_energy is not None:
        fields["Collision_energy"] = f"{float(collision_energy):g}"
    if acquired:
        fields[ACQUIRED_FIELD] = _one_line(acquired)
    # written always, and from the spectrum rather than from an argument:
    # the base peak's height is known here and nowhere afterwards, since
    # what is stored is every peak as a share of it
    fields[BASE_INTENSITY_FIELD] = f"{top:.6g}"
    if isotopic_purity:
        fields[PURITY_FIELD] = _one_line(isotopic_purity)
    if comment:
        fields["Comment"] = _one_line(comment)
    return LibraryEntry(
        name=name,
        precursor=None if precursor is None else float(precursor),
        precursor_type=_one_line(precursor_type),
        formula=_one_line(formula),
        mz=mz[keep],
        intensity=intensity[keep] / top,
        fields=fields,
        # the same text `format_msp` will write, so a record knows what its
        # precursor is good to before it has been through a file
        precursor_text="" if precursor is None else _write_mass(precursor),
    )


def format_msp(entries: list[LibraryEntry]) -> str:
    """The records as NIST-style MSP text, a blank line between them."""
    out: list[str] = []
    for entry in entries:
        written = {
            "PrecursorMZ": "" if entry.precursor is None else _write_mass(entry.precursor),
            "Precursor_type": entry.precursor_type,
            "Formula": entry.formula,
        }
        out.append(f"Name: {_one_line(entry.name)}")
        for key in _HEAD_FIELDS:
            if written[key]:
                out.append(f"{key}: {written[key]}")
        for key, value in entry.fields.items():
            if str(value).strip():
                out.append(f"{_one_line(key)}: {_one_line(value)}")
        out.append(f"Num Peaks: {entry.peaks}")
        for m, i in zip(entry.mz, entry.intensity):
            # intensities as a percentage of the base peak, which is what
            # `parse_msp` normalises away again on the way back in
            out.append(f"{m:.5f} {i * 100:.6g}")
        out.append("")
    return "\n".join(out) + ("\n" if out else "")


def write_msp(entries: list[LibraryEntry], path: str | os.PathLike,
              append: bool = False) -> int:
    """
    Write records to an `.msp` file and return how many were written.

    `append` is the ordinary case for a library of one's own: every infusion
    is one more record in the same file. A record ends at a blank line, so a
    file that does not end in one is given the separator it lacks before the
    next record starts — otherwise the two run together into one.
    """
    path = str(path)
    text = format_msp(entries)
    mode = "a" if append and os.path.exists(path) else "w"
    prefix = ""
    if mode == "a":
        with open(path, encoding="utf-8", errors="replace") as handle:
            existing = handle.read()
        if existing and not existing.endswith("\n\n"):
            prefix = "\n" if existing.endswith("\n") else "\n\n"
    with open(path, mode, encoding="utf-8", newline="\n") as handle:
        handle.write(prefix + text)
    return len(entries)


def count_records(path: str | os.PathLike) -> int:
    """How many records a library file holds, without keeping them."""
    try:
        return len(load_library(path))
    except OSError:
        return 0


# --------------------------------------------------------------------------- #
# a batch of infusions at once, and rewriting what was written
# --------------------------------------------------------------------------- #
#: what separates the pieces of a record's comment. The Explorer's spectrum
#: pane already titles itself "sample · channel · average of n scans · RT a–b
#: min", and a record made from it keeps those words; a whole batch written
#: at once writes the same shape, so one parser reads both.
PROVENANCE_SEPARATOR = " · "

#: how many decimals a computed precursor is written with. A mass worked
#: out from a formula is a float with seventeen significant figures and no
#: instrument has ever measured one: `504.32914261554896` in a record is a
#: claim nobody can hold it to, and five decimals is what the peak list
#: beside it is written with — 0.02 ppm at m/z 500, finer than any mass
#: spectrometer's own agreement with itself.
EXACT_DECIMALS = 5

#: how far apart two peaks have to be before they are two peaks, in Da. The
#: figure `spectra_compare.MIN_DISTANCE` picks an infusion's peaks with,
#: because a record rewritten from the file has to come back with the peaks
#: the record was written with — a second opinion about where a centroid
#: lies would show up as the standard having changed.
OWN_MIN_DISTANCE = 0.05

#: the acquisition a comment names, taken by its extension rather than by
#: position: the pieces around it hold separators of their own. The same
#: rule `standard_history.file_of` reads a history's files with.
_COMMENT_FILE = re.compile(r"[^\s·|,;]+\.(?:wiff2?|mzml|mzxml|raw|d)\b",
                           re.IGNORECASE)
_COMMENT_SCANS = re.compile(r"(\d[\d,]*)\s+scans?", re.IGNORECASE)
_COMMENT_RT = re.compile(r"RT\s*([\d.]+)\s*[–—-]\s*([\d.]+)")
_COMMENT_ADDED = re.compile(r"\badded\s+(\S+)", re.IGNORECASE)
#: the bottle a standard was infused from, as the New standard dialog writes
#: it. The one thing about a record that is not in the acquisition at all: two
#: records of the same compound six months apart are the same standard only if
#: they are the same lot, and nothing but the person holding the vial can say
_COMMENT_LOT = re.compile(r"\blot\s+(\S+)", re.IGNORECASE)

#: pieces of a comment that say how the spectrum was made rather than where
#: it came from. What is left, in order, is the sample and the channel.
#: Matched as whole words: `^CE` alone would take `CEramide` for a collision
#: energy, and a sample is named by whoever ran it.
_COMMENT_NOTE = re.compile(
    r"^(added|recalibrated|background|average|scans?|RT|CE|lot)\b",
    re.IGNORECASE)

#: how the report names the formula and the adduct it identified, in the
#: sentence it prints under the table. Read rather than worked out again:
#: see `identity_of`.
_IDENTITY = re.compile(r"formula\s+(\S+?)\s+as\s+(\[[^\]]+\][-+]?\d*[-+]?)")


def _flat_label(text) -> str:
    """A label with its spacing and case set aside, for comparing two."""
    return " ".join(str(text or "").split()).lower()


@dataclass(frozen=True)
class Provenance:
    """
    Where a record of one's own came from, as its own comment says.

    Nothing else in a record can say: a library format holds a name, a
    precursor and peaks, and the comment is the only field left to write an
    acquisition into. So the comment is written in a fixed shape and read
    back here, and everything that has to know which measurement a record
    *is* — the duplicate check, the rewrite — asks this rather than the text.
    """

    file: str = ""
    sample: str = ""
    channel: str = ""
    scans: int = 0
    rt_range: tuple[float, float] | None = None
    #: the day the record was written, as the comment says it
    added: str = ""
    #: the bottle the standard was infused from, where the record says. Not a
    #: measurement and not recoverable from the acquisition: it is what the
    #: analyst typed when the standard was entered, and the one field that
    #: says whether two records months apart are of the same material.
    lot: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """
        What makes two records the same measurement: **the acquisition file
        and the channel inside it**, both as the comment names them, with
        case and spacing set aside.

        Not the compound and not the name: the same vial infused twice is
        two measurements and belongs in the file twice, while the same
        channel of the same file written twice is one measurement written
        down twice, which is what turns a history into a chart of nothing.
        A record whose comment names no file has no key — see `keyed`.
        """
        return (self.file.lower(), _flat_label(self.channel))

    @property
    def keyed(self) -> bool:
        """
        Whether this provenance can decide anything.

        A record that does not name its acquisition — somebody else's
        library, or one written before the comment carried one — is never
        called a duplicate of anything. Silence is not a match.
        """
        return bool(self.file)


def provenance_comment(file: str = "", sample: str = "", channel: str = "",
                       scans: int = 0,
                       rt_range: "tuple[float, float] | None" = None,
                       added: str = "", note: str = "", lot: str = "") -> str:
    """
    The comment a record of one's own carries, in the shape read back.

    The pieces are the sample, the channel, how much of the run was
    averaged, the file and the day the record was made — the Explorer's own
    pane title with the file and the date after it, which is what one
    spectrum added by hand has always written. `note` goes on the end for
    anything done to the axis, which at present is the mass recalibration.

    `lot` is the bottle, and it is the one piece here that no acquisition
    holds: it is written when the standard is entered and read back by
    `provenance_of`, so that a history of one compound can say whether it is
    a history of one material.
    """
    pieces = [p for p in (str(sample or "").strip(),
                          str(channel or "").strip()) if p]
    if scans:
        pieces.append(f"average of {int(scans):,} scans")
    if rt_range is not None:
        low, high = min(rt_range), max(rt_range)
        pieces.append(f"RT {low:.4f}–{high:.4f} min")
    if file:
        pieces.append(os.path.basename(str(file)))
    if lot:
        pieces.append(f"lot {str(lot).strip()}")
    if note:
        pieces.append(str(note).strip())
    if added:
        pieces.append(f"added {added}")
    return _one_line(PROVENANCE_SEPARATOR.join(pieces))


def provenance_of(entry: LibraryEntry) -> Provenance:
    """
    What a record's comment says about where it came from.

    The file is found by its extension and the times and the scan count by
    the words around them, so a comment whose pieces were reordered still
    reads; the sample and the channel are the first two pieces that describe
    neither, in that order, which is the one thing here that is positional.
    A comment written by another program gives an empty provenance rather
    than a wrong one.
    """
    comment = field_value(entry, {"comment"})
    if not comment:
        return Provenance()
    found = _COMMENT_FILE.search(comment)
    file = os.path.basename(found.group()) if found else ""
    plain: list[str] = []
    for piece in comment.split("·"):
        piece = piece.strip()
        if not piece or _COMMENT_NOTE.match(piece):
            continue
        if _COMMENT_FILE.search(piece):
            continue
        plain.append(piece)
    scans = _COMMENT_SCANS.search(comment)
    times = _COMMENT_RT.search(comment)
    added = _COMMENT_ADDED.search(comment)
    lot = _COMMENT_LOT.search(comment)
    return Provenance(
        file=file,
        sample=plain[0] if plain else "",
        channel=plain[1] if len(plain) > 1 else "",
        scans=int(scans.group(1).replace(",", "")) if scans else 0,
        rt_range=((float(times.group(1)), float(times.group(2)))
                  if times else None),
        added=added.group(1) if added else "",
        lot=lot.group(1) if lot else "",
    )


def provenance_keys(path: str | os.PathLike) -> set:
    """
    The provenance key of every record a library file already holds.

    Read from the file rather than from anything in memory: a library of
    one's own is appended to over months and from more than one window, and
    what is on disk is what is already there.
    """
    try:
        entries = load_library(path).entries
    except OSError:
        return set()
    keys = set()
    for entry in entries:
        provenance = provenance_of(entry)
        if provenance.keyed:
            keys.add(provenance.key)
    return keys


def own_peaks(mz, intensity) -> list:
    """
    The peaks of an averaged spectrum a record of one's own is made of.

    `processing.pick_peaks` at this library's own floor and ceiling, with
    the centroid taken across each maximum: exactly what the Infusions tab
    already picked for scoring, so a record written from a row and the same
    record rewritten from the file come back with the same numbers.
    """
    from .processing import pick_peaks

    return pick_peaks(np.asarray(mz, dtype=float),
                      np.abs(np.asarray(intensity, dtype=float)),
                      max_peaks=OWN_MAX_PEAKS, min_relative=OWN_MIN_RELATIVE,
                      min_distance=OWN_MIN_DISTANCE, centroid=True)


def identity_of(report) -> tuple[str, str]:
    """
    The formula and the adduct an infusion report already worked out.

    Read off the report rather than worked out a second time: the report
    identifies the adduct against the channel's written precursor and puts
    back the labels the compound's name declares, and a record carrying a
    second opinion about either would disagree with the table it was made
    from. Everything is read defensively, and a report that says nothing
    gives two empty strings — a record without a formula, rather than a
    guess at one.
    """
    adduct = str(getattr(report, "adduct", "") or "").strip()
    explanation = getattr(report, "explanation", None)
    record = getattr(explanation, "record", None)
    formula = str(getattr(record, "formula", "") or "").strip()
    found = _IDENTITY.search(str(getattr(report, "basis", "") or ""))
    if found:
        # the basis carries the formula as it was explained — with the
        # labels the component table has no column for
        formula = found.group(1).strip() or formula
        adduct = adduct or found.group(2).strip()
    return formula, adduct


@dataclass(frozen=True)
class Skipped:
    """One infusion no record was made of, and why."""

    label: str
    reason: str

    def __str__(self) -> str:
        return f"{self.label} ({self.reason})"


@dataclass
class OwnRecords:
    """The records a batch of infusions offers, and what it does not."""

    entries: list = field(default_factory=list)
    skipped: list = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def line(self, written: int | None = None) -> str:
        """
        What was written and what was not, in one line, with the reasons.

        The reasons are the point: a row that produced no record is a row
        somebody has to decide about, and a count on its own hides which.
        """
        written = len(self.entries) if written is None else int(written)
        said = f"{written} record(s) written"
        if self.skipped:
            said += (f", {len(self.skipped)} skipped: "
                     + "; ".join(str(s) for s in self.skipped))
        return said + "."


def records_from_summary(rows, existing=(), added: str = "",
                         identify=None, acquired=None,
                         lot: str = "") -> OwnRecords:
    """
    One record per measured infusion, for a whole batch written in one go.

    `rows` is an `infusion_report.InfusionSummary` or its rows. Each carries
    the averaged, centroided peaks the tab already picked, so nothing is
    read from a file here and nothing is centroided twice: the record is
    made of the numbers the table was made of.

    What goes into a record, and where it comes from:

    * the name is the compound the row proposes — a row that could not
      propose one is skipped and says so, since a record nobody can find
      again is not a record;
    * the adduct and the formula are what the report identified
      (`identity_of`), or whatever `identify(row)` returns where the caller
      knows better — the panel asks the method's component table as well;
    * `PrecursorMZ` is what that formula and that adduct weigh, so the
      record's two accounts of its own precursor agree; where there is no
      formula the measured precursor stands, and the method's written one
      only where neither does;
    * the collision energy and the activation come from the channel;
    * `Acquired` is the day the instrument measured on, from `acquired` — a
      mapping from file name to acquisition time, since a report holds the
      file name and only the session holds the sample;
    * the comment is the provenance, in the shape `provenance_of` reads,
      with `lot` — the bottle — after the file where one is given.

    A row whose acquisition and channel are already in `existing` — the keys
    `provenance_keys` gives for the file being appended to — is skipped
    rather than written twice; so is a second row of the same key inside one
    batch. Nothing is written to disk here: the records come back and the
    caller writes them, which is what lets this be exercised without a
    library and without a dialog.
    """
    import datetime as _dt

    rows = list(getattr(rows, "rows", rows) or [])
    added = added or _dt.date.today().isoformat()
    seen = set(existing or ())
    times = dict(acquired or {})
    made = OwnRecords()
    for row in rows:
        report = getattr(row, "report", row)
        compound = str(getattr(row, "compound", "")
                       or getattr(report, "compound", "") or "").strip()
        file = str(getattr(report, "file", "") or "")
        label = str(getattr(report, "sample", "") or file
                    or compound or "an infusion")
        if not compound:
            made.skipped.append(Skipped(
                label, "no compound could be proposed from its name"))
            continue
        peaks = list(getattr(row, "peaks", ()) or [])
        if not peaks:
            made.skipped.append(Skipped(
                label, f"no peak at or above {OWN_MIN_RELATIVE:.0%} of the "
                       f"base peak to write"))
            continue
        channel = _short_channel(report)
        provenance = Provenance(
            file=os.path.basename(file),
            sample=str(getattr(report, "sample", "") or ""),
            channel=channel, scans=int(getattr(report, "scans", 0) or 0),
            rt_range=getattr(report, "rt_range", None), lot=str(lot or ""))
        if provenance.keyed and provenance.key in seen:
            made.skipped.append(Skipped(
                label, f"already in the file from {provenance.file}"))
            continue
        formula, adduct = (identify(row) if identify is not None
                           else identity_of(report))
        try:
            entry = entry_from_spectrum(
                compound,
                [p[0] for p in peaks], [p[1] for p in peaks],
                precursor=_own_precursor(report, row, formula, adduct),
                precursor_type=adduct, formula=formula,
                collision_energy=getattr(report, "collision_energy", None),
                comment=provenance_comment(
                    file=provenance.file, sample=provenance.sample,
                    channel=channel, scans=provenance.scans,
                    rt_range=provenance.rt_range, added=added, lot=lot),
                acquired=str(times.get(provenance.file, "")
                             or getattr(report, "acquired", "") or ""))
        except ValueError as exc:
            made.skipped.append(Skipped(label, str(exc)))
            continue
        _set_activation(entry, _activation_in(
            getattr(report, "channel", ""), getattr(report, "channel_name", ""),
            getattr(report, "sample", ""), compound))
        made.entries.append(entry)
        if provenance.keyed:
            seen.add(provenance.key)
    return made


def _short_channel(report) -> str:
    """
    The channel a record's comment names: the experiment and its precursor.

    `wiff.ChannelInfo.short_label`'s words — the whole label carries the mass
    range and the collision energy, which describe the method rather than
    name the channel, and a comment holding them cannot be compared with one
    written from the Explorer, which holds the short form.
    """
    name = str(getattr(report, "channel_name", "") or "").strip()
    precursor = getattr(report, "written_precursor", None)
    if name and precursor:
        return f"{name} {float(precursor):.2f}"
    return name or str(getattr(report, "channel", "") or "").strip()


def _own_precursor(report, row, formula: str, adduct: str) -> float | None:
    """
    What a record of one's own writes as its `PrecursorMZ`.

    The mass the identified formula and adduct actually have, where both are
    known: a record whose written precursor and whose formula disagree is one
    `precursor_disagrees` flags in every later search, and a method types its
    precursor to two decimals. Failing that the measurement, and failing that
    what the method wrote — the order of how much each number knows.
    """
    exact = (chemistry.mass_from_formula(formula, adduct)
             if formula and adduct else None)
    if exact is not None:
        return round(float(exact), EXACT_DECIMALS)
    found = getattr(row, "found", None)
    if found:
        return float(found[0])
    written = getattr(report, "written_precursor", None)
    return None if written is None else float(written)


def _activation_in(*texts) -> str:
    """How the compound was fragmented, where one of these names it."""
    from .standard_history import activation_in

    return activation_in(*texts)


def _set_activation(entry: LibraryEntry, activation: str) -> None:
    """
    Write the activation into a record, before the comment.

    A field of its own rather than left to the comment: `standard_history`
    charts CID and EAD of the same compound as different series, and it
    should not have to find that out from a file name.
    """
    if not activation or field_value(entry, {"activation"}):
        return
    fields = dict(entry.fields)
    comment = fields.pop("Comment", None)
    fields["Activation"] = activation
    if comment is not None:
        fields["Comment"] = comment
    entry.fields = fields


# --------------------------------------------------------------------------- #
# rewriting a library of one's own from the acquisitions it names
# --------------------------------------------------------------------------- #
@dataclass
class Rewrite:
    """What rewriting a library of one's own from its files came to."""

    path: str = ""
    #: the copy of the file as it was, or "" when nothing was rewritten
    backup: str = ""
    #: the records read again from their acquisition, by name
    rewritten: list = field(default_factory=list)
    #: the records left exactly as they were, with why
    kept: list = field(default_factory=list)
    #: how many were rewritten onto a corrected mass axis
    recalibrated: int = 0
    seconds: float = 0.0

    def summary(self) -> str:
        said = [f"{len(self.rewritten)} record(s) rewritten"]
        if self.recalibrated:
            said.append(f"{self.recalibrated} on a corrected mass axis")
        if self.kept:
            said.append(f"{len(self.kept)} kept as they were: "
                        + "; ".join(f"{name} ({reason})"
                                    for name, reason in self.kept))
        if self.backup:
            said.append(f"the file as it was is {os.path.basename(self.backup)}")
        return "; ".join(said) + "."


#: what a rewritten record writes for itself, so the old record's own copy of
#: it is not carried over beside it. Matched the way `field_value` matches.
_REWRITTEN_FIELDS = frozenset(
    {"comment", "activation", "collisionenergy", "ce"}
    | set(_ACQUIRED_KEYS) | set(_BASE_INTENSITY_KEYS))


def rewrite_records(path: str | os.PathLike, folders=(), reader=None,
                    corrections=None) -> Rewrite:
    """
    Every record whose acquisition is still on disk, read again and written
    over with what this version of the writer knows.

    A library of one's own is written a record at a time over months, and a
    record written in March carries what March's writer wrote: no `Acquired`,
    no `Base_peak_intensity`, no formula, a precursor typed by hand. The
    files are usually still there, so the record does not have to stay that
    way. Each is looked up by the acquisition its comment names, averaged
    over the same scans, centroided with the same floor and ceiling, and
    written back in place.

    `folders` are the directories to look a file name up in — a comment names
    a file, never a path — with the library's own folder beside them.
    `reader` opens one (`raw.open_raw` by default, so a test can hand over a
    reader of its own). `corrections` maps a file name to the mass correction
    in force for it, which is how a recalibrated batch's records come out on
    the corrected axis; the comment then says so, because a mass axis that
    has been moved and does not admit it is worse than one that is wrong.

    A record whose file is gone is **kept exactly as it is** and listed with
    the reason: the measurement it holds is the last copy of that spectrum,
    and losing it to a tidy-up would be the one unrecoverable outcome here.
    The file as it was is copied to `<name>.msp.bak` before anything is
    written over it.
    """
    import shutil
    import time

    started = time.perf_counter()
    path = str(path)
    result = Rewrite(path=path)
    try:
        entries = list(load_library(path).entries)
    except OSError as exc:
        result.kept.append((os.path.basename(path), str(exc)))
        return result
    if reader is None:
        from .raw import open_raw

        reader = open_raw
    corrections = {str(k).lower(): v
                   for k, v in dict(corrections or {}).items()}
    places = [os.path.dirname(os.path.abspath(path))]
    places += [str(f) for f in folders if f]
    opened: dict = {}
    out: list[LibraryEntry] = []
    try:
        for entry in entries:
            provenance = provenance_of(entry)
            if not provenance.keyed:
                out.append(entry)
                result.kept.append((entry.name,
                                    "its comment names no acquisition"))
                continue
            found = _locate(provenance.file, places)
            if not found:
                out.append(entry)
                result.kept.append((entry.name,
                                    f"{provenance.file} is not on disk"))
                continue
            try:
                handle = opened.get(found)
                if handle is None:
                    handle = opened[found] = reader(found)
                fresh, corrected = _reread(
                    entry, provenance, handle,
                    corrections.get(provenance.file.lower()))
            except Exception as exc:              # any reader, any reason
                out.append(entry)
                result.kept.append((entry.name, f"{provenance.file}: {exc}"))
                continue
            out.append(fresh)
            result.rewritten.append(fresh.name)
            result.recalibrated += 1 if corrected else 0
    finally:
        for handle in opened.values():
            try:
                handle.close()
            except Exception:
                pass
    if result.rewritten:
        result.backup = path + ".bak"
        shutil.copy2(path, result.backup)
        write_msp(out, path)
    result.seconds = time.perf_counter() - started
    return result


def _locate(name: str, folders) -> str:
    """The first of those folders holding a file of that name, or ""."""
    for folder in dict.fromkeys(folders):
        candidate = os.path.join(str(folder), name)
        if os.path.exists(candidate):
            return candidate
    return ""


def _reread(entry: LibraryEntry, provenance: Provenance, handle,
            correction=None) -> tuple[LibraryEntry, bool]:
    """One record made again from the file its comment names."""
    sample = _sample_named(handle, provenance.sample)
    channel = _channel_named(sample, provenance.channel)
    if channel is None:
        raise LookupError(f"{provenance.channel or 'the channel'} is not in it")
    window = _window(channel, provenance.rt_range)
    mz, intensity = channel.spectrum_rt_range(*window)
    mz = np.asarray(mz, dtype=float)
    note = ""
    if correction is not None and mz.size:
        moved = float(np.median(np.asarray(correction.ppm_at(mz), dtype=float)))
        mz = np.asarray(correction.apply(mz), dtype=float)
        note = f"recalibrated {moved:+.1f} ppm"
    peaks = own_peaks(mz, intensity)
    if not peaks:
        raise ValueError("nothing above the floor in it now")
    info = getattr(channel, "info", None)
    first, last = channel.scans_in_range(*window)
    fresh = entry_from_spectrum(
        entry.name, [p[0] for p in peaks], [p[1] for p in peaks],
        # the record's two accounts of its own precursor, made to agree:
        # where the formula and the adduct give a mass, that is the mass
        precursor=(round(entry.exact_precursor, EXACT_DECIMALS)
                   if entry.exact_precursor is not None else entry.precursor),
        precursor_type=entry.precursor_type, formula=entry.formula,
        collision_energy=(getattr(info, "collision_energy", None)
                          if info is not None else None),
        comment=provenance_comment(
            file=provenance.file, sample=provenance.sample,
            channel=(_flat_channel(info) or provenance.channel),
            scans=int(last - first + 1), rt_range=window,
            added=provenance.added, note=note),
        acquired=(str(getattr(sample, "acquisition_time", "") or "")
                  or acquired_of(entry)))
    if not fresh.fields.get("Collision_energy"):
        energy = field_value(entry, {"collisionenergy", "ce"})
        if energy:
            fresh.fields["Collision_energy"] = energy
    _set_activation(fresh, _activation_in(entry.name, provenance.sample,
                                          provenance.channel))
    # whatever else the old record carried and this writer does not write —
    # somebody's instrument, a note of their own — stays with it
    for key, value in entry.fields.items():
        flat = str(key).strip().lower().replace("_", "").replace(" ", "")
        if flat not in _REWRITTEN_FIELDS and key not in fresh.fields:
            fresh.fields[key] = value
    return fresh, bool(note)


def _flat_channel(info) -> str:
    return str(getattr(info, "short_label", "") or "") if info is not None else ""


def _sample_named(handle, name: str):
    """
    The sample of that name inside the file, or the first one.

    An infusion is one sample in one file, and the name a record carries is
    the one the samples table shortened for the screen — so a name that does
    not match is an ordinary outcome and the first sample is the answer,
    rather than a failure to rewrite.
    """
    names = [str(n) for n in (getattr(handle, "sample_names", None) or [])]
    want = _flat_label(name)
    for index, written in enumerate(names):
        if want and _flat_label(written) == want:
            return handle.sample(index)
    return handle.sample(0)


def _channel_named(sample, name: str):
    """
    The channel whose label the comment names, or None.

    Matched against both the short label and the whole one, and by prefix
    either way round: a comment written by an older version carries whichever
    of the two that version put in it, and the two agree on everything up to
    the mass range.
    """
    channels = list(getattr(sample, "channels", None) or [])
    if not channels:
        return None
    want = _flat_label(name)
    if not want:
        return channels[0] if len(channels) == 1 else None
    for channel in channels:
        info = getattr(channel, "info", None)
        for label in (getattr(info, "short_label", ""),
                      getattr(info, "label", "")):
            flat = _flat_label(label)
            if flat and (flat == want or flat.startswith(want)
                         or want.startswith(flat)):
                return channel
    return None


def _window(channel, wanted) -> tuple[float, float]:
    """
    The time range to average again, snapped to the scans that are there.

    A comment writes its times to four decimals, and a bound rounded a
    ten-thousandth of a minute past the first scan drops that scan from the
    average — one scan out of a few hundred, silently, in a record that
    claims to be the same measurement. Taking the nearest scan time to each
    bound gives back exactly the range that was written.
    """
    times = np.asarray(getattr(channel, "rt", ()), dtype=float)
    if times.size == 0:
        raise ValueError("its channel has no scans")
    if wanted is None:
        return float(times[0]), float(times[-1])
    low = float(times[int(np.argmin(np.abs(times - float(wanted[0]))))])
    high = float(times[int(np.argmin(np.abs(times - float(wanted[1]))))])
    return min(low, high), max(low, high)
