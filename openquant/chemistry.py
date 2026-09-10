"""
Elemental composition tools: formula parsing, exact masses, isotope patterns,
mass accuracy and formula finding.

Masses are monoisotopic unless stated otherwise. Abundances come from the
IUPAC 2013 representative isotopic compositions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

ELECTRON_MASS = 0.000548579909
PROTON_MASS = 1.007276466879

#: element -> [(isotope mass, natural abundance), ...], most abundant first
ISOTOPES: dict[str, list[tuple[float, float]]] = {
    "H": [(1.00782503207, 0.999885), (2.01410177785, 0.000115)],
    "D": [(2.01410177785, 1.0)],
    "C": [(12.0, 0.9893), (13.00335483778, 0.0107)],
    "N": [(14.0030740048, 0.99636), (15.0001088982, 0.00364)],
    "O": [(15.9949146196, 0.99757), (16.9991317012, 0.00038), (17.9991596129, 0.00205)],
    "F": [(18.99840322, 1.0)],
    "Na": [(22.9897692809, 1.0)],
    "Si": [(27.9769265325, 0.92223), (28.976494700, 0.04685), (29.973770171, 0.03092)],
    "P": [(30.97376163, 1.0)],
    "S": [(31.97207100, 0.9499), (32.97145876, 0.0075), (33.96786690, 0.0425),
          (35.96708076, 0.0001)],
    "Cl": [(34.96885268, 0.7576), (36.96590259, 0.2424)],
    "K": [(38.96370668, 0.932581), (39.96399848, 0.000117), (40.96182576, 0.067302)],
    "Br": [(78.9183371, 0.5069), (80.9162906, 0.4931)],
    "I": [(126.904473, 1.0)],
    "Se": [(79.9165213, 0.4961), (77.9173091, 0.2377), (81.9166994, 0.0873),
           (76.919914, 0.0763), (75.9192134, 0.0937), (73.9224764, 0.0089)],
}

#: valence used for the ring-plus-double-bond equivalent
VALENCE: dict[str, int] = {
    "H": 1, "D": 1, "F": 1, "Cl": 1, "Br": 1, "I": 1, "Na": 1, "K": 1,
    "O": 2, "S": 2, "Se": 2,
    "N": 3, "P": 3,
    "C": 4, "Si": 4,
}

# An isotope written as [13C] or [2H]; D is accepted as shorthand for [2H].
_TOKEN = re.compile(r"(\[\d+[A-Z][a-z]?\]|[A-Z][a-z]?)(\d*)")
_BRACKET = re.compile(r"\[(\d+)([A-Z][a-z]?)\]")


class FormulaError(ValueError):
    """Raised for a formula that cannot be parsed or uses unknown elements."""


def _resolve_isotope(token: str) -> str:
    """Turn `[13C]` into a key of ISOTOPES, adding it on first use."""
    match = _BRACKET.fullmatch(token)
    if match is None:
        return token
    nucleons, element = int(match.group(1)), match.group(2)
    if element not in ISOTOPES:
        raise FormulaError(f"unknown element: {element}")
    for mass, _abundance in ISOTOPES[element]:
        if round(mass) == nucleons:
            ISOTOPES.setdefault(token, [(mass, 1.0)])
            VALENCE.setdefault(token, VALENCE.get(element, 0))
            return token
    raise FormulaError(f"{element} has no isotope with mass number {nucleons}")


def parse_formula(formula: str) -> dict[str, int]:
    """
    Parse a molecular formula into element counts.

    Handles nested groups and multipliers, `C18H32O3`, `Ca(NO3)2`, and single
    isotopes written in brackets: `[13C]` or `D` for deuterium. Counts of zero
    are dropped.
    """
    text = formula.strip().replace(" ", "")
    if not text:
        return {}
    counts, stack = {}, []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "(":
            stack.append(counts)
            counts = {}
            index += 1
            continue
        if char == ")":
            if not stack:
                raise FormulaError("unbalanced parentheses")
            index += 1
            digits = ""
            while index < len(text) and text[index].isdigit():
                digits += text[index]
                index += 1
            multiplier = int(digits) if digits else 1
            inner, counts = counts, stack.pop()
            for element, number in inner.items():
                counts[element] = counts.get(element, 0) + number * multiplier
            continue
        match = _TOKEN.match(text, index)
        if match is None:
            raise FormulaError(f"cannot read {formula!r} at position {index}")
        token, digits = match.group(1), match.group(2)
        element = _resolve_isotope(token)
        if element not in ISOTOPES:
            raise FormulaError(f"unknown element: {element}")
        counts[element] = counts.get(element, 0) + (int(digits) if digits else 1)
        index = match.end()
    if stack:
        raise FormulaError("unbalanced parentheses")
    return {element: n for element, n in counts.items() if n}


def format_formula(counts: dict[str, int]) -> str:
    """Render element counts in Hill order (C, H, then alphabetical)."""
    remaining = dict(counts)
    parts = []
    for element in ("C", "H"):
        if remaining.pop(element, 0):
            n = counts[element]
            parts.append(element if n == 1 else f"{element}{n}")
    for element in sorted(remaining):
        n = remaining[element]
        if n:
            parts.append(element if n == 1 else f"{element}{n}")
    return "".join(parts)


def monoisotopic_mass(counts: dict[str, int]) -> float:
    """Mass built from the most abundant isotope of each element."""
    return sum(ISOTOPES[element][0][0] * n for element, n in counts.items())


def average_mass(counts: dict[str, int]) -> float:
    """Mass weighted by natural abundance, as used for large molecules."""
    total = 0.0
    for element, n in counts.items():
        isotopes = ISOTOPES[element]
        weight = sum(abundance for _mass, abundance in isotopes) or 1.0
        total += n * sum(mass * abundance for mass, abundance in isotopes) / weight
    return total


def rdbe(counts: dict[str, int]) -> float:
    """
    Rings plus double bonds. Half-integer values mean an odd-electron species,
    which for an even-electron ion signals an impossible formula.
    """
    total = 2.0
    for element, n in counts.items():
        total += n * (VALENCE.get(element, 2) - 2)
    return total / 2.0


# --------------------------------------------------------------------------- #
# lipid shorthand -> formula
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class LipidClass:
    """
    How a class's formula is built from its chains.

    Every lipid in the shorthand is a head group plus one, two or three
    chains, and the arithmetic is the same for all of them: the chains
    contribute their carbons, and every double bond takes two hydrogens
    away. So a class needs only what its head group adds —

        C = chain carbons + `carbons`
        H = 2 x chain carbons - 2 x double bonds + `hydrogens`

    — and the fixed atoms of that head group. A hydroxyl replaces a hydrogen
    with an OH, so it moves the oxygen count and leaves C and H alone, which
    is why the sphingoid base's hydroxyls are counted apart from `atoms`:
    `d` (two), `t` (three) and `m` (one) change the oxygens and nothing else.
    """

    name: str
    #: how many chains the shorthand names — 1 for a lyso species or a
    #: sphingoid base, 2 for a diacyl or a ceramide, 3 for a triacylglycerol
    chains: int
    #: carbons the head group adds
    carbons: int = 0
    #: the hydrogen offset above
    hydrogens: int = 0
    #: everything else the head group carries, its oxygens included
    atoms: dict[str, int] = field(default_factory=dict)
    #: whether the first chain is a sphingoid base, whose hydroxyls are
    #: written as the `d`/`t`/`m` prefix and default to two
    sphingoid: bool = False


#: hydroxyls each sphingoid base prefix stands for
_BASE_HYDROXYLS = {"m": 1, "d": 2, "t": 3}
DEFAULT_BASE_HYDROXYLS = 2

#: the classes the shorthand is understood for. Every one was checked against
#: a published exact mass before it was written down.
LIPID_CLASSES: dict[str, LipidClass] = {
    c.name: c for c in [
        LipidClass("FA", 1, 0, 0, {"O": 2}),
        LipidClass("MG", 1, 3, 6, {"O": 4}),
        LipidClass("DG", 2, 3, 4, {"O": 5}),
        LipidClass("TG", 3, 3, 2, {"O": 6}),
        LipidClass("CE", 1, 27, 44, {"O": 2}),
        LipidClass("PA", 2, 3, 5, {"O": 8, "P": 1}),
        LipidClass("PC", 2, 8, 16, {"N": 1, "O": 8, "P": 1}),
        LipidClass("PE", 2, 5, 10, {"N": 1, "O": 8, "P": 1}),
        LipidClass("PG", 2, 6, 11, {"O": 10, "P": 1}),
        LipidClass("PI", 2, 9, 15, {"O": 13, "P": 1}),
        LipidClass("PS", 2, 6, 10, {"N": 1, "O": 10, "P": 1}),
        LipidClass("LPA", 1, 3, 7, {"O": 7, "P": 1}),
        LipidClass("LPC", 1, 8, 18, {"N": 1, "O": 7, "P": 1}),
        LipidClass("LPE", 1, 5, 12, {"N": 1, "O": 7, "P": 1}),
        LipidClass("LPG", 1, 6, 13, {"O": 9, "P": 1}),
        LipidClass("LPI", 1, 9, 17, {"O": 12, "P": 1}),
        LipidClass("LPS", 1, 6, 12, {"N": 1, "O": 9, "P": 1}),
        LipidClass("Cer", 2, 0, 1, {"N": 1, "O": 1}, sphingoid=True),
        LipidClass("SM", 2, 5, 13, {"N": 2, "O": 4, "P": 1}, sphingoid=True),
        LipidClass("HexCer", 2, 6, 11, {"N": 1, "O": 6}, sphingoid=True),
        LipidClass("Hex2Cer", 2, 12, 21, {"N": 1, "O": 11}, sphingoid=True),
        LipidClass("CerP", 2, 0, 2, {"N": 1, "O": 4, "P": 1}, sphingoid=True),
        LipidClass("SPB", 1, 0, 3, {"N": 1}, sphingoid=True),
        LipidClass("SPBP", 1, 0, 4, {"N": 1, "O": 3, "P": 1}, sphingoid=True),
    ]
}

#: what a name may call a class, and the double bonds that class's own base
#: carries when the number does not say. `Sphingosine C17:0` is the d17:1
#: base and `Sphinganine C17:0` the d17:0 one: the trailing `:0` counts the
#: carbons of a chain that is the base itself, and sphingosine's double bond
#: is in the word rather than in the number. The written precursor is what
#: decides whether that reading was right.
LIPID_ALIASES: dict[str, tuple[str, int | None]] = {
    "fa": ("FA", None), "fattyacid": ("FA", None),
    "mg": ("MG", None), "mag": ("MG", None),
    "dg": ("DG", None), "dag": ("DG", None),
    "tg": ("TG", None), "tag": ("TG", None),
    "ce": ("CE", None), "cholesterylester": ("CE", None),
    "pa": ("PA", None), "pc": ("PC", None), "pe": ("PE", None),
    "pg": ("PG", None), "pi": ("PI", None), "ps": ("PS", None),
    "lpa": ("LPA", None), "lpc": ("LPC", None), "lpe": ("LPE", None),
    "lpg": ("LPG", None), "lpi": ("LPI", None), "lps": ("LPS", None),
    "cer": ("Cer", None), "ceramide": ("Cer", None),
    "dhcer": ("Cer", None), "dihydroceramide": ("Cer", None),
    "sm": ("SM", None), "sphingomyelin": ("SM", None),
    "hexcer": ("HexCer", None), "glccer": ("HexCer", None),
    "galcer": ("HexCer", None),
    "glucosylceramide": ("HexCer", None),
    "galactosylceramide": ("HexCer", None),
    "glucosyl ceramide": ("HexCer", None),
    "galactosyl ceramide": ("HexCer", None),
    "galact ceramide": ("HexCer", None),
    "hex2cer": ("Hex2Cer", None), "laccer": ("Hex2Cer", None),
    "lactosylceramide": ("Hex2Cer", None),
    "lactosyl ceramide": ("Hex2Cer", None),
    "cerp": ("CerP", None), "cer1p": ("CerP", None),
    "ceramide-1-p": ("CerP", None), "ceramide 1 phosphate": ("CerP", None),
    "spb": ("SPB", None), "sph": ("SPB", 1),
    "sphingosine": ("SPB", 1), "sphinganine": ("SPB", 0),
    "dhsph": ("SPB", 0), "sphingoid base": ("SPB", None),
    "spbp": ("SPBP", None), "s1p": ("SPBP", 1),
    "sphingosine1p": ("SPBP", 1), "sphingosine-1-p": ("SPBP", 1),
    "sphingosine 1 phosphate": ("SPBP", 1),
    "sphinganine1p": ("SPBP", 0), "sphinganine-1-p": ("SPBP", 0),
    "sphinganine 1 phosphate": ("SPBP", 0),
    "dhs1p": ("SPBP", 0),
}

#: the base a two-chain sphingolipid is taken to have when the name writes
#: one chain only — `Cer1P (16:0)`, `C14_SM`. It is much the commonest base,
#: and the written precursor confirms the reading or it is thrown away.
DEFAULT_BASE = (18, 1)

#: a chain: `18:1`, `d18:1`, `h24:0`, and the `C` a method writes in front of
#: one — `C16:0-Ceramide` — which says nothing the number does not
_CHAIN = re.compile(r"(?<![A-Za-z0-9])([dtmhc]?)(\d{1,3}):(\d{1,2})(?![:\d])")
#: a chain written without its double bonds: the `C20` of `C20 Sphinganine`
_BARE_CHAIN = re.compile(r"(?<![A-Za-z0-9:])c?(\d{1,3})(?![:\d])")
#: unplaced deuterium: `-d4`, `d7`, `(d9)`. The digits may not be followed by
#: a colon, which is what keeps the `d18` of `d18:1` a sphingoid base rather
#: than eighteen labels.
_LABEL = re.compile(r"(?<![A-Za-z0-9])d(\d{1,2})(?![:\d])")
#: a double-bond position, `(15Z)`, which says nothing about the composition
_POSITION = re.compile(r"\(\d{1,2}[ez]\)")
#: a hydroxyl written out: `OH`, or `2OH` — where the 2 is the position it
#: sits at and not how many there are, so either is one oxygen
_HYDROXYL = re.compile(r"(?<![A-Za-z0-9])\d?oh(?![a-z])")
#: `;O2`, LIPID MAPS's own way of writing the oxygens
_OXYGENS = re.compile(r";o(\d?)")

#: sanity: a chain outside these is not a chain, it is something else that
#: happened to be written as a number
MIN_CHAIN_CARBONS = 2
MAX_CHAIN_CARBONS = 60
MAX_TOTAL_CARBONS = 100


def _find_class(text: str) -> tuple[LipidClass, int | None, int, int] | None:
    """
    The longest class name in the text, and where it sat.

    Longest wins, so `LacCer` is not read as `Cer`, `HexCer` not as `Cer`,
    and `Sphinganine1P` not as `Sphinganine` followed by a chain of one
    carbon. A match has to be delimited: a class name may end where a digit
    or a bracket begins, never in the middle of a longer word.
    """
    best: tuple[int, str, int | None, int, int] | None = None
    for alias, (class_name, base_double_bonds) in LIPID_ALIASES.items():
        start = text.find(alias)
        while start >= 0:
            end = start + len(alias)
            delimited = ((start == 0 or not text[start - 1].isalnum())
                         and (end == len(text) or not text[end].isalpha()))
            if delimited and (best is None or len(alias) > best[0]):
                best = (len(alias), class_name, base_double_bonds, start, end)
            start = text.find(alias, start + 1)
    if best is None:
        return None
    _length, class_name, base_double_bonds, start, end = best
    return LIPID_CLASSES[class_name], base_double_bonds, start, end


def formulas_from_name(name: str) -> list[str]:
    """
    Every formula a lipid shorthand name can be read as, best guess first.

    There is more than one only where the name is genuinely ambiguous: a
    two-chain sphingolipid written with a single chain is `SM 34:1` in LIPID
    MAPS's own shorthand, where the number is the whole species, and
    `C14_SM` in a method's, where it is the N-acyl and the base is left
    unsaid. Both readings are arithmetic; only the written precursor can say
    which was meant, so both are offered and the caller checks them.
    """
    return _readings(name)


def formula_from_name(name: str) -> str | None:
    """
    The elemental formula a lipid shorthand name implies, or None.

    Understands the forms a method actually carries: `SM(d18:1/12:0)`,
    `Cer(d18:1/16:0)`, `PC 34:1`, `LPC 18:0`, `TG 52:2`, `FA 18:1`, the class
    written after the chain (`C16:0-Ceramide`, `C14_SM`), a hydroxyl written
    as `h24:0`, `(2OH)` or `;O3`, a double-bond position in brackets that
    says nothing about the composition (`24:1(15Z)`), and unplaced deuterium
    as `-d4`, `d7` or `(d9)`.

    **Nothing here is a measurement.** It is what the name says, and a name
    is written by a person: a two-chain sphingolipid given one chain is taken
    to have the d18:1 base, `Sphingosine C17:0` to be the d17:1 base its own
    word names, and either reading can be wrong. So every caller in this
    package checks the answer against the precursor the method already
    carries, to the precision that precursor was written with, and throws the
    formula away when the two disagree — a wrong formula is a wrong lock mass
    for the recalibration, which is worse than no lock mass at all.

    Where a name has more than one reading — see `formulas_from_name` — this
    returns the first, which is the standard shorthand's. Returns None rather
    than guess when there is no class name, no chain, or a count outside what
    a lipid chain can be.
    """
    readings = _readings(name)
    return readings[0] if readings else None


def _readings(name: str) -> list[str]:
    text = " ".join(str(name or "").split()).lower().replace("_", " ")
    if not text:
        return []

    labels = sum(int(n) for n in _LABEL.findall(text))
    text = _LABEL.sub(" ", text)
    text = _POSITION.sub(" ", text)

    extra_oxygens = len(_HYDROXYL.findall(text))
    text = _HYDROXYL.sub(" ", text)
    written_oxygens: int | None = None
    for count in _OXYGENS.findall(text):
        written_oxygens = int(count) if count else 1
    text = _OXYGENS.sub(" ", text)

    found = _find_class(text)
    if found is None:
        return []
    lipid, base_double_bonds, start, end = found
    rest = text[:start] + " " + text[end:]

    chains = [(prefix, int(carbons), int(double_bonds))
              for prefix, carbons, double_bonds in _CHAIN.findall(rest)]
    if not chains:
        chains = [("", int(carbons), 0) for carbons in _BARE_CHAIN.findall(rest)]
    if not chains or len(chains) > lipid.chains:
        return []
    if any(not MIN_CHAIN_CARBONS <= carbons <= MAX_CHAIN_CARBONS
           for _prefix, carbons, _db in chains):
        return []

    carbons = sum(c for _prefix, c, _db in chains)
    double_bonds = sum(db for _prefix, _c, db in chains)
    extra_oxygens += sum(1 for prefix, _c, _db in chains if prefix == "h")

    base_hydroxyls = DEFAULT_BASE_HYDROXYLS if lipid.sphingoid else 0
    for prefix, _c, _db in chains:
        if prefix in _BASE_HYDROXYLS:
            base_hydroxyls = _BASE_HYDROXYLS[prefix]
            break
    if written_oxygens is not None:
        if lipid.sphingoid:
            base_hydroxyls = written_oxygens
        else:
            extra_oxygens += written_oxygens

    if len(chains) == 1 and base_double_bonds is not None and not double_bonds:
        double_bonds = base_double_bonds

    # (carbons, double bonds) per reading, the standard shorthand's first
    readings = [(carbons, double_bonds)]
    if lipid.sphingoid and len(chains) < lipid.chains:
        # the base was not written. It may have been left out because the
        # number is the whole species (`SM 34:1`) or because the method
        # names the N-acyl alone (`C14_SM`); both are offered.
        readings.append((carbons + DEFAULT_BASE[0],
                         double_bonds + DEFAULT_BASE[1]))
        if carbons < DEFAULT_BASE[0] + MIN_CHAIN_CARBONS:
            readings.pop(0)     # too few carbons to be a whole sphingolipid

    out = []
    for total_carbons, total_double_bonds in readings:
        if not MIN_CHAIN_CARBONS <= total_carbons <= MAX_TOTAL_CARBONS:
            continue
        counts = {"C": total_carbons + lipid.carbons,
                  "H": (2 * total_carbons - 2 * total_double_bonds
                        + lipid.hydrogens)}
        for element, n in lipid.atoms.items():
            counts[element] = counts.get(element, 0) + n
        counts["O"] = counts.get("O", 0) + base_hydroxyls + extra_oxygens
        if counts["H"] < labels:
            continue
        if labels:
            counts["H"] -= labels
            counts["D"] = labels
        out.append(format_formula({e: n for e, n in counts.items() if n}))
    return out


# --------------------------------------------------------------------------- #
# adducts
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Adduct:
    """An ionisation form: m/z = (M + delta) / |charge|."""

    name: str
    charge: int
    delta: float

    def mz(self, neutral_mass: float) -> float:
        return (neutral_mass + self.delta) / abs(self.charge)

    def neutral_mass(self, mz: float) -> float:
        return mz * abs(self.charge) - self.delta


#: not an ion: the entry that lets a neutral mass be searched as if it were one
NEUTRAL = "M (neutral)"

ADDUCTS: list[Adduct] = [
    Adduct("[M-H]-", -1, -PROTON_MASS),
    Adduct("[M+Cl]-", -1, 34.96885268 + ELECTRON_MASS),
    Adduct("[M+HCOO]-", -1, 44.99765396),
    Adduct("[M+CH3COO]-", -1, 59.01330402),
    Adduct("[M-2H]2-", -2, -2 * PROTON_MASS),
    Adduct("[M+H]+", 1, PROTON_MASS),
    Adduct("[M+NH4]+", 1, 18.03382555),
    Adduct("[M+Na]+", 1, 22.98922421),
    Adduct("[M+K]+", 1, 38.96315810),
    Adduct("[M+2H]2+", 2, 2 * PROTON_MASS),
    Adduct(NEUTRAL, 1, 0.0),
]

ADDUCTS_BY_NAME = {a.name: a for a in ADDUCTS}


def mass_error_ppm(measured: float, theoretical: float) -> float:
    """Relative mass error in parts per million."""
    if theoretical == 0:
        return 0.0
    return (measured - theoretical) / theoretical * 1e6


def mass_error_mda(measured: float, theoretical: float) -> float:
    """Absolute mass error in millidaltons."""
    return (measured - theoretical) * 1000.0


# --------------------------------------------------------------------------- #
# isotope patterns
# --------------------------------------------------------------------------- #
def _convolve(a: list[tuple[float, float]], b: list[tuple[float, float]],
              prune: float) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for mass_a, abundance_a in a:
        for mass_b, abundance_b in b:
            abundance = abundance_a * abundance_b
            if abundance >= prune:
                out.append((mass_a + mass_b, abundance))
    return out


def _merge(peaks: list[tuple[float, float]],
           tolerance: float) -> list[tuple[float, float]]:
    """Collapse peaks closer than `tolerance` into their weighted centroid."""
    if not peaks:
        return []
    peaks = sorted(peaks)
    merged = [list(peaks[0])]
    for mass, abundance in peaks[1:]:
        last = merged[-1]
        if mass - last[0] <= tolerance:
            total = last[1] + abundance
            last[0] = (last[0] * last[1] + mass * abundance) / total if total else mass
            last[1] = total
        else:
            merged.append([mass, abundance])
    return [(mass, abundance) for mass, abundance in merged]


def isotope_pattern(counts: dict[str, int], adduct: Adduct | None = None,
                    min_abundance: float = 0.001, max_peaks: int = 12,
                    merge_tolerance: float = 0.01) -> list[tuple[float, float]]:
    """
    Theoretical isotope pattern as (m/z, relative abundance), the base peak
    scaled to 1.0.

    `merge_tolerance` collapses the fine structure that a given resolving power
    cannot separate: at 0.01 Da the 13C and 15N peaks of the same nominal mass
    come out as one, which is what a TOF instrument actually records.
    """
    if not counts:
        return []
    prune = min_abundance * 1e-3
    distribution: list[tuple[float, float]] = [(0.0, 1.0)]
    for element, n in counts.items():
        isotopes = ISOTOPES[element]
        if len(isotopes) == 1:
            distribution = [(mass + isotopes[0][0] * n, abundance)
                            for mass, abundance in distribution]
            continue
        total = sum(abundance for _m, abundance in isotopes)
        normalised = [(mass, abundance / total) for mass, abundance in isotopes]
        power = normalised
        remaining = n
        base = normalised
        result: list[tuple[float, float]] = [(0.0, 1.0)]
        while remaining:  # binary exponentiation keeps big counts affordable
            if remaining & 1:
                result = _merge(_convolve(result, power, prune), merge_tolerance / 4)
            remaining >>= 1
            if remaining:
                power = _merge(_convolve(power, power, prune), merge_tolerance / 4)
        del base
        distribution = _merge(_convolve(distribution, result, prune),
                              merge_tolerance / 4)

    peaks = _merge(distribution, merge_tolerance)
    top = max(abundance for _m, abundance in peaks)
    peaks = [(mass, abundance / top) for mass, abundance in peaks
             if abundance / top >= min_abundance]
    peaks.sort()
    peaks = peaks[:max_peaks]
    if adduct is not None:
        peaks = [(adduct.mz(mass), abundance) for mass, abundance in peaks]
    return peaks


def match_isotope_pattern(mz: np.ndarray, intensity: np.ndarray,
                          pattern: list[tuple[float, float]],
                          tolerance: float = 0.02) -> float:
    """
    Score a theoretical pattern against a measured spectrum, from 0 to 1.

    Both patterns are put on the same scale by dividing through their
    monoisotopic peak, and the score is then built only from the satellites
    (M+1, M+2, ...):

        score = 1 - sum|measured - theoretical| / sum(theoretical)

    Scoring the satellites alone is the point. The monoisotopic peak is the one
    the search matched on, so it always agrees; including it in the sum would
    dilute every disagreement and push unrelated candidates to the same high
    number. Measured against the satellites, a formula whose M+1 is absent
    scores 0, which is the honest answer.
    """
    if mz.size == 0 or len(pattern) < 2:
        return 0.0
    measured = []
    for target, _abundance in pattern:
        window = (mz >= target - tolerance) & (mz <= target + tolerance)
        measured.append(float(intensity[window].max()) if window.any() else 0.0)
    if measured[0] <= 0:
        return 0.0

    theoretical = [abundance for _mz, abundance in pattern]
    if theoretical[0] <= 0:
        return 0.0
    measured = [value / measured[0] for value in measured]
    theoretical = [value / theoretical[0] for value in theoretical]

    weight = sum(theoretical[1:])
    if weight <= 0:
        return 0.0
    difference = sum(abs(a - b) for a, b in zip(measured[1:], theoretical[1:]))
    return max(0.0, 1.0 - difference / weight)


#: 13C - 12C, the spacing between consecutive isotope peaks of an organic ion
NEUTRON_SPACING = 1.0033548378


def has_isotope_satellites(mz: np.ndarray, intensity: np.ndarray,
                           base_mz: float, charge: int = 1,
                           tolerance: float = 0.02,
                           min_relative: float = 0.005) -> bool:
    """
    Does the spectrum actually carry an isotope pattern for this ion?

    Any organic molecule shows an M+1 of roughly 1.1% per carbon, so anything
    below `min_relative` means the satellites are not there. That is the normal
    situation in a product-ion scan, where Q1 isolates the monoisotopic
    precursor and its satellites never reach the detector — scoring candidates
    against that spectrum only measures noise.
    """
    if mz.size == 0 or base_mz <= 0:
        return False
    window = (mz >= base_mz - tolerance) & (mz <= base_mz + tolerance)
    if not window.any():
        return False
    base = float(intensity[window].max())
    if base <= 0:
        return False
    satellite_mz = base_mz + NEUTRON_SPACING / max(abs(charge), 1)
    window = (mz >= satellite_mz - tolerance) & (mz <= satellite_mz + tolerance)
    if not window.any():
        return False
    return float(intensity[window].max()) / base >= min_relative


# --------------------------------------------------------------------------- #
# formula finder
# --------------------------------------------------------------------------- #
@dataclass
class FormulaHit:
    """One candidate composition for a measured mass."""

    counts: dict[str, int]
    neutral_mass: float
    mz: float
    error_mda: float
    error_ppm: float
    rdbe: float
    isotope_score: float = 0.0
    formula: str = field(default="", init=False)

    def __post_init__(self):
        self.formula = format_formula(self.counts)


#: default search ranges, chosen for small molecules such as lipid mediators
DEFAULT_RANGES: dict[str, tuple[int, int]] = {
    "C": (0, 60),
    "H": (0, 120),
    "N": (0, 4),
    "O": (0, 12),
    "S": (0, 2),
    "P": (0, 2),
}


def passes_golden_rules(counts: dict[str, int]) -> bool:
    """
    Element-ratio checks from the "Seven Golden Rules" (Kind & Fiehn, 2007),
    which throw away compositions that are arithmetically valid but chemically
    implausible.
    """
    carbon = counts.get("C", 0)
    hydrogen = counts.get("H", 0) + counts.get("D", 0)
    if carbon == 0:
        return hydrogen == 0 or not counts
    ratios = {
        "H": (0.1, 3.1),
        "N": (0.0, 1.3),
        "O": (0.0, 1.2),
        "P": (0.0, 0.3),
        "S": (0.0, 0.8),
    }
    for element, (low, high) in ratios.items():
        n = hydrogen if element == "H" else counts.get(element, 0)
        ratio = n / carbon
        if not low <= ratio <= high:
            return False
    return True


def find_formulas(neutral_mass: float, tolerance: float, unit: str = "ppm",
                  ranges: dict[str, tuple[int, int]] | None = None,
                  rdbe_range: tuple[float, float] = (-0.5, 40.0),
                  even_electron: bool = True, golden_rules: bool = True,
                  max_results: int = 100) -> list[FormulaHit]:
    """
    All elemental compositions whose monoisotopic mass matches `neutral_mass`.

    The search walks the elements from heaviest to lightest, bounding each
    count by the mass still unassigned, so the tree stays small. `even_electron`
    keeps only integer RDBE values, which is what a closed-shell molecule has.
    """
    ranges = ranges or DEFAULT_RANGES
    elements = [e for e in ranges if ranges[e][1] > 0]
    if not elements or neutral_mass <= 0:
        return []
    for element in elements:
        if element not in ISOTOPES:
            raise FormulaError(f"unknown element: {element}")

    half_width = (neutral_mass * tolerance * 1e-6 if unit.lower() == "ppm"
                  else tolerance)
    lo, hi = neutral_mass - half_width, neutral_mass + half_width

    masses = {e: ISOTOPES[e][0][0] for e in elements}
    order = sorted(elements, key=lambda e: masses[e], reverse=True)
    hits: list[FormulaHit] = []

    def recurse(index: int, remaining_lo: float, remaining_hi: float,
                counts: dict[str, int]) -> None:
        if len(hits) >= max_results:
            return
        if index == len(order):
            if remaining_lo <= 0.0 <= remaining_hi:
                _accept(counts)
            return
        element = order[index]
        mass = masses[element]
        low, high = ranges[element]
        start = max(low, 0)
        stop = min(high, int(remaining_hi // mass))
        for n in range(start, stop + 1):
            counts[element] = n
            recurse(index + 1, remaining_lo - n * mass, remaining_hi - n * mass,
                    counts)
            if len(hits) >= max_results:
                break
        counts.pop(element, None)

    def _accept(counts: dict[str, int]) -> None:
        clean = {e: n for e, n in counts.items() if n}
        if not clean:
            return
        value = rdbe(clean)
        if not rdbe_range[0] <= value <= rdbe_range[1]:
            return
        if even_electron and abs(value - round(value)) > 1e-9:
            return
        if golden_rules and not passes_golden_rules(clean):
            return
        mass = monoisotopic_mass(clean)
        hits.append(
            FormulaHit(
                counts=clean,
                neutral_mass=mass,
                mz=mass,
                error_mda=mass_error_mda(neutral_mass, mass),
                error_ppm=mass_error_ppm(neutral_mass, mass),
                rdbe=value,
            )
        )

    recurse(0, lo, hi, {})
    hits.sort(key=lambda hit: abs(hit.error_ppm))
    return hits


def rank_by_isotope_pattern(hits: list[FormulaHit], mz: np.ndarray,
                            intensity: np.ndarray, adduct: Adduct,
                            tolerance: float = 0.02) -> list[FormulaHit]:
    """
    Score each candidate against the measured isotope pattern and re-rank.

    Exact mass alone rarely separates candidates above a few hundred daltons;
    the relative heights of the M+1 and M+2 peaks usually do.
    """
    for hit in hits:
        pattern = isotope_pattern(hit.counts, adduct, min_abundance=0.01,
                                  max_peaks=5)
        hit.mz = adduct.mz(hit.neutral_mass)
        hit.isotope_score = match_isotope_pattern(mz, intensity, pattern,
                                                  tolerance)
    hits.sort(key=lambda hit: (-hit.isotope_score, abs(hit.error_ppm)))
    return hits
