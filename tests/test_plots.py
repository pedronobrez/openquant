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
