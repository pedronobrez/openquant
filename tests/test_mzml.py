"""
Reading and writing mzML.

The writer exists to test the reader, so most of what is here is a round
trip. That is not enough on its own — a reader checked only against its own
writer shares every assumption with it — so the cases that come from other
people's files are built by hand: seconds instead of minutes, 32-bit arrays,
uncompressed binaries, a centroided run, numpress.
"""

import base64
import zlib

import numpy as np
import pytest

from openquant import mzml, raw
from openquant.wiff import ChannelInfo


# --------------------------------------------------------------------------- #
# a stand-in for a sample, so a round trip needs no instrument
# --------------------------------------------------------------------------- #
class FakeChannel:
    def __init__(self, index, info, times, spectra, totals=None):
        self.index, self.info = index, info
        self._times = np.asarray(times, dtype=float)
        self._spectra = spectra
        self._totals = (np.asarray(totals, dtype=float) if totals is not None
                        else np.array([float(np.sum(s[1])) for s in spectra]))

    def tic(self):
        return self._times, self._totals

    @property
    def rt(self):
        return self._times

    def spectrum(self, scan, add_zeros=True):
        return self._spectra[int(scan)]


class FakeSample:
    name = "run"
    instrument = "TripleTOF 6600"
    acquisition_time = "2026-09-06T10:00:00Z"

    def __init__(self, channels):
        self.channels = channels


def _ms1(times=(0.1, 0.2, 0.3), totals=None):
    spectra = [
        (np.array([100.1234, 264.2686, 500.5001]), np.array([10.0, 5000.0, 3.0])),
        (np.array([100.1235, 264.2687]), np.array([12.0, 6000.0])),
        (np.array([264.2686]), np.array([7000.0])),
    ]
    return FakeChannel(0, ChannelInfo(0, "TOF MS", "MS", "Positive", None,
                                      100.0, 2000.0, 3, None),
                       times, spectra, totals)


def _ms2(times=(0.1, 0.2, 0.3)):
    spectra = [
        (np.array([264.2686, 282.2791]), np.array([900.0, 300.0])),
        (np.array([264.2686]), np.array([950.0])),
        (np.array([264.2686, 282.2791]), np.array([880.0, 290.0])),
    ]
    return FakeChannel(1, ChannelInfo(1, "TOF PI", "Product Ion", "Positive",
                                      538.5188, 50.0, 550.0, 3, -35.0),
                       times, spectra)


@pytest.fixture
def written(tmp_path):
    path = tmp_path / "round-trip.mzML"
    mzml.write_mzml(FakeSample([_ms1(), _ms2()]), path)
    return path


# --------------------------------------------------------------------------- #
def test_the_channels_come_back(written):
    sample = mzml.MzmlFile(written).sample(0)
    assert len(sample.channels) == 2
    ms1, ms2 = sample.channels
    assert ms1.info.is_ms1
    assert ms2.info.precursor == pytest.approx(538.5188)
    assert ms2.info.collision_energy == pytest.approx(-35.0)
    assert ms2.info.start_mass == pytest.approx(50.0)
    assert ms2.info.end_mass == pytest.approx(550.0)


def test_the_spectra_come_back_unchanged(written):
    sample = mzml.MzmlFile(written).sample(0)
    for index, source in enumerate((_ms1(), _ms2())):
        for scan in range(3):
            want_mz, want_intensity = source.spectrum(scan)
            got_mz, got_intensity = sample.channels[index].spectrum(scan)
            assert np.array_equal(got_mz, want_mz)
            assert np.array_equal(got_intensity, want_intensity)


def test_the_instruments_own_totals_are_kept_not_recomputed(tmp_path):
    """
    The total ion current is the detector's number, not a sum of the points.

    A profile spectrum is stored with its zeros stripped out, so adding up
    what is left is not what the instrument reported — on a real acquisition
    the difference moved every integrated area by about two per cent.
    """
    reported = [12345.5, 999.25, 0.0]
    path = tmp_path / "totals.mzML"
    mzml.write_mzml(FakeSample([_ms1(totals=reported)]), path)
    _, values = mzml.MzmlFile(path).sample(0).channels[0].tic()
    assert np.array_equal(values, np.array(reported))


def test_a_scan_with_nothing_in_it_is_not_mistaken_for_a_missing_total(tmp_path):
    """
    A total of zero is a measurement. Reading it as absence made the whole
    channel fall back to summing the stored points, which is a different
    number — and it happened on three of five real acquisitions.
    """
    path = tmp_path / "zero.mzML"
    mzml.write_mzml(FakeSample([_ms1(totals=[0.0, 0.0, 4242.0])]), path)
    file = mzml.MzmlFile(path)
    assert all(h.total_ion_current is not None for h in file.headers)
    _, values = file.sample(0).channels[0].tic()
    assert np.array_equal(values, np.array([0.0, 0.0, 4242.0]))


