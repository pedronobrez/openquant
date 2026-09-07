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
from dataclasses import asdict, dataclass, fields

from .chemistry import ADDUCTS_BY_NAME, FormulaError, monoisotopic_mass, parse_formula
from .processing import SNR_MODES, SNR_PEAK_TO_PEAK

#: how a component's result is reported
RESPONSE_AREA = "area"
RESPONSE_RATIO = "ratio"
RESPONSE_CONCENTRATION = "concentration"
RESPONSES = (RESPONSE_AREA, RESPONSE_RATIO, RESPONSE_CONCENTRATION)

DEFAULT_TOLERANCE = 0.02
DEFAULT_UNIT = "Da"


@dataclass
class AcceptanceLimits:
    """
    What a row has to satisfy to pass review.

    Every limit of zero is off, so a fresh method flags nothing until the
    criteria are actually stated.
    """

    #: largest allowed |measured RT - expected RT|, in minutes
    rt_tolerance: float = 0.0
    #: largest allowed |accuracy - 100|, in percent
    accuracy_tolerance: float = 0.0
    #: smallest acceptable signal-to-noise
    min_snr: float = 0.0

    @property
    def is_active(self) -> bool:
        return bool(self.rt_tolerance or self.accuracy_tolerance or self.min_snr)

    def copy(self) -> "AcceptanceLimits":
        return AcceptanceLimits(**asdict(self))


@dataclass
class IntegrationParams:
    """
    How one component's peaks are found and measured.

    The method carries a set of defaults and a component may override them, so
    a single awkward analyte can be tuned without disturbing the rest of the
    batch.
    """

    smoothing: float = 0.0
    baseline_window: float = 0.0
    min_relative_height: float = 0.05
    min_snr: float = 3.0
    #: stretch of baseline used to measure noise; None falls back to the
    #: automatic estimate over the whole trace
    noise_start: float | None = None
    noise_end: float | None = None
    snr_mode: str = SNR_PEAK_TO_PEAK

    def __post_init__(self):
        if self.snr_mode not in SNR_MODES:
            self.snr_mode = SNR_PEAK_TO_PEAK

    @property
    def noise_region(self) -> tuple[float, float] | None:
        if self.noise_start is None or self.noise_end is None:
            return None
        return self.noise_start, self.noise_end

    def copy(self) -> "IntegrationParams":
        return IntegrationParams(**asdict(self))

    def cache_key(self) -> tuple:
        """Only the parts that change the conditioned trace."""
        return (self.smoothing, self.baseline_window)

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
    "qualifier_of": {"qualifier_of", "qualifier", "qualificador_de",
                     "quantifier", "quantifier_name"},
    "ion_ratio": {"ion_ratio", "expected_ion_ratio", "razao_ionica"},
    "ion_ratio_tolerance": {"ion_ratio_tolerance", "ion_ratio_tol",
                            "tolerancia_razao_ionica"},
    "regression": {"regression", "curve", "fit", "regressao"},
    "weighting": {"weighting", "weight", "ponderacao", "peso"},
    "lm_id": {"lm_id", "lipidmaps", "lipidmaps_id", "lmid"},
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
    #: name of the quantifier component this one confirms, when it is a
    #: qualifier transition
    qualifier_of: str = ""
    #: expected qualifier/quantifier area ratio, in percent
    ion_ratio: float | None = None
    #: allowed relative deviation from `ion_ratio`, in percent; 0 uses the
    #: method default
    ion_ratio_tolerance: float = 0.0
    #: calibration
    regression: str = "linear"
    weighting: str = "1"
    #: LIPID MAPS identifier, when the component has been annotated
    lm_id: str = ""
    #: integration overrides for this component; None uses the method defaults
    integration: IntegrationParams | None = None
    #: acceptance overrides for this component; None uses the method defaults
    acceptance: AcceptanceLimits | None = None

    @property
    def is_qualifier(self) -> bool:
        return bool(self.qualifier_of)

    @property
    def calibration_response(self) -> str:
        """
        What a calibration curve is built from: the ratio to the internal
        standard when there is one, and the raw area otherwise. This is the
        measured quantity, distinct from `response`, which says what the
        results table reports.
        """
        return "ratio" if self.internal_standard else "area"

    def __post_init__(self):
        if self.response not in RESPONSES:
            self.response = RESPONSE_AREA
        if isinstance(self.integration, dict):
            known = {k: v for k, v in self.integration.items()
                     if k in IntegrationParams.__dataclass_fields__}
            self.integration = IntegrationParams(**known)
        if isinstance(self.acceptance, dict):
            known = {k: v for k, v in self.acceptance.items()
                     if k in AcceptanceLimits.__dataclass_fields__}
            self.acceptance = AcceptanceLimits(**known)
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
                qualifier_of=str(row.get("qualifier_of") or "").strip(),
                ion_ratio=_to_float(row.get("ion_ratio")),
                ion_ratio_tolerance=_to_float(row.get("ion_ratio_tolerance"), 0.0) or 0.0,
                regression=str(row.get("regression") or "linear").strip() or "linear",
                weighting=str(row.get("weighting") or "1").strip() or "1",
                lm_id=str(row.get("lm_id") or "").strip(),
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
              "internal_standard", "response", "concentration_unit",
              "qualifier_of", "ion_ratio", "ion_ratio_tolerance",
              "regression", "weighting", "lm_id"]


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
                c.qualifier_of, _fmt(c.ion_ratio), _fmt(c.ion_ratio_tolerance),
                c.regression, c.weighting, c.lm_id,
            ])


COMPONENT_FIELDS = [f.name for f in fields(Component)]
