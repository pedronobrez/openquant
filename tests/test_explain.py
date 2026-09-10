"""Scoring a candidate structure against a measured product spectrum."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from openquant.explain import (
    explain,
    match_peaks,
    rank_candidates,
    significant_peaks,
)
from openquant.lipidmaps import LipidDatabase, LipidRecord
from openquant.structure import parse_molblock, predict

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


# -- letting the spectrum choose between routes ------------------------------- #
def test_a_route_implies_its_own_intermediates(cholic):
    from openquant.explain import companion_masses
    from openquant.structure import predict

    ions = predict(cholic.molecule(), max_cuts=1, max_losses=2)
    two_waters = next(i for i in ions if i.losses == ("H2O", "H2O"))
    companions = companion_masses(cholic.molecule(), two_waters)
    # losing two waters means the one-water ion existed on the way
    assert len(companions) == 2
    assert companions[0] == pytest.approx(two_waters.mz + 18.0106, abs=1e-3)
    assert companions[1] == pytest.approx(two_waters.mz + 36.0211, abs=1e-3)


def test_a_route_with_no_losses_implies_nothing(cholic):
    from openquant.explain import companion_masses
    from openquant.structure import predict

    ions = predict(cholic.molecule(), max_cuts=1, max_losses=0)
    assert companion_masses(cholic.molecule(), ions[0]) == []


def test_the_route_whose_ladder_is_present_wins(cholic):
    """Two routes reach one mass; only the companions separate them."""
    from openquant.explain import routes_for
    from openquant.structure import predict

    molecule = cholic.molecule()
    ions = predict(molecule, max_cuts=1, max_losses=2)
    target = next(i for i in ions if i.losses == ("H2O", "H2O"))
    from openquant.explain import companion_masses

    with_ladder = [(target.mz, 100.0)] + [
        (m, 50.0) for m in companion_masses(molecule, target)]
    routes = routes_for(molecule, target, with_ladder)
    assert routes[0].support == pytest.approx(1.0)

    alone = routes_for(molecule, target, [(target.mz, 100.0)])
    assert alone[0].support == 0.0


def test_the_match_carries_the_route_the_spectrum_supports(cholic):
    peaks = [(391.2843, 1000.0), (373.2737, 500.0), (409.2948, 200.0)]
    result = explain(cholic, peaks)
    assert result.matches
    assert all(m.route is not None for m in result.matches)
    assert all(m.best_route for m in result.matches)


def test_a_spectrum_that_cannot_tell_them_apart_says_so(cholic):
    """No ladder present is an honest answer, not a reason to pick one."""
    from openquant.explain import routes_for
    from openquant.structure import predict

    molecule = cholic.molecule()
    target = next(i for i in predict(molecule, max_cuts=1, max_losses=2)
                  if i.losses == ("H2O", "H2O"))
    routes = routes_for(molecule, target, [(target.mz, 100.0)])
    assert all(r.support == 0.0 for r in routes)


# --------------------------------------------------------------------------- #
# a structure or formula the database does not hold
# --------------------------------------------------------------------------- #
def test_a_formula_alone_gives_the_precursor_and_its_losses():
    from openquant.explain import explain_formula, formula_ions

    ions = formula_ions("C24H40O5", "[M-H]-")
    descriptions = {ion.description for ion in ions}
    # a loss ion is written as what is left, and how it got there
    assert "C24H40O5" in descriptions and "C24H38O4 -H2O" in descriptions
    assert "C23H36O -H2O -H2O -CO2" in descriptions       # O5 - 2 - 2
    assert not any("-NH3" in d for d in descriptions)          # no nitrogen
    assert len(ions) == len(descriptions)                       # no duplicates
    intact = next(ion for ion in ions if not ion.losses)
    assert intact.mz == pytest.approx(407.2803, abs=0.001)
    peaks = [(407.2803, 1000.0), (389.2697, 300.0), (200.0, 100.0)]
    explanation = explain_formula("C24H40O5", "[M-H]-", peaks, name="Cholic acid")
    assert explanation.name == "Cholic acid"
    assert explanation.matched == 2 and explanation.share == pytest.approx(1300 / 1400)
    routes = {m.best_route for m in explanation.matches}
    assert "C24H38O4 -H2O" in routes


def test_unplaced_deuterium_offers_every_count_and_the_spectrum_picks_one():
    from openquant.explain import D_MINUS_H, explain_formula

    # a d4 cholic acid: the intact ion carries all four; a water loss may
    # have taken one with it
    d4 = 407.2803 + 4 * D_MINUS_H
    peaks = [(d4, 1000.0), (d4 - 18.0106 - D_MINUS_H, 200.0)]
    explanation = explain_formula("C24H40O5", "[M-H]-", peaks, deuterium=4)
    assert explanation.matched == 2
    routes = {m.best_route for m in explanation.matches}
    assert any(r.endswith("+4D") and "-H2O" not in r for r in routes)
    assert any("-H2O" in r and r.endswith("+3D") for r in routes)


def test_a_drawing_of_ones_own_is_scored_like_a_record(tmp_path):
    from openquant.explain import explain_structure, read_molfile, with_labels
    from openquant.structure import predict

    hexanol = """1-hexanol
  test

  7  6  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0
    3.0000    0.0000    0.0000 C   0  0  0  0  0  0
    4.5000    0.0000    0.0000 C   0  0  0  0  0  0
    6.0000    0.0000    0.0000 C   0  0  0  0  0  0
    7.5000    0.0000    0.0000 C   0  0  0  0  0  0
    9.0000    0.0000    0.0000 O   0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
  5  6  1  0
  6  7  1  0
