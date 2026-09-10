"""
Repairing a written precursor from the formula: the rows offered, the rows
ticked, what Apply writes, and what it leaves alone.

The rule under test is the one that makes the dialog safe to press: a
difference under half a dalton is one compound written to fewer places and is
ticked; a whole dalton is two different compounds and is offered unticked,
because nothing here can say whether the name or the mass is the typo.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from openquant.audit import PRECURSOR_REPAIRED
from openquant.components import Component, precursor_repairs
from openquant.quantify import PeakResult
from openquant.session import Session
from openquant.ui.method_workspace import COL, MethodWorkspace
from openquant.ui.repair_dialog import RepairPrecursorsDialog


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def method():
    """
    Four rows off the real method, and one that is right.

    `dHCer(d18:0/12:0)` is 15 ppm out and `C25:0-Ceramide` 0.26 Da — both the
    same compound written to fewer places. `LacCER(d18:1/18:1(9Z))` is exactly
    2.0000 Da out and `C18:1 Cer` 100 Da, a dropped digit. `SM(d18:1/12:0)`
    agrees and must never appear.
    """
    return [
        Component(name="dHCer(d18:0/12:0)", precursor=484.465, fragment=284.2948,
                  adduct="[M+H]+", rt=5.0),
        Component(name="C25:0-Ceramide", precursor=664.4, fragment=264.2686,
                  adduct="[M+H]+", rt=8.0),
        Component(name="LacCER(d18:1/18:1(9Z))", precursor=886.6407,
                  fragment=264.2686, adduct="[M+H]+", rt=7.0),
        Component(name="C18:1 Cer", precursor=464.4, fragment=264.2686,
                  adduct="[M+H]+", rt=6.0),
        Component(name="SM(d18:1/12:0)", precursor=647.5, fragment=184.0733,
                  adduct="[M+H]+", rt=4.0),
        # no adduct: nothing to put the formula's mass through, so nothing to
        # repair either
        Component(name="C16:0-Ceramide", precursor=1.0, fragment=264.2686),
    ]


def make(components=None):
    session = Session()
    session.set_components(components if components is not None else method())
    repairs = precursor_repairs(session.method.components)
    dialog = RepairPrecursorsDialog(session, repairs,
                                    session.method.components)
    return session, dialog


def tick(dialog, row, on=True):
    dialog.table.item(row, 0).setCheckState(
        QtCore.Qt.CheckState.Checked if on else QtCore.Qt.CheckState.Unchecked)


def named(dialog, name):
    for row, repair in enumerate(dialog.repairs):
        if repair.component.name == name:
            return row
    raise AssertionError(f"{name} is not offered")


# -- what is listed ------------------------------------------------------------ #
def test_only_the_disagreeing_rows_are_listed(qapp):
    _session, dialog = make()
    assert dialog.table.rowCount() == 4
    assert [r.component.name for r in dialog.repairs] == [
        "dHCer(d18:0/12:0)", "C25:0-Ceramide", "LacCER(d18:1/18:1(9Z))",
        "C18:1 Cer"]


def test_a_row_carries_both_masses_the_difference_and_the_window(qapp):
    _session, dialog = make()
    row = named(dialog, "dHCer(d18:0/12:0)")
    cells = [dialog.table.item(row, column).text()
             for column in range(len(dialog.COLUMNS))]
    assert cells[1] == "dHCer(d18:0/12:0)"
    assert cells[2] == "484.4650" and cells[3] == "484.4724"
    assert cells[4] == "C30H61NO3"
    assert cells[5] == "+7.4"          # mDa
    assert cells[6] == "+15.3"         # ppm
    # this row extracts on its fragment, so the window is the same either way
    # and the row says why it is worth repairing anyway
    assert cells[7] == cells[8] == "284.2748–284.3148"
    assert "the window is the fragment's and stays" in cells[9]


def test_a_row_without_a_fragment_shows_the_window_moving(qapp):
    _session, dialog = make([Component(name="dHCer(d18:0/12:0)",
                                       precursor=484.465, adduct="[M+H]+")])
    row = named(dialog, "dHCer(d18:0/12:0)")
    before = dialog.table.item(row, 7).text()
    after = dialog.table.item(row, 8).text()
    assert before != after
    assert before == "484.4450–484.4850" and after == "484.4524–484.4924"
    assert dialog.repairs[row].moves_window
    assert "the window moves with it" in dialog.table.item(row, 9).text()


# -- the pre-ticking ----------------------------------------------------------- #
def test_sub_dalton_rows_are_ticked_and_whole_dalton_rows_are_not(qapp):
    _session, dialog = make()
    ticked = {r.component.name: dialog.table.item(row, 0).checkState()
              for row, r in enumerate(dialog.repairs)}
    assert ticked["dHCer(d18:0/12:0)"] == QtCore.Qt.CheckState.Checked
    assert ticked["C25:0-Ceramide"] == QtCore.Qt.CheckState.Checked
    assert ticked["LacCER(d18:1/18:1(9Z))"] == QtCore.Qt.CheckState.Unchecked
    assert ticked["C18:1 Cer"] == QtCore.Qt.CheckState.Unchecked
    assert [r.component.name for r in dialog.selected()] == [
        "dHCer(d18:0/12:0)", "C25:0-Ceramide"]


def test_a_whole_dalton_row_can_still_be_ticked_by_hand(qapp):
    """Unticked is not disabled: the person is allowed to say which is wrong."""
    _session, dialog = make()
    row = named(dialog, "LacCER(d18:1/18:1(9Z))")
    item = dialog.table.item(row, 0)
    assert item.flags() & QtCore.Qt.ItemFlag.ItemIsUserCheckable
    tick(dialog, row)
    assert "LacCER(d18:1/18:1(9Z))" in [r.component.name for r in dialog.selected()]


def test_a_whole_dalton_row_says_it_is_a_different_compound(qapp):
    _session, dialog = make()
    row = named(dialog, "LacCER(d18:1/18:1(9Z))")
    note = dialog.table.item(row, 9).text()
    assert "2.0000 Da apart" in note and "say which" in note


# -- applying ------------------------------------------------------------------ #
def test_apply_writes_the_precursor_and_the_formula_of_a_ticked_row(qapp):
    session, dialog = make()
    dialog.apply_selected()
    repaired = session.method.by_name("dHCer(d18:0/12:0)")
    assert repaired.precursor == pytest.approx(484.4724, abs=5e-5)
    assert repaired.formula == "C30H61NO3"


def test_apply_leaves_an_unticked_row_exactly_as_it_was(qapp):
    session, dialog = make()
    dialog.apply_selected()
    for name, mass in (("LacCER(d18:1/18:1(9Z))", 886.6407),
                       ("C18:1 Cer", 464.4)):
        untouched = session.method.by_name(name)
        assert untouched.precursor == mass
        assert untouched.formula == ""


def test_apply_touches_no_row_that_was_never_offered(qapp):
    session, dialog = make()
    dialog.apply_selected()
    agreeing = session.method.by_name("SM(d18:1/12:0)")
    assert agreeing.precursor == 647.5 and agreeing.formula == ""
    assert session.method.by_name("C16:0-Ceramide").precursor == 1.0


def test_unticking_every_row_changes_nothing(qapp):
    session, dialog = make()
    for row in range(dialog.table.rowCount()):
        tick(dialog, row, on=False)
    assert dialog.apply_selected() == 0
    assert [c.precursor for c in session.method.components] == [
        484.465, 664.4, 886.6407, 464.4, 647.5, 1.0]
    assert not [e for e in session.audit if e.what == PRECURSOR_REPAIRED]
    assert dialog.summary() == "No precursor was changed."


# -- the record ---------------------------------------------------------------- #
def test_every_repair_is_one_audit_entry_naming_the_formula(qapp):
    session, dialog = make()
    dialog.apply_selected()
    entries = [e for e in session.audit if e.what == PRECURSOR_REPAIRED]
    assert len(entries) == 2
    first = entries[0]
    assert first.target == "dHCer(d18:0/12:0) · precursor"
    assert first.change == "484.465 → 484.4724"
    assert first.note.startswith("from formula C30H61NO3")
    assert "+15.3 ppm" in first.note


def test_a_whole_dalton_repair_says_so_in_the_trail(qapp):
    session, dialog = make()
    tick(dialog, named(dialog, "C18:1 Cer"))
    dialog.apply_selected()
    entry = [e for e in session.audit if e.target.startswith("C18:1 Cer")][0]
    assert entry.change == "464.4 → 564.5350"
    assert "accepted by hand" in entry.note


def test_applying_marks_the_project_and_drops_the_cached_traces(qapp):
    session, dialog = make()
    session.dirty = False
    session.cache.put(("something",), ("x", "y"))
    dialog.apply_selected()
    assert session.dirty
    assert session.cache.get(("something",)) is None


# -- from the workspace -------------------------------------------------------- #
def test_the_workspace_opens_the_dialog_over_the_table_it_shows(qapp, monkeypatch):
    session = Session()
    session.set_components(method())
    widget = MethodWorkspace(session)
    seen = {}

    def fake(self):
        seen["rows"] = self.table.rowCount()
        return self.apply_selected()

    monkeypatch.setattr(RepairPrecursorsDialog, "exec", fake)
    widget.repair_precursors()
    assert seen["rows"] == 4
    assert widget.session.method.by_name("C25:0-Ceramide").precursor == \
        pytest.approx(664.6602, abs=5e-5)
    # the table follows the method rather than keeping the old mass on screen
    assert widget.table.item(1, COL["Precursor"]).text().startswith("664.66")
    assert "2 precursor(s) repaired" in widget.status.text()


def test_a_method_that_agrees_is_told_so_and_no_dialog_opens(qapp, monkeypatch):
    session = Session()
    session.set_components([Component(name="SM(d18:1/12:0)", precursor=647.5,
                                      fragment=184.0733, adduct="[M+H]+")])
    widget = MethodWorkspace(session)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information",
                        staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(RepairPrecursorsDialog, "exec",
                        lambda self: pytest.fail("nothing to repair"))
    widget.repair_precursors()
    assert "No precursor contradicts its formula" in widget.status.text()


def test_the_refusals_dialog_offers_the_repair(qapp, monkeypatch):
    """
    Where the disagreement is found is where the way out of it is offered —
    and pressing it is a second, separate decision.
    """
    session = Session()
    session.set_components(method())
    widget = MethodWorkspace(session)
    offered = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "addButton",
        lambda self, text, role: offered.append(text) or QtWidgets.QPushButton(text))
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: None)
    monkeypatch.setattr(RepairPrecursorsDialog, "exec",
                        lambda self: pytest.fail("opened without being asked"))
    widget.fill_formulas()
    assert offered == ["Repair precursors…"]


def test_the_summary_says_which_rows_were_integrated_with_the_old_masses(qapp):
    """
    Nothing here reintegrates anything: the numbers on screen were measured
    through the windows that have just moved, and the person has to be told
    so rather than left to notice.
    """
    session, dialog = make()
    session.results.results = [
        PeakResult(sample_key="s1", sample_name="01",
                   component="dHCer(d18:0/12:0)", area=10.0),
        PeakResult(sample_key="s2", sample_name="02",
                   component="dHCer(d18:0/12:0)", area=11.0),
        PeakResult(sample_key="s1", sample_name="01",
                   component="SM(d18:1/12:0)", area=5.0),
    ]
    dialog.apply_selected()
    said = dialog.summary()
    assert "2 precursor(s) repaired" in said
    assert "2 result row(s) were integrated with the old masses" in said
    assert "process the batch again" in said
