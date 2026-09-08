"""
A response floor an internal standard declares, and everything that reads it.

The batch could not derive one — measured, its precision did not track its
response — and signal-to-noise cannot stand in for one on a scheduled
acquisition. So the method declares it, and four places have to honour the
declaration: the control chart, the acceptance of every row normalised
against the standard, the method check, and the CSV the method travels in.
"""

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openquant.components import Component, load_components, save_components  # noqa: E402
from openquant.health import WARNING, check_method  # noqa: E402
from openquant.method import ProcessingMethod  # noqa: E402
from openquant.qc import MIN_SNR, batch_qc, control_chart  # noqa: E402
from openquant.quantify import PeakResult, ResultsSet, evaluate_acceptance  # noqa: E402
from openquant.samples import SampleEntry  # noqa: E402


def _entries(n=8):
    return [SampleEntry(f"/d/S{i:02d}.wiff", 0, f"S{i:02d}") for i in range(n)]


def _points(entries, values):
    return list(zip(entries, values))


def test_the_floor_decides_quantifiable_and_snr_no_longer_does():
    entries = _entries()
    values = [20.0, 22.0, 19.0, 21.0, 20.0, 23.0, 18.0, 20.0]
    weak = control_chart("IS", _points(entries, values), True, snr=2.0)
    assert not weak.quantifiable                      # S/N rule, no floor
    floored = control_chart("IS", _points(entries, values), True, snr=2.0, floor=15.0)
    assert floored.quantifiable and floored.floor == 15.0
    below = control_chart("IS", _points(entries, values), True, snr=500.0, floor=100.0)
    assert not below.quantifiable
    assert "below the floor of 100" in below.note


def test_injections_under_the_floor_are_listed_on_a_usable_chart():
    entries = _entries()
    values = [1000.0, 1010.0, 990.0, 40.0, 1005.0, 995.0, 1000.0, 1002.0]
    chart = control_chart("IS", _points(entries, values), True, floor=500.0)
    assert chart.quantifiable
    assert [point.sample for point in chart.below_floor] == ["S03"]
    assert control_chart("IS", _points(entries, values), True).below_floor == []


def _method(floor):
    method = ProcessingMethod()
    method.replace_all([
        Component("IS", 700.0, 184.0, rt=6.0, is_internal_standard=True,
                  min_response=floor),
        Component("A", 703.0, 184.0, rt=6.0, internal_standard="IS"),
    ])
    return method


def _results(entries, is_areas):
    results = ResultsSet()
    for entry, area in zip(entries, is_areas):
        standard = PeakResult(entry.key, entry.name, "IS")
        standard.area = area
        analyte = PeakResult(entry.key, entry.name, "A")
        analyte.area = 500.0
        analyte.internal_standard = "IS"
        analyte.is_area = area
        analyte.area_ratio = 500.0 / area
        results.results += [standard, analyte]
    return results


def test_batch_qc_passes_the_methods_floor_to_the_chart():
    entries = _entries()
    areas = [30.0, 32.0, 29.0, 31.0, 30.0, 33.0, 28.0, 30.0]
    with_floor = batch_qc(_results(entries, areas), entries, _method(100.0))
    assert with_floor.charts[0].floor == 100.0
    assert not with_floor.charts[0].quantifiable
    without = batch_qc(_results(entries, areas), entries, _method(None))
    assert without.charts[0].floor is None
    assert without.charts[0].quantifiable          # no S/N measured, no floor


def test_a_row_whose_standard_is_under_the_floor_fails_and_says_so():
    entries = _entries(2)
    method = _method(100.0)
    results = _results(entries, [500.0, 40.0])
    evaluate_acceptance(results, entries, method)
    fine = results.get(entries[0].key, "A")
    low = results.get(entries[1].key, "A")
    assert fine.status == "Pass" and fine.flags == []
    assert low.status == "Fail"
    assert low.flags == ["IS 40 below its floor of 100"]
    # the standard's own row is not judged against itself
    assert results.get(entries[1].key, "IS").flags == []


def test_without_a_floor_the_acceptance_says_nothing_about_the_standard():
    entries = _entries(2)
    results = _results(entries, [500.0, 40.0])
    evaluate_acceptance(results, entries, _method(None))
    assert results.get(entries[1].key, "A").status == ""


def test_check_method_warns_of_a_standard_with_no_floor():
    health = check_method(_method(None))
    finding = next(f for f in health.findings
                   if f.check == "internal standard without a response floor")
    assert finding.severity == WARNING and finding.components == ["IS"]
    assert "signal-to-noise" in finding.detail and f"{MIN_SNR:g}" == "10"
    assert not any(f.check == "internal standard without a response floor"
                   for f in check_method(_method(100.0)).findings)
    # a standard nothing points at is nobody's floor to declare
    lonely = ProcessingMethod()
    lonely.replace_all([Component("IS", 700.0, 184.0, is_internal_standard=True)])
    assert not any(f.check == "internal standard without a response floor"
                   for f in check_method(lonely).findings)


def test_the_floor_travels_through_the_csv_and_the_project(tmp_path):
    method = _method(2500.0)
    path = tmp_path / "m.csv"
    save_components(path, method.components)
    header = path.read_text().splitlines()[0]
    assert "min_response" in header
    loaded = load_components(path)
    assert loaded[0].min_response == 2500.0 and loaded[1].min_response is None
    path.write_text("name,precursor,piso_resposta\nIS,700.0,1200\n")
    assert load_components(path)[0].min_response == 1200.0
    again = ProcessingMethod.from_dict(method.to_dict())
    assert again.components[0].min_response == 2500.0


def test_the_method_table_edits_the_floor():
    from PyQt6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from openquant.session import Session
    from openquant.ui.method_workspace import COL, MethodWorkspace

    session = Session()
    session.method = _method(None)
    workspace = MethodWorkspace(session)
    workspace.reload()
    assert workspace.table.item(0, COL["Min. response"]).text() == ""
    workspace.table.item(0, COL["Min. response"]).setText("1500")
    workspace._commit()
    assert session.method.components[0].min_response == 1500.0
    workspace.deleteLater()
    app.processEvents()
