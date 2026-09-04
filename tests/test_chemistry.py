"""Tests for formula parsing, exact masses, isotope patterns and the finder."""

import numpy as np
import pytest

from openpeakview import chemistry as ch


# --- parsing --------------------------------------------------------------- #
def test_parse_simple_formula():
    assert ch.parse_formula("C18H32O3") == {"C": 18, "H": 32, "O": 3}


def test_parse_single_atoms_and_two_letter_elements():
    assert ch.parse_formula("CHNOPSCl") == {
        "C": 1, "H": 1, "N": 1, "O": 1, "P": 1, "S": 1, "Cl": 1
    }


def test_parse_nested_groups():
    assert ch.parse_formula("C6H4(NO2)2") == {"C": 6, "H": 4, "N": 2, "O": 4}
    assert ch.parse_formula("((CH2)2O)3") == {"C": 6, "H": 12, "O": 3}


def test_parse_repeated_element_accumulates():
    assert ch.parse_formula("CH3CH2OH") == {"C": 2, "H": 6, "O": 1}


def test_parse_deuterium_and_bracketed_isotopes():
    assert ch.parse_formula("C18H28D4O3") == {"C": 18, "H": 28, "D": 4, "O": 3}
    counts = ch.parse_formula("[13C]2C16H32O3")
    assert counts["[13C]"] == 2 and counts["C"] == 16


def test_parse_rejects_unknown_element():
    with pytest.raises(ch.FormulaError, match="unknown element"):
        ch.parse_formula("C6Xx2")


def test_parse_rejects_unbalanced_parentheses():
    with pytest.raises(ch.FormulaError, match="parentheses"):
        ch.parse_formula("C6H4(NO2")


def test_parse_empty_is_empty():
    assert ch.parse_formula("   ") == {}


def test_format_formula_uses_hill_order():
    assert ch.format_formula({"O": 3, "H": 32, "C": 18}) == "C18H32O3"
    assert ch.format_formula({"H": 1, "Cl": 1}) == "HCl"


# --- masses ----------------------------------------------------------------- #
def test_monoisotopic_mass_of_dihome():
    # 12,13-DiHOME, C18H34O4
    mass = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    assert mass == pytest.approx(314.245709, abs=5e-5)


def test_deprotonated_dihome_matches_the_measured_precursor():
    neutral = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    mz = ch.ADDUCTS_BY_NAME["[M-H]-"].mz(neutral)
    assert mz == pytest.approx(313.2384, abs=1e-3)


def test_average_mass_is_above_monoisotopic():
    counts = ch.parse_formula("C18H34O4")
    assert ch.average_mass(counts) > ch.monoisotopic_mass(counts)
    assert ch.average_mass(counts) == pytest.approx(314.46, abs=0.05)


def test_adduct_round_trip():
    adduct = ch.ADDUCTS_BY_NAME["[M+Na]+"]
    assert adduct.neutral_mass(adduct.mz(500.0)) == pytest.approx(500.0)


def test_doubly_charged_adduct_halves_the_mz():
    single = ch.ADDUCTS_BY_NAME["[M+H]+"].mz(500.0)
    double = ch.ADDUCTS_BY_NAME["[M+2H]2+"].mz(500.0)
    assert double < single / 2 + 1.0


def test_rdbe_of_benzene_is_four():
    assert ch.rdbe(ch.parse_formula("C6H6")) == pytest.approx(4.0)


def test_rdbe_of_a_saturated_fatty_acid_is_one():
    assert ch.rdbe(ch.parse_formula("C18H36O2")) == pytest.approx(1.0)


def test_mass_errors():
    assert ch.mass_error_ppm(313.2394, 313.2384) == pytest.approx(3.19, abs=0.05)
    assert ch.mass_error_mda(313.2394, 313.2384) == pytest.approx(1.0, abs=1e-6)


