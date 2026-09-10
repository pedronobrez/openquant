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
                        comment: str = "",
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
