"""
The per-compound report for a direct infusion.

What matters here is the verdict. It is the only part of the document that
makes a claim, and the claim it is allowed to make is arithmetic: it sums the
checks that were run and says nothing about the ones that were not. So most
of what follows constructs a report with one thing checked, or none, and
reads the sentences back.

The rest is the shape of the document — the header from the file rather than
from the file name, the picture actually embedded, the tables present — and
the printed side, which is opened as a PDF because nothing about pagination
is visible in the HTML.
"""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from openquant import audit, infusion_report as ir  # noqa: E402
from openquant.explain import explain_formula, formula_ions  # noqa: E402
from openquant.library import (SpectralLibrary,  # noqa: E402
                               entry_from_spectrum)
from openquant.precursor import MIN_INTENSITY  # noqa: E402
from openquant.samples import SampleEntry  # noqa: E402
from openquant.session import Session  # noqa: E402
from openquant.wiff import ChannelInfo  # noqa: E402

FORMULA = "C20H34O2"
ADDUCT = "[M+H]+"
#: a mass the formula does not predict, to be left unexplained
STRAY = 150.1000


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _ions(max_losses: int = 2) -> list[float]:
    """The formula's ions, the intact one first — which is the precursor.

    Sorted rather than taken in the order they are generated: `formula_ions`
    returns them by mass, so `ions[0]` meant the smallest loss ion and every
    fixture built on it was isolating a fragment.
    """
    ions = formula_ions(FORMULA, ADDUCT, max_losses=max_losses)
    ions.sort(key=lambda ion: (len(ion.losses), -ion.mz))
    return [ion.mz for ion in ions]


def _grid(centres, width: float = 0.05, step: float = 0.005) -> np.ndarray:
    """A profile axis with points only around the masses that matter."""
    return np.unique(np.concatenate(
        [np.arange(c - width, c + width + step / 2, step) for c in centres]))


def _profile(mz: np.ndarray, peaks: dict[float, float]) -> np.ndarray:
    """Gaussian humps of the given heights at the given masses."""
    out = np.zeros(mz.size)
    for centre, height in peaks.items():
        out += height * np.exp(-0.5 * ((mz - centre) / 0.008) ** 2)
    return out


class FakeChannel:
    """Enough of `wiff.Channel` for the report: a TIC and an average."""

    def __init__(self, index: int, mz, peaks: dict, precursor=None,
                 collision_energy=20.0, n: int = 160, name="TOF PI"):
        self.index = index
        self.mz = np.asarray(mz, dtype=float)
        self._peaks = dict(peaks)
        self._rt = np.linspace(0.0, 1.5, n)
        self._y = np.full(n, 50_000.0)
        self.info = ChannelInfo(
            index=index, name=name,
            experiment_type="Product" if precursor else "TOF MS",
            polarity="Positive", precursor=precursor,
            start_mass=float(self.mz[0]), end_mass=float(self.mz[-1]),
            n_scans=n,
            collision_energy=collision_energy if precursor else None)

    def tic(self):
        return self._rt, self._y

    @property
    def rt(self):
        return self._rt

    def spectrum(self, scan, add_zeros=True):
        return self.mz, _profile(self.mz, self._peaks)

    def spectrum_rt_range(self, rt_start, rt_end, add_zeros=True):
        return self.mz, _profile(self.mz, self._peaks)

    def scan_at_rt(self, rt):
        return int(np.argmin(np.abs(self._rt - rt)))

    def rt_at_scan(self, scan):
        return float(self._rt[int(np.clip(scan, 0, self._rt.size - 1))])

    def scans_in_range(self, rt_start, rt_end):
        return 0, self._rt.size - 1

    def bpc(self, *args, **kwargs):
        return self._rt, self._y

    def xic(self, mz, tolerance=0.02, unit="Da"):
        return self._rt, self._y

    def xic_range(self, mz_lo, mz_hi):
        return self._rt, self._y

    def parameters(self):
        return {}


