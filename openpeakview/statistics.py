"""Grouped statistics over a results table."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .method import ProcessingMethod
from .quantify import PeakResult, ResultsSet
from .samples import SampleEntry

GROUP_BY_CONCENTRATION = "concentration"
GROUP_BY_SAMPLE_NAME = "sample name"
GROUP_BY_SAMPLE_TYPE = "sample type"
GROUPINGS = (GROUP_BY_CONCENTRATION, GROUP_BY_SAMPLE_NAME, GROUP_BY_SAMPLE_TYPE)

QUANTITIES = ("response", "area", "height", "calculated concentration",
              "retention time", "area ratio")


@dataclass
class StatisticsRow:
    """One component measured across a group of samples."""

    component: str
    group: str
    used: int
    total: int
    mean: float | None = None
    standard_deviation: float | None = None
    percent_cv: float | None = None
    accuracy: float | None = None
    values: list[tuple[str, float | None, bool]] = field(default_factory=list)


def _value_of(result: PeakResult, quantity: str, response_mode: str) -> float | None:
    if quantity == "response":
        return result.response(response_mode)
    if quantity == "area":
        return result.area if result.found else None
    if quantity == "height":
        return result.height if result.found else None
    if quantity == "calculated concentration":
        return result.calculated_concentration
    if quantity == "retention time":
        return result.rt if result.found else None
    if quantity == "area ratio":
        return result.area_ratio
    return None


def _group_key(entry: SampleEntry | None, grouping: str) -> str | None:
    if entry is None:
        return None
    if grouping == GROUP_BY_CONCENTRATION:
        if entry.actual_concentration is None:
            return None
        return f"{entry.actual_concentration:g}"
    if grouping == GROUP_BY_SAMPLE_TYPE:
        return entry.sample_type
    return entry.name


def summarise(results: ResultsSet, entries: list[SampleEntry],
              method: ProcessingMethod,
              grouping: str = GROUP_BY_CONCENTRATION,
              quantity: str = "response") -> list[StatisticsRow]:
    """
    Mean, standard deviation and %CV per component and group.

    Rows the operator unticked are counted in the total but left out of the
    arithmetic, so excluding an injection shows up as a smaller n rather than
    quietly changing the mean with no trace.
    """
    by_key = {e.key: e for e in entries}
    buckets: dict[tuple[str, str], list[PeakResult]] = {}
    order: list[tuple[str, str]] = []

    for result in results:
        key = _group_key(by_key.get(result.sample_key), grouping)
        if key is None:
            continue
        bucket = (result.component, key)
        if bucket not in buckets:
            buckets[bucket] = []
            order.append(bucket)
        buckets[bucket].append(result)

    rows: list[StatisticsRow] = []
    for component_name, key in order:
        members = buckets[(component_name, key)]
        component = method.by_name(component_name)
        mode = component.response if component else "area"
        values = [(r.sample_name, _value_of(r, quantity, mode), r.used)
                  for r in members]
        usable = [v for _name, v, used in values if used and v is not None]

        row = StatisticsRow(component=component_name, group=key,
                            used=len(usable), total=len(members), values=values)
        if usable:
            array = np.array(usable, dtype=float)
            row.mean = float(array.mean())
            # sample standard deviation; a single value has no spread to report
            row.standard_deviation = (float(array.std(ddof=1))
                                      if array.size > 1 else None)
            if row.standard_deviation is not None and row.mean:
                row.percent_cv = abs(row.standard_deviation / row.mean * 100.0)
            if grouping == GROUP_BY_CONCENTRATION:
                try:
                    expected = float(key)
                except ValueError:
                    expected = 0.0
                if expected and quantity == "calculated concentration":
                    row.accuracy = row.mean / expected * 100.0
        rows.append(row)
    return rows
