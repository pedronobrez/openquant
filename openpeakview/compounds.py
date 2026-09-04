"""
Lista de compostos alvo — equivalente ao XIC Manager do PeakView.

Um composto descreve o que extrair (precursor, fragmento, tolerancia) e onde
esperar o pico (tempo de retencao e meia-janela). A lista e lida e gravada em
CSV para poder ser mantida fora do programa.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, fields

# Aceita cabecalhos em portugues e ingles; a chave e o nome do campo.
_ALIASES = {
    "name": {"nome", "name", "composto", "compound", "analito", "analyte"},
    "precursor": {"precursor", "q1", "precursor_mz", "parent", "precursormz"},
    "fragment": {"fragmento", "fragment", "q3", "produto", "product",
                 "fragment_mz", "productmz"},
    "rt": {"rt", "tr", "tempo", "retention_time", "rt_min"},
    "rt_halfwidth": {"janela", "window", "rt_halfwidth", "rt_window",
                     "meia_janela", "tolerancia_rt"},
    "tolerance": {"tolerancia", "tolerance", "tol", "mz_tolerance"},
    "unit": {"unidade", "unit", "tol_unit"},
}

DEFAULT_TOLERANCE = 0.02
DEFAULT_UNIT = "Da"


@dataclass
class Compound:
    """Um alvo da lista de extracao."""

    name: str
    precursor: float
    fragment: float | None = None
    rt: float | None = None
    rt_halfwidth: float = 0.5
    tolerance: float = DEFAULT_TOLERANCE
    unit: str = DEFAULT_UNIT

    @property
    def target_mz(self) -> float:
        """Massa efetivamente extraida: o fragmento, ou o precursor se nao houver."""
        return self.fragment if self.fragment is not None else self.precursor

    def mass_window(self) -> tuple[float, float]:
        """Faixa de m/z do XIC, resolvendo a tolerancia em Da ou ppm."""
        mz = self.target_mz
        half = mz * self.tolerance * 1e-6 if self.unit.lower() == "ppm" else self.tolerance
        return mz - half, mz + half

    def rt_window(self) -> tuple[float, float] | None:
        """Faixa de tempo esperada, ou None quando o RT nao foi informado."""
        if self.rt is None:
            return None
        return self.rt - self.rt_halfwidth, self.rt + self.rt_halfwidth

    @property
    def label(self) -> str:
        parts = [self.name]
        if self.fragment is not None:
            parts.append(f"{self.precursor:.4f} → {self.fragment:.4f}")
        else:
            parts.append(f"{self.precursor:.4f}")
        return "  ".join(parts)


def _normalise_header(row: dict) -> dict:
    """Mapeia os cabecalhos do CSV para os nomes de campo do dataclass."""
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
    Le uma lista de compostos de um CSV.

    Obrigatorias: uma coluna de nome e uma de precursor. As demais colunas
    (fragmento, rt, janela, tolerancia, unidade) sao opcionais. O delimitador e
    detectado automaticamente entre virgula, ponto e virgula e tabulacao.
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
        raise ValueError("CSV sem coluna de nome (use 'nome' ou 'name').")
    if "precursor" not in rows[0]:
        raise ValueError("CSV sem coluna de precursor (use 'precursor' ou 'Q1').")

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
            raise ValueError(f"linha {number} do CSV: {exc}") from exc
    return compounds


def _fmt(value: float | None) -> str:
    """
    Formata sem perder precisao de massa exata: 12 digitos significativos.
    Com menos que isso um m/z como 313.2384 seria gravado como 313.238, um erro
    de mais de 1 ppm — o bastante para deslocar a janela de um XIC estreito.
    """
    return "" if value is None else f"{value:.12g}"


def save_compounds(path: str | os.PathLike, compounds: list[Compound]) -> None:
    """Grava a lista em CSV, com cabecalhos que `load_compounds` reconhece."""
    header = ["nome", "precursor", "fragmento", "rt", "janela", "tolerancia", "unidade"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for c in compounds:
            writer.writerow([
                c.name,
                _fmt(c.precursor),
                _fmt(c.fragment),
                _fmt(c.rt),
                _fmt(c.rt_halfwidth),
                _fmt(c.tolerance),
                c.unit,
            ])


COMPOUND_FIELDS = [f.name for f in fields(Compound)]