# --- isotope patterns -------------------------------------------------------- #
def test_isotope_pattern_base_peak_is_first_and_normalised():
    pattern = ch.isotope_pattern(ch.parse_formula("C18H34O4"))
    assert pattern[0][1] == pytest.approx(1.0)
    assert all(abundance <= 1.0 for _mz, abundance in pattern)
    assert np.all(np.diff([mz for mz, _a in pattern]) > 0)


def test_carbon_13_satellite_scales_with_carbon_count():
    small = ch.isotope_pattern(ch.parse_formula("C10H22"))
    large = ch.isotope_pattern(ch.parse_formula("C40H82"))
    assert large[1][1] > small[1][1]
    # roughly 1.1% per carbon
    assert small[1][1] == pytest.approx(0.11, abs=0.02)


def test_chlorine_gives_the_expected_m2_ratio():
    pattern = ch.isotope_pattern(ch.parse_formula("C6H5Cl"), min_abundance=0.01)
    m2 = [a for mz, a in pattern if mz > pattern[0][0] + 1.5]
    assert m2 and m2[0] == pytest.approx(0.32, abs=0.03)


def test_isotope_pattern_applies_the_adduct():
    counts = ch.parse_formula("C18H34O4")
    neutral = ch.isotope_pattern(counts)
    ionised = ch.isotope_pattern(counts, ch.ADDUCTS_BY_NAME["[M-H]-"])
    assert ionised[0][0] == pytest.approx(neutral[0][0] - ch.PROTON_MASS)


def test_isotope_pattern_of_empty_formula():
    assert ch.isotope_pattern({}) == []


def test_match_isotope_pattern_perfect_and_absent():
    pattern = ch.isotope_pattern(ch.parse_formula("C18H34O4"),
                                 ch.ADDUCTS_BY_NAME["[M-H]-"], max_peaks=3)
    mz = np.array([p[0] for p in pattern])
    intensity = np.array([p[1] for p in pattern]) * 1000.0
    assert ch.match_isotope_pattern(mz, intensity, pattern) == pytest.approx(1.0, abs=0.02)
    empty = np.zeros(0)
    assert ch.match_isotope_pattern(empty, empty, pattern) == 0.0


# --- formula finder ----------------------------------------------------------- #
def test_finder_recovers_dihome():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    hits = ch.find_formulas(target, tolerance=5, unit="ppm")
    assert "C18H34O4" in [hit.formula for hit in hits]
    assert abs(hits[0].error_ppm) < 5


def test_finder_respects_the_tolerance():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    tight = ch.find_formulas(target, tolerance=1, unit="ppm")
    loose = ch.find_formulas(target, tolerance=50, unit="ppm")
    assert len(loose) > len(tight)
    assert all(abs(hit.error_ppm) <= 1.001 for hit in tight)


def test_finder_accepts_millidalton_tolerance():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    hits = ch.find_formulas(target, tolerance=0.003, unit="Da")
    assert all(abs(hit.error_mda) <= 3.001 for hit in hits)


def test_finder_honours_element_ranges():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    hits = ch.find_formulas(target, tolerance=20, unit="ppm",
                            ranges={"C": (0, 60), "H": (0, 120), "O": (0, 12)})
    assert all(set(hit.counts) <= {"C", "H", "O"} for hit in hits)


def test_finder_drops_odd_electron_formulas_by_default():
    target = ch.monoisotopic_mass(ch.parse_formula("C18H34O4"))
    hits = ch.find_formulas(target, tolerance=30, unit="ppm")
    assert all(abs(hit.rdbe - round(hit.rdbe)) < 1e-9 for hit in hits)


def test_golden_rules_shrink_the_candidate_list():
    target = 400.0
    with_rules = ch.find_formulas(target, 20, "ppm", golden_rules=True)
    without = ch.find_formulas(target, 20, "ppm", golden_rules=False)
    assert len(with_rules) < len(without)


def test_finder_returns_nothing_for_impossible_mass():
    assert ch.find_formulas(0.5, 5, "ppm") == []


