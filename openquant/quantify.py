"""
Turning samples and a method into results.

Kept apart from the interface so the extraction and integration can be tested,
scripted and reused by more than one workspace.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from .calibration import Calibration, CalibrationPoint
from .calibration import fit as fit_curve
from .calibration import remove_outliers
from .components import Component, IntegrationParams
from .matching import match_channel
from .method import ProcessingMethod
from .processing import (
    ChromPeak,
    choose_peak,
    detect_peaks,
    estimate_noise,
    gaussian_smooth,
    integrate_window,
    noise_in_region,
    subtract_baseline,
)
from .samples import CALIBRATION_TYPES, SampleEntry

#: scans given to the detector either side of the window, so that it can
#: see a peak's edges rather than a slice of its middle
MARGIN_SCANS = 3

#: below this `detect_peaks` refuses, and the reason is reported as such
MIN_DETECTION_POINTS = 5

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
    #: quantitation
    actual_concentration: float | None = None
    calculated_concentration: float | None = None
    accuracy: float | None = None
    #: acceptance review
    flags: list[str] = field(default_factory=list)
    status: str = NOT_APPLICABLE

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
        The number this component is reported by: the raw area, its ratio to
        the internal standard, or the concentration read off the curve.
        """
        if mode == "ratio":
            return self.area_ratio
        if mode == "concentration":
            return self.calculated_concentration
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


def condition(x: np.ndarray, y: np.ndarray,
              params: IntegrationParams) -> np.ndarray:
    """Apply a component's baseline and smoothing, as the display does."""
    if params.baseline_window > 0:
        y = subtract_baseline(x, y, params.baseline_window)
    if params.smoothing > 0:
        y = gaussian_smooth(y, params.smoothing)
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
    params = method.integration_for(component)
    mz_lo, mz_hi = component.mass_window()
    key = (entry.key, channel.index, round(mz_lo, 6), round(mz_hi, 6),
           params.cache_key())
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit[0], hit[1], channel
    x, y = channel.xic_range(mz_lo, mz_hi)
    y = condition(x, y, params)
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

    params = method.integration_for(component)
    noise = measured_noise(x, y, params)
    peaks = detect_peaks(x[detection_range(x, mask)], y[detection_range(x, mask)],
                         min_relative=params.min_relative_height,
                         min_snr=params.min_snr, noise=noise)
    if window is not None:
        # the window says where the apex may be, not where the peak has to
        # end. Peaks found in the margin belong to something else.
        peaks = [p for p in peaks if window[0] <= p.apex_rt <= window[1]]
    if not peaks:
        result.note = _nothing_found(x, mask)
        return result
    peak, note = choose_peak(peaks, component.rt, params.peak_choice)
    result = apply_peak(result, peak)
    if note:
        result.note = note
    return result