def test_retention_times_survive_to_the_last_digit(tmp_path):
    times = [0.123456789012, 1.9999999999, 21.431166666667]
    path = tmp_path / "times.mzML"
    mzml.write_mzml(FakeSample([_ms1(times=times)]), path)
    got, _ = mzml.MzmlFile(path).sample(0).channels[0].tic()
    assert np.array_equal(got, np.array(times))


def test_the_whole_run_can_be_summed(written):
    sample = mzml.MzmlFile(written).sample(0)
    times, total = sample.tic()
    assert times.size == 3
    assert total.sum() > 0


def test_an_extracted_chromatogram_sums_the_window(written):
    sample = mzml.MzmlFile(written).sample(0)
    _, values = sample.channels[1].xic(264.2686, 0.02)
    assert np.array_equal(values, np.array([900.0, 950.0, 880.0]))


def test_the_file_says_where_it_came_from(written):
    sample = mzml.MzmlFile(written).sample(0)
    meta = sample.metadata()
    assert meta["Format"] == "mzML"
    assert meta["Instrument"] == "TripleTOF 6600"
    assert sample.acquisition_time == "2026-09-06T10:00:00Z"


# --------------------------------------------------------------------------- #
# files written by somebody else
# --------------------------------------------------------------------------- #
def _hand_written(tmp_path, *, spectrum_body: str, name="other.mzML") -> str:
    path = tmp_path / name
    path.write_text(
        '<?xml version="1.0"?>\n'
        '<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0" id="x">'
        '<run id="x"><spectrumList count="1">'
        + spectrum_body +
        "</spectrumList></run></mzML>"
    )
    return str(path)


def _binary(values, *, bits=64, compress=False):
    fmt = "<f8" if bits == 64 else "<f4"
    raw_bytes = np.asarray(values, dtype=fmt).tobytes()
    if compress:
        raw_bytes = zlib.compress(raw_bytes)
    return base64.b64encode(raw_bytes).decode()


def _array_xml(values, accession, name, *, bits=64, compress=False):
    encoding = ('<cvParam accession="MS:1000523" name="64-bit float" value=""/>'
                if bits == 64 else
                '<cvParam accession="MS:1000521" name="32-bit float" value=""/>')
    compression = ('<cvParam accession="MS:1000574" name="zlib compression" value=""/>'
                   if compress else
                   '<cvParam accession="MS:1000576" name="no compression" value=""/>')
    return (
        "<binaryDataArray>" + encoding + compression
        + f'<cvParam accession="{accession}" name="{name}" value=""/>'
        + f"<binary>{_binary(values, bits=bits, compress=compress)}</binary>"
        + "</binaryDataArray>"
    )


def test_seconds_are_converted_to_minutes(tmp_path):
    """
    ProteoWizard writes minutes from one vendor and seconds from another, and
    the unit is in the file. Reading the number without it turns a twenty
    minute run into a twenty hour one.
    """
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="1">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<scanList count="1"><scan>'
        '<cvParam accession="MS:1000016" name="scan start time" value="90.0"'
        ' unitAccession="UO:0000010" unitName="second"/>'
        "</scan></scanList><binaryDataArrayList count=\"2\">"
        + _array_xml([100.0], "MS:1000514", "m/z array")
        + _array_xml([5.0], "MS:1000515", "intensity array")
        + "</binaryDataArrayList></spectrum>"
    )
    file = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body))
    assert file.headers[0].rt == pytest.approx(1.5)


@pytest.mark.parametrize("bits,compress", [(64, False), (32, False),
                                           (64, True), (32, True)])
def test_every_combination_of_width_and_compression(tmp_path, bits, compress):
    masses = [100.5, 200.25, 300.125]
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="3">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<binaryDataArrayList count="2">'
        + _array_xml(masses, "MS:1000514", "m/z array", bits=bits, compress=compress)
        + _array_xml([1.0, 2.0, 3.0], "MS:1000515", "intensity array",
                     bits=bits, compress=compress)
        + "</binaryDataArrayList></spectrum>"
    )
    name = f"w{bits}{'z' if compress else ''}.mzML"
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name=name)).sample(0)
    mz, intensity = sample.channels[0].spectrum(0)
    assert mz == pytest.approx(masses, rel=1e-6)
    assert intensity == pytest.approx([1.0, 2.0, 3.0], rel=1e-6)


