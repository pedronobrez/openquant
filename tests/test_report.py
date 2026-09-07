"""
The batch report.

A report is read once, months later, by somebody who does not have the
project. What matters is that every number in it is the number in the
results, that a missing thing says so instead of printing nothing, and that
it is built without a window so it can be checked here.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from openquant import report  # noqa: E402
from openquant.calibration import CalibrationPoint, fit  # noqa: E402
from openquant.components import Component  # noqa: E402
from openquant.quantify import PeakResult, ResultsSet  # noqa: E402
from openquant.samples import SampleEntry  # noqa: E402
from openquant.session import Session  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _session(qapp):
    session = Session()
    session.entries = [
        SampleEntry("/d/STD_L1.wiff", 0, "STD_L1", "Standard", 5.0, 1.0, ""),
        SampleEntry("/d/QC01.wiff", 0, "QC01", "Quality Control", 75.0, 2.0, "spiked"),
    ]
    session.set_components([
        Component(name="PC 34:1", precursor=760.5851, fragment=184.0733,
                  rt=11.42, rt_halfwidth=0.6, tolerance=0.02,
                  group="phosphatidylcholines", internal_standard="PC 34:1 (d7)"),
        Component(name="PC 34:1 (d7)", precursor=767.6289, fragment=184.0733,
                  rt=11.40, rt_halfwidth=0.6, tolerance=0.02,
                  is_internal_standard=True),
    ])
    return session


def _result(sample, component, **kwargs):
    row = PeakResult(sample_key=sample, sample_name=sample, component=component)
    for key, value in kwargs.items():
        setattr(row, key, value)
    return row


def test_a_report_can_be_built_without_a_window(qapp):
    """Nothing here reads a widget, so it can be generated and checked."""
    session = _session(qapp)
    document = report.build_html(session, title="A batch")
    assert document.startswith("<html>")
    assert "A batch" in document
    for section in ("Summary", "Samples", "Method", "Calibration", "Results",
                    "Statistics"):
        assert f">{section}<" in document, section


def test_the_numbers_are_the_results_numbers(qapp):
    session = _session(qapp)
    session.results = ResultsSet.from_list([])
    session.results.replace(_result("QC01", "PC 34:1", rt=11.398,
                                area=10618.25, height=47020.5, snr=2153.0,
                                area_ratio=0.4271, used=True))
    document = report.build_html(session)
    assert "11.398" in document
    assert "10,618.2" in document          # área, uma casa
    assert "0.4271" in document            # razão, quatro


def test_a_status_is_counted_whatever_its_case(qapp):
    """
    The results capitalise it. Counting in lower case made a batch with
    twenty-eight passes and two failures report that no acceptance criteria
    had been set at all.
    """
    session = _session(qapp)
    session.results = ResultsSet.from_list([])
    for index in range(3):
        session.results.replace(_result(f"S{index}", "PC 34:1", area=1.0,
                                    status="Pass"))
    session.results.replace(_result("S9", "PC 34:1", area=1.0, status="Fail"))
    document = report.build_html(session)
    assert "Pass / Marginal / Fail" in document
    assert ">3 / 0 / 1<" in document


def test_no_acceptance_criteria_is_said_rather_than_implied(qapp):
    session = _session(qapp)
    session.results = ResultsSet.from_list([])
    session.results.replace(_result("QC01", "PC 34:1", area=1.0))
    assert "no criteria set" in report.build_html(session)


def test_an_empty_section_explains_itself(qapp):
    """
    A blank space under a heading tells the reader nothing. A curve that was
    never built should say what would have built it.
    """
    session = _session(qapp)
    document = report.build_html(session)
    assert "Mark samples as Standard" in document
    assert "Nothing was integrated" in document


def test_a_calibration_is_reported_with_its_equation(qapp):
    session = _session(qapp)
    points = [CalibrationPoint(sample_key=f"STD_L{n}", sample_name=f"STD_L{n}",
                               concentration=c, response=r)
              for n, (c, r) in enumerate([(5.0, 0.06183), (20.0, 0.2566),
                                          (50.0, 0.6277)], start=1)]
    curve = fit(points, "linear", "1", "PC 34:1")
    session.calibrations["PC 34:1"] = curve
    document = report.build_html(session)
    assert "linear" in document
    assert curve.equation in document
    assert "3 of 3" in document


def test_a_name_that_looks_like_markup_is_escaped(qapp):
    """A component called <b> must not become bold text in the report."""
    session = _session(qapp)
    session.set_components([Component(name="<b>PC & 34:1</b>", precursor=1.0,
                                      fragment=1.0, rt=1.0)])
    document = report.build_html(session)
    assert "&lt;b&gt;PC &amp; 34:1&lt;/b&gt;" in document
    assert "<b>PC" not in document


def test_sections_can_be_left_out(qapp):
    """A hundred-component method makes a results section nobody prints."""
    session = _session(qapp)
    document = report.build_html(session, sections=("summary", "samples"))
    assert ">Samples<" in document
    assert ">Results<" not in document


def test_it_writes_a_pdf_that_is_a_pdf(qapp, tmp_path):
    session = _session(qapp)
    session.results = ResultsSet.from_list([])
    session.results.replace(_result("QC01", "PC 34:1", rt=11.4, area=10.0))
    path = report.write_pdf(session, tmp_path / "batch.pdf", title="Batch")
    assert os.path.getsize(path) > 1000
    with open(path, "rb") as handle:
        assert handle.read(5) == b"%PDF-"


def test_it_writes_html_that_opens_on_its_own(qapp, tmp_path):
    session = _session(qapp)
    path = report.write_html(session, tmp_path / "batch.html")
    text = open(path, encoding="utf-8").read()
    assert text.startswith("<html>")
    assert "<style>" in text          # no separate stylesheet to lose


def test_an_internal_standards_curve_is_labelled_as_meaningless(qapp):
    """
    A curve is built for anything with standards behind it, an internal
    standard included — and that one is flat by construction, because the same
    amount goes into every sample whatever the analyte's concentration. Its r²
    lands near zero and reads as a failed calibration rather than a
    meaningless one.
    """
    session = _session(qapp)
    for name in ("PC 34:1", "PC 34:1 (d7)"):
        points = [CalibrationPoint(sample_key=f"L{n}", sample_name=f"L{n}",
                                   concentration=c, response=r)
                  for n, (c, r) in enumerate([(5.0, 0.05), (20.0, 0.2),
                                              (50.0, 0.5)], start=1)]
        session.calibrations[name] = fit(points, "linear", "1", name)
    document = report.build_html(session)
    assert "flat by design" in document
    # said once, about the internal standard, not about the analyte
    assert document.count("flat by design") == 1
