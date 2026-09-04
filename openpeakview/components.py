"""
Components of a processing method — the equivalent of MultiQuant's component
table.

A component says what to extract (precursor, fragment, tolerance), where the
peak is expected (retention time and half window), and how its result is
reported (raw area, ratio to an internal standard, or a concentration read off
a calibration curve).
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field, fields

from .chemistry import ADDUCTS_BY_NAME, FormulaError, monoisotopic_mass, parse_formula

#: how a component's result is reported
RESPONSE_AREA = "area"
RESPONSE_RATIO = "ratio"
RESPONSE_CONCENTRATION = "concentration"
RESPONSES = (RESPONSE_AREA, RESPONSE_RATIO, RESPONSE_CONCENTRATION)

DEFAULT_TOLERANCE = 0.02
DEFAULT_UNIT = "Da"

# Header aliases, English and Portuguese, keyed by dataclass field name. Lists
# written by earlier versions used Portuguese headers, so both keep working.
_ALIASES = {
    "name": {"name", "compound", "component", "analyte", "nome", "composto", "analito"},
    "group": {"group", "grupo"},
    "precursor": {"precursor", "q1", "precursor_mz", "parent", "precursormz"},
    "fragment": {"fragment", "q3", "product", "fragment_mz", "productmz",
                 "fragmento", "produto"},
    "rt": {"rt", "retention_time", "rt_min", "tr", "tempo"},
    "rt_halfwidth": {"window", "rt_window", "rt_halfwidth", "half_window",
                     "janela", "meia_janela", "tolerancia_rt"},
    "tolerance": {"tolerance", "tol", "mz_tolerance", "tolerancia"},
    "unit": {"unit", "tol_unit", "unidade"},
    "formula": {"formula", "chemical_formula", "molecular_formula"},
    "adduct": {"adduct", "aduto", "ion"},
    "is_internal_standard": {"is", "is_internal_standard", "internal_standard?",
                             "istd", "is_istd", "e_padrao_interno"},
    "internal_standard": {"internal_standard", "is_name", "istd_name",
                          "padrao_interno"},
    "response": {"response", "response_type", "resposta"},
    "concentration_unit": {"concentration_unit", "conc_unit", "units",
                           "unidade_concentracao"},
}

_TRUE = {"1", "true", "yes", "y", "sim", "is", "istd", "x"}


@dataclass
class Component:
    """One target of the processing method."""

    name: str
    precursor: float = 0.0
    fragment: float | None = None
    rt: float | None = None
    rt_halfwidth: float = 0.5
    tolerance: float = DEFAULT_TOLERANCE
    unit: str = DEFAULT_UNIT
    group: str = ""
    formula: str = ""
    adduct: str = ""
    is_internal_standard: bool = False
    internal_standard: str = ""
    response: str = RESPONSE_AREA
    concentration_unit: str = ""
    #: per-component integration overrides; filled in a later phase
    integration: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.response not in RESPONSES:
            self.response = RESPONSE_AREA
        if not self.precursor and self.formula:
            computed = self.precursor_from_formula()
            if computed is not None:
                self.precursor = computed

    # -- masses ---------------------------------------------------------------- #
    def precursor_from_formula(self) -> float | None:
        """
        Precursor m/z from the formula and adduct, or None if either is missing
        or unreadable. Lets a labelled internal standard be entered as
        `C18H30D4O4` instead of a hand-computed mass.
        """
        if not self.formula:
            return None
        try:
            counts = parse_formula(self.formula)
        except FormulaError:
            return None
        adduct = ADDUCTS_BY_NAME.get(self.adduct)
        if adduct is None:
            return None
        return adduct.mz(monoisotopic_mass(counts))

    @property
    def target_mz(self) -> float:
        """The mass actually extracted: the fragment, or the precursor if none."""
        return self.fragment if self.fragment is not None else self.precursor

    def mass_window(self) -> tuple[float, float]:
        """XIC m/z range, resolving the tolerance in Da or ppm."""
        mz = self.target_mz
        half = mz * self.tolerance * 1e-6 if self.unit.lower() == "ppm" else self.tolerance
        return mz - half, mz + half

    def rt_window(self) -> tuple[float, float] | None:
        """Expected time range, or None when no retention time was given."""
        if self.rt is None:
            return None
        return self.rt - self.rt_halfwidth, self.rt + self.rt_halfwidth

    # -- presentation ----------------------------------------------------------- #
    @property
    def label(self) -> str:
        base = self.name
        if self.is_internal_standard:
            base += " (IS)"
        if self.fragment is not None:
            return f"{base}  {self.precursor:.4f} → {self.fragment:.4f}"
        return f"{base}  {self.precursor:.4f}"

    @property
    def is_valid(self) -> bool:
        return bool(self.name) and self.precursor > 0


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def _normalise_header(row: dict) -> dict:
    """Map CSV headers onto the dataclass field names."""
    out = {}
    for raw_key, value in row.items():
        if raw_key is None:
            continue
        key = raw_key.strip().lower().replace(" ", "_").replace("/", "_")
        for field_name, aliases in _ALIASES.items():
            if key in aliases:
                out[field_name] = value
                break
    return out


def _to_float(value, default=None):
    if value is None:
        return default
    text = str(value).strip().replace(",", ".")
    if not text:
        return default
    return float(text)


def _to_bool(value) -> bool:
    return str(value or "").strip().lower() in _TRUE


def load_components(path: str | os.PathLike) -> list[Component]:
    """
    Read a component list from CSV.

    Required: a name column, plus either a precursor column or a formula and
    adduct the precursor can be computed from. Everything else is optional. The
    delimiter is detected automatically among comma, semicolon and tab.
    """
    with open(path, newline="", encoding="utf-8-sig") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = [_normalise_header(row) for row in csv.DictReader(handle, dialect=dialect)]

    if not rows:
        return []
    if "name" not in rows[0]:
        raise ValueError("CSV has no name column (use 'name' or 'component').")
    if "precursor" not in rows[0] and "formula" not in rows[0]:
        raise ValueError("CSV has no precursor column and no formula column.")

    components: list[Component] = []
    for number, row in enumerate(rows, start=2):
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        unit = str(row.get("unit") or DEFAULT_UNIT).strip() or DEFAULT_UNIT
        response = str(row.get("response") or RESPONSE_AREA).strip().lower()
        try:
            component = Component(
                name=name,
                precursor=_to_float(row.get("precursor"), 0.0) or 0.0,
                fragment=_to_float(row.get("fragment")),
                rt=_to_float(row.get("rt")),
                rt_halfwidth=_to_float(row.get("rt_halfwidth"), 0.5) or 0.5,
                tolerance=_to_float(row.get("tolerance"), DEFAULT_TOLERANCE),
                unit="ppm" if unit.lower() == "ppm" else "Da",
                group=str(row.get("group") or "").strip(),
                formula=str(row.get("formula") or "").strip(),
                adduct=str(row.get("adduct") or "").strip(),
                is_internal_standard=_to_bool(row.get("is_internal_standard")),
                internal_standard=str(row.get("internal_standard") or "").strip(),
                response=response,
                concentration_unit=str(row.get("concentration_unit") or "").strip(),
            )
        except ValueError as exc:
            raise ValueError(f"CSV line {number}: {exc}") from exc
        if component.is_valid:
            components.append(component)
    return components


def _fmt(value: float | None) -> str:
    """
    Format without losing exact-mass precision: 12 significant digits. With
    fewer, an m/z such as 313.2384 would be written as 313.238 — an error of
    more than 1 ppm, enough to shift a narrow XIC window.
    """
    return "" if value is None else f"{value:.12g}"


CSV_HEADER = ["name", "group", "precursor", "fragment", "rt", "window",
              "tolerance", "unit", "formula", "adduct", "is",
              "internal_standard", "response", "concentration_unit"]


def save_components(path: str | os.PathLike, components: list[Component]) -> None:
    """Write the list to CSV with headers that `load_components` accepts."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADER)
        for c in components:
            writer.writerow([
                c.name, c.group, _fmt(c.precursor), _fmt(c.fragment), _fmt(c.rt),
                _fmt(c.rt_halfwidth), _fmt(c.tolerance), c.unit, c.formula,
                c.adduct, "yes" if c.is_internal_standard else "",
                c.internal_standard, c.response, c.concentration_unit,
            ])


COMPONENT_FIELDS = [f.name for f in fields(Component)]