class FakeSample:
    instrument = "ZenoTOF 7600"
    acquisition_time = "2026-09-09T09:00:00Z"
    problem = None

    def __init__(self, channels, name="mix1"):
        self.channels = channels
        self.name = name

    def tic(self):
        rt = self.channels[0].rt
        return rt, np.sum([c.tic()[1] for c in self.channels], axis=0)

    def metadata(self):
        return {"Sample": self.name}


def _entry(name="TESTOL_infusion_A", survives=True, energy=20.0,
           with_survey=False, stray_only=False):
    """
    One infused standard.

    `survives` puts the precursor in the product-ion spectrum; without it
    the window holds a tenth of `MIN_INTENSITY`, which is what a precursor
    fragmented away looks like and what the report must not call a mass.
    """
    ions = _ions()
    precursor = ions[0]
    peaks = {ions[1]: 4_000.0, ions[2]: 2_000.0, STRAY: 900.0}
    if stray_only:
        peaks = {STRAY: 900.0}
    peaks[precursor] = 9_000.0 if survives else MIN_INTENSITY / 10.0
    mz = _grid(list(peaks))
    channels = []
    if with_survey:
        channels.append(FakeChannel(0, mz, {precursor: 30_000.0},
                                    precursor=None, name="TOF MS"))
    channels.append(FakeChannel(len(channels), mz, peaks, precursor=precursor,
                                collision_energy=energy))
    entry = SampleEntry(f"/d/{name}.wiff", 0, name)
    entry.sample = FakeSample(channels, name=name)
    return entry, channels[-1]


def _explanation(entry, channel):
    mz, intensity = channel.spectrum_rt_range(0.0, 1.5)
    from openquant.explain import significant_peaks
    from openquant.processing import centroid_spectrum

    cmz, cit = centroid_spectrum(mz, intensity)
    return explain_formula(FORMULA, ADDUCT, significant_peaks(cmz, cit),
                           name="Testol")


def _library(entry, channel, energy=45.0):
    from openquant.processing import centroid_spectrum

    mz, intensity = channel.spectrum_rt_range(0.0, 1.5)
    cmz, cit = centroid_spectrum(mz, intensity)
    record = entry_from_spectrum(
        "Testol reference", cmz, cit, precursor=channel.info.precursor,
        precursor_type=ADDUCT, formula=FORMULA, collision_energy=energy,
        comment="TESTOL_infusion_A · TOF PI · average of whole run · "
                "added 2026-09-10")
    library = SpectralLibrary([record], path="/d/own.msp")
    hits = library.search(cmz, cit, channel.info.precursor,
                          precursor_tolerance=0.05)
    return library, hits[0]


# --------------------------------------------------------------------------- #
# the header
# --------------------------------------------------------------------------- #
def test_the_header_comes_from_the_file_not_from_the_file_name(qapp):
    entry, channel = _entry()
    report = ir.report_for(entry, channel)

    assert report.compound == "TESTOL"          # the name's prefix
    assert report.file == "TESTOL_infusion_A.wiff"
    assert report.instrument == "ZenoTOF 7600"
    assert report.polarity == "Positive"
    assert report.written_precursor == pytest.approx(_ions()[0])
    assert report.collision_energy == pytest.approx(20.0)
    assert report.scans == 160
    assert report.rt_range == (pytest.approx(0.0), pytest.approx(1.5))
    assert report.verdict is not None and report.verdict.infusion
    # the whole run, averaged, with its peaks above the label floor
    assert report.base_peak()[0] == pytest.approx(_ions()[0], abs=0.01)
    assert 1 <= len(report.peaks()) <= ir.PEAKS_LISTED


def test_a_compound_is_the_part_of_the_name_before_the_conditions():
    assert ir.compound_of("CA-d4_TOFMSMS_Mix1") == "CA-d4"
    assert ir.compound_of("CA-d4_TOFMSMS_EAD_22CE.wiff") == "CA-d4"
    assert ir.compound_of("TDCA-d4 EAD 22") == "TDCA-d4"
    assert ir.compound_of("") == ""


