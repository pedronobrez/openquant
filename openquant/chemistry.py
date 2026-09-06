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