def test_numpress_is_refused_by_name(tmp_path):
    """
    It is lossy at its usual settings. Reading it wrongly would be worse than
    not reading it, so the refusal says what to do instead.
    """
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="1">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<binaryDataArrayList count="1"><binaryDataArray>'
        '<cvParam accession="MS:1002312" name="MS-Numpress linear" value=""/>'
        '<cvParam accession="MS:1000514" name="m/z array" value=""/>'
        "<binary>AAAA</binary></binaryDataArray>"
        "</binaryDataArrayList></spectrum>"
    )
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name="np.mzML")).sample(0)
    with pytest.raises(mzml.MzmlError, match="numpress"):
        sample.channels[0].spectrum(0)


def test_a_truncated_array_is_an_error_not_a_short_spectrum(tmp_path):
    """The file says how many points there are; silently returning fewer
    would put a spectrum with holes into an identification."""
    body = (
        '<spectrum index="0" id="scan=1" defaultArrayLength="5">'
        '<cvParam accession="MS:1000511" name="ms level" value="1"/>'
        '<binaryDataArrayList count="2">'
        + _array_xml([100.0, 200.0], "MS:1000514", "m/z array")
        + _array_xml([1.0, 2.0], "MS:1000515", "intensity array")
        + "</binaryDataArrayList></spectrum>"
    )
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name="short.mzML")).sample(0)
    with pytest.raises(mzml.MzmlError, match="declares 5 points"):
        sample.channels[0].spectrum(0)


def test_channels_are_inferred_when_nothing_records_them(tmp_path):
    """
    Another vendor's file has no idea of an experiment. Scans that share an
    MS level, a precursor and a mass range came from the same entry in the
    method, and that is all there is to go on.
    """
    def spectrum(index, level, precursor=None):
        precursor_xml = ""
        if precursor is not None:
            precursor_xml = (
                "<precursorList count=\"1\"><precursor><selectedIonList "
                "count=\"1\"><selectedIon>"
                f'<cvParam accession="MS:1000744" name="selected ion m/z" '
                f'value="{precursor}"/>'
                "</selectedIon></selectedIonList></precursor></precursorList>"
            )
        return (
            f'<spectrum index="{index}" id="scan={index}" defaultArrayLength="1">'
            f'<cvParam accession="MS:1000511" name="ms level" value="{level}"/>'
            '<scanList count="1"><scan>'
            f'<cvParam accession="MS:1000016" name="scan start time" '
            f'value="{index * 0.1}" unitName="minute"/>'
            "</scan></scanList>" + precursor_xml
            + '<binaryDataArrayList count="2">'
            + _array_xml([100.0], "MS:1000514", "m/z array")
            + _array_xml([1.0], "MS:1000515", "intensity array")
            + "</binaryDataArrayList></spectrum>"
        )

    body = "".join([spectrum(0, 1), spectrum(1, 2, 500.1), spectrum(2, 1),
                    spectrum(3, 2, 500.1), spectrum(4, 2, 600.2)])
    sample = mzml.MzmlFile(_hand_written(tmp_path, spectrum_body=body,
                                         name="infer.mzML")).sample(0)
    assert len(sample.channels) == 3
    assert [len(c._headers) for c in sample.channels] == [2, 2, 1]
    assert sample.channels[0].info.is_ms1
    assert sample.channels[1].info.precursor == pytest.approx(500.1)
    assert sample.channels[2].info.precursor == pytest.approx(600.2)


def test_a_file_that_is_not_mzml_says_so(tmp_path):
    path = tmp_path / "not.mzML"
    path.write_text("this is not a mass spectrum")
    with pytest.raises(mzml.MzmlError, match="does not look like mzML"):
        mzml.MzmlFile(path)


# --------------------------------------------------------------------------- #
# choosing a reader
# --------------------------------------------------------------------------- #
def test_the_dispatcher_knows_both_formats():
    assert raw.format_of("a.wiff") == "SCIEX"
    assert raw.format_of("a.mzML") == "mzML"
    assert raw.format_of("a.MZML") == "mzML"
    assert raw.is_supported("b.mzml")
    assert not raw.is_supported("b.raw")


def test_an_unknown_extension_says_what_is_supported():
    with pytest.raises(raw.UnsupportedFormat, match="wiff"):
        raw.format_of("acquisition.raw")


def test_opening_mzml_needs_no_dotnet(written):
    """
    The SCIEX reader starts a .NET runtime on import. Someone working with
    mzML alone should not need one, so the dispatcher must not reach for it.
    """
    file = raw.open_raw(written)
    assert isinstance(file, mzml.MzmlFile)
    file.close()