# --------------------------------------------------------------------------- #
# the verdict — one sentence per check, and none for a check not run
# --------------------------------------------------------------------------- #
def test_nothing_run_says_so_rather_than_saying_nothing(qapp):
    entry, channel = _entry()
    report = ir.report_for(entry, channel, measure_precursor=False)

    assert len(report.sentences()) == 1
    assert "Nothing was checked" in report.sentences()[0]
    assert "no library was searched" in report.sentences()[0]


def test_a_precursor_that_survives_is_confirmed_with_its_error(qapp):
    entry, channel = _entry(survives=True)
    report = ir.report_for(entry, channel)

    assert report.survivor is not None
    assert report.error_ppm() == pytest.approx(0.0, abs=20.0)
    said = report.sentences()[0]
    assert said.startswith("Precursor confirmed at")
    assert "product-ion scan itself" in said
    assert "no survey scan" in said


def test_a_precursor_fragmented_away_is_not_confirmed_and_says_why(qapp):
    entry, channel = _entry(survives=False)
    report = ir.report_for(entry, channel)

    assert report.survivor is None
    assert report.error_ppm() is None
    said = report.sentences()[0]
    assert said.startswith("Precursor not confirmed:")
    assert "too little of the precursor survives" in said
    # the height it did find, so a reader can judge the refusal
    assert f"{MIN_INTENSITY:,.0f} counts" in said


def test_a_survey_scan_is_preferred_to_the_product_ion_scan(qapp):
    entry, channel = _entry(with_survey=True)
    report = ir.report_for(entry, channel)

    assert report.measurement is not None and report.measurement.found
    assert report.survivor is None            # not needed, so not taken
    assert "the survey scan puts" in report.sentences()[0]


def test_the_fragments_are_counted_against_what_was_predicted(qapp):
    entry, channel = _entry()
    explanation = _explanation(entry, channel)
    report = ir.report_for(entry, channel, explanation=explanation,
                           basis="the precursor and its losses",
                           measure_precursor=False)

    assert explanation.predicted > explanation.matched > 0
    said = [s for s in report.sentences() if "ions predicted" in s]
    assert len(said) == 1
    assert f"of the {explanation.predicted} ions predicted" in said[0]
    # the stray mass the formula cannot reach is named as unexplained
    assert "not accounted for" in said[0]
    assert any(abs(mz - STRAY) < 0.01 for mz, _h in report.unexplained())


def test_a_library_hit_is_summed_with_both_its_scores(qapp):
    entry, channel = _entry()
    library, hit = _library(entry, channel, energy=20.0)
    report = ir.report_for(entry, channel, hit=hit, library="own.msp",
                           measure_precursor=False)

    said = [s for s in report.sentences() if "library record" in s]
    assert len(said) == 1
    assert "Testol reference" in said[0]
    assert f"score {hit.score * 100:.0f}" in said[0]
    assert f"reverse {hit.reverse * 100:.0f}" in said[0]
    # the record was made at this energy, so nothing is said about energy
    assert report.energy_gap() is None
    assert not [s for s in report.sentences() if "Collision energy differs" in s]


def test_an_energy_the_record_was_not_taken_at_is_said_so(qapp):
    entry, channel = _entry(energy=12.0)
    _library_, hit = _library(entry, channel, energy=45.0)
    report = ir.report_for(entry, channel, hit=hit, measure_precursor=False)

    assert report.energy_gap() == (12.0, 45.0)
    said = [s for s in report.sentences() if "Collision energy differs" in s]
    assert len(said) == 1
    assert "12 against 45 eV" in said[0]
    assert "not necessarily the compound" in said[0]