M  END
"""
    molecule, name = read_molfile(hexanol)
    assert molecule is not None and name == "1-hexanol"
    assert molecule.formula == "C6H14O"
    ions = predict(molecule, charge=1, max_cuts=1, max_losses=1)
    labelled = with_labels(ions, deuterium=2)
    assert len(labelled) > len(ions)
    assert any(ion.labels == 2 and ion.description.endswith("+2D") for ion in labelled)
    assert all(ion.labels <= 2 for ion in labelled)
    explanation = explain_structure(molecule, [(103.1117, 100.0)], name="1-hexanol",
                                    charge=1)
    assert explanation.name == "1-hexanol" and explanation.record.category == "your own"


def test_the_panel_explains_with_a_formula():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from openquant.ui.lipid_panel import LipidPanel

    panel = LipidPanel()
    import numpy as np
    panel.set_spectrum(np.array([407.2803, 389.2697]), np.array([1000.0, 300.0]))
    panel.explain_adduct.setCurrentText("[M-H]-")
    panel.own_formula.setText("C24H40O5")
    panel.own_name.setText("Cholic acid")
    panel.explain_own()
    assert panel.explain_tree.topLevelItemCount() == 1
    assert panel.explain_tree.topLevelItem(0).text(0) == "Cholic acid"
    assert panel.match_tree.topLevelItemCount() == 2
    assert "no bonds to cut" in panel.status.text()
    panel.deleteLater()
    app.processEvents()


# --------------------------------------------------------------------------- #
# where the labels are
# --------------------------------------------------------------------------- #
HEXANOIC = """hexanoic acid
  test

  8  7  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0
    3.0000    0.0000    0.0000 C   0  0  0  0  0  0
    4.5000    0.0000    0.0000 C   0  0  0  0  0  0
    6.0000    0.0000    0.0000 C   0  0  0  0  0  0
    7.5000    0.0000    0.0000 C   0  0  0  0  0  0
    8.2500    1.2990    0.0000 O   0  0  0  0  0  0
    9.0000    0.0000    0.0000 O   0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
  5  6  1  0
  6  7  2  0
  6  8  1  0
