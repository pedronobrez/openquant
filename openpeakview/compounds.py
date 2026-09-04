"""
Target compound list — the equivalent of PeakView's XIC Manager.

A compound says what to extract (precursor, fragment, tolerance) and where the
peak is expected (retention time and half window). The list is read from and
written to CSV so it can be maintained outside the program.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, fields

# Header aliases, English and Portuguese, keyed by dataclass field name. Lists
# written by earlier versions used Portuguese headers, so both keep working.
_ALIASES = {
    "name": {"name", "compound", "analyte", "nome", "composto", "analito"},
    "precursor": {"precursor", "q1", "precursor_mz", "parent", "precursormz"},
    "fragment": {"fragment", "q3", "product", "fragment_mz", "productmz",
                 "fragmento", "produto"},
    "rt": {"rt", "retention_time", "rt_min", "tr", "tempo"},
    "rt_halfwidth": {"window", "rt_window", "rt_halfwidth", "half_window",
                     "janela", "meia_janela", "tolerancia_rt"},
    "tolerance": {"tolerance", "tol", "mz_tolerance", "tolerancia"},
    "unit": {"unit", "tol_unit", "unidade"},
}

DEFAULT_TOLERANCE = 0.02
DEFAULT_UNIT = "Da"


@dataclass
class Compound:
    """One target of the extraction list."""

    name: str
    precursor: float
    fragment: float | None = None
    rt: float | None = None
    rt_halfwidth: float = 0.5
    tolerance: float = DEFAULT_TOLERANCE
    unit: str = DEFAULT_UNIT

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

    @property
    def label(self) -> str:
        if self.fragment is not None:
            return f"{self.name}  {self.precursor:.4f} → {self.fragment:.4f}"
        return f"{self.name}  {self.precursor:.4f}"


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


def load_compounds(path: str | os.PathLike) -> list[Compound]:
    """
    Read a compound list from CSV.

    Required: a name column and a precursor column. Everything else (fragment,
    rt, window, tolerance, unit) is optional. The delimiter is detected
    automatically among comma, semicolon and tab.
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
        raise ValueError("CSV has no name column (use 'name' or 'compound').")
    if "precursor" not in rows[0]:
        raise ValueError("CSV has no precursor column (use 'precursor' or 'Q1').")

    compounds: list[Compound] = []
    for number, row in enumerate(rows, start=2):
        name = str(row.get("name", "")).strip()
        precursor = _to_float(row.get("precursor"))
        if not name or precursor is None:
            continue
        unit = str(row.get("unit") or DEFAULT_UNIT).strip() or DEFAULT_UNIT
        try:
            compounds.append(
                Compound(
                    name=name,
                    precursor=precursor,
                    fragment=_to_float(row.get("fragment")),
                    rt=_to_float(row.get("rt")),
                    rt_halfwidth=_to_float(row.get("rt_halfwidth"), 0.5) or 0.5,
                    tolerance=_to_float(row.get("tolerance"), DEFAULT_TOLERANCE),
                    unit="ppm" if unit.lower() == "ppm" else "Da",
                )
            )
        except ValueError as exc:
            raise ValueError(f"CSV line {number}: {exc}") from exc
    return compounds


def _fmt(value: float | None) -> str:
    """
    Format without losing exact-mass precision: 12 significant digits. With
    fewer, an m/z such as 313.2384 would be written as 313.238 — an error of
    more than 1 ppm, enough to shift a narrow XIC window.
    """
    return "" if value is None else f"{value:.12g}"


def save_compounds(path: str | os.PathLike, compounds: list[Compound]) -> None:
    """Write the list to CSV with headers that `load_compounds` accepts."""
    header = ["name", "precursor", "fragment", "rt", "window", "tolerance", "unit"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for c in compounds:
            writer.writerow([
                c.name, _fmt(c.precursor), _fmt(c.fragment), _fmt(c.rt),
                _fmt(c.rt_halfwidth), _fmt(c.tolerance), c.unit,
            ])


COMPOUND_FIELDS = [f.name for f in fields(Compound)]