def test_the_verdict_never_passes_or_fails_the_compound(qapp):
    entry, channel = _entry()
    explanation = _explanation(entry, channel)
    _library_, hit = _library(entry, channel)
    report = ir.report_for(entry, channel, explanation=explanation, hit=hit)

    text = " ".join(report.sentences()).lower()
    for word in ("pass", "fail", "confirmed identity", "identified as"):
        assert word not in text.replace("not confirmed", ""), word
    assert len(report.sentences()) >= 3


# --------------------------------------------------------------------------- #
# other infusions of the same compound
# --------------------------------------------------------------------------- #
def test_another_infusion_is_scored_against_this_one(qapp):
    entry, channel = _entry(name="TESTOL_infusion_A")
    other, other_channel = _entry(name="TESTOL_infusion_B")
    report = ir.report_for(entry, channel, others=[(other, other_channel)],
                           measure_precursor=False)

    assert len(report.compared) == 1
    compared = report.compared[0]
    assert compared.label == "TESTOL_infusion_B"
    # the same spectrum twice, so it matches itself exactly
    assert compared.score == pytest.approx(1.0, abs=1e-6)
    assert compared.reverse == pytest.approx(1.0, abs=1e-6)
    assert compared.matched == compared.of_other > 0
    assert "160 scans" in compared.note
    assert len(compared.comparison.traces) == 2


def test_a_different_compound_scores_lower_than_the_same_one(qapp):
    entry, channel = _entry(name="TESTOL_infusion_A")
    same, same_channel = _entry(name="TESTOL_infusion_B")
    other, other_channel = _entry(name="OTHEROL_infusion", stray_only=True)
    report = ir.report_for(entry, channel,
                           others=[(same, same_channel),
                                   (other, other_channel)],
                           measure_precursor=False)

    by_name = {c.label: c for c in report.compared}
    assert by_name["OTHEROL_infusion"].score < by_name["TESTOL_infusion_B"].score


# --------------------------------------------------------------------------- #
# the document
# --------------------------------------------------------------------------- #
def test_the_html_carries_its_picture_and_its_tables(qapp):
    entry, channel = _entry()
    explanation = _explanation(entry, channel)
    _library_, hit = _library(entry, channel, energy=45.0)
    report = ir.report_for(entry, channel, explanation=explanation, hit=hit,
                           library="own.msp")
    document = ir.build_html(report)

    assert document.startswith("<!DOCTYPE html>")
    assert "TESTOL — direct infusion" in document
    # the drawing is inside the file, not a path into somebody's home
    assert document.count("data:image/png;base64,") >= 2
    for heading in ("What was measured", "Averaged spectrum",
                    "Structural explanation", "Peaks it does not account for",
                    "Library — Testol reference", "Where the record came from"):
        assert heading in document, heading
    # the record's provenance, as it was written
    assert "added 2026-09-10" in document
    assert "Collision_energy" in document
    # the header, from the file
    assert "ZenoTOF 7600" in document and "Positive" in document
    # and no verdict of the kind this report refuses to give
    assert "PASS" not in document and "FAIL" not in document


def test_a_report_with_nothing_run_is_the_spectrum_and_says_so(qapp):
    entry, channel = _entry()
    report = ir.report_for(entry, channel, measure_precursor=False)
    document = ir.build_html(report)

    assert "Nothing was checked" in document
    assert "Structural explanation" not in document
    assert "Library —" not in document
    assert "Other infusions" not in document


def test_it_writes_a_pdf_that_is_a_pdf(qapp, tmp_path):
    entry, channel = _entry()
    explanation = _explanation(entry, channel)
    _library_, hit = _library(entry, channel)
    report = ir.report_for(entry, channel, explanation=explanation, hit=hit)
    path = ir.write_pdf(report, tmp_path / "infusion.pdf")

    assert os.path.exists(path)
    with open(path, "rb") as handle:
        assert handle.read(5) == b"%PDF-"

    from PyQt6.QtPdf import QPdfDocument

    document = QPdfDocument(None)
    document.load(path)
    assert document.pageCount() >= 1