M  END
"""

#: the same acid drawn with its three methyl hydrogens written out and
#: marked heavy — how a vendor draws a d3 standard
HEXANOIC_D3 = """hexanoic acid-d3
  test

 11 10  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0
    3.0000    0.0000    0.0000 C   0  0  0  0  0  0
    4.5000    0.0000    0.0000 C   0  0  0  0  0  0
    6.0000    0.0000    0.0000 C   0  0  0  0  0  0
    7.5000    0.0000    0.0000 C   0  0  0  0  0  0
    8.2500    1.2990    0.0000 O   0  0  0  0  0  0
    9.0000    0.0000    0.0000 O   0  0  0  0  0  0
   -0.5000    0.8660    0.0000 H   0  0  0  0  0  0
   -0.5000   -0.8660    0.0000 H   0  0  0  0  0  0
   -1.0000    0.0000    0.0000 H   0  0  0  0  0  0
  1  2  1  0
  2  3  1  0
  3  4  1  0
  4  5  1  0
  5  6  1  0
  6  7  2  0
  6  8  1  0
  1  9  1  0
  1 10  1  0
  1 11  1  0
M  ISO  3   9   2  10   2  11   2
M  END
"""


def labelled_ions(molecule, deuterium=3):
    from openquant.explain import with_labels

    return with_labels(predict(molecule, charge=-1, max_cuts=1, max_losses=0),
                       deuterium)


def one_ion(ions, atoms, labels):
    """The predicted ion for one piece carrying one number of labels."""
    wanted = frozenset(atoms)
    found = [i for i in ions if i.fragment.atoms == wanted and i.labels == labels]
    assert found, f"no ion for {sorted(atoms)} carrying {labels}"
    return sorted(found, key=lambda i: abs(i.hydrogens))[0]


def observed(molecule, ions, seen, rivals=None):
    """An explanation made by hand: these ions, matched exactly."""
    from openquant.explain import Explanation, PeakMatch, custom_record

    matches = [PeakMatch(mz=ion.mz, intensity=height, ion=ion)
               for ion, height in seen]
    total = sum(height for _ion, height in seen)
    return Explanation(record=custom_record("test", molecule.formula, molecule),
                       matches=matches, explained=total, total=total,
                       considered=len(matches),
                       ions=list(rivals if rivals is not None
                                 else [ion for ion, _h in seen]))


def test_a_piece_that_kept_none_of_the_labels_rules_its_atoms_out():
    from openquant.explain import infer_labels, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    # the acid end comes off carrying none of the three labels
    explanation = observed(molecule, ions,
                           [(one_ion(ions, {4, 5, 6, 7}, 0), 1000.0)])
    inference = infer_labels(explanation, molecule, deuterium=3)
    assert inference.placements
    placed = {atom for placement in inference.placements
              for site in placement.sites for atom in site.atoms}
    assert 4 not in placed and placed <= {0, 1, 2, 3}
    assert inference.agreement == pytest.approx(1.0)


def test_a_piece_that_kept_all_of_them_rules_its_atoms_in_and_ties():
    from openquant.explain import infer_labels, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    explanation = observed(molecule, ions,
                           [(one_ion(ions, {0, 1, 2, 3}, 3), 1000.0)])
    inference = infer_labels(explanation, molecule, deuterium=3)
    placed = {atom for placement in inference.placements
              for site in placement.sites for atom in site.atoms}
    assert placed <= {0, 1, 2, 3}
    # three labels over a methyl and three methylenes: seventeen ways
    assert inference.tied == 17
    assert inference.total > inference.tied
    assert not inference.agreed          # no single position is in all of them


def test_two_pieces_together_place_the_labels():
    from openquant.explain import infer_labels, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    explanation = observed(molecule, ions, [
        (one_ion(ions, {0, 1, 2, 3}, 3), 1000.0),   # the four keep all three
        (one_ion(ions, {4, 5, 6, 7}, 0), 500.0),
    ])
    inference = infer_labels(explanation, molecule, deuterium=3)
    # the second piece says nothing the first did not, so the tie stands
    assert inference.tied == 17
    explanation = observed(molecule, ions, [
        (one_ion(ions, {0, 1, 2, 3}, 3), 1000.0),
        (one_ion(ions, {1, 2, 3, 4, 5, 6, 7}, 0), 500.0),
    ])
    inference = infer_labels(explanation, molecule, deuterium=3)
    assert inference.tied == 1
    assert [(a.atom, a.labels) for a in inference.agreed] == [(0, 3)]
    assert "C1" in inference.agreed[0].description


def test_heteroatom_bound_positions_are_left_out_unless_asked_for():
    from openquant.explain import label_positions, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    carbon = label_positions(molecule)
    everything = label_positions(molecule, heteroatoms=True)
    assert [atom for atom, _capacity in carbon] == [0, 1, 2, 3, 4]
    assert [atom for atom, _capacity in everything] == [0, 1, 2, 3, 4, 7]
    assert dict(carbon)[0] == 3                 # a methyl holds three


def test_a_drawing_that_places_its_labels_is_checked_not_inferred():
    from openquant.explain import infer_labels, placed_labels, read_molfile

    molecule, name = read_molfile(HEXANOIC_D3)
    assert name == "hexanoic acid-d3"
    assert molecule.formula == "C6H9D3O2"       # the explicit ones folded in
    assert placed_labels(molecule) == (0, 0, 0)
    ions = predict(molecule, charge=-1, max_cuts=1, max_losses=0)
    explanation = observed(molecule, ions,
                           [(one_ion(ions, {0, 1, 2, 3}, 0), 1000.0)])
    inference = infer_labels(explanation, molecule)
    assert inference.placed
    assert inference.checked == (0, 0, 0)
    assert inference.checked_top and inference.checked_agreement == pytest.approx(1.0)
    assert "The drawing places its labels itself" in inference.summary()


def test_a_peak_two_label_counts_reach_is_not_used():
    from openquant.explain import infer_labels, read_molfile

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    ion = one_ion(ions, {0, 1, 2, 3}, 3)
    # every prediction is offered as a rival, and a deuterium is 1.55 mDa
    # from the hydrogen it replaced: at m/z 60 that is 26 ppm
    explanation = observed(molecule, ions, [(ion, 1000.0)], rivals=ions)
    wide = infer_labels(explanation, molecule, deuterium=3, tolerance_ppm=40.0)
    assert wide.undecided == 1 and not wide.placements
    assert "with a different number" in wide.note
    assert "1.55 mDa" in wide.note
    narrow = infer_labels(explanation, molecule, deuterium=3, tolerance_ppm=5.0)
    assert narrow.undecided == 0 and narrow.placements


def test_the_panel_places_the_labels_under_the_table():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import numpy as np
    from PyQt6 import QtWidgets

    from openquant.explain import read_molfile
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from openquant.ui.lipid_panel import LipidPanel

    molecule, _name = read_molfile(HEXANOIC)
    ions = labelled_ions(molecule)
    ion = one_ion(ions, {0, 1, 2, 3}, 3)
    panel = LipidPanel()
    panel.set_spectrum(np.array([ion.mz]), np.array([1000.0]))
    panel.explain_adduct.setCurrentText("[M-H]-")
    panel._own_molecule = molecule
    panel.own_name.setText("hexanoic acid-d3")
    panel.own_deuterium.setValue(3)
    panel.own_cuts.setValue(1)
    panel.own_losses.setValue(0)
    panel.explain_own()
    assert panel.labels_box.isVisibleTo(panel)
    assert "position" in panel.labels_text.text()
    before = len(panel._inference.positions)
    panel.labels_hetero.setChecked(True)
    assert len(panel._inference.positions) > before
    panel.own_deuterium.setValue(0)
    panel.explain_own()
    assert not panel.labels_box.isVisibleTo(panel)
    panel.deleteLater()
    app.processEvents()
