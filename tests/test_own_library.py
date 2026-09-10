"""
A spectral library of one's own, built from the spectra on screen.

An infused deuterated standard is in no public library, so the record has
to be made from the measurement. What is tested is that a record written
from a spectrum comes back from `parse_msp` as the same record — the same
peaks, the same fields — that appending leaves the records before it
readable, that the floor and the ceiling on the peaks are applied, and that
the panel's flow writes the file, counts it, and reloads the library when
it is the one the record went into.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openquant.library import (OWN_MAX_PEAKS, entry_from_spectrum,  # noqa: E402
                               format_msp, load_library, parse_msp, write_msp)

#: a made-up product spectrum with a base peak, two flanks and a whisper
MZ = np.array([80.9601, 121.0653, 289.2168, 371.2591, 411.3054])
INTENSITY = np.array([120.0, 4.0, 3800.0, 900.0, 45.0])


def a_record(**kwargs):
    fields = dict(name="cholic acid-d4", precursor=411.3054,
                  precursor_type="[M-H]-", formula="C24H36D4O5",
                  collision_energy=-35.0,
                  comment="CA-d4_TOFMSMS_Mix1.wiff · scans 1-120 · 2026-09-09")
    fields.update(kwargs)
    return entry_from_spectrum(mz=MZ, intensity=INTENSITY, **fields)


def test_a_record_from_a_spectrum_holds_relative_peaks_above_the_floor():
    entry = a_record()
    # 4.0 counts is 0.1% of the base peak: under the one per cent floor
    assert entry.peaks == 4
    assert 121.0653 not in entry.mz
    assert entry.intensity.max() == pytest.approx(1.0)
    assert entry.mz[0] == pytest.approx(80.9601)          # sorted by mass
    assert entry.intensity[entry.mz == 289.2168][0] == pytest.approx(1.0)
    assert entry.fields["Collision_energy"] == "-35"
    assert entry.fields["Comment"].startswith("CA-d4")


def test_a_record_keeps_the_strongest_peaks_and_needs_a_name():
    rng = np.random.default_rng(7)
    mz = np.linspace(100.0, 900.0, 500)
    intensity = rng.uniform(0.02, 1.0, 500) * 1000.0
    intensity[123] = 5000.0
    entry = entry_from_spectrum("crowded", mz, intensity)
    assert entry.peaks == OWN_MAX_PEAKS
    assert entry.mz[np.argmax(entry.intensity)] == pytest.approx(mz[123])
    # the ceiling keeps the strongest, so the weakest kept is above the
    # weakest dropped
    assert entry.intensity.min() * 5000.0 >= np.sort(intensity)[-OWN_MAX_PEAKS]
    with pytest.raises(ValueError):
        entry_from_spectrum("  ", mz, intensity)
    with pytest.raises(ValueError):
        entry_from_spectrum("empty", np.zeros(0), np.zeros(0))


def test_a_written_record_is_read_back_as_the_same_record(tmp_path):
    entry = a_record()
    path = tmp_path / "own.msp"
    assert write_msp([entry], path) == 1
    back = load_library(path)
    assert len(back) == 1
    read = back.entries[0]
    assert read.name == entry.name
    assert read.precursor == pytest.approx(411.3054)
    assert read.precursor_type == "[M-H]-" and read.formula == "C24H36D4O5"
    assert read.fields["Collision_energy"] == "-35"
    assert read.fields["Comment"] == entry.fields["Comment"]
    assert read.peaks == entry.peaks
    assert read.mz == pytest.approx(entry.mz, abs=1e-5)
    assert read.intensity == pytest.approx(entry.intensity, rel=1e-5)
    # and it scores one against the spectrum it was made from
    hit = back.search(MZ, INTENSITY, precursor=411.3054)[0]
    assert hit.score == pytest.approx(1.0)
    assert hit.matched == entry.peaks


def test_a_record_with_no_precursor_or_energy_writes_no_such_field():
    text = format_msp([entry_from_spectrum("bare", MZ, INTENSITY)])
    assert "PrecursorMZ" not in text and "Collision_energy" not in text
    assert "Num Peaks: 4" in text
    read = parse_msp(text)[0]
    assert read.precursor is None and read.name == "bare"


def test_appending_leaves_the_record_before_it_readable(tmp_path):
    path = tmp_path / "own.msp"
    write_msp([a_record(name="first")], path)
    write_msp([a_record(name="second", precursor=395.3105)], path, append=True)
    write_msp([a_record(name="third")], path, append=True)
    names = [e.name for e in load_library(path).entries]
    assert names == ["first", "second", "third"]
    # a file that somebody left without its trailing blank line still appends
    truncated = tmp_path / "truncated.msp"
    truncated.write_text(format_msp([a_record(name="first")]).rstrip("\n"),
                         encoding="utf-8")
    write_msp([a_record(name="second")], truncated, append=True)
    assert [e.name for e in load_library(truncated).entries] == ["first", "second"]


def test_a_newline_in_a_field_cannot_end_the_record(tmp_path):
    entry = a_record(name="one\ntwo", comment="a\nb")
    assert entry.name == "one two"
    path = tmp_path / "own.msp"
    write_msp([entry], path)
    read = load_library(path).entries
    assert len(read) == 1 and read[0].fields["Comment"] == "a b"


# --------------------------------------------------------------------------- #
# the panel
# --------------------------------------------------------------------------- #
@pytest.fixture
def panel(qapp_module):
    from openquant.ui.library_panel import LibraryPanel
    widget = LibraryPanel()
    yield widget
    widget.deleteLater()


@pytest.fixture(scope="module")
def qapp_module():
    from PyQt6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_the_panel_writes_a_record_and_counts_its_own_library(panel, tmp_path):
    path = str(tmp_path / "mine.msp")
    panel.set_own_path(path)
    assert "not written yet" in panel.own_label.text()
    panel.set_spectrum(MZ, INTENSITY, 411.3054,
                       {"title": "Mix1 · TOF PI 411.30 · average of 120 scans",
                        "file": "CA-d4_TOFMSMS_Mix1.wiff", "sample": "Mix1",
                        "polarity": "Negative", "collision_energy": -35.0})
    prefill = panel.own_prefill()
    assert prefill["precursor"] == pytest.approx(411.3054)
    assert prefill["precursor_type"] == "[M-H]-"
    assert prefill["collision_energy"] == pytest.approx(-35.0)
    assert "CA-d4_TOFMSMS_Mix1.wiff" in prefill["comment"]
    assert "average of 120 scans" in prefill["comment"]

    entry = panel.add_to_own_library("cholic acid-d4", **{
        k: prefill[k] for k in ("precursor", "precursor_type",
                                "collision_energy", "comment")})
    assert entry is not None and entry.peaks == 4
    assert "1 record(s) in mine.msp" in panel.own_label.text()
    assert "cholic acid-d4" in panel.status.text()
    written = load_library(path).entries[0]
    assert written.precursor == pytest.approx(411.3054)

    # a second one appends rather than replacing
    panel.add_to_own_library("deoxycholic acid-d4", precursor=395.3105)
    assert "2 record(s)" in panel.own_label.text()


def test_the_record_is_searchable_at_once_when_it_is_the_loaded_library(panel,
                                                                       tmp_path):
    path = str(tmp_path / "mine.msp")
    write_msp([a_record(name="deoxycholic acid-d4", precursor=395.3105,
                       formula="C24H36D4O4")], path)
    panel.load(path)
    panel.set_own_path(path)
    assert len(panel.library) == 1
    panel.set_spectrum(MZ, INTENSITY, 411.3054)
    panel.add_to_own_library("cholic acid-d4", precursor=411.3054)
    assert len(panel.library) == 2                  # reloaded, not stale
    panel.search()
    assert panel.hits.topLevelItemCount() == 1
    assert panel.hits.topLevelItem(0).text(0) == "cholic acid-d4"
    assert panel.hits.topLevelItem(0).text(1) == "100"


def test_a_record_keeps_the_precision_its_precursor_was_given(tmp_path):
    """
    A method value of `430.35` written back as `430.3500` would claim four
    decimals it does not have, and `precursor_disagrees` would then measure
    it to ±0.00005 and call the compound's own formula wrong.
    """
    path = tmp_path / "own.msp"
    write_msp([a_record(name="cholic acid-d4", precursor=430.35,
                        precursor_type="[M+NH4]+", formula="C24H36D4O5")], path)
    assert "PrecursorMZ: 430.35\n" in path.read_text(encoding="utf-8")
    read = load_library(path).entries[0]
    assert read.precursor_text == "430.35"
    assert read.exact_precursor == pytest.approx(430.3465, abs=1e-4)
    assert not read.precursor_disagrees
    # and a precursor genuinely known to four decimals still writes them
    write_msp([a_record(precursor=411.3054)], path)
    assert "PrecursorMZ: 411.3054\n" in path.read_text(encoding="utf-8")


def test_the_panel_gates_on_the_channel_polarity_until_the_box_is_ticked(panel,
                                                                        tmp_path):
    path = tmp_path / "mixed.msp"
    path.write_text(
        "Name: a positive record\nPrecursorMZ: 411.3054\n"
        "Precursor_type: [M+H]+\nNum Peaks: 2\n"
        "80.9601 999\n289.2168 500\n\n"
        "Name: a negative record\nPrecursorMZ: 411.3054\n"
        "Precursor_type: [M-H]-\nNum Peaks: 2\n"
        "80.9601 999\n289.2168 500\n", encoding="utf-8")
    panel.load(str(path))
    assert not panel.other_polarity.isChecked()          # off by default
    panel.set_spectrum(MZ, INTENSITY, 411.3054,
                       {"title": "t", "polarity": "Negative"})
    assert panel.query_polarity() == "Negative"
    panel.search()
    listed = [panel.hits.topLevelItem(i).text(0)
              for i in range(panel.hits.topLevelItemCount())]
    assert listed == ["a negative record"]
    assert "negative records only" in panel.status.text()
    panel.other_polarity.setChecked(True)
    panel.search()
    assert panel.hits.topLevelItemCount() == 2
    # with no context there is nothing to gate on and everything is scored
    panel.other_polarity.setChecked(False)
    panel.set_spectrum(MZ, INTENSITY, 411.3054, {"title": "t"})
    panel.search()
    assert panel.hits.topLevelItemCount() == 2


def test_the_panel_says_which_precursor_the_delta_was_measured_against(panel,
                                                                      tmp_path):
    path = tmp_path / "mixed.msp"
    path.write_text(
        "Name: with a formula\nPrecursorMZ: 430.35\n"
        "Precursor_type: [M+NH4]+\nFormula: C24H36D4O5\nNum Peaks: 2\n"
        "80.9601 999\n289.2168 500\n\n"
        "Name: typed wrong\nPrecursorMZ: 430.35\n"
        "Precursor_type: [M+NH4]+\nFormula: C24H36D4O4\nNum Peaks: 2\n"
        "80.9601 999\n289.2168 500\n", encoding="utf-8")
    panel.load(str(path))
    panel.set_spectrum(MZ, INTENSITY, 430.34, {"title": "t"})
    panel.precursor_tol.setValue(0.05)
    panel.search()
    rows = {panel.hits.topLevelItem(i).text(0): panel.hits.topLevelItem(i)
            for i in range(panel.hits.topLevelItemCount())}
    assert set(rows) == {"with a formula", "typed wrong"}
    assert rows["with a formula"].text(5) == "-15.1"
    assert rows["with a formula"].text(6) == "formula"
    assert rows["with a formula"].text(4) == "430.3500"      # no disagreement
    # the record whose formula is a different compound says both numbers
    assert "≠" in rows["typed wrong"].text(4)


def test_the_panel_refuses_without_a_file_or_a_spectrum(panel, tmp_path):
    panel.set_own_path("")
    panel.set_spectrum(MZ, INTENSITY, 411.3054)
    assert panel.add_to_own_library("nowhere") is None
    assert "Choose a file" in panel.status.text()
    panel._spectrum = None
    assert panel.add_to_own_library("x", path=str(tmp_path / "a.msp")) is None
    assert "Show a spectrum first" in panel.status.text()


def test_the_hook_may_carry_the_context_and_need_not(panel, tmp_path):
    panel.spectrum_source = lambda: (MZ, INTENSITY, 411.3054,
                                     {"polarity": "Negative", "file": "a.wiff"})
    panel._pull_spectrum()
    assert panel.own_prefill()["precursor_type"] == "[M-H]-"
    # the three-value form of the hook, which is what it was before
    panel.spectrum_source = lambda: (MZ, INTENSITY, 411.3054)
    panel._pull_spectrum()
    assert panel._spectrum is not None


def test_the_dialog_prefills_and_gives_back_what_was_typed(qapp_module):
    from openquant.ui.library_add_dialog import AddToLibraryDialog
    from PyQt6.QtWidgets import QDialogButtonBox

    dialog = AddToLibraryDialog(
        {"precursor": 411.3054, "precursor_type": "[M-H]-",
         "collision_energy": -35.0, "comment": "from a file"}, peaks=4,
        target="mine.msp")
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()                   # nothing is written unnamed
    dialog.name_edit.setText("cholic acid-d4")
    assert ok.isEnabled()
    dialog.formula_edit.setText("C24H36D4O5")
    values = dialog.values()
    assert values["name"] == "cholic acid-d4"
    assert values["precursor"] == pytest.approx(411.3054)
    assert values["precursor_type"] == "[M-H]-"
    assert values["formula"] == "C24H36D4O5"
    assert values["collision_energy"] == pytest.approx(-35.0)
    assert values["comment"] == "from a file"
    dialog.deleteLater()


def test_the_explorer_hands_over_where_the_spectrum_came_from(qapp_module):
    """
    A record has to say which file, sample, channel and scans it was made
    from, and the Explorer is the only place that knows.
    """
    from openquant.samples import SampleEntry
    from openquant.session import Session
    from openquant.ui.explorer import ChannelRef, ExplorerWorkspace
    from openquant.ui.plots import Trace
    from openquant.wiff import ChannelInfo

    explorer = ExplorerWorkspace(Session())
    mz = np.linspace(100.0, 200.0, 201)
    intensity = np.exp(-((mz - 150.0) ** 2) / 0.02) * 1000.0
    explorer.spectrum.set_traces([Trace("spec", "spectrum", mz, intensity, "#000")])
    explorer.spectrum.set_title("Mix1 · TOF PI 411.30 · average of 120 scans (1–120)")

    class _Channel:
        info = ChannelInfo(index=3, name="TOF PI", experiment_type="Product",
                           polarity="Negative", precursor=411.3, start_mass=50.0,
                           end_mass=500.0, n_scans=120, collision_energy=-35.0)

    entry = SampleEntry(path="/data/CA-d4_TOFMSMS_Mix1.wiff", sample_index=0,
                        name="Mix1")
    explorer.active_ref = ChannelRef(entry, _Channel())
    result = explorer._library_spectrum()
    assert result is not None and len(result) == 4
    _mz, _intensity, precursor, context = result
    assert precursor == pytest.approx(411.3)
    assert context["file"] == "CA-d4_TOFMSMS_Mix1.wiff"
    assert context["sample"] == "Mix1"
    assert context["polarity"] == "Negative"
    assert context["collision_energy"] == pytest.approx(-35.0)
    assert "average of 120 scans" in context["title"]
    # and the panel turns that into a comment naming all of it
    explorer.library_panel._pull_spectrum()
    comment = explorer.library_panel.own_prefill()["comment"]
    assert "CA-d4_TOFMSMS_Mix1.wiff" in comment and "average of 120 scans" in comment
    assert explorer.library_panel.own_prefill()["precursor_type"] == "[M-H]-"
    explorer.deleteLater()


def test_the_dialog_names_a_page_the_manual_has():
    from openquant.manual import manual
    from openquant.ui.library_add_dialog import HELP_PAGE
    assert HELP_PAGE in manual().pages
