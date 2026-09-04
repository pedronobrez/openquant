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
    method.smoothing = 2.0
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
