"""
Local LIPID MAPS lookup.

The LIPID MAPS Structure Database is redistributed under CC BY 4.0 as a single
SDF. This module keeps a compact local index of it, so annotation works with no
network and answers a whole component table in microseconds — a batch of eighty
precursors would otherwise be eighty HTTP round trips against a public service.

Only the annotation fields are kept. The structures themselves are most of the
file and are not needed to match a mass.

What a mass search returns is a *species*, never a compound: forty-six
structures in the database share the formula of a DiHOME, eleven of them named
DiHOME, and no exact mass separates isomers. Treat every result as a shortlist
for a person to confirm.

This indexes LMSD, the curated structure database — every record has a name and
an LM_ID. LIPID MAPS also publishes COMP_DB, a computationally enumerated set of
theoretical species that covers more masses but carries no compound names, and
that is what the public `moverz/LIPIDS` endpoint searches. A mass with no hit
here may still match a theoretical species there; for naming components, the
curated database is the one worth having.

Six hundred of the fifty thousand records carry no exact mass in the published
file and are skipped: without a mass they cannot be matched, which is this
module's whole purpose.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import urlopen

import numpy as np

from .bootstrap import CACHE_DIR, urlopen as safe_urlopen
from .chemistry import ADDUCTS, ADDUCTS_BY_NAME, NEUTRAL, Adduct
from .structure import Structure, parse_molblock

#: elements a lipid from a biological sample is built from. LMSD also holds
#: organoarsenic and fluorinated structures, which are valid entries and absurd
#: candidates for a plasma oxylipin panel; without this filter a rounded
#: precursor mass happily matches one.
BIOLOGICAL_ELEMENTS = frozenset("C H N O P S Se".split())

_ELEMENT = re.compile(r"([A-Z][a-z]?)\d*")

#: the published SDF, about 21 MB compressed
DATABASE_URL = "https://www.lipidmaps.org/files/?file=LMSD&ext=sdf.zip"
INDEX_PATH = CACHE_DIR / "lipidmaps" / "lmsd-index.json.gz"
#: where it lived before the software was renamed. A 21 MB download should not
#: have to happen twice because the cache directory changed name.
LEGACY_INDEX_PATH = Path.home() / ".openpeakview" / "lipidmaps" / "lmsd-index.json.gz"
INDEX_VERSION = 2

#: SDF tags kept in the index, mapped to the field they fill
_TAGS = {
    "LM_ID": "lm_id",
    "NAME": "name",
    "SYSTEMATIC_NAME": "systematic_name",
    "ABBREVIATION": "abbrev",
    "FORMULA": "formula",
    "EXACT_MASS": "exact_mass",
    "CATEGORY": "category",
    "MAIN_CLASS": "main_class",
    "SUB_CLASS": "sub_class",
}


@dataclass(frozen=True)
class LipidRecord:
    """One structure in the database, stripped to its annotation."""

    lm_id: str
    name: str
    abbrev: str
    formula: str
    exact_mass: float
    category: str = ""
    main_class: str = ""
    sub_class: str = ""
    systematic_name: str = ""
    #: the connection table in its compact form, or None for a record whose
    #: structure the file did not carry
    structure: dict | None = None

    def molecule(self) -> Structure | None:
        """The structure, rebuilt from the index."""
        if not self.structure:
            return None
        return Structure.from_compact(self.structure)

    @property
    def species(self) -> str:
        """The shorthand species name, falling back to the formula."""
        return self.abbrev or self.formula

    @property
    def elements(self) -> frozenset[str]:
        return frozenset(_ELEMENT.findall(self.formula))


@dataclass(frozen=True)
class LipidMatch:
    """A record matched against a measured mass."""

    record: LipidRecord
    measured: float
    theoretical: float
    adduct: str = ""

    @property
    def error_mda(self) -> float:
        return (self.measured - self.theoretical) * 1000.0

    @property
    def error_ppm(self) -> float:
        if not self.theoretical:
            return 0.0
        return (self.measured - self.theoretical) / self.theoretical * 1e6


@dataclass(frozen=True)
class IonForm:
    """
    A lipid seen through one ionisation form: the reverse of a mass search.

    The website lists these on every molecule page. They are arithmetic on the
    exact mass, so they are computed here rather than fetched: no network, and
    the answer carries the full precision of the formula instead of the four
    decimals a page prints.
    """

    record: LipidRecord
    adduct: str
    mz: float
    charge: int

    @property
    def species(self) -> str:
        return self.record.species

    @property
    def formula(self) -> str:
        return self.record.formula

    @property
    def name(self) -> str:
        return self.record.name or self.record.abbrev


@dataclass
class SpeciesMatch:
    """
    Every structure that shares one species and formula.

    Matches are grouped this way because that is the honest unit of a mass
    search: `FA 18:1;O2` is a family of isomers, and showing eleven DiHOMEs as
    eleven separate answers would imply a precision the measurement does not
    have.
    """

    species: str
    formula: str
    theoretical: float
    measured: float
    adduct: str
    records: list[LipidRecord]

    @property
    def error_mda(self) -> float:
        return (self.measured - self.theoretical) * 1000.0

    @property
    def error_ppm(self) -> float:
        if not self.theoretical:
            return 0.0
        return (self.measured - self.theoretical) / self.theoretical * 1e6

    @property
    def category(self) -> str:
        return self.records[0].category if self.records else ""

    @property
    def main_class(self) -> str:
        return self.records[0].main_class if self.records else ""

    @property
    def names(self) -> list[str]:
        return [r.name for r in self.records if r.name]


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def parse_sdf(stream) -> list[LipidRecord]:
    """
    Read the annotation tags and the connection table out of an SDF.

    Works line by line over a text stream so the 280 MB file never has to be
    held in memory or written to disk; only one record is in hand at a time.
    """
    records: list[LipidRecord] = []
    fields: dict[str, str] = {}
    tag: str | None = None
    value: list[str] = []
    block: list[str] | None = []

    def close_tag():
        nonlocal tag, value
        if tag is not None:
            text = " ".join(part.strip() for part in value).strip()
            if text:
                fields[_TAGS[tag]] = text
        tag, value = None, []

    for raw in stream:
        line = raw.rstrip("\n").rstrip("\r")
        if block is not None:
            block.append(line)
            if line.startswith("M  END"):
                fields["molblock"] = "\n".join(block)
                block = None
            continue
        if line.startswith("> <"):
            close_tag()
            name = line[3:].split(">", 1)[0]
            tag = name if name in _TAGS else None
            continue
        if line == "$$$$":
            close_tag()
            record = _record_from(fields)
            if record is not None:
                records.append(record)
            fields = {}
            block = []
            continue
        if tag is not None:
            if line == "":
                close_tag()
            else:
                value.append(line)
    close_tag()
    record = _record_from(fields)
    if record is not None:
        records.append(record)
    return records


def _record_from(fields: dict) -> LipidRecord | None:
    lm_id = fields.get("lm_id")
    if not lm_id:
        return None
    try:
        mass = float(fields.get("exact_mass", ""))
    except ValueError:
        return None
    return LipidRecord(
        lm_id=lm_id,
        name=fields.get("name", ""),
        abbrev=fields.get("abbrev", ""),
        formula=fields.get("formula", ""),
        exact_mass=mass,
        category=fields.get("category", ""),
        main_class=fields.get("main_class", ""),
        sub_class=fields.get("sub_class", ""),
        systematic_name=fields.get("systematic_name", ""),
        structure=_compact_structure(fields),
    )


def _compact_structure(fields: dict) -> dict | None:
    """The connection table, small enough to keep for every record."""
    block = fields.get("molblock")
    if not block:
        return None
    molecule = parse_molblock(block, fields.get("formula", ""))
    return molecule.to_compact() if molecule is not None else None


# --------------------------------------------------------------------------- #
# the database
# --------------------------------------------------------------------------- #
class LipidDatabase:
    """A searchable index over the records."""

    def __init__(self, records: list[LipidRecord]):
        self.records = sorted(records, key=lambda r: r.exact_mass)
        self._masses = np.array([r.exact_mass for r in self.records],
                                dtype=np.float64)
        self._by_formula: dict[str, list[LipidRecord]] = {}
        for record in self.records:
            self._by_formula.setdefault(record.formula, []).append(record)

    def __len__(self) -> int:
        return len(self.records)

    # -- searching ------------------------------------------------------------- #
    def search_mass(self, mass: float, tolerance: float = 0.01,
                    unit: str = "Da",
                    elements: frozenset[str] | None = BIOLOGICAL_ELEMENTS,
                    ) -> list[LipidMatch]:
        """
        Records whose neutral monoisotopic mass matches, nearest first.

        `elements` restricts the answer to structures built only from those
        atoms; pass None to search everything.
        """
        if not self.records or mass <= 0:
            return []
        half = mass * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        lo = int(np.searchsorted(self._masses, mass - half, side="left"))
        hi = int(np.searchsorted(self._masses, mass + half, side="right"))
        matches = []
        for i in range(lo, hi):
            record = self.records[i]
            if elements is not None and not record.elements <= elements:
                continue
            matches.append(LipidMatch(record=record, measured=mass,
                                      theoretical=record.exact_mass))
        matches.sort(key=lambda m: abs(m.error_mda))
        return matches

    def search_mz(self, mz: float, adduct: str | Adduct = "[M-H]-",
                  tolerance: float = 0.01, unit: str = "Da",
                  elements: frozenset[str] | None = BIOLOGICAL_ELEMENTS,
                  ) -> list[LipidMatch]:
        """
        Records matching a measured m/z through an ionisation form.

        The tolerance is applied on the m/z, where it was measured, not on the
        neutral mass — for a multiply charged adduct the two differ by the
        charge.
        """
        form = ADDUCTS_BY_NAME.get(adduct) if isinstance(adduct, str) else adduct
        if form is None:
            raise KeyError(f"unknown adduct: {adduct}")
        half = mz * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        charge = abs(form.charge) or 1
        neutral = form.neutral_mass(mz)
        matches = self.search_mass(neutral, half * charge, "Da", elements)
        return [
            LipidMatch(record=m.record, measured=mz,
                       theoretical=form.mz(m.record.exact_mass),
                       adduct=form.name)
            for m in matches
        ]

    def search_formula(self, formula: str) -> list[LipidRecord]:
        return list(self._by_formula.get(formula.strip(), []))

    def search_name(self, text: str, limit: int = 50) -> list[LipidRecord]:
        """Case-insensitive substring search over names and abbreviations."""
        return self.find_by_name(text, limit)

    def find_by_name(self, text: str, limit: int = 25) -> list[LipidRecord]:
        """
        Records whose name, abbreviation or LM_ID matches, best first.

        An exact name outranks one that merely contains it: searching
        `12,13-DiHOME` should not answer `12,13-DiHOME(9)` first because it
        happens to sit earlier in the file.
        """
        needle = _squash(text)
        if not needle:
            return []
        scored: list[tuple[int, int, int, LipidRecord]] = []
        for index, record in enumerate(self.records):
            best = None
            for field in (record.name, record.abbrev, record.lm_id):
                if not field:
                    continue
                squashed = _squash(field)
                if squashed == needle:
                    rank = 0
                elif squashed.startswith(needle):
                    rank = 1
                elif needle in squashed:
                    rank = 2
                else:
                    continue
                best = rank if best is None else min(best, rank)
            if best is not None:
                # shorter names are the more specific ones at the same rank
                scored.append((best, len(record.name or record.abbrev), index,
                               record))
        scored.sort()
        return [record for _rank, _length, _index, record in scored[:limit]]

    def precursor(self, name: str, adduct: str | Adduct = "[M+H]+",
                  ) -> IonForm | None:
        """
        The m/z of the named lipid through one adduct — a mass search run
        backwards, for when the compound is known and the channel is not.
        """
        found = self.find_by_name(name, limit=1)
        return ion_form(found[0], adduct) if found else None

    def by_id(self, lm_id: str) -> LipidRecord | None:
        target = lm_id.strip().upper()
        for record in self.records:
            if record.lm_id == target:
                return record
        return None

    # -- persistence ------------------------------------------------------------ #
    def save(self, path: str | os.PathLike = INDEX_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INDEX_VERSION,
            "source": DATABASE_URL,
            "count": len(self.records),
            "records": [asdict(r) for r in self.records],
        }
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        return path

    @classmethod
    def load(cls, path: str | os.PathLike = INDEX_PATH) -> "LipidDatabase":
        with gzip.open(Path(path), "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        known = LipidRecord.__dataclass_fields__
        return cls([LipidRecord(**{k: v for k, v in row.items() if k in known})
                    for row in payload.get("records", [])])


def _squash(text: str) -> str:
    """
    Compare names without tripping over spacing.

    LIPID MAPS writes `SM 30:1;O2` where a method writes `SM(d18:1/12:0)`;
    neither should fail to match itself over a stray space.
    """
    return "".join(text.split()).casefold()


def ion_form(record: LipidRecord, adduct: str | Adduct) -> IonForm | None:
    """The m/z a record would be seen at through one adduct."""
    form = ADDUCTS_BY_NAME.get(adduct) if isinstance(adduct, str) else adduct
    if form is None or not record.exact_mass:
        return None
    return IonForm(record=record, adduct=form.name,
                   mz=form.mz(record.exact_mass), charge=form.charge)


def ion_forms(record: LipidRecord,
              adducts: list[str] | None = None) -> list[IonForm]:
    """
    Every adduct's m/z for one record, positive first then negative.

    The neutral entry is left out: it exists so a neutral mass can be searched
    as if it were an ion, and it is not one. The neutral mass belongs to the
    lipid, and is on the record.
    """
    names = (adducts if adducts is not None
             else [a.name for a in ADDUCTS if a.name != NEUTRAL])
    forms = [ion_form(record, name) for name in names]
    found = [f for f in forms if f is not None]
    found.sort(key=lambda f: (-f.charge, f.mz))
    return found


def mass_precision(value: float, text: str | None = None) -> float:
    """
    How well a written mass is actually known, as a half-width in Da.

    A precursor recorded as `351.20` is known to ±0.005 Da — about 14 ppm at
    that mass. Searching it to 5 ppm claims a precision the number does not
    carry, and the window then fills with whatever happens to sit nearby.
    """
    text = text if text is not None else repr(float(value))
    if "." not in text:
        return 0.5
    # trailing zeros in a written mass are significant: 351.20 says two
    # decimals were measured, and stripping them would overstate the window
    decimals = len(text.split(".")[1])
    return 0.5 * 10 ** (-decimals) if decimals else 0.5


def group_by_species(matches: list[LipidMatch]) -> list[SpeciesMatch]:
    """Collapse structure matches into the species they belong to."""
    buckets: dict[tuple[str, str], SpeciesMatch] = {}
    order: list[tuple[str, str]] = []
    for match in matches:
        key = (match.record.species, match.record.formula)
        if key not in buckets:
            buckets[key] = SpeciesMatch(
                species=match.record.species, formula=match.record.formula,
                theoretical=match.theoretical, measured=match.measured,
                adduct=match.adduct, records=[],
            )
            order.append(key)
        buckets[key].records.append(match.record)
    groups = [buckets[key] for key in order]
    groups.sort(key=lambda g: (abs(g.error_mda), -len(g.records)))
    return groups


# --------------------------------------------------------------------------- #
# installation
# --------------------------------------------------------------------------- #
def adopt_legacy_index(path: str | os.PathLike = INDEX_PATH) -> bool:
    """
    Move an index left behind under the old cache directory.

    Returns True when one was adopted. Falling back to reading it in place
    would work too, but moving it means the answer stops depending on a
    directory named after software that no longer exists.
    """
    target = Path(path)
    if target.exists() or not LEGACY_INDEX_PATH.exists():
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        LEGACY_INDEX_PATH.replace(target)
    except OSError:
        return False
    return True


def is_installed(path: str | os.PathLike = INDEX_PATH) -> bool:
    if Path(path).exists():
        return True
    return adopt_legacy_index(path)


def build_index(zip_bytes: bytes,
                path: str | os.PathLike = INDEX_PATH) -> LipidDatabase:
    """Parse the downloaded archive and write the index."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".sdf")]
        if not names:
            raise ValueError("the archive contains no .sdf file")
        with archive.open(names[0]) as raw:
            stream = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            records = parse_sdf(stream)
    if not records:
        raise ValueError("no records found in the database")
    database = LipidDatabase(records)
    database.save(path)
    return database


def install(path: str | os.PathLike = INDEX_PATH, progress=None) -> LipidDatabase:
    """
    Download the database and build the local index.

    `progress` is called with a short status line, so a caller can report what
    is happening during a download of about twenty megabytes.
    """
    if progress:
        progress("Downloading the LIPID MAPS database…")
    try:
        payload = safe_urlopen(DATABASE_URL).read()
    except Exception:
        with urlopen(DATABASE_URL) as response:   # noqa: S310 - fixed URL
            payload = response.read()
    if progress:
        progress("Building the local index…")
    database = build_index(payload, path)
    if progress:
        progress(f"{len(database):,} lipid structures indexed.")
    return database


_CACHED: LipidDatabase | None = None


def database(path: str | os.PathLike = INDEX_PATH) -> LipidDatabase | None:
    """The installed database, loaded once, or None when it is not installed."""
    global _CACHED
    if _CACHED is None and is_installed(path):
        _CACHED = LipidDatabase.load(path)
    return _CACHED


def forget() -> None:
    """Drop the cached database; the next call reloads it from disk."""
    global _CACHED
    _CACHED = None
