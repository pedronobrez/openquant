"""
Turning samples and a method into results.

Kept apart from the interface so the extraction and integration can be tested,
scripted and reused by more than one workspace.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from .components import Component
from .matching import match_channel
from .method import ProcessingMethod
from .processing import ChromPeak, detect_peaks, gaussian_smooth, subtract_baseline
from .samples import SampleEntry

#: confidence of a qualifier's ion ratio
PASS = "Pass"
MARGINAL = "Marginal"
FAIL = "Fail"
NOT_APPLICABLE = ""


@dataclass
class PeakResult:
    """One integrated peak: a component measured in a sample."""

    sample_key: str
    sample_name: str
    component: str
    group: str = ""
    channel: str = "—"
    mz: float = 0.0
    rt: float = 0.0
    expected_rt: float | None = None
    area: float = 0.0
    height: float = 0.0
    width: float = 0.0
    snr: float = 0.0
    start_rt: float = 0.0
    end_rt: float = 0.0
    note: str = ""
    used: bool = True
    manual: bool = False
    #: internal standard this component is reported against, and its response
    internal_standard: str = ""
    is_area: float | None = None
    is_height: float | None = None
    area_ratio: float | None = None
    height_ratio: float | None = None
    #: qualifier confirmation
    quantifier: str = ""
    ion_ratio: float | None = None
    expected_ion_ratio: float | None = None
    confidence: str = NOT_APPLICABLE

    @property
    def key(self) -> tuple[str, str]:
        return (self.sample_key, self.component)

    @property
    def found(self) -> bool:
        return self.area > 0.0

    @property
    def rt_delta(self) -> float | None:
        """Signed difference from the expected retention time, in minutes."""
        if self.expected_rt is None or not self.found:
            return None
        return self.rt - self.expected_rt

    def response(self, mode: str) -> float | None:
        """
        The number this component is reported by: the raw area, or its ratio to
        the internal standard.
        """
        if mode == "ratio":
            return self.area_ratio
        return self.area

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PeakResult":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class ResultsSet:
    """Every result of one processing run, addressable by sample and component."""

    results: list[PeakResult] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    def clear(self) -> None:
        self.results = []

    def get(self, sample_key: str, component: str) -> PeakResult | None:
        for result in self.results:
            if result.sample_key == sample_key and result.component == component:
                return result
        return None

    def for_component(self, component: str) -> list[PeakResult]:
        return [r for r in self.results if r.component == component]

    def for_sample(self, sample_key: str) -> list[PeakResult]:
        return [r for r in self.results if r.sample_key == sample_key]

    def replace(self, result: PeakResult) -> None:
        for index, existing in enumerate(self.results):
            if existing.key == result.key:
                self.results[index] = result
                return
        self.results.append(result)

    def to_list(self) -> list[dict]:
        return [r.to_dict() for r in self.results]

    @classmethod
    def from_list(cls, rows: list[dict]) -> "ResultsSet":
        return cls([PeakResult.from_dict(row) for row in rows or []])


# --------------------------------------------------------------------------- #
# extraction
# --------------------------------------------------------------------------- #
class XicCache:
    """
    Memoises extracted chromatograms.

    Switching between components in the review grid re-reads the same traces
    over and over; a small cache keeps that instant without holding a whole
    batch in memory.
    """

    def __init__(self, max_entries: int = 512):
        self._data: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
        self._order: list[tuple] = []
        self.max_entries = max_entries

    def clear(self) -> None:
        self._data.clear()
        self._order.clear()

    def get(self, key: tuple):
        return self._data.get(key)

    def put(self, key: tuple, value) -> None:
        if key not in self._data and len(self._order) >= self.max_entries:
            self._data.pop(self._order.pop(0), None)
        if key not in self._data:
            self._order.append(key)
        self._data[key] = value


def condition(x: np.ndarray, y: np.ndarray, method: ProcessingMethod) -> np.ndarray:
    """Apply the method's baseline and smoothing, as the display does."""
    if method.baseline_window > 0:
        y = subtract_baseline(x, y, method.baseline_window)
    if method.smoothing > 0:
        y = gaussian_smooth(y, method.smoothing)
    return y


def extract_xic(entry: SampleEntry, component: Component,
                method: ProcessingMethod,
                cache: XicCache | None = None) -> tuple[np.ndarray, np.ndarray, object]:
    """
    The chromatogram of one component in one sample, already conditioned.

    Returns the trace and the channel it came from, so callers can label the
    panel with the experiment that was actually used.
    """
    empty = (np.zeros(0), np.zeros(0), None)
    if not entry.is_loaded:
        return empty
    channel = match_channel(entry.sample, component)
    if channel is None:
        return empty
    mz_lo, mz_hi = component.mass_window()
    key = (entry.key, channel.index, round(mz_lo, 6), round(mz_hi, 6),
           method.baseline_window, method.smoothing)
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit[0], hit[1], channel
    x, y = channel.xic_range(mz_lo, mz_hi)
    y = condition(x, y, method)
    if cache is not None:
        cache.put(key, (x, y))
    return x, y, channel


