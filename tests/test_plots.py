"""Tests for the view-level transforms of the plot panes.

These need a QApplication but no window is ever shown.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from openpeakview.ui.plots import ChromatogramView, SpectrumView, Trace  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def two_traces():
    x = np.linspace(0, 10, 500)
    y1 = np.exp(-((x - 5) ** 2) / 0.1) * 1000
    y2 = np.exp(-((x - 5) ** 2) / 0.1) * 400
    return [
        Trace("a", "first", x, y1, "#1f77b4"),
        Trace("b", "second", x, y2, "#d62728"),
    ]


def test_mirror_flips_every_other_trace(qapp, two_traces):
    view = ChromatogramView()
    view.set_traces(two_traces)
    view.set_mirror(True)
    _, first = view._display(two_traces[0], 0)
    _, second = view._display(two_traces[1], 1)
    assert first.max() > 0
    assert second.min() < 0


def test_cascade_offsets_shift_x_and_y(qapp, two_traces):
    view = ChromatogramView()
    view.set_traces(two_traces)
    view.set_offsets(0.5, 20.0)
    x0, y0 = view._display(two_traces[0], 0)
    x1, y1 = view._display(two_traces[1], 1)
    assert x1[0] == pytest.approx(x0[0] + 0.5)
    assert y1.min() > y0.min()


def test_relative_labels_report_distance_to_marker(qapp, two_traces):
    view = SpectrumView()
    view.set_traces(two_traces)
    assert view._label_for(5.0) == "5.0000"
    view.add_marker(6.0, snap_to_peak=False)
    assert view._label_for(6.0) == "6.0000"      # sits on the marker
    assert view._label_for(5.0) == "-1.0000"     # one unit below it


def test_relative_labels_can_be_turned_off(qapp, two_traces):
    view = SpectrumView()
    view.set_traces(two_traces)
    view.add_marker(6.0, snap_to_peak=False)
    view.set_relative_labels(False)
    assert view._label_for(5.0) == "5.0000"


def test_marker_snaps_to_nearest_peak(qapp, two_traces):
    view = SpectrumView()
    view.set_traces(two_traces)
    view.add_marker(5.05)
    assert view.markers[0] == pytest.approx(5.0, abs=0.05)


def test_centroid_mode_shortens_the_axis(qapp, two_traces):
    view = SpectrumView()
    view.set_traces(two_traces)
    profile_x, _ = view.conditioned("a")
    view.set_centroid(True)
    centroid_x, _ = view.conditioned("a")
    assert centroid_x.size < profile_x.size
    assert view.centroided


def test_overlay_is_anchored_on_the_measured_monoisotopic_peak(qapp):
    """A minor ion's overlay must match its own height, not the base peak's."""
    mz = np.array([100.0, 200.0, 201.0034])
    intensity = np.array([10_000.0, 500.0, 100.0])  # base peak is elsewhere
    view = SpectrumView()
    view.set_traces([Trace("s", "spectrum", mz, intensity, "#1f77b4")])
    pattern = [(200.0, 1.0), (201.0034, 0.2)]
    scale = view._overlay_scale(pattern)
    assert scale == pytest.approx(500.0)          # anchored on m/z 200, not 10000
    assert scale * pattern[1][1] == pytest.approx(100.0)


def test_overlay_falls_back_to_the_base_peak_when_the_ion_is_absent(qapp):
    mz = np.array([100.0, 150.0])
    intensity = np.array([10_000.0, 500.0])
    view = SpectrumView()
    view.set_traces([Trace("s", "spectrum", mz, intensity, "#1f77b4")])
    assert view._overlay_scale([(400.0, 1.0)]) == pytest.approx(10_000.0)


def test_overlay_can_be_set_and_cleared(qapp):
    mz = np.linspace(100, 200, 100)
    view = SpectrumView()
    view.set_traces([Trace("s", "spectrum", mz, np.ones(100), "#1f77b4")])
    assert not view.has_overlay
    view.set_overlay([(150.0, 1.0), (151.0, 0.2)], "C10H20O")
    assert view.has_overlay
    view.clear_overlay()
    assert not view.has_overlay