def test_it_writes_html_that_opens_on_its_own(qapp, tmp_path):
    entry, channel = _entry()
    report = ir.report_for(entry, channel)
    path = ir.write_html(report, tmp_path / "infusion.html")

    with open(path, encoding="utf-8") as handle:
        assert handle.read().startswith("<!DOCTYPE html>")


def test_a_batch_is_one_section_per_compound_in_one_document(qapp, tmp_path):
    first, first_channel = _entry(name="TESTOL_infusion_A")
    second, second_channel = _entry(name="OTHEROL_infusion", stray_only=True)
    reports = [ir.report_for(first, first_channel, measure_precursor=False),
               ir.report_for(second, second_channel, measure_precursor=False)]
    document = ir.build_html(reports)

    assert "Direct infusion report" in document
    assert ">1. TESTOL</h2>" in document
    assert ">2. OTHEROL</h2>" in document
    assert "Contents" in document
    # every compound after the first starts a page of its own
    assert 'class="break">2. OTHEROL' in document

    from PyQt6.QtPdf import QPdfDocument

    path = ir.write_pdf(reports, tmp_path / "every.pdf")
    document_ = QPdfDocument(None)
    document_.load(path)
    assert document_.pageCount() >= 2


def test_a_heading_is_not_left_behind_by_its_picture(qapp, tmp_path):
    """
    Qt will not split a picture, and lays a block holding one out as though
    it fitted — so the page test alone left a figure's title at the foot of
    one page and the figure at the top of the next.
    """
    from openquant.report import OBJECT_CHARACTER

    entry, channel = _entry()
    explanation = _explanation(entry, channel)
    _library_, hit = _library(entry, channel)
    report = ir.report_for(entry, channel, explanation=explanation, hit=hit)
    path = ir.write_pdf(report, tmp_path / "flow.pdf")
    assert os.path.exists(path)

    from PyQt6 import QtCore, QtGui
    from openquant import report as batch_report

    writer = QtGui.QPdfWriter(str(tmp_path / "measure.pdf"))
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
    left, top, right, bottom = batch_report.MARGINS_MM
    writer.setPageMargins(QtCore.QMarginsF(left, top, right, bottom),
                          QtGui.QPageLayout.Unit.Millimeter)
    scale = writer.resolution() / 25.4
    body = QtCore.QSizeF(
        writer.width(),
        writer.height() - batch_report.HEADER_MM * scale
        - batch_report.FOOTER_MM * scale)

    def stranded(breaks):
        document = QtGui.QTextDocument()
        document.documentLayout().setPaintDevice(writer)
        document.setHtml(ir.build_html(report, contents={}, breaks=breaks))
        document.setPageSize(body)
        return batch_report._orphan_headings(document, body.height())

    breaks: set[str] = set()
    for _ in range(ir.REFLOWS):
        left_over = stranded(breaks) - breaks
        if not left_over:
            break
        breaks |= left_over
    assert stranded(breaks) <= breaks       # everything found has been pushed
    assert OBJECT_CHARACTER == "￼"


# --------------------------------------------------------------------------- #
# the Explorer and the dialog
# --------------------------------------------------------------------------- #
def _explorer(qapp, entries):
    from openquant.ui.explorer import ExplorerWorkspace

    session = Session()
    session.entries.extend(entries)
    explorer = ExplorerWorkspace(session)
    explorer.rebuild_tree()
    return session, explorer


def test_the_action_is_offered_on_an_infusion_and_nowhere_else(qapp):
    entry, _channel = _entry()
    session, explorer = _explorer(qapp, [entry])

    assert explorer.act_inf_report.isEnabled()
    assert explorer.act_inf_reports.isEnabled()
    assert explorer.act_inf_report in explorer.build_actions()["Process"]

    explorer.deleteLater()
    qapp.processEvents()


