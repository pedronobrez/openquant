"""
mzML: the open format, so data from other instruments can be read too.

mzML is what everything converts to. A Thermo .raw, an Agilent .d, a Bruker
.tdf all become mzML through ProteoWizard's msconvert, and a laboratory that
runs more than one instrument has mzML whether it wanted it or not. Reading it
is what turns this from a SCIEX viewer into something that can look at the
rest of the bench.

Two halves:

  * a reader that presents an mzML file through the same Channel and Sample
    interface as `wiff.py`, so nothing above this layer has to know which
    format it came from;
  * a writer, because a converted file that cannot be checked against its
    source is a file nobody should trust. Exporting from the .wiff reader —
    which is verified — and reading the result back is how the reader gets
    tested against something other than itself.

What mzML does not have is the notion of an experiment. A .wiff knows it holds
81 channels because the acquisition method said so; an mzML holds a flat list
of spectra and the channels have to be inferred from what distinguishes them:
MS level, precursor, collision energy, mass range. That inference is the only
guesswork in here, and it is written to be visible rather than clever.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import zlib
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import numpy as np

from .wiff import ChannelInfo

#: PSI-MS controlled vocabulary accessions this reader acts on. Anything not
#: listed is carried past without comment: an mzML written by a vendor tool
#: is full of terms that describe the instrument rather than the data.
MS_LEVEL = "MS:1000511"
SCAN_START_TIME = "MS:1000016"
SELECTED_ION_MZ = "MS:1000744"
COLLISION_ENERGY = "MS:1000045"
SCAN_WINDOW_LOWER = "MS:1000501"
SCAN_WINDOW_UPPER = "MS:1000500"
TOTAL_ION_CURRENT = "MS:1000285"
BASE_PEAK_MZ = "MS:1000504"
BASE_PEAK_INTENSITY = "MS:1000505"
POSITIVE_SCAN = "MS:1000130"
NEGATIVE_SCAN = "MS:1000129"
CENTROID_SPECTRUM = "MS:1000127"
PROFILE_SPECTRUM = "MS:1000128"

BIT_64 = "MS:1000523"
BIT_32 = "MS:1000521"
ZLIB = "MS:1000574"
NO_COMPRESSION = "MS:1000576"
MZ_ARRAY = "MS:1000514"
INTENSITY_ARRAY = "MS:1000515"
TIME_ARRAY = "MS:1000595"

#: numpress is lossy at its usual settings and is not decoded here. A file
#: that uses it is rejected by name rather than read wrongly.
NUMPRESS = {
    "MS:1002312": "linear",
    "MS:1002313": "positive integer",
    "MS:1002314": "short logged float",
}

#: how close two precursor masses must be to be counted as the same channel.
#: Vendors write the same transition with slightly different rounding from
#: scan to scan, and a channel per rounding error would be useless.
PRECURSOR_TOLERANCE = 0.01

#: our own writer records the experiment a spectrum came from, so a file this
#: application wrote reconstructs exactly rather than by inference
EXPERIMENT_PARAM = "openquant experiment"
#: and what the acquisition method called it. mzML has nowhere to put a
#: vendor's experiment name, so a converted file loses "TOF PI" and becomes
#: "MS2". Ours keeps it; anyone else's is described by its MS level, which is
#: all their file says.
EXPERIMENT_NAME_PARAM = "openquant experiment name"


class MzmlError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #
def _local(tag: str) -> str:
    """The tag without its namespace — mzML declares one and never varies it."""
    return tag.rsplit("}", 1)[-1]


def _params(element) -> dict[str, str]:
    """
    Every cvParam and userParam under an element, by accession and by name.

    Indexing both ways is deliberate: accessions are what the standard
    guarantees, names are what a hand-written file is likely to have right.
    """
    found: dict[str, str] = {}
    for child in element.iter():
        tag = _local(child.tag)
        if tag not in ("cvParam", "userParam"):
            continue
        value = child.get("value", "")
        accession = child.get("accession")
        if accession:
            found[accession] = value
        name = child.get("name")
        if name:
            found[name] = value
    return found


def _decode_array(element) -> np.ndarray:
    """One binaryDataArray, from base64 through compression to numbers."""
    params = _params(element)
    for accession, kind in NUMPRESS.items():
        if accession in params:
            raise MzmlError(
                f"this file uses numpress {kind} compression, which is lossy "
                "and is not decoded here; reconvert with "
                "--filter 'peakPicking' left off and no numpress"
            )
    binary = element.find("binary")
    if binary is None:
        binary = next((c for c in element if _local(c.tag) == "binary"), None)
    if binary is None or not (binary.text or "").strip():
        return np.zeros(0, dtype=np.float64)

    raw = base64.b64decode(binary.text)
    if ZLIB in params:
        raw = zlib.decompress(raw)
    if BIT_64 in params:
        return np.frombuffer(raw, dtype="<f8").astype(np.float64)
    if BIT_32 in params:
        return np.frombuffer(raw, dtype="<f4").astype(np.float64)
    raise MzmlError("a binary array declares neither 32- nor 64-bit floats")


def _arrays(element) -> dict[str, np.ndarray]:
    """The m/z, intensity and time arrays of one spectrum or chromatogram."""
    out: dict[str, np.ndarray] = {}
    for array in element.iter():
        if _local(array.tag) != "binaryDataArray":
            continue
        params = _params(array)
        values = _decode_array(array)
        if MZ_ARRAY in params:
            out["mz"] = values
        elif INTENSITY_ARRAY in params:
            out["intensity"] = values
        elif TIME_ARRAY in params:
            out["time"] = values
    return out


@dataclass(frozen=True)
class _ScanHeader:
    """What is known about a spectrum without decoding its arrays."""

    index: int
    offset: int
    end: int
    ms_level: int
    rt: float                       # minutes
    precursor: float | None
    collision_energy: float | None
    low: float
    high: float
    polarity: str
    centroided: bool
    total_ion_current: float | None      # None when the file does not say
    n_points: int
    experiment: int | None          # only in files this application wrote
    experiment_name: str

    @property
    def key(self) -> tuple:
        """What makes two scans belong to the same channel."""
        if self.experiment is not None:
            return ("experiment", self.experiment)
        precursor = (round(self.precursor / PRECURSOR_TOLERANCE)
                     if self.precursor is not None else None)
        return (self.ms_level, precursor,
                round(self.collision_energy, 2) if self.collision_energy else None,
                round(self.low, 1), round(self.high, 1), self.polarity)


class MzmlChannel:
    """
    One inferred experiment: the scans that share a precursor and a range.

    The same interface as `wiff.Channel`, because the workspaces above use it
    without asking where the data came from.
    """

    def __init__(self, sample: "MzmlSample", index: int,
                 headers: list[_ScanHeader]):
        self._sample = sample
        self._headers = headers
        self.index = index
        # cached here rather than with lru_cache on the method: that keeps one
        # instance alive for the life of the process, and with maxsize=1 it
        # caches nothing at all when the caller walks 81 channels in turn
        self._tic: tuple[np.ndarray, np.ndarray] | None = None
        self.info = self._read_info()

    def _read_info(self) -> ChannelInfo:
        first = self._headers[0]
        if first.experiment_name:
            name = first.experiment_name
        elif first.ms_level <= 1:
            name = "MS"
        else:
            name = f"MS{first.ms_level}"
        return ChannelInfo(
            index=self.index,
            name=name,
            experiment_type="MS" if first.ms_level <= 1 else "Product Ion",
            polarity=first.polarity,
            precursor=first.precursor,
            start_mass=first.low,
            end_mass=first.high,
            n_scans=len(self._headers),
            collision_energy=first.collision_energy,
        )

    # -- chromatograms -------------------------------------------------------- #
    def tic(self) -> tuple[np.ndarray, np.ndarray]:
        """
        The total ion current per scan.

        Taken from the cvParam the converter wrote where it exists. That is
        the number the instrument reported, and recomputing it from the arrays
        would substitute our arithmetic for the instrument's — a difference
        that shows up as a chromatogram that does not match the vendor's.
        """
        if self._tic is None:
            times = np.array([h.rt for h in self._headers], dtype=float)
            if all(h.total_ion_current is not None for h in self._headers):
                values = np.array([h.total_ion_current for h in self._headers],
                                  dtype=float)
            else:
                values = np.array([float(self._read(h)["intensity"].sum())
                                   for h in self._headers], dtype=float)
            self._tic = (times, values)
        return self._tic

    @property
    def rt(self) -> np.ndarray:
        return self.tic()[0]

    def bpc(self, mz_min: float | None = None, mz_max: float | None = None,
            tolerance: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
        lo = self.info.start_mass if mz_min is None else mz_min
        hi = self.info.end_mass if mz_max is None else mz_max
        times, values = [], []
        for header in self._headers:
            arrays = self._read(header)
            mz, intensity = arrays["mz"], arrays["intensity"]
            inside = (mz >= lo) & (mz <= hi)
            times.append(header.rt)
            values.append(float(intensity[inside].max()) if inside.any() else 0.0)
        return np.array(times), np.array(values)

    def xic(self, mz: float, tolerance: float = 0.02,
            unit: str = "Da") -> tuple[np.ndarray, np.ndarray]:
        half = mz * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        return self.xic_range(mz - half, mz + half)

    def xic_range(self, mz_min: float, mz_max: float) -> tuple[np.ndarray, np.ndarray]:
        """
        Sum the intensity inside a mass window, scan by scan.

        Every point whose mass falls inside the window, and nothing else.

        SCIEX's own extraction gives a slightly larger number, and always
        larger: a window narrow enough to be useful cuts through the sides of
        the peak it is extracting, and Clearcore2 counts some of what falls
        outside. Measured over the 81 channels of one acquisition, extracting
        each channel at its own strongest mass, the two differ by a median of
        0.58% and at most 12% of the peak height.

        What is here is a plain sum, because two attempts at reproducing the
        vendor's edge rule were tried and neither survived being tested on
        windows other than the ones it was derived from — the second was a
        coin toss, better on 41 channels and worse on 38. An invented rule
        that is wrong half the time is worse than a stated one that is
        different every time, because only the second can be corrected for.

        The rest of the file does not have this problem: spectra, the total
        ion current and chromatographic integration all round-trip exactly.
        """
        lo, hi = sorted((float(mz_min), float(mz_max)))
        times, values = [], []
        for header in self._headers:
            arrays = self._read(header)
            mz, intensity = arrays["mz"], arrays["intensity"]
            inside = (mz >= lo) & (mz <= hi)
            times.append(header.rt)
            values.append(float(intensity[inside].sum()) if inside.any() else 0.0)
        return np.array(times), np.array(values)

    # -- spectra -------------------------------------------------------------- #
    def _read(self, header: _ScanHeader) -> dict[str, np.ndarray]:
        return self._sample._file._spectrum_arrays(header)

    def spectrum(self, scan: int,
                 add_zeros: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """
        One scan.

        `add_zeros` is accepted and ignored. It exists because SCIEX strips
        zero-intensity points out of a profile spectrum and its library can
        put them back using the instrument's own step size. An mzML holds
        whatever the converter wrote and nothing that says what the step was,
        so inventing the zeros here would be inventing data.
        """
        if not self._headers:
            return np.zeros(0), np.zeros(0)
        index = int(np.clip(scan, 0, len(self._headers) - 1))
        arrays = self._read(self._headers[index])
        return arrays["mz"], arrays["intensity"]

    def spectrum_rt_range(self, rt_start: float, rt_end: float,
                          add_zeros: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """
        The average spectrum over a time range.

        Averaging profile spectra means putting them on a common mass axis
        first. The axis used is the union of the masses actually measured,
        which keeps every peak the instrument saw; a fixed bin width would
        move them.
        """
        lo, hi = sorted((float(rt_start), float(rt_end)))
        chosen = [h for h in self._headers if lo <= h.rt <= hi]
        if not chosen:
            return self.spectrum(self.scan_at_rt((lo + hi) / 2))
        if len(chosen) == 1:
            arrays = self._read(chosen[0])
            return arrays["mz"], arrays["intensity"]

        parts = [self._read(h) for h in chosen]
        axis = np.unique(np.concatenate([p["mz"] for p in parts]))
        if axis.size == 0:
            return np.zeros(0), np.zeros(0)
        total = np.zeros(axis.size, dtype=float)
        for part in parts:
            if part["mz"].size:
                total += np.interp(axis, part["mz"], part["intensity"],
                                   left=0.0, right=0.0)
        return axis, total / len(parts)

    def parameters(self) -> dict[str, str]:
        first = self._headers[0]
        out = {
            "MS level": str(first.ms_level),
            "Scans": str(len(self._headers)),
            "Mass range": f"{first.low:g} – {first.high:g}",
        }
        if first.precursor is not None:
            out["Precursor"] = f"{first.precursor:.4f}"
        if first.collision_energy is not None:
            out["Collision energy"] = f"{first.collision_energy:g}"
        out["Spectrum type"] = "centroid" if first.centroided else "profile"
        return out

    # -- positions ------------------------------------------------------------ #
    def scan_at_rt(self, rt: float) -> int:
        times = self.rt
        if times.size == 0:
            return 0
        return int(np.argmin(np.abs(times - rt)))

    def rt_at_scan(self, scan: int) -> float:
        times = self.rt
        if times.size == 0:
            return 0.0
        return float(times[int(np.clip(scan, 0, times.size - 1))])

    def scans_in_range(self, rt_start: float, rt_end: float) -> tuple[int, int]:
        lo, hi = sorted((rt_start, rt_end))
        times = self.rt
        idx = np.nonzero((times >= lo) & (times <= hi))[0]
        if idx.size == 0:
            centre = self.scan_at_rt((lo + hi) / 2)
            return centre, centre
        return int(idx[0]), int(idx[-1])

    def __repr__(self) -> str:
        return f"<MzmlChannel {self.index}: {self.info.label}>"


class MzmlSample:
    """
    One run.

    An mzML holds a single run, so a file is one sample. Where a .wiff can
    carry a whole batch in one file, a converted batch is a directory of them.
    """

    def __init__(self, file: "MzmlFile"):
        self._file = file
        self.index = 0
        self._tic: tuple[np.ndarray, np.ndarray] | None = None
        self.name = file.run_id or os.path.splitext(file.filename)[0]
        self.instrument = file.instrument
        self.channels: list[MzmlChannel] = file._build_channels(self)

    def tic(self) -> tuple[np.ndarray, np.ndarray]:
        """
        The TIC of the whole run: every channel's total, at the times it was
        actually measured.

        Summed by cycle, which is how the instrument reports it.

        The experiments of one cycle are measured one after another, so no two
        of them share a time: the union of all the channels' times is one
        point per spectrum — 23,722 of them for an acquisition whose own total
        ion chromatogram has 577. That is not a chromatogram, it is a comb.

        A method runs its experiments in periods, and every experiment of a
        period has the same number of cycles. Grouping the channels by that
        count recovers the periods, and summing a group cycle by cycle at the
        times of its first experiment gives back exactly what SCIEX reports:
        for the acquisition this was checked against, two periods of 339 and
        238 cycles, and 577 points.
        """
        if self._tic is not None:
            return self._tic
        if not self.channels:
            return np.zeros(0), np.zeros(0)
        periods: dict[int, list] = {}
        for channel in self.channels:
            times, values = channel.tic()
            periods.setdefault(times.size, []).append((times, values))

        axes, totals = [], []
        for members in periods.values():
            axis = members[0][0]
            total = np.zeros(axis.size, dtype=float)
            for _times, values in members:
                total += values
            axes.append(axis)
            totals.append(total)
        axis = np.concatenate(axes)
        total = np.concatenate(totals)
        order = np.argsort(axis, kind="stable")
        self._tic = (axis[order], total[order])
        return self._tic

    @property
    def problem(self) -> str | None:
        """An mzML is one file: nothing is beside it to go missing."""
        return None

    @property
    def acquisition_time(self) -> str:
        return self._file.start_time or ""

    def metadata(self) -> dict[str, str]:
        out = {
            "Format": "mzML",
            "Source": self._file.source_file or self._file.filename,
            "Instrument": self.instrument,
            "Channels": str(len(self.channels)),
            "Spectra": str(len(self._file.headers)),
        }
        if self._file.start_time:
            out["Acquired"] = self._file.start_time
        if self._file.software:
            out["Written by"] = self._file.software
        return out

    def __repr__(self) -> str:
        return f"<MzmlSample {self.name}: {len(self.channels)} channels>"


class MzmlFile:
    """An mzML file, presented the way `WiffFile` is."""

    def __init__(self, path: str | os.PathLike):
        self.path = os.path.realpath(str(path))
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        with open(self.path, "rb") as handle:
            self._data = handle.read()
        if b"<mzML" not in self._data[:4096] and b"<indexedmzML" not in self._data[:4096]:
            raise MzmlError(f"{self.filename} does not look like mzML")

        self.run_id = ""
        self.start_time = ""
        self.instrument = "unknown"
        self.source_file = ""
        self.software = ""
        self._read_header()
        self.headers = self._read_scan_headers()
        self.sample_names = [self.run_id or os.path.splitext(self.filename)[0]]
        self._samples: dict[int, MzmlSample] = {}

    # -- file-level metadata --------------------------------------------------- #
    def _read_header(self) -> None:
        """Everything before the spectra: who wrote it, from what, and when."""
        head = self._data[:self._data.find(b"<spectrumList")
                          if b"<spectrumList" in self._data else len(self._data)]
        for match in re.finditer(rb'<run[^>]*>', head):
            attributes = match.group(0).decode("utf-8", "replace")
            self.run_id = _attribute(attributes, "id") or self.run_id
            self.start_time = _attribute(attributes, "startTimeStamp") or self.start_time
        for match in re.finditer(rb'<sourceFile[^>]*>', head):
            attributes = match.group(0).decode("utf-8", "replace")
            self.source_file = _attribute(attributes, "name") or self.source_file
        for match in re.finditer(rb'<software[^>]*>', head):
            attributes = match.group(0).decode("utf-8", "replace")
            identifier = _attribute(attributes, "id")
            if identifier:
                self.software = identifier
        self.instrument = self._read_instrument(head) or self.instrument

    @staticmethod
    def _read_instrument(head: bytes) -> str:
        """
        The instrument model, written two different ways in the wild.

        A vendor converter names the exact model as its own CV term and leaves
        the value empty — "TripleTOF 6600", accession MS:1000932. A generic
        writer uses the parent term "instrument model" and puts the model in
        the value. Reading only one convention leaves half the files saying
        "unknown".
        """
        block = _between(head, b"<instrumentConfiguration",
                         b"</instrumentConfigurationList>")
        if not block:
            return ""
        # stop at the component list: its cvParams describe the source and the
        # detector, not the instrument
        cut = block.find(b"<componentList")
        if cut > 0:
            block = block[:cut]
        first_named = ""
        for match in re.finditer(rb"<cvParam[^>]*/?>", block):
            text = match.group(0).decode("utf-8", "replace")
            accession = _attribute(text, "accession")
            name = _attribute(text, "name")
            value = _attribute(text, "value")
            if accession == "MS:1000031" and value:
                return value
            if name and not value and not first_named:
                first_named = name
        return first_named

    # -- the scan index --------------------------------------------------------- #
    def _read_scan_headers(self) -> list[_ScanHeader]:
        """
        One pass over the file, reading each spectrum's description but not
        its arrays.

        A run of this size is tens of thousands of spectra and gigabytes of
        decoded numbers; holding them would be pointless when a chromatogram
        needs only the time and the total. The byte range of each spectrum is
        kept so the arrays can be fetched when something actually asks.
        """
        headers: list[_ScanHeader] = []
        for index, (start, stop) in enumerate(_element_ranges(self._data, b"spectrum")):
            fragment = self._data[start:stop]
            cut = fragment.find(b"<binaryDataArrayList")
            head = fragment if cut < 0 else fragment[:cut] + b"</spectrum>"
            try:
                element = ET.fromstring(head)
            except ET.ParseError:
                continue
            headers.append(self._header_of(element, index, start, stop))
        return headers

    def _header_of(self, element, index: int, start: int, stop: int) -> _ScanHeader:
        params = _params(element)
        rt = _minutes(element)
        precursor = _float_or_none(params.get(SELECTED_ION_MZ))
        ce = _float_or_none(params.get(COLLISION_ENERGY))
        low = _float_or_none(params.get(SCAN_WINDOW_LOWER))
        high = _float_or_none(params.get(SCAN_WINDOW_UPPER))
        experiment = params.get(EXPERIMENT_PARAM)
        return _ScanHeader(
            index=index,
            offset=start,
            end=stop,
            ms_level=int(float(params.get(MS_LEVEL, 1) or 1)),
            rt=rt,
            precursor=precursor,
            collision_energy=ce,
            low=low if low is not None else 0.0,
            high=high if high is not None else 0.0,
            polarity="Negative" if NEGATIVE_SCAN in params else "Positive",
            centroided=CENTROID_SPECTRUM in params,
            # not `or -1.0`: a scan with nothing in it has a total of zero,
            # which is falsy, and reading that as "missing" made a whole
            # channel fall back to summing the points instead of using the
            # totals the instrument recorded
            total_ion_current=_float_or_none(params.get(TOTAL_ION_CURRENT)),
            n_points=int(element.get("defaultArrayLength", 0) or 0),
            experiment=int(experiment) if experiment not in (None, "") else None,
            experiment_name=params.get(EXPERIMENT_NAME_PARAM, ""),
        )

    def _spectrum_arrays(self, header: _ScanHeader) -> dict[str, np.ndarray]:
        element = ET.fromstring(self._data[header.offset:header.end])
        arrays = _arrays(element)
        length = int(element.get("defaultArrayLength", 0) or 0)
        mz = arrays.get("mz", np.zeros(0))
        intensity = arrays.get("intensity", np.zeros(0))
        if length and (mz.size != length or intensity.size != length):
            raise MzmlError(
                f"spectrum {header.index} declares {length} points but decoded "
                f"{mz.size} m/z and {intensity.size} intensities"
            )
        return {"mz": mz, "intensity": intensity}

    # -- channels ---------------------------------------------------------------- #
    def _build_channels(self, sample: MzmlSample) -> list[MzmlChannel]:
        """
        Group the scans into experiments.

        mzML has no idea of an experiment; it has a list of spectra. Scans
        that share an MS level, a precursor, a collision energy and a mass
        range came from the same entry in the acquisition method — except
        when a method has two entries that agree on all of those, which is
        common enough: a panel may run the same transition twice at different
        points in the cycle. On a real 81-channel acquisition, grouping by
        those properties alone gave 69 channels.

        What separates them is the order of acquisition, which mzML does keep.
        A scheduled method runs its experiments in a fixed cycle, so the
        position of a spectrum within that cycle says which entry produced it,
        and identical entries sit at different positions. See `acquisition
        cycles` below for how the cycle is found, and for what happens when
        there is not one — data-dependent acquisition has no repeating order,
        and there the properties are all there is.
        """
        cycles = acquisition_cycles([h.key for h in self.headers])
        grouped: dict[tuple, list[_ScanHeader]] = {}
        # strict: one position per spectrum, and a mismatch would silently
        # drop the scans past the end of the shorter list
        for position, header in zip(cycles, self.headers, strict=True):
            key = header.key if position is None else position
            grouped.setdefault(key, []).append(header)
        return [MzmlChannel(sample, index, group)
                for index, group in enumerate(grouped.values())]

    # -- the same surface as WiffFile -------------------------------------------- #
    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    def sample(self, index: int = 0) -> MzmlSample:
        if index not in self._samples:
            self._samples[index] = MzmlSample(self)
        return self._samples[index]

    def close(self) -> None:
        self._data = b""

    def __repr__(self) -> str:
        return f"<MzmlFile {self.filename}: {len(self.headers)} spectra>"


# --------------------------------------------------------------------------- #
# acquisition cycles
# --------------------------------------------------------------------------- #
#: the longest cycle worth looking for. A scheduled method with more entries
#: than this in one cycle is not something this has been seen to encounter,
#: and an unbounded search over tens of thousands of spectra is slow for
#: nothing.
MAX_CYCLE = 4096

#: a cycle has to repeat at least this many times to be believed. Two
#: consecutive stretches that happen to match are a coincidence; twenty are a
#: method.
MIN_REPEATS = 4


def acquisition_cycles(keys: list) -> list:
    """
    Where each spectrum sits in the method's cycle, or None if there is no cycle.

    A scheduled acquisition runs its experiments in a fixed order and repeats
    it: this file's 23,722 spectra are a cycle of 44 experiments run 339
    times, followed by a cycle of 37 run 238 times — 44 + 37 being exactly the
    81 channels the vendor's own file declares. Position in the cycle is
    therefore the experiment, and it separates two entries that a method
    happens to have given identical settings.

    Returns a list the same length as `keys`, each item either
    (period, position) or None where no cycle was found. Data-dependent
    acquisition chooses its precursors from the last survey scan, so nothing
    repeats and everything comes back None, which leaves the caller to group
    by the properties of the scans as before.
    """
    total = len(keys)
    positions: list = [None] * total
    start, period = 0, 0
    while start < total:
        length, end = _cycle_at(keys, start, total)
        if length is None:
            # no cycle from here on: leave the rest ungrouped by position
            break
        for index in range(start, end):
            positions[index] = (period, (index - start) % length)
        start, period = end, period + 1
    return positions


def _cycle_at(keys: list, start: int, total: int):
    """The shortest cycle beginning at `start`, and how far it runs."""
    limit = min(MAX_CYCLE, (total - start) // MIN_REPEATS)
    for length in range(1, limit + 1):
        if keys[start:start + length] != keys[start + length:start + 2 * length]:
            continue
        end = start + length
        while (end + length <= total
               and keys[end:end + length] == keys[start:start + length]):
            end += length
        if (end - start) // length >= MIN_REPEATS:
            # whatever is left of a final, incomplete cycle belongs to this
            # period too — an acquisition can be stopped part way through one
            remainder = total - end
            if 0 < remainder < length and keys[end:total] == keys[start:start + remainder]:
                end = total
            return length, end
    return None, total


# --------------------------------------------------------------------------- #
# small parsing helpers
# --------------------------------------------------------------------------- #
def _attribute(text: str, name: str) -> str:
    match = re.search(rf'{name}="([^"]*)"', text)
    return match.group(1) if match else ""


def _between(data: bytes, opening: bytes, closing: bytes) -> bytes:
    start = data.find(opening)
    if start < 0:
        return b""
    stop = data.find(closing, start)
    return data[start:stop] if stop > 0 else data[start:]


def _float_or_none(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _minutes(element) -> float:
    """
    The scan start time, in minutes.

    mzML records the unit, and converters disagree: ProteoWizard writes
    minutes from a SCIEX file and seconds from a Thermo one. Reading the
    number without the unit is how a twenty-minute run becomes a twenty-hour
    one.
    """
    for child in element.iter():
        if _local(child.tag) != "cvParam":
            continue
        if child.get("accession") != SCAN_START_TIME:
            continue
        value = _float_or_none(child.get("value"))
        if value is None:
            return 0.0
        unit = (child.get("unitAccession") or "").strip()
        unit_name = (child.get("unitName") or "").lower()
        if unit == "UO:0000010" or unit_name.startswith("second"):
            return value / 60.0
        if unit == "UO:0000032" or unit_name.startswith("hour"):
            return value * 60.0
        return value
    return 0.0


def _element_ranges(data: bytes, name: bytes):
    """
    The byte range of every `<name ...>...</name>` at any depth.

    Finding these by scanning rather than by the file's own index list is
    deliberate: an index is optional, is written by the converter, and is
    wrong often enough that trusting it means reading the wrong bytes with no
    error to say so.
    """
    opening = re.compile(rb"<" + name + rb"[\s>]")
    closing = b"</" + name + b">"
    position = 0
    while True:
        match = opening.search(data, position)
        if match is None:
            return
        start = match.start()
        # an empty element closes itself and has no arrays worth reading
        head_end = data.find(b">", start)
        if head_end > 0 and data[head_end - 1:head_end] == b"/":
            position = head_end + 1
            continue
        stop = data.find(closing, start)
        if stop < 0:
            return
        stop += len(closing)
        yield start, stop
        position = stop


# --------------------------------------------------------------------------- #
# writing
# --------------------------------------------------------------------------- #
#: 64-bit for both arrays and zlib on top: lossless, and about the same size
#: as 32-bit uncompressed. Fidelity is the whole point of exporting from a
#: reader that has been checked; giving it back with 32-bit intensities would
#: throw away digits this application can prove it read correctly.
def _encode(values: np.ndarray, compress: bool = True) -> tuple[str, int]:
    raw = np.asarray(values, dtype="<f8").tobytes()
    if compress:
        raw = zlib.compress(raw, 6)
    encoded = base64.b64encode(raw).decode("ascii")
    return encoded, len(encoded)


def _cv(accession: str, name: str, value=None, unit: str = "",
        unit_name: str = "") -> str:
    parts = [f'accession="{accession}"', 'cvRef="MS"', f'name="{name}"']
    parts.append(f'value="{"" if value is None else value}"')
    if unit:
        parts.append(f'unitCvRef="{unit.split(":")[0]}"')
        parts.append(f'unitAccession="{unit}"')
        parts.append(f'unitName="{unit_name}"')
    return "<cvParam " + " ".join(parts) + "/>"


def _binary_array(values: np.ndarray, accession: str, name: str,
                  unit: str = "", unit_name: str = "",
                  compress: bool = True) -> str:
    encoded, length = _encode(values, compress)
    compression = (_cv(ZLIB, "zlib compression") if compress
                   else _cv(NO_COMPRESSION, "no compression"))
    return (
        f'<binaryDataArray encodedLength="{length}">'
        + _cv(BIT_64, "64-bit float")
        + compression
        + _cv(accession, name, unit=unit, unit_name=unit_name)
        + f"<binary>{encoded}</binary>"
        + "</binaryDataArray>"
    )


def write_mzml(sample, path: str | os.PathLike, compress: bool = True,
               progress=None) -> str:
    """
    Write one sample out as indexed mzML.

    Everything the reader above needs to rebuild the channels is recorded:
    the precursor, the collision energy, the scan window, the polarity, and —
    beyond the standard — the experiment each scan came from, so a file this
    application wrote reconstructs its channels exactly rather than by
    inference. Another program ignores that user parameter and infers, which
    is what it would have to do for any vendor's file.

    Spectra are written as the instrument stored them. SCIEX strips the zeros
    out of a profile spectrum and its own library can put them back; that is a
    rendering step, and baking it into an exported file would be exporting a
    picture rather than a measurement.
    """
    path = str(path)
    scans = []
    for channel in sample.channels:
        # the instrument's own total ion current, not a sum of the points it
        # chose to store. A profile spectrum arrives with its zeros stripped
        # out, so adding up what is left is not what the detector reported —
        # measured on one acquisition, recomputing it moved every integrated
        # area by about two per cent.
        times, totals = channel.tic()
        for scan in range(len(times)):
            total = float(totals[scan]) if scan < len(totals) else None
            scans.append((channel, scan, float(times[scan]), total))
    # spectra go in time order, as an acquisition produces them
    scans.sort(key=lambda item: (item[2], item[0].index))

    run_id = _xml_escape(getattr(sample, "name", "run"))
    source = _xml_escape(os.path.basename(getattr(sample, "_wiff", None).path
                                          if getattr(sample, "_wiff", None) else path))

    offsets: list[tuple[str, int]] = []
    with open(path, "wb") as handle:
        def emit(text: str) -> None:
            handle.write(text.encode("utf-8"))

        emit(_HEADER.format(run_id=run_id, source=source,
                            instrument=_xml_escape(getattr(sample, "instrument", "")),
                            started=_xml_escape(getattr(sample, "acquisition_time", "") or ""),
                            count=len(scans)))
        for index, (channel, scan, rt, total) in enumerate(scans):
            if progress is not None and index % 500 == 0:
                progress(index, len(scans))
            mz, intensity = channel.spectrum(scan, add_zeros=False)
            identifier = (f"index={index} experiment={channel.index} "
                          f"scan={scan}")
            offsets.append((identifier, handle.tell()))
            emit(_spectrum_xml(index, identifier, channel, rt, mz, intensity,
                               compress, total))
        emit("</spectrumList></run></mzML>")

        index_offset = handle.tell()
        emit('<indexList count="1"><index name="spectrum">')
        for identifier, offset in offsets:
            emit(f'<offset idRef="{_xml_escape(identifier)}">{offset}</offset>')
        emit("</index></indexList>")
        emit(f"<indexListOffset>{index_offset}</indexListOffset>")
        emit("<fileChecksum>")
        handle.flush()

    # the checksum covers everything up to and including the opening tag of
    # the element it sits in, which is how the standard defines it
    with open(path, "rb") as handle:
        digest = hashlib.sha1(handle.read()).hexdigest()
    with open(path, "ab") as handle:
        handle.write(f"{digest}</fileChecksum></indexedmzML>".encode("utf-8"))
    if progress is not None:
        progress(len(scans), len(scans))
    return path


def _spectrum_xml(index: int, identifier: str, channel, rt: float,
                  mz: np.ndarray, intensity: np.ndarray,
                  compress: bool, total: float | None = None) -> str:
    info = channel.info
    level = 1 if info.is_ms1 else 2
    if total is None:
        total = float(np.sum(intensity)) if intensity.size else 0.0
    parts = [
        f'<spectrum index="{index}" id="{_xml_escape(identifier)}" '
        f'defaultArrayLength="{mz.size}">',
        _cv(MS_LEVEL, "ms level", level),
        _cv("MS:1000579" if level == 1 else "MS:1000580",
            "MS1 spectrum" if level == 1 else "MSn spectrum"),
        _cv(PROFILE_SPECTRUM, "profile spectrum"),
        _cv(NEGATIVE_SCAN if info.polarity.lower().startswith("neg")
            else POSITIVE_SCAN,
            "negative scan" if info.polarity.lower().startswith("neg")
            else "positive scan"),
        # repr, not a fixed number of decimals: a float written to six
        # places and read back is not the same float, and the difference
        # reaches the integrated areas
        _cv(TOTAL_ION_CURRENT, "total ion current", repr(float(total))),
    ]
    if intensity.size:
        peak = int(np.argmax(intensity))
        parts.append(_cv(BASE_PEAK_MZ, "base peak m/z", repr(float(mz[peak])),
                         unit="MS:1000040", unit_name="m/z"))
        parts.append(_cv(BASE_PEAK_INTENSITY, "base peak intensity",
                         repr(float(intensity[peak]))))

    parts.append('<scanList count="1">')
    parts.append(_cv("MS:1000795", "no combination"))
    parts.append("<scan>")
    parts.append(_cv(SCAN_START_TIME, "scan start time", repr(float(rt)),
                     unit="UO:0000031", unit_name="minute"))
    # the experiment this scan belongs to: not part of the standard, and the
    # only thing that lets a reader rebuild the channels without guessing
    parts.append(f'<userParam name="{EXPERIMENT_PARAM}" '
                 f'value="{channel.index}" type="xsd:int"/>')
    if info.name:
        parts.append(f'<userParam name="{EXPERIMENT_NAME_PARAM}" '
                     f'value="{_xml_escape(info.name)}"/>')
    parts.append('<scanWindowList count="1"><scanWindow>')
    parts.append(_cv(SCAN_WINDOW_LOWER, "scan window lower limit",
                     f"{info.start_mass:.6f}", unit="MS:1000040", unit_name="m/z"))
    parts.append(_cv(SCAN_WINDOW_UPPER, "scan window upper limit",
                     f"{info.end_mass:.6f}", unit="MS:1000040", unit_name="m/z"))
    parts.append("</scanWindow></scanWindowList></scan></scanList>")

    if not info.is_ms1 and info.precursor is not None:
        parts.append('<precursorList count="1"><precursor>')
        parts.append("<selectedIonList count=\"1\"><selectedIon>")
        parts.append(_cv(SELECTED_ION_MZ, "selected ion m/z",
                         f"{info.precursor:.6f}", unit="MS:1000040",
                         unit_name="m/z"))
        parts.append("</selectedIon></selectedIonList>")
        parts.append("<activation>")
        parts.append(_cv("MS:1000133", "collision-induced dissociation"))
        if info.collision_energy is not None:
            parts.append(_cv(COLLISION_ENERGY, "collision energy",
                             f"{info.collision_energy:g}", unit="UO:0000266",
                             unit_name="electronvolt"))
        parts.append("</activation></precursor></precursorList>")

    parts.append('<binaryDataArrayList count="2">')
    parts.append(_binary_array(mz, MZ_ARRAY, "m/z array",
                               unit="MS:1000040", unit_name="m/z",
                               compress=compress))
    parts.append(_binary_array(intensity, INTENSITY_ARRAY, "intensity array",
                               unit="MS:1000131", unit_name="number of detector counts",
                               compress=compress))
    parts.append("</binaryDataArrayList></spectrum>")
    return "".join(parts)


def _xml_escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


_HEADER = """<?xml version="1.0" encoding="utf-8"?>
<indexedmzML xmlns="http://psi.hupo.org/ms/mzml" \
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" \
xsi:schemaLocation="http://psi.hupo.org/ms/mzml \
http://psidev.info/files/ms/mzML/xsd/mzML1.1.2_idx.xsd">
<mzML xmlns="http://psi.hupo.org/ms/mzml" version="1.1.0" id="{run_id}">
<cvList count="2">
<cv id="MS" fullName="Proteomics Standards Initiative Mass Spectrometry Ontology" \
URI="https://raw.githubusercontent.com/HUPO-PSI/psi-ms-CV/master/psi-ms.obo"/>
<cv id="UO" fullName="Unit Ontology" \
URI="https://raw.githubusercontent.com/bio-ontology-research-group/unit-ontology/master/unit.obo"/>
</cvList>
<fileDescription>
<fileContent>
<cvParam cvRef="MS" accession="MS:1000579" name="MS1 spectrum" value=""/>
<cvParam cvRef="MS" accession="MS:1000580" name="MSn spectrum" value=""/>
</fileContent>
<sourceFileList count="1">
<sourceFile id="source" name="{source}" location="file://">
<cvParam cvRef="MS" accession="MS:1000770" name="WIFF nativeID format" value=""/>
</sourceFile>
</sourceFileList>
</fileDescription>
<softwareList count="1">
<software id="OpenQuant" version="1">
<cvParam cvRef="MS" accession="MS:1000799" name="custom unreleased software tool" value="OpenQuant"/>
</software>
</softwareList>
<instrumentConfigurationList count="1">
<instrumentConfiguration id="instrument">
<cvParam cvRef="MS" accession="MS:1000031" name="instrument model" value="{instrument}"/>
</instrumentConfiguration>
</instrumentConfigurationList>
<dataProcessingList count="1">
<dataProcessing id="export">
<processingMethod order="0" softwareRef="OpenQuant">
<cvParam cvRef="MS" accession="MS:1000544" name="Conversion to mzML" value=""/>
</processingMethod>
</dataProcessing>
</dataProcessingList>
<run id="{run_id}" defaultInstrumentConfigurationRef="instrument" \
startTimeStamp="{started}">
<spectrumList count="{count}" defaultDataProcessingRef="export">
"""
