"""Scoring a candidate structure against a measured product spectrum."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from openquant.explain import (  # noqa: E402
    explain,
    match_peaks,
    rank_candidates,
    significant_peaks,
)
from openquant.lipidmaps import LipidDatabase, LipidRecord  # noqa: E402
from openquant.structure import parse_molblock, predict  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def record(lm_id, name, formula, fixture, mass):
    molecule = parse_molblock((FIXTURES / f"{fixture}.mol").read_text(), formula)
    return LipidRecord(lm_id=lm_id, name=name, abbrev="", formula=formula,
                       exact_mass=mass, structure=molecule.to_compact())


@pytest.fixture
def cholic():
    return record("LMST04010001", "Cholic acid", "C24H40O5", "LMST04010001",
                  408.287574)


@pytest.fixture
def database(cholic):
    return LipidDatabase([
        cholic,
        record("LMSP03010002", "SM(d18:1/12:0)", "C35H71N2O6P",
               "LMSP03010002", 646.504974),
    ])


# -- picking the peaks worth explaining -------------------------------------- #
def test_only_peaks_above_the_noise_share_are_considered():
    mz = np.array([100.0, 200.0, 300.0])
    intensity = np.array([1000.0, 5.0, 400.0])
    kept = significant_peaks(mz, intensity, noise_share=0.01)
    assert [round(m) for m, _ in kept] == [100, 300]


def test_the_strongest_come_first_and_the_list_is_capped():
    mz = np.arange(100.0, 200.0)
    intensity = np.arange(100.0, 200.0)
    kept = significant_peaks(mz, intensity, limit=5)
    assert len(kept) == 5
    assert kept[0][1] > kept[-1][1]


def test_an_empty_spectrum_explains_nothing():
    assert significant_peaks(np.array([]), np.array([])) == []
    assert significant_peaks(np.array([1.0]), np.array([0.0])) == []


# -- pairing ------------------------------------------------------------------ #
def test_a_peak_takes_the_nearest_prediction(cholic):
    ions = predict(cholic.molecule())
    peaks = [(391.2843, 100.0)]
    matches = match_peaks(peaks, ions, tolerance_ppm=20.0)
    assert len(matches) == 1
    assert abs(matches[0].error_ppm) < 5


def test_one_prediction_cannot_claim_two_peaks(cholic):
    """Otherwise a dense prediction scores twice for the same ion."""
    ions = predict(cholic.molecule())
    peaks = [(391.2843, 100.0), (391.2845, 90.0)]
    matches = match_peaks(peaks, ions, tolerance_ppm=20.0)
    assert len({id(m.ion) for m in matches}) == len(matches)


def test_a_peak_nothing_predicts_is_left_unmatched(cholic):
    ions = predict(cholic.molecule())
    matches = match_peaks([(123.4567, 100.0)], ions, tolerance_ppm=1.0)
    assert matches == []


def test_nothing_to_match_against():
    assert match_peaks([], []) == []
    assert match_peaks([(100.0, 1.0)], []) == []


# -- scoring ------------------------------------------------------------------ #
def test_the_share_is_intensity_accounted_for_not_peaks_counted(cholic):
    # a candidate that explains the base peak beats one explaining forty specks
    peaks = [(391.2843, 1000.0), (123.4567, 10.0)]
    result = explain(cholic, peaks)
    assert result.matched == 1
    assert result.share > 0.98


def test_the_peaks_it_cannot_account_for_are_reported(cholic):
    peaks = [(391.2843, 1000.0), (123.4567, 10.0)]
    result = explain(cholic, peaks)
    left = result.unexplained(peaks)
    assert [round(m, 4) for m, _ in left] == [123.4567]


def test_a_record_with_no_structure_cannot_be_scored():
    bare = LipidRecord(lm_id="LMX", name="x", abbrev="", formula="C2H6O",
                       exact_mass=46.0)
    assert explain(bare, [(46.0, 1.0)]) is None


# -- ranking ------------------------------------------------------------------ #
def test_candidates_are_ordered_by_what_they_account_for(database, cholic):
    peaks = [(391.2843, 1000.0), (373.2737, 500.0), (355.2632, 200.0)]
    ranked = rank_candidates(database, 409.2948, peaks, adduct="[M+H]+",
                             tolerance=0.7, unit="Da")
    assert ranked
    assert ranked[0].record.lm_id == "LMST04010001"
    assert ranked == sorted(ranked, key=lambda e: (-e.share, -e.matched))


def test_a_precursor_nothing_sits_at_returns_nothing(database):
    assert rank_candidates(database, 999.9999, [(100.0, 1.0)],
                           tolerance=0.7, unit="Da") == []


def test_one_structure_per_species_is_scored(database):
    """A mass search answers with a family; scoring each is the same answer
    twelve times."""
    peaks = [(391.2843, 1000.0)]
    ranked = rank_candidates(database, 409.2948, peaks, tolerance=0.7,
                             unit="Da")
    species = [e.record.species for e in ranked]
    assert len(species) == len(set(species))