def detection_range(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    The stretch the detector is given: the window, plus room to see the edges.

    A retention-time window says where the apex may be. It is not a statement
    about where the peak ends, and handing the detector exactly that window
    has two consequences, both measured on real data.

    A peak is truncated at the boundary, which biases its area. And below five
    points `detect_peaks` declines outright — so with the 14.6 s sampling of a
    scheduled method, a ±0.5 min window holding four scans returned nothing at
    all, whatever was in it: a peak of 44,875 counts came back as "no peak
    above noise". Whether a component was integrated then depended on whether
    its window happened to catch four scans or five, which is set by the
    channel's start offset — an accident of the acquisition rather than
    anything about the chemistry.

    So the detector sees a few scans either side and the apex is required to
    land inside the declared window afterwards. The margin is deliberately
    small: everything in it competes on relative height with the real peak,
    and a wide margin would let a tall neighbour suppress it.
    """
    inside = np.flatnonzero(mask)
    if inside.size == 0:
        return mask
    first = max(int(inside[0]) - MARGIN_SCANS, 0)
    last = min(int(inside[-1]) + MARGIN_SCANS, x.size - 1)
    widened = np.zeros(x.size, dtype=bool)
    widened[first:last + 1] = True
    return widened


def _nothing_found(x: np.ndarray, mask: np.ndarray) -> str:
    """Why there is no peak — which is not always that there is no signal."""
    points = int(detection_range(x, mask).sum())
    if points < MIN_DETECTION_POINTS:
        return (f"only {points} points to detect in; the window is narrower "
                f"than the sampling can resolve")
    return "no peak above noise"


def measured_noise(x: np.ndarray, y: np.ndarray,
                   params: IntegrationParams) -> float | None:
    """
    The noise a signal-to-noise ratio is measured against.

    Taken over the component's noise region when one is set, and otherwise
    over the whole chromatogram. It deliberately is not measured inside the
    retention-time window: that stretch is mostly peak, so its point-to-point
    spread reports the peak's own slope — on real data that read 16,944 where
    the trace's actual noise was 505, and the same peak came out at S/N 19
    automatically against 531 by hand.
    """
    region = params.noise_region
    if region is not None:
        return noise_in_region(x, y, region[0], region[1], params.snr_mode)
    return estimate_noise(y)


def integrate_manually(entry: SampleEntry, component: Component,
                       method: ProcessingMethod, start: float, end: float,
                       previous: PeakResult | None = None,
                       cache: XicCache | None = None) -> PeakResult:
    """
    Integrate exactly the stretch the operator marked on a chromatogram.

    No peak finding runs: the boundaries are the answer. The row is flagged
    manual so a later reprocessing can be told to leave it alone.
    """
    mz_lo, mz_hi = component.mass_window()
    result = previous or PeakResult(
        sample_key=entry.key, sample_name=entry.name, component=component.name,
        group=component.group, mz=(mz_lo + mz_hi) / 2, expected_rt=component.rt,
    )
    x, y, channel = extract_xic(entry, component, method, cache)
    if channel is None or x.size == 0:
        result.note = "no data"
        return result
    result.channel = channel.info.short_label
    params = method.integration_for(component)
    peak = integrate_window(x, y, start, end, measured_noise(x, y, params))
    if peak is None:
        result.note = "selection too narrow to integrate"
        return result
    return apply_peak(result, peak, manual=True)


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
            # the component was pointed at another standard, at none, or at a
            # name nothing answers to: the old ratios describe a link that is
            # gone, so they go with it rather than quietly standing
            result.internal_standard = ""
            result.is_area = None
            result.is_height = None
            result.area_ratio = None
            result.height_ratio = None
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


def evaluate_acceptance(results: ResultsSet, entries: list[SampleEntry],
                        method: ProcessingMethod) -> None:
    """
    Score every row against its component's acceptance criteria.

    A row with no criteria set gets no status at all rather than a green light:
    a method that has not been told what to check has not checked anything, and
    saying otherwise would be worse than saying nothing.
    """
    by_key = {e.key: e for e in entries}
    for result in results:
        result.flags = []
        result.status = NOT_APPLICABLE
        component = method.by_name(result.component)
        if component is None:
            continue
        limits = method.acceptance_for(component)
        checked = False

        if not result.found:
            result.flags.append("not integrated")
            result.status = FAIL
            continue

        if limits.rt_tolerance:
            checked = True
            delta = result.rt_delta
            if delta is not None and abs(delta) > limits.rt_tolerance:
                result.flags.append(f"RT {delta:+.3f} min")

        if limits.min_snr:
            checked = True
            if result.snr < limits.min_snr:
                result.flags.append(f"S/N {result.snr:.0f}")

        if limits.accuracy_tolerance:
            entry = by_key.get(result.sample_key)
            wanted = entry is not None and entry.actual_concentration is not None
            if wanted:
                checked = True
                if result.accuracy is None:
                    result.flags.append("no concentration")
                elif abs(result.accuracy - 100.0) > limits.accuracy_tolerance:
                    result.flags.append(f"accuracy {result.accuracy:.0f}%")

        if result.confidence == FAIL:
            checked = True
            result.flags.append(f"ion ratio {result.ion_ratio:.1f}%")
        elif result.confidence == MARGINAL:
            checked = True

        if not checked:
            continue
        if result.flags:
            result.status = FAIL
        elif result.confidence == MARGINAL:
            result.status = MARGINAL
        else:
            result.status = PASS


def build_calibrations(results: ResultsSet, entries: list[SampleEntry],
                       method: ProcessingMethod,
                       auto_outliers: bool = False,
                       tolerance: float = 15.0,
                       previous: dict[str, Calibration] | None = None,
                       ) -> dict[str, Calibration]:
    """
    Fit one curve per component from the samples marked as standards.

    Points the operator excluded by hand are carried over from `previous`, so
    refitting after a parameter change does not quietly put them back.
    """
    by_key = {e.key: e for e in entries}
    excluded: dict[tuple[str, str], bool] = {}
    for name, curve in (previous or {}).items():
        for point in curve.points:
            excluded[(name, point.sample_key)] = point.used

    curves: dict[str, Calibration] = {}
    for component in method.components:
        mode = component.calibration_response
        points: list[CalibrationPoint] = []
        for result in results.for_component(component.name):
            entry = by_key.get(result.sample_key)
            if entry is None or entry.sample_type not in CALIBRATION_TYPES:
                continue
            if entry.actual_concentration is None:
                continue
            response = result.response(mode)
            if response is None:
                continue
            points.append(CalibrationPoint(
                sample_key=result.sample_key, sample_name=result.sample_name,
                concentration=entry.actual_concentration, response=response,
                used=excluded.get((component.name, result.sample_key), True),
            ))
        if not points:
            continue
        points.sort(key=lambda p: p.concentration)
        curve = fit_curve(points, component.regression, component.weighting,
                          component.name)
        if auto_outliers and curve.is_fitted:
            curve = remove_outliers(curve, tolerance)
        curves[component.name] = curve
    return curves


def apply_calibrations(results: ResultsSet, entries: list[SampleEntry],
                       method: ProcessingMethod,
                       curves: dict[str, Calibration]) -> None:
    """
    Read a concentration off each component's curve and score its accuracy.

    The dilution factor multiplies the result, because the curve describes the
    vial that was injected and the answer wanted is the original sample.
    """
    by_key = {e.key: e for e in entries}
    for result in results:
        component = method.by_name(result.component)
        entry = by_key.get(result.sample_key)
        if entry is not None:
            result.actual_concentration = entry.actual_concentration
        result.calculated_concentration = None
        result.accuracy = None
        if component is None:
            continue
        curve = curves.get(component.name)
        if curve is None or not curve.is_fitted or not result.found:
            continue
        response = result.response(component.calibration_response)
        if response is None:
            continue
        value = curve.concentration_at(response)
        if value is None:
            continue
        dilution = entry.dilution_factor if entry else 1.0
        result.calculated_concentration = value * (dilution or 1.0)
        if result.actual_concentration:
            result.accuracy = (result.calculated_concentration
                               / result.actual_concentration * 100.0)


def process(entries: list[SampleEntry], method: ProcessingMethod,
            cache: XicCache | None = None, progress=None,
            previous: ResultsSet | None = None,
            keep_manual: bool = True,
            only: list[str] | None = None) -> ResultsSet:
    """
    Run the method over the batch.

    `previous` carries the rows of an earlier run. With `keep_manual`, any row
    the operator integrated by hand is carried across untouched, so adjusting a
    parameter does not silently undo their work. `only` limits the run to named
    components, which is what makes re-tuning one analyte cheap.
    """
    components = [c for c in method.components if c.is_valid]
    if only is not None:
        wanted = set(only)
        components = [c for c in components if c.name in wanted]
    loaded = [e for e in entries if e.is_loaded]
    total = len(components) * len(loaded)
    out = ResultsSet()
    if previous is not None and only is not None:
        keep = set(only)
        out.results = [r for r in previous if r.component not in keep]
    done = 0
    for entry in loaded:
        for component in components:
            kept = previous.get(entry.key, component.name) if previous else None
            if keep_manual and kept is not None and kept.manual:
                out.results.append(kept)
            else:
                out.results.append(
                    integrate_component(entry, component, method, cache))
            done += 1
            if progress is not None and progress(done, total) is False:
                break
        else:
            continue
        break
    link_internal_standards(out, method)
    compute_ion_ratios(out, method)
    return out
