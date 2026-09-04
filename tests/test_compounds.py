"""Tests for the compound list (CSV round-trip)."""

import pytest

from openpeakview.compounds import Compound, load_compounds, save_compounds


def test_roundtrip_csv(tmp_path):
    compounds = [
        Compound("12,13-DiHOME", 313.2384, 183.1391, 14.7, 0.5, 0.02, "Da"),
        Compound("9,10-DiHOME", 313.2384, 201.1496, 14.2, 0.5, 20.0, "ppm"),
    ]
    path = tmp_path / "compounds.csv"
    save_compounds(path, compounds)
    back = load_compounds(path)
    assert back == compounds


def test_load_accepts_minimal_columns(tmp_path):
    path = tmp_path / "min.csv"
    path.write_text("name,precursor\nDiHOME,313.2384\n", encoding="utf-8")
    [compound] = load_compounds(path)
    assert compound.name == "DiHOME"
    assert compound.precursor == pytest.approx(313.2384)
    assert compound.fragment is None


def test_load_rejects_missing_name(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("precursor\n313.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="name column"):
        load_compounds(path)


def test_mass_window_da():
    compound = Compound("x", 313.2, 183.1391, tolerance=0.02, unit="Da")
    lo, hi = compound.mass_window()
    assert (lo, hi) == pytest.approx((183.1191, 183.1591))


def test_mass_window_ppm():
    compound = Compound("x", 313.2, 200.0, tolerance=25.0, unit="ppm")
    lo, hi = compound.mass_window()
    assert (hi - lo) == pytest.approx(0.01, rel=1e-6)


def test_mass_window_falls_back_to_precursor():
    compound = Compound("x", 313.2, None, tolerance=0.02)
    lo, hi = compound.mass_window()
    assert (lo + hi) / 2 == pytest.approx(313.2)


def test_rt_window_none_when_unset():
    assert Compound("x", 313.2).rt_window() is None
    assert Compound("x", 313.2, rt=10.0, rt_halfwidth=0.5).rt_window() == (9.5, 10.5)