def integrate_component(entry: SampleEntry, component: Component,
                        method: ProcessingMethod,
                        cache: XicCache | None = None) -> PeakResult:
    """
    Integrate one component in one sample.

    When the component declares a retention time whose window the matched
    channel does not cover, the result comes back empty and annotated instead
    of reporting a peak found somewhere else in the run.
    """
    mz_lo, mz_hi = component.mass_window()
    result = PeakResult(
        sample_key=entry.key, sample_name=entry.name, component=component.name,
        group=component.group, mz=(mz_lo + mz_hi) / 2,
        expected_rt=component.rt, rt=component.rt or 0.0,
    )

    x, y, channel = extract_xic(entry, component, method, cache)
    if channel is None:
        result.note = "no matching channel"
        return result
    result.channel = channel.info.short_label
    if x.size == 0:
        result.note = "no data"
        return result

    window = component.rt_window()
    if window is None:
        mask = np.ones(x.size, dtype=bool)
    else:
        mask = (x >= window[0]) & (x <= window[1])
        if mask.sum() < 3:
            result.note = (f"channel does not cover "
                           f"{window[0]:.2f}–{window[1]:.2f} min")
            return result

    peaks = detect_peaks(x[mask], y[mask],
                         min_relative=method.min_relative_height,
                         min_snr=method.min_snr)
    if not peaks:
        result.note = "no peak above noise"
        return result
    return apply_peak(result, peaks[0])


def apply_peak(result: PeakResult, peak: ChromPeak, manual: bool = False) -> PeakResult:
    """Copy an integrated peak onto a result row."""
    result.rt = peak.apex_rt
    result.area = peak.area
    result.height = peak.height
    result.width = peak.width
    result.snr = peak.snr
    result.start_rt = peak.start_rt
    result.end_rt = peak.end_rt
    result.note = ""
    result.manual = manual
    return result


def link_internal_standards(results: ResultsSet, method: ProcessingMethod) -> None:
    """
    Fill in each result's ratio to its internal standard.

    Done after the whole batch, because the standard's own peak has to be
    integrated before anything can be divided by it.
    """
    for result in results:
        component = method.by_name(result.component)
        if component is None:
            continue
        standard = method.internal_standard_for(component)
        if standard is None:
            continue
        result.internal_standard = standard.name
        reference = results.get(result.sample_key, standard.name)
        if reference is None or not reference.found:
            result.is_area = None
            result.is_height = None
            result.area_ratio = None
            result.height_ratio = None
            continue
        result.is_area = reference.area
        result.is_height = reference.height
        result.area_ratio = result.area / reference.area
        result.height_ratio = (result.height / reference.height
                               if reference.height else None)


def ion_ratio_confidence(measured: float | None, expected: float | None,
                         tolerance: float, marginal: float) -> str:
    """
    Grade a measured ion ratio against the expected one.

    The deviation is relative to the expected ratio, which is how a qualifier
    tolerance is normally written: "within 20% of the expected ratio".
    """
    if measured is None or expected in (None, 0):
        return NOT_APPLICABLE
    deviation = abs(measured - expected) / abs(expected) * 100.0
    if deviation <= tolerance:
        return PASS
    if deviation <= marginal:
        return MARGINAL
    return FAIL


def compute_ion_ratios(results: ResultsSet, method: ProcessingMethod) -> None:
    """Score every qualifier against its quantifier, in each sample."""
    for result in results:
        component = method.by_name(result.component)
        if component is None:
            continue
        quantifier = method.quantifier_for(component)
        if quantifier is None:
            continue
        result.quantifier = quantifier.name
        result.expected_ion_ratio = component.ion_ratio
        reference = results.get(result.sample_key, quantifier.name)
        if reference is None or not reference.found or not result.found:
            result.ion_ratio = None
            result.confidence = NOT_APPLICABLE
            continue
        result.ion_ratio = result.area / reference.area * 100.0
        tolerance, marginal = method.ion_ratio_limits(component)
        result.confidence = ion_ratio_confidence(
            result.ion_ratio, component.ion_ratio, tolerance, marginal)


def process(entries: list[SampleEntry], method: ProcessingMethod,
            cache: XicCache | None = None, progress=None) -> ResultsSet:
    """
    Run every component over every sample.

    `progress` is called as (done, total) and may return False to stop, which
    keeps whatever was computed so far rather than throwing it away.
    """
    components = [c for c in method.components if c.is_valid]
    loaded = [e for e in entries if e.is_loaded]
    total = len(components) * len(loaded)
    out = ResultsSet()
    done = 0
    for entry in loaded:
        for component in components:
            out.results.append(integrate_component(entry, component, method, cache))
            done += 1
            if progress is not None and progress(done, total) is False:
                link_internal_standards(out, method)
                compute_ion_ratios(out, method)
                return out
    link_internal_standards(out, method)
    compute_ion_ratios(out, method)
    return out