def test_isotope_ranking_prefers_the_right_carbon_count():
    truth = ch.parse_formula("C18H34O4")
    adduct = ch.ADDUCTS_BY_NAME["[M-H]-"]
    pattern = ch.isotope_pattern(truth, adduct, min_abundance=0.005, max_peaks=4)
    mz = np.array([p[0] for p in pattern])
    intensity = np.array([p[1] for p in pattern]) * 5000.0

    hits = ch.find_formulas(adduct.neutral_mass(float(mz[0])), 30, "ppm")
    ranked = ch.rank_by_isotope_pattern(hits, mz, intensity, adduct)
    assert ranked[0].formula == "C18H34O4"
    assert ranked[0].isotope_score > 0.9


# --- isotope scoring is built from the satellites ---------------------------- #
def _measured(pattern, scale=1000.0, factors=None):
    """Turn a theoretical pattern into a fake measured spectrum."""
    factors = factors or [1.0] * len(pattern)
    mz = np.array([p[0] for p in pattern])
    intensity = np.array([p[1] * f for p, f in zip(pattern, factors)]) * scale
    return mz, intensity


def test_score_is_zero_when_the_satellites_are_missing():
    pattern = ch.isotope_pattern(ch.parse_formula("C18H34O4"),
                                 ch.ADDUCTS_BY_NAME["[M-H]-"], max_peaks=3)
    mz, intensity = _measured(pattern, factors=[1.0, 0.0, 0.0])
    assert ch.match_isotope_pattern(mz, intensity, pattern) == pytest.approx(0.0)


def test_score_falls_as_the_satellite_drifts():
    pattern = ch.isotope_pattern(ch.parse_formula("C18H34O4"),
                                 ch.ADDUCTS_BY_NAME["[M-H]-"], max_peaks=2)
    exact = ch.match_isotope_pattern(*_measured(pattern), pattern)
    off_10 = ch.match_isotope_pattern(*_measured(pattern, factors=[1.0, 1.1]), pattern)
    off_50 = ch.match_isotope_pattern(*_measured(pattern, factors=[1.0, 1.5]), pattern)
    assert exact > off_10 > off_50
    assert exact == pytest.approx(1.0, abs=0.01)


def test_score_separates_carbon_counts():
    """A C40 pattern must not score well against C10 data, and vice versa."""
    adduct = ch.ADDUCTS_BY_NAME["[M+H]+"]
    small = ch.isotope_pattern(ch.parse_formula("C10H22"), adduct, max_peaks=3)
    large = ch.isotope_pattern(ch.parse_formula("C40H82"), adduct, max_peaks=3)
    mz, intensity = _measured(small)
    # compare the large-molecule pattern against small-molecule data, at the
    # same masses, so only the satellite ratios differ
    shifted = [(m, a) for (m, _), (_, a) in zip(small, large)]
    assert ch.match_isotope_pattern(mz, intensity, small) > 0.95
    assert ch.match_isotope_pattern(mz, intensity, shifted) < 0.6


def test_single_peak_pattern_cannot_be_scored():
    assert ch.match_isotope_pattern(np.array([100.0]), np.array([10.0]),
                                    [(100.0, 1.0)]) == 0.0


def test_satellites_detected_when_present():
    mz = np.array([325.1853, 326.1886, 327.1920])
    intensity = np.array([39400.0, 9486.0, 5138.0])
    assert ch.has_isotope_satellites(mz, intensity, 325.1853)


def test_satellites_absent_in_an_isolated_precursor():
    # what a product-ion scan looks like: Q1 kept only the monoisotopic peak
    mz = np.array([325.1860, 326.1890])
    intensity = np.array([17694.0, 9.0])
    assert not ch.has_isotope_satellites(mz, intensity, 325.1860)


def test_satellites_use_the_charge_spacing():
    mz = np.array([325.0, 325.5017])
    intensity = np.array([1000.0, 200.0])
    assert ch.has_isotope_satellites(mz, intensity, 325.0, charge=2)
    assert not ch.has_isotope_satellites(mz, intensity, 325.0, charge=1)


def test_satellites_on_empty_spectrum():
    empty = np.zeros(0)
    assert not ch.has_isotope_satellites(empty, empty, 300.0)
