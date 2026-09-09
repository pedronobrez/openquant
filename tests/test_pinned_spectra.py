"""
Spectra held for comparison: the live one first, the pinned ones after.

What matters is that the first trace stays the live spectrum — every panel
reads it — and that the pinned ones survive the live one changing.
"""

import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from openquant.session import Session  # noqa: E402
from openquant.ui.explorer import ExplorerWorkspace  # noqa: E402
from openquant.ui.plots import Trace  # noqa: E402


def test_pinning_keeps_the_live_spectrum_first_and_the_pins_after():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    explorer = ExplorerWorkspace(Session())
    mz = np.linspace(100, 200, 50)
    first = Trace("spec", "spectrum", mz, np.ones(50), "#1f77b4")
    explorer.spectrum.set_traces([first])
    explorer.spectrum.set_title("sample A · scan 3")
    assert not explorer.act_unpin.isEnabled()
    explorer.pin_spectrum()
    assert explorer.act_unpin.isEnabled()
    assert [t.key for t in explorer.spectrum.traces] == ["spec", "pin1"]
    assert explorer.pinned_spectra[0].label == "sample A · scan 3"
    # the next live spectrum draws over the pin, and stays first
    second = Trace("spec", "spectrum", mz, np.ones(50) * 2, "#1f77b4")
    explorer.spectrum.set_traces(explorer._with_pins(second))
    assert [t.key for t in explorer.spectrum.traces] == ["spec", "pin1"]
    assert explorer._current_spectrum()[1].max() == 2.0
    explorer.pin_spectrum()
    assert [t.key for t in explorer.spectrum.traces] == ["spec", "pin1", "pin2"]
    assert explorer.pinned_spectra[1].colour != explorer.pinned_spectra[0].colour
    explorer.unpin_spectra()
    assert [t.key for t in explorer.spectrum.traces] == ["spec"]
    assert not explorer.act_unpin.isEnabled()
    explorer.deleteLater()
    app.processEvents()