def test_the_run_total_is_summed_by_cycle_not_by_time(tmp_path):
    """
    The experiments of one cycle are measured one after another, so no two
    share a time. Summing on the union of all the times gives one point per
    spectrum — a comb, not a chromatogram — and it is not what the instrument
    reports either. Channels with the same number of cycles belong to the same
    period and are summed cycle by cycle.
    """
    fast = np.array([0.10, 0.20, 0.30, 0.40])
    slow = np.array([0.15, 0.35])
    channels = [
        FakeChannel(0, ChannelInfo(0, "TOF MS", "MS", "Positive", None,
                                   100.0, 2000.0, 4, None),
                    fast, [(np.array([100.0]), np.array([1.0]))] * 4,
                    totals=[10.0, 20.0, 30.0, 40.0]),
        FakeChannel(1, ChannelInfo(1, "TOF PI", "Product Ion", "Positive",
                                   500.0, 50.0, 550.0, 4, -30.0),
                    fast + 0.01, [(np.array([100.0]), np.array([1.0]))] * 4,
                    totals=[1.0, 2.0, 3.0, 4.0]),
        FakeChannel(2, ChannelInfo(2, "TOF PI", "Product Ion", "Positive",
                                   600.0, 50.0, 650.0, 2, -30.0),
                    slow, [(np.array([100.0]), np.array([1.0]))] * 2,
                    totals=[100.0, 200.0]),
    ]
    path = tmp_path / "periods.mzML"
    mzml.write_mzml(FakeSample(channels), path)
    times, total = mzml.MzmlFile(path).sample(0).tic()

    # four cycles of the fast period plus two of the slow one, in time order
    assert times.size == 6
    assert np.array_equal(times, np.array([0.10, 0.15, 0.20, 0.30, 0.35, 0.40]))
    # the fast period's two channels are added cycle by cycle; the slow one
    # keeps its own times
    assert np.array_equal(total, np.array([11.0, 100.0, 22.0, 33.0, 200.0, 44.0]))


# --------------------------------------------------------------------------- #
# the acquisition cycle
# --------------------------------------------------------------------------- #
def test_a_repeating_method_is_split_by_position_in_the_cycle():
    """
    Two entries of a method can agree on every property mzML records. On a
    real 81-channel acquisition, grouping by MS level, precursor, collision
    energy and mass range alone gave 69 channels: a panel ran some transitions
    twice at different points in the cycle. The order of acquisition is what
    separates them, and mzML does keep that.
    """
    cycle = ["ms1", "a", "b", "a"]          # "a" twice, at positions 1 and 3
    keys = cycle * 8
    positions = mzml.acquisition_cycles(keys)
    assert all(p is not None for p in positions)
    assert len(set(positions)) == 4, "four entries, not three"
    # the two "a" entries are told apart
    a_positions = {p for p, k in zip(positions, keys) if k == "a"}
    assert len(a_positions) == 2


def test_two_periods_are_found_one_after_the_other():
    """
    A method runs in periods and each has its own cycle. The acquisition this
    was checked against is a cycle of 44 run 339 times followed by a cycle of
    37 run 238 times — and 44 + 37 is exactly the 81 channels the vendor's own
    file declares.
    """
    keys = ["p", "q"] * 10 + ["x", "y", "z"] * 10
    positions = mzml.acquisition_cycles(keys)
    periods = {p[0] for p in positions if p is not None}
    assert periods == {0, 1}
    assert len({p for p in positions if p is not None}) == 5   # 2 + 3


def test_an_acquisition_stopped_mid_cycle_keeps_its_last_scans():
    keys = ["a", "b", "c"] * 6 + ["a", "b"]
    positions = mzml.acquisition_cycles(keys)
    assert all(p is not None for p in positions)
    assert positions[-2:] == [(0, 0), (0, 1)]


def test_data_dependent_acquisition_has_no_cycle_and_says_so():
    """
    DDA picks its precursors from the last survey scan, so nothing repeats.
    Reporting a cycle there would invent channels; the properties of the scans
    are all there is, and the caller falls back to them.
    """
    keys = ["ms1", "p1", "p2", "ms1", "p3", "p4", "ms1", "p5", "p6",
            "ms1", "p7", "p8"]
    assert all(p is None for p in mzml.acquisition_cycles(keys))


def test_a_short_run_is_not_mistaken_for_a_cycle():
    """Two stretches that happen to match are a coincidence, not a method."""
    assert all(p is None for p in mzml.acquisition_cycles(["a", "b", "a", "b"]))
