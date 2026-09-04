"""Tests for extraction and integration, using stub channels."""

import numpy as np
import pytest

from openpeakview.components import Component
from openpeakview.method import ProcessingMethod
from openpeakview.quantify import (
    PeakResult,
    ResultsSet,
    XicCache,
    extract_xic,
    integrate_component,
    process,
)
from openpeakview.samples import SampleEntry
from tests.test_matching import Channel, Sample


def gaussian(x, centre, sigma, height):
    return height * np.exp(-((x - centre) ** 2) / (2 * sigma**2))


class TracedChannel(Channel):
    """A channel that returns a synthetic peak and counts its extractions."""

    def __init__(self, *args, apex=13.1, height=1000.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.apex = apex
        self.height = height
        self.calls = 0

    def xic_range(self, mz_lo, mz_hi):
        self.calls += 1
        x = self.rt
        return x, gaussian(x, self.apex, 0.05, self.height)


def make_entry(name="QC", apex=13.1, height=1000.0):
    channel = TracedChannel(1, 325.20, 50.0, 330.0, 12.0, 14.0, n=400,
                            apex=apex, height=height)
    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = Sample([channel])
    return entry, channel


@pytest.fixture
def method():
    m = ProcessingMethod()
    m.replace_all([Component("Oxy", 325.20, 183.0137, rt=13.1, rt_halfwidth=0.5)])
    return m


# --- extraction --------------------------------------------------------------- #
def test_extract_returns_the_trace_and_its_channel(method):
    entry, channel = make_entry()
    x, y, used = extract_xic(entry, method.components[0], method)
    # the apex falls between samples, so the peak reads just under its height
    assert x.size == 400 and y.max() == pytest.approx(1000.0, rel=0.01)
    assert used is channel


def test_extract_on_an_unloaded_sample_is_empty(method):
    entry = SampleEntry("/d/x.wiff", 0, "x")
    x, y, channel = extract_xic(entry, method.components[0], method)
    assert x.size == 0 and channel is None


def test_cache_avoids_re_reading_the_same_trace(method):
    entry, channel = make_entry()
    cache = XicCache()
    for _ in range(5):
        extract_xic(entry, method.components[0], method, cache)
    assert channel.calls == 1


def test_changing_the_method_bypasses_the_cache(method):
    entry, channel = make_entry()
    cache = XicCache()
    extract_xic(entry, method.components[0], method, cache)
    method.defaults.smoothing = 2.0
    extract_xic(entry, method.components[0], method, cache)
    assert channel.calls == 2


def test_component_override_bypasses_the_shared_cache_entry(method):
    """Two components on the same channel must not share a conditioned trace."""
    from openpeakview.components import IntegrationParams

    entry, channel = make_entry()
    cache = XicCache()
    extract_xic(entry, method.components[0], method, cache)
    method.components[0].integration = IntegrationParams(smoothing=3.0)
    extract_xic(entry, method.components[0], method, cache)
    assert channel.calls == 2


def test_cache_evicts_the_oldest_entry():
    cache = XicCache(max_entries=2)
    for i in range(3):
        cache.put((i,), (np.zeros(1), np.zeros(1)))
    assert cache.get((0,)) is None
    assert cache.get((2,)) is not None


# --- integration --------------------------------------------------------------- #
def test_integration_finds_the_peak(method):
    entry, _ = make_entry(apex=13.1)
    result = integrate_component(entry, method.components[0], method)
    assert result.found
    assert result.rt == pytest.approx(13.1, abs=0.02)
    assert result.area > 0 and result.snr > 3
    assert result.note == ""


def test_retention_time_delta_is_signed(method):
    entry, _ = make_entry(apex=13.25)
    result = integrate_component(entry, method.components[0], method)
    assert result.rt_delta == pytest.approx(0.15, abs=0.02)


def test_delta_is_none_without_an_expected_time():
    method = ProcessingMethod()
    method.replace_all([Component("Oxy", 325.20, 183.0137)])
    entry, _ = make_entry()
    assert integrate_component(entry, method.components[0], method).rt_delta is None


def test_peak_outside_the_window_is_not_reported(method):
    """A peak at 12.2 min must not be returned for a component expected at 13.1."""
    entry, _ = make_entry(apex=12.2)
    result = integrate_component(entry, method.components[0], method)
    assert not result.found
    assert result.note == "no peak above noise"


def test_window_the_channel_does_not_cover_is_flagged(method):
    method.components[0].rt = 30.0
    entry, _ = make_entry()
    result = integrate_component(entry, method.components[0], method)
    assert not result.found
    assert "does not cover" in result.note
    assert result.rt == 30.0  # the expected time, not an invented one


def test_no_matching_channel_is_flagged(method):
    entry = SampleEntry("/d/x.wiff", 0, "x")
    entry.sample = Sample([Channel(1, 900.0, 800.0, 1000.0, 0.0, 20.0)])
    result = integrate_component(entry, method.components[0], method)
    assert result.note == "no matching channel"


def test_flat_trace_gives_no_peak(method):
    entry, channel = make_entry(height=0.0)
    result = integrate_component(entry, method.components[0], method)
    assert not result.found


# --- batch ---------------------------------------------------------------------- #
def test_process_covers_every_sample_and_component(method):
    method.add(Component("Other", 325.20, 200.0, rt=13.1, rt_halfwidth=0.5))
    entries = [make_entry("A")[0], make_entry("B")[0]]
    results = process(entries, method)
    assert len(results) == 4
    assert {r.sample_name for r in results} == {"A", "B"}


def test_process_skips_unloaded_samples(method):
    entries = [make_entry("A")[0], SampleEntry("/d/B.wiff", 0, "B")]
    assert len(process(entries, method)) == 1


def test_process_can_be_cancelled(method):
    entries = [make_entry(n)[0] for n in "ABCD"]
    results = process(entries, method, progress=lambda done, total: done < 2)
    assert len(results) == 2


def test_invalid_components_are_skipped(method):
    method.add(Component("bad", 0.0))
    assert len(process([make_entry()[0]], method)) == 1


# --- results set ------------------------------------------------------------------ #
def test_results_lookup_and_replace():
    results = ResultsSet([
        PeakResult("s1", "A", "X", area=10.0),
        PeakResult("s1", "A", "Y", area=20.0),
        PeakResult("s2", "B", "X", area=30.0),
    ])
    assert results.get("s1", "Y").area == 20.0
    assert len(results.for_component("X")) == 2
    assert len(results.for_sample("s1")) == 2
    results.replace(PeakResult("s1", "A", "X", area=99.0))
    assert results.get("s1", "X").area == 99.0
    assert len(results) == 3


def test_results_round_trip():
    original = ResultsSet([PeakResult("s1", "A", "X", area=10.0, used=False,
                                      note="hand checked")])
    back = ResultsSet.from_list(original.to_list())
    assert back.results == original.results


def test_results_from_none_is_empty():
    assert len(ResultsSet.from_list(None)) == 0


# --- internal standards and ion ratios ---------------------------------------- #
def _method_with_is():
    method = ProcessingMethod()
    method.replace_all([
        Component("Analyte", 325.20, 183.0, rt=13.1, rt_halfwidth=0.5,
                  internal_standard="IS", response="ratio"),
        Component("Qual", 325.20, 119.0, rt=13.1, rt_halfwidth=0.5,
                  qualifier_of="Analyte", ion_ratio=50.0),
        Component("IS", 339.20, 339.2, rt=13.1, rt_halfwidth=0.5,
                  is_internal_standard=True),
    ])
    return method


def _results(analyte=100.0, qualifier=50.0, standard=200.0):
    rows = [
        PeakResult("s1", "QC", "Analyte", area=analyte, height=analyte / 2),
        PeakResult("s1", "QC", "Qual", area=qualifier, height=qualifier / 2),
        PeakResult("s1", "QC", "IS", area=standard, height=standard / 2),
    ]
    return ResultsSet(rows)


def test_area_and_height_ratios():
    from openpeakview.quantify import link_internal_standards
    method, results = _method_with_is(), _results()
    link_internal_standards(results, method)
    analyte = results.get("s1", "Analyte")
    assert analyte.internal_standard == "IS"
    assert analyte.is_area == 200.0
    assert analyte.area_ratio == pytest.approx(0.5)
    assert analyte.height_ratio == pytest.approx(0.5)


def test_ratio_is_none_when_the_standard_is_missing():
    from openpeakview.quantify import link_internal_standards
    method = _method_with_is()
    results = _results(standard=0.0)   # the standard did not integrate
    link_internal_standards(results, method)
    analyte = results.get("s1", "Analyte")
    assert analyte.area_ratio is None
    assert analyte.is_area is None


def test_response_follows_the_component_setting():
    from openpeakview.quantify import link_internal_standards
    method, results = _method_with_is(), _results()
    link_internal_standards(results, method)
    analyte = results.get("s1", "Analyte")
    assert analyte.response("area") == 100.0
    assert analyte.response("ratio") == pytest.approx(0.5)


def test_ion_ratio_passes_within_tolerance():
    from openpeakview.quantify import compute_ion_ratios
    method, results = _method_with_is(), _results(qualifier=50.0)
    compute_ion_ratios(results, method)
    qualifier = results.get("s1", "Qual")
    assert qualifier.quantifier == "Analyte"
    assert qualifier.ion_ratio == pytest.approx(50.0)
    assert qualifier.confidence == "Pass"


@pytest.mark.parametrize("measured,expected_grade", [
    (50.0, "Pass"),       # exact
    (60.0, "Pass"),       # +20%, on the pass boundary
    (64.0, "Marginal"),   # +28%
    (65.0, "Marginal"),   # +30%, on the marginal boundary
    (70.0, "Fail"),       # +40%
    (30.0, "Fail"),       # -40%, deviation is absolute
])
def test_ion_ratio_grading(measured, expected_grade):
    """Deviation is relative to the expected ratio: 20% passes, 30% is marginal."""
    from openpeakview.quantify import ion_ratio_confidence
    assert ion_ratio_confidence(measured, 50.0, 20.0, 30.0) == expected_grade


def test_ion_ratio_grading_reaches_the_results():
    from openpeakview.quantify import compute_ion_ratios
    method = _method_with_is()
    results = _results(qualifier=90.0)     # 90% against an expected 50%
    compute_ion_ratios(results, method)
    assert results.get("s1", "Qual").confidence == "Fail"


def test_ion_ratio_is_not_applicable_without_an_expectation():
    from openpeakview.quantify import compute_ion_ratios, ion_ratio_confidence
    assert ion_ratio_confidence(50.0, None, 20.0, 30.0) == ""
    assert ion_ratio_confidence(None, 50.0, 20.0, 30.0) == ""
    method = _method_with_is()
    method.by_name("Qual").ion_ratio = None
    results = _results()
    compute_ion_ratios(results, method)
    qualifier = results.get("s1", "Qual")
    assert qualifier.ion_ratio == pytest.approx(50.0)   # still measured
    assert qualifier.confidence == ""                    # but not graded


def test_ion_ratio_needs_both_peaks():
    from openpeakview.quantify import compute_ion_ratios
    method = _method_with_is()
    results = _results(analyte=0.0)     # the quantifier did not integrate
    compute_ion_ratios(results, method)
    assert results.get("s1", "Qual").ion_ratio is None


def test_component_level_tolerance_overrides_the_method():
    method = _method_with_is()
    method.by_name("Qual").ion_ratio_tolerance = 45.0
    assert method.ion_ratio_limits(method.by_name("Qual")) == (45.0, 45.0)
    assert method.ion_ratio_limits(method.by_name("Analyte")) == (20.0, 30.0)


def test_process_fills_ratios_end_to_end():
    method = ProcessingMethod()
    method.replace_all([
        Component("Analyte", 325.20, 183.0, rt=13.1, rt_halfwidth=0.5,
                  internal_standard="IS"),
        Component("IS", 325.20, 200.0, rt=13.1, rt_halfwidth=0.5,
                  is_internal_standard=True),
    ])
    entry, _ = make_entry()
    results = process([entry], method)
    analyte = results.get(entry.key, "Analyte")
    assert analyte.internal_standard == "IS"
    assert analyte.area_ratio == pytest.approx(1.0, rel=0.01)


# --- per-component integration and manual work --------------------------------- #
def test_integration_defaults_and_overrides():
    from openpeakview.components import IntegrationParams

    method = ProcessingMethod()
    component = Component("A", 100.0)
    method.replace_all([component])
    assert method.integration_for(component) is method.defaults

    method.set_integration(component, IntegrationParams(smoothing=5.0))
    assert method.integration_for(component).smoothing == 5.0
    assert method.defaults.smoothing == 0.0     # the defaults are untouched

    method.set_integration(component, None)
    assert method.integration_for(component) is method.defaults


def test_apply_integration_to_a_group_copies_rather_than_shares():
    from openpeakview.components import IntegrationParams

    method = ProcessingMethod()
    method.replace_all([
        Component("A", 100.0, group="g"),
        Component("B", 200.0, group="g"),
        Component("C", 300.0, group="other"),
    ])
    touched = method.apply_integration_to_group("g", IntegrationParams(min_snr=9.0))
    assert touched == 2
    assert method.by_name("C").integration is None
    method.by_name("A").integration.min_snr = 1.0
    assert method.by_name("B").integration.min_snr == 9.0   # not the same object


def test_manual_integration_marks_the_row_and_uses_the_range(method):
    from openpeakview.quantify import integrate_manually

    entry, _ = make_entry(apex=13.1)
    result = integrate_manually(entry, method.components[0], method, 13.0, 13.2)
    assert result.manual
    assert result.found
    assert result.start_rt == pytest.approx(13.0, abs=0.02)
    assert result.end_rt == pytest.approx(13.2, abs=0.02)


def test_manual_integration_can_pick_a_range_with_no_peak(method):
    """The operator's boundaries win: no peak finding second-guesses them."""
    from openpeakview.quantify import integrate_manually

    entry, _ = make_entry(apex=13.1)
    result = integrate_manually(entry, method.components[0], method, 12.2, 12.5)
    assert result.manual
    assert result.rt == pytest.approx(12.35, abs=0.2)


def test_manual_integration_rejects_a_sliver(method):
    from openpeakview.quantify import integrate_manually

    entry, _ = make_entry()
    result = integrate_manually(entry, method.components[0], method, 13.1, 13.1)
    assert "too narrow" in result.note


def test_reprocessing_keeps_manual_rows(method):
    from openpeakview.quantify import integrate_manually

    entry, _ = make_entry()
    first = process([entry], method)
    manual = integrate_manually(entry, method.components[0], method, 13.0, 13.2)
    first.replace(manual)

    method.defaults.smoothing = 5.0
    again = process([entry], method, previous=first, keep_manual=True)
    kept = again.get(entry.key, "Oxy")
    assert kept.manual and kept.area == pytest.approx(manual.area)

    forced = process([entry], method, previous=first, keep_manual=False)
    assert not forced.get(entry.key, "Oxy").manual


def test_reprocessing_only_named_components(method):
    method.add(Component("Other", 325.20, 200.0, rt=13.1, rt_halfwidth=0.5))
    entry, _ = make_entry()
    first = process([entry], method)
    first.get(entry.key, "Other").note = "left alone"

    again = process([entry], method, previous=first, only=["Oxy"])
    assert len(again) == 2
    assert again.get(entry.key, "Other").note == "left alone"
    assert again.get(entry.key, "Oxy").note == ""


class NoisyChannel(TracedChannel):
    """A peak sitting on real noise, so a noise region has something to measure."""

    def xic_range(self, mz_lo, mz_hi):
        self.calls += 1
        x = self.rt
        rng = np.random.default_rng(1)
        return x, gaussian(x, self.apex, 0.05, self.height) + abs(
            rng.normal(0, 20.0, x.size))


def test_noise_region_drives_the_reported_snr(method):
    from openpeakview.components import IntegrationParams

    entry = SampleEntry("/d/noisy.wiff", 0, "noisy")
    entry.sample = Sample([NoisyChannel(1, 325.20, 50.0, 330.0, 12.0, 14.0,
                                        n=800, apex=13.1, height=1000.0)])
    component = method.components[0]

    automatic = integrate_component(entry, component, method).snr

    # peak-to-peak over a stretch of pure baseline is the stricter reading
    method.set_integration(component, IntegrationParams(
        noise_start=12.0, noise_end=12.6, min_snr=0.0,
        snr_mode="peak-to-peak"))
    peak_to_peak = integrate_component(entry, component, method).snr

    method.set_integration(component, IntegrationParams(
        noise_start=12.0, noise_end=12.6, min_snr=0.0,
        snr_mode="standard deviation"))
    deviation = integrate_component(entry, component, method).snr

    assert peak_to_peak < deviation
    assert automatic > 0


def test_noise_is_measured_over_the_trace_not_the_peak_window(method):
    """
    Automatic and manual integration must report comparable S/N.

    The retention-time window is mostly peak, so estimating noise inside it
    measures the peak's own slope; both paths take the whole trace instead.
    """
    from openpeakview.quantify import extract_xic, integrate_manually

    entry = SampleEntry("/d/noisy.wiff", 0, "noisy")
    entry.sample = Sample([NoisyChannel(1, 325.20, 50.0, 330.0, 12.0, 14.0,
                                        n=800, apex=13.1, height=1000.0)])
    component = method.components[0]
    automatic = integrate_component(entry, component, method)
    manual = integrate_manually(entry, component, method,
                                automatic.start_rt, automatic.end_rt)
    assert automatic.snr == pytest.approx(manual.snr, rel=0.2)

    x, y, _ = extract_xic(entry, component, method)
    from openpeakview.processing import estimate_noise
    from openpeakview.quantify import measured_noise
    assert measured_noise(x, y, method.defaults) == pytest.approx(estimate_noise(y))
