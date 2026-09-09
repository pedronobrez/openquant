"""
A spectral library read from text and searched with a spectrum.

The parsers are tested on the shapes real exporters produce — NIST's
fields, MassBank's, an MGF — and the search on what a cosine has to do:
give a record its own spectrum back at one, give a shifted spectrum
nothing, forgive an impurity in the reverse score and not in the plain
one, and keep the precursor filter honest about records it cannot apply to.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openquant.library import (SpectralLibrary, load_library, match,  # noqa: E402
                               parse_mgf, parse_msp)

MSP = """Name: Sphingomyelin d18:1/16:0
PrecursorMZ: 703.5749
Precursor_type: [M+H]+
Formula: C39H79N2O6P
Comment: "some exporter's note"
Num Peaks: 4
184.0733 999
86.0964 120
104.1070 60
125.0004 30

NAME: Ceramide d18:1/16:0
PRECURSORMZ: 538.5194
PRECURSORTYPE: [M+H]+
Num Peaks: 3
264.2686 999; 282.2791 400; 252.2686 80

Name: no precursor here
Num Peaks: 2
184.0733 999
86.0964 300
"""

MGF = """BEGIN IONS
TITLE=PC 34:1
PEPMASS=760.5851 1200
CHARGE=1+
FORMULA=C42H82NO8P
184.0733 100.0
86.0964 12.5
END IONS
BEGIN IONS
PEPMASS=500.1
100.0 50
END IONS
"""


def test_msp_records_are_read_with_their_fields_and_peaks():
    entries = parse_msp(MSP, "x.msp")
    assert [e.name for e in entries] == ["Sphingomyelin d18:1/16:0",
                                         "Ceramide d18:1/16:0", "no precursor here"]
    sm = entries[0]
    assert sm.precursor == pytest.approx(703.5749)
    assert sm.precursor_type == "[M+H]+" and sm.formula == "C39H79N2O6P"
    assert sm.fields["Comment"].startswith('"some')
    assert sm.peaks == 4
    assert sm.intensity.max() == 1.0 and sm.mz[0] == pytest.approx(86.0964)
    cer = entries[1]
    assert cer.peaks == 3 and cer.precursor == pytest.approx(538.5194)
    assert entries[2].precursor is None


def test_mgf_records_are_read():
    entries = parse_mgf(MGF, "x.mgf")
    assert entries[0].name == "PC 34:1"
    assert entries[0].precursor == pytest.approx(760.5851)
    assert entries[0].formula == "C42H82NO8P" and entries[0].peaks == 2
    assert entries[1].name == "unnamed"


def test_a_record_gets_its_own_spectrum_back_at_one():
    library = SpectralLibrary(parse_msp(MSP))
    sm = library.entries[0]
    hits = library.search(sm.mz, sm.intensity * 1000, precursor=703.575)
    assert hits[0].entry is sm
    assert hits[0].score == pytest.approx(1.0)
    assert hits[0].reverse == pytest.approx(1.0)
    assert hits[0].matched == 4 and hits[0].delta_ppm == pytest.approx(0.14, abs=0.1)


def test_a_shifted_spectrum_matches_nothing():
    library = SpectralLibrary(parse_msp(MSP))
    sm = library.entries[0]
    hits = library.search(sm.mz + 0.5, sm.intensity)
    assert hits == []


def test_the_reverse_score_forgives_an_impurity_and_the_plain_one_does_not():
    library = SpectralLibrary(parse_msp(MSP))
    sm = library.entries[0]
    mz = np.concatenate([sm.mz, [300.1, 400.2, 450.3]])
    intensity = np.concatenate([sm.intensity, [0.9, 0.8, 0.7]])
    hit = next(h for h in library.search(mz, intensity, precursor=703.575)
               if h.entry is sm)
    assert hit.reverse == pytest.approx(1.0)
    assert hit.score < 0.8


def test_one_peak_in_common_is_not_a_hit_unless_asked_for():
    """
    Measured on MassBank: a spectrum that is mostly one ion at 184.07 scored
    83 against a record whose fragment sits 13 ppm away, on that one peak.
    """
    library = SpectralLibrary(parse_msp(MSP))
    mz = np.array([184.0733, 500.0])
    intensity = np.array([1.0, 0.5])
    assert library.search(mz, intensity) == []
    loose = library.search(mz, intensity, min_matched=1)
    assert loose and all(h.matched == 1 for h in loose)


def test_the_search_only_scores_records_that_share_a_bin_with_the_query():
    library = SpectralLibrary(parse_msp(MSP))
    sm = library.entries[0]
    assert library._index is None
    hits = library.search(sm.mz, sm.intensity)
    assert library._index is not None
    assert hits[0].entry is sm
    # the filtered search is a vector comparison and never builds the index
    fresh = SpectralLibrary(parse_msp(MSP))
    fresh.search(sm.mz, sm.intensity, precursor=703.575)
    assert fresh._index is None


def test_the_precursor_filter_leaves_out_records_that_carry_none_unless_asked():
    """
    Measured on MassBank: 24,000 of 139,000 records carry no precursor,
    and a filter that admits them all had every search dominated by them.
    """
    library = SpectralLibrary(parse_msp(MSP))
    sm = library.entries[0]
    hits = library.search(sm.mz, sm.intensity, precursor=703.575,
                          precursor_tolerance=0.02, min_matched=1)
    names = [h.entry.name for h in hits]
    assert "Ceramide d18:1/16:0" not in names            # 538, filtered out
    assert "no precursor here" not in names              # no precursor, left out
    asked = library.search(sm.mz, sm.intensity, precursor=703.575,
                           precursor_tolerance=0.02, min_matched=1,
                           include_unknown_precursor=True)
    bare = next(h for h in asked if h.entry.name == "no precursor here")
    assert bare.delta_ppm is None and bare.matched == 2


def test_matching_takes_the_strongest_library_peak_first():
    query_mz = np.array([184.0733, 184.0760])
    query_i = np.array([1.0, 0.1])
    lib_mz = np.array([184.0740, 184.0765])
    lib_i = np.array([0.1, 1.0])
    _score, _reverse, pairs = match(query_mz, query_i, lib_mz, lib_i, tolerance_ppm=20)
    strongest = next(p for p in pairs if p.library == pytest.approx(184.0765))
    assert strongest.measured == pytest.approx(184.0760)


def test_a_library_is_loaded_by_extension(tmp_path):
    msp = tmp_path / "lib.msp"
    msp.write_text(MSP, encoding="utf-8")
    mgf = tmp_path / "lib.mgf"
    mgf.write_text(MGF, encoding="utf-8")
    assert len(load_library(msp)) == 3 and load_library(msp).with_precursor == 2
    assert len(load_library(mgf)) == 2


def test_the_panel_loads_searches_and_offers_the_overlay(tmp_path):
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from openquant.ui.library_panel import LibraryPanel

    path = tmp_path / "lib.msp"
    path.write_text(MSP, encoding="utf-8")
    panel = LibraryPanel()
    panel.load(str(path))
    assert "3 records" in panel.library_label.text()
    sm = panel.library.entries[0]
    panel.spectrum_source = lambda: (sm.mz, sm.intensity * 5000, 703.5749)
    panel.search()
    assert panel.precursor_tol.value() == pytest.approx(0.02)   # four decimals given
    panel.set_spectrum(sm.mz, sm.intensity, 703.5)
    assert panel.precursor_tol.value() >= 0.05                   # one decimal: ±0.05
    assert panel.hits.topLevelItemCount() >= 1
    assert panel.hits.topLevelItem(0).text(0) == "Sphingomyelin d18:1/16:0"
    assert panel.hits.topLevelItem(0).text(1) == "100"
    assert panel.pairs.topLevelItemCount() == 4
    overlays = []
    panel.sigOverlay.connect(lambda peaks, label: overlays.append((peaks, label)))
    panel.btn_overlay.click()
    assert overlays and overlays[0][1] == "Sphingomyelin d18:1/16:0"
    assert len(overlays[0][0]) == 4
    panel.deleteLater()
    app.processEvents()