def test_the_dialog_writes_the_report_and_records_it(qapp, tmp_path):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="TESTOL_infusion_B")
    session, explorer = _explorer(qapp, [first, second])
    from openquant.ui.infusion_report_dialog import InfusionReportDialog

    dialog = InfusionReportDialog(explorer, parent=explorer)
    # the other infusion of the same compound comes ticked
    assert dialog.list.count() == 1
    assert len(dialog.chosen()) == 1
    dialog.format_box.setCurrentText(ir_html := "HTML, one file that opens "
                                                "in a browser")
    assert dialog.format_box.currentText() == ir_html
    dialog.path_edit.setText(str(tmp_path / "one.html"))

    path = dialog.write()
    assert path is not None and os.path.exists(path)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    assert "TESTOL" in text
    assert "Other infusions of the same compound" in text

    written = session.audit.of(audit.INFUSION_REPORT)
    assert len(written) == 1
    assert written[0].target == "TESTOL"
    assert written[0].after == "one.html"
    assert "precursor" in written[0].note

    dialog.deleteLater()
    explorer.deleteLater()
    qapp.processEvents()


def test_the_dialog_reports_every_open_infusion_in_one_document(qapp, tmp_path):
    first, _c1 = _entry(name="TESTOL_infusion_A")
    second, _c2 = _entry(name="OTHEROL_infusion", stray_only=True)
    session, explorer = _explorer(qapp, [first, second])
    from openquant.ui.infusion_report_dialog import InfusionReportDialog

    dialog = InfusionReportDialog(explorer, batch=True, parent=explorer)
    assert dialog.list is None                    # nothing to compare against
    assert dialog.summary.count() == 2
    dialog.format_box.setCurrentIndex(1)          # HTML
    dialog.path_edit.setText(str(tmp_path / "every.html"))

    path = dialog.write()
    assert path is not None
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    assert ">1. TESTOL</h2>" in text and ">2. OTHEROL</h2>" in text
    assert session.audit.of(audit.INFUSION_REPORT)[0].note.startswith(
        "2 compound(s)")

    dialog.deleteLater()
    explorer.deleteLater()
    qapp.processEvents()


def test_the_dialog_refuses_a_path_it_was_not_given(qapp):
    entry, _channel = _entry()
    session, explorer = _explorer(qapp, [entry])
    from openquant.ui.infusion_report_dialog import InfusionReportDialog

    dialog = InfusionReportDialog(explorer, parent=explorer)
    dialog.path_edit.setText("")
    assert dialog.write() is None
    assert "Choose a file" in dialog.status.text()
    assert not session.audit.of(audit.INFUSION_REPORT)

    dialog.deleteLater()
    explorer.deleteLater()
    qapp.processEvents()


def test_the_dialog_names_the_page_that_explains_it(qapp):
    entry, _channel = _entry()
    session, explorer = _explorer(qapp, [entry])
    from openquant.manual import manual
    from openquant.ui.help_window import help_page_for
    from openquant.ui.infusion_report_dialog import HELP_PAGE, \
        InfusionReportDialog

    dialog = InfusionReportDialog(explorer, parent=explorer)
    assert help_page_for(dialog) == HELP_PAGE
    assert HELP_PAGE in manual().pages

    dialog.deleteLater()
    explorer.deleteLater()
    qapp.processEvents()


def test_what_the_explorer_hands_over_is_what_is_on_screen(qapp):
    entry, channel = _entry()
    session, explorer = _explorer(qapp, [entry])
    explorer.floor_spin.setValue(5.0)

    report = ir.from_explorer(explorer, measure_precursor=False)
    assert report is not None
    assert report.label_floor == pytest.approx(0.05)
    assert report.sample == "TESTOL_infusion_A"
    # the pane's own conditioned spectrum, not a second average off the disk
    on_screen = explorer._current_spectrum()
    assert report.trace.mz.size == on_screen[0].size

    explorer.deleteLater()
    qapp.processEvents()
