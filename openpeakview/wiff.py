"""
Data layer: SCIEX WIFF files as numpy arrays.

Hierarchy: WiffFile -> Sample -> Channel (one "experiment" of the method).
Each Channel yields TIC, BPC, XIC and spectra (single scan or range average).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from . import bootstrap

_API = None


def _api():
    """Import the .NET types once, after the bootstrap."""
    global _API
    if _API is None:
        bootstrap.ensure()
        from System import Array, Double
        from Clearcore2.Data.AnalystDataProvider import (
            AnalystDataProviderFactory,
            AnalystWiffDataProvider,
        )
        from Clearcore2.Data.DataAccess.SampleData import (
            BasePeakChromatogramSettings,
            ExtractedIonChromatogramSettings,
        )
        from Clearcore2.Utility import OpenFileMode

        _API = {
            "Array": Array,
            "Double": Double,
            "Factory": AnalystDataProviderFactory,
            "Provider": AnalystWiffDataProvider,
            "BPCSettings": BasePeakChromatogramSettings,
            "XICSettings": ExtractedIonChromatogramSettings,
            "OpenFileMode": OpenFileMode,
        }
    return _API


def _to_numpy(net_array) -> np.ndarray:
    if net_array is None:
        return np.zeros(0, dtype=np.float64)
    return np.asarray(list(net_array), dtype=np.float64)


def _double_array(values) -> "object":
    api = _api()
    arr = api["Array"].CreateInstance(api["Double"], len(values))
    for i, v in enumerate(values):
        arr[i] = float(v)
    return arr


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ChannelInfo:
    """Metadata of one experiment (channel) of the acquisition method."""

    index: int
    name: str
    experiment_type: str
    polarity: str
    precursor: float | None
    start_mass: float
    end_mass: float
    n_scans: int
    collision_energy: float | None

    @property
    def is_ms1(self) -> bool:
        return self.precursor is None

    @property
    def label(self) -> str:
        if self.is_ms1:
            return f"{self.name}  ({self.start_mass:.0f}-{self.end_mass:.0f})"
        ce = f", CE {self.collision_energy:g}" if self.collision_energy else ""
        return f"{self.name}  {self.precursor:.2f}  ->  {self.start_mass:.0f}-{self.end_mass:.0f}{ce}"

    @property
    def short_label(self) -> str:
        return self.name if self.is_ms1 else f"{self.name} {self.precursor:.2f}"


# --------------------------------------------------------------------------- #
class Channel:
    """One experiment of the method: TOF MS, TOF PI (MRM-HR), MRM, and so on."""

    def __init__(self, sample: "Sample", index: int):
        self._sample = sample
        self._exp = sample._ms.GetMSExperiment(index)
        self.index = index
        self.info = self._read_info()

    # -- metadata ------------------------------------------------------------ #
    def _read_info(self) -> ChannelInfo:
        d = self._exp.Details
        ranges = list(d.MassRangeInfo) if d.MassRangeInfo else []
        first = ranges[0] if ranges else None

        precursor = None
        if first is not None and hasattr(first, "FixedMasses"):
            fixed = list(first.FixedMasses or [])
            if fixed:
                precursor = float(fixed[0])

        ce = None
        try:
            info = self._exp.GetMassSpectrumInfo(0)
            value = getattr(info, "CollisionEnergy", None)
            if value is not None and float(value) != 0.0:
                ce = float(value)
        except Exception:
            ce = None

        return ChannelInfo(
            index=self.index,
            name=str(d.ExperimentName),
            experiment_type=str(d.ExperimentType),
            polarity=str(d.Polarity),
            precursor=precursor,
            start_mass=float(d.StartMass),
            end_mass=float(d.EndMass),
            n_scans=int(d.NumberOfScans),
            collision_energy=ce,
        )

    # -- chromatograms -------------------------------------------------------- #
    @lru_cache(maxsize=1)
    def tic(self) -> tuple[np.ndarray, np.ndarray]:
        c = self._exp.GetTotalIonChromatogram()
        return _to_numpy(c.GetActualXValues()), _to_numpy(c.GetActualYValues())

    @property
    def rt(self) -> np.ndarray:
        return self.tic()[0]

    def bpc(self, mz_min: float | None = None, mz_max: float | None = None,
            tolerance: float = 0.1) -> tuple[np.ndarray, np.ndarray]:
        api = _api()
        lo = self.info.start_mass if mz_min is None else mz_min
        hi = self.info.end_mass if mz_max is None else mz_max
        settings = api["BPCSettings"](tolerance, _double_array([lo]), _double_array([hi]))
        c = self._exp.GetBasePeakChromatogram(settings)
        return _to_numpy(c.GetActualXValues()), _to_numpy(c.GetActualYValues())

    def xic(self, mz: float, tolerance: float = 0.02,
            unit: str = "Da") -> tuple[np.ndarray, np.ndarray]:
        """Extracted ion chromatogram over a window around `mz`."""
        half = mz * tolerance * 1e-6 if unit.lower() == "ppm" else tolerance
        return self.xic_range(mz - half, mz + half)

    def xic_range(self, mz_min: float, mz_max: float) -> tuple[np.ndarray, np.ndarray]:
        api = _api()
        c = self._exp.GetExtractedIonChromatogram(
            api["XICSettings"](float(mz_min), float(mz_max))
        )
        return _to_numpy(c.GetActualXValues()), _to_numpy(c.GetActualYValues())

    # -- spectra -------------------------------------------------------------- #
    def spectrum(self, scan: int) -> tuple[np.ndarray, np.ndarray]:
        """Spectrum of a single scan (0-based cycle index)."""
        scan = int(np.clip(scan, 0, max(self.info.n_scans - 1, 0)))
        s = self._exp.GetMassSpectrum(scan)
        return _to_numpy(s.GetActualXValues()), _to_numpy(s.GetActualYValues())

    def spectrum_rt_range(self, rt_start: float,
                          rt_end: float) -> tuple[np.ndarray, np.ndarray]:
        """Average spectrum of the scans inside the given time range."""
        lo, hi = sorted((float(rt_start), float(rt_end)))
        s = self._exp.GetMassSpectrum(lo, hi)
        return _to_numpy(s.GetActualXValues()), _to_numpy(s.GetActualYValues())

    def parameters(self) -> dict[str, str]:
        """Experiment parameters from the method (DP, CE, CES, ...)."""
        out: dict[str, str] = {}
        try:
            table = self._exp.Details.Parameters
        except Exception:
            return out
        for key in table.Keys:
            parameter = table[key]
            try:
                start, stop = float(parameter.Start), float(parameter.Stop)
            except Exception:
                out[str(key)] = str(parameter)
                continue
            # Start != Stop means a ramp (e.g. collision energy spread)
            out[str(key)] = f"{start:g}" if start == stop else f"{start:g} – {stop:g}"
        return out

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
        return f"<Channel {self.index}: {self.info.label}>"


# --------------------------------------------------------------------------- #
class Sample:
    """One injection inside the wiff file."""

    def __init__(self, wiff: "WiffFile", index: int):
        self._wiff = wiff
        self.index = index
        self._sample = wiff._batch.GetSample(index)
        self._ms = self._sample.MassSpectrometerSample
        self.name = str(wiff.sample_names[index])
        self.instrument = str(self._ms.InstrumentName)
        self.channels: list[Channel] = [
            Channel(self, i) for i in range(int(self._ms.ExperimentCount))
        ]

    @lru_cache(maxsize=1)
    def tic(self) -> tuple[np.ndarray, np.ndarray]:
        """TIC of the whole sample (sum over all experiments)."""
        c = self._ms.GetTotalIonChromatogram()
        return _to_numpy(c.GetActualXValues()), _to_numpy(c.GetActualYValues())

    @property
    def acquisition_time(self) -> str:
        try:
            return str(self._sample.Details.AcquisitionDateTime.ToString("s"))
        except Exception:
            return ""

    def metadata(self) -> dict[str, str]:
        """Sample and acquisition information, for the details panel."""
        details = self._sample.Details
        wanted = [
            ("Sample", "SampleName"),
            ("ID", "SampleID"),
            ("Type", "SampleType"),
            ("Acquired", None),
            ("Instrument", "InstrumentName"),
            ("Serial number", "InstrumentSerialNumber"),
            ("Method", "AcquisitionMethodName"),
            ("Batch", "BatchName"),
            ("Rack", "Rack"),
            ("Plate", "Plate"),
            ("Vial", "Vial"),
            ("Injection volume", "InjectionVolume"),
            ("Dilution factor", "DilutionFactor"),
            ("Operator", "UserName"),
            ("Software", "SoftwareVersion"),
            ("Comment", "SampleComment"),
        ]
        out: dict[str, str] = {}
        for label, attr in wanted:
            if attr is None:
                out[label] = self.acquisition_time
                continue
            try:
                value = getattr(details, attr)
            except Exception:
                continue
            text = "" if value is None else str(value)
            if text:
                out[label] = text
        out["Channels"] = str(len(self.channels))
        rt = self.tic()[0]
        if rt.size:
            out["Time range"] = f"{rt[0]:.2f} – {rt[-1]:.2f} min"
        return out

    def __repr__(self) -> str:
        return f"<Sample {self.name}: {len(self.channels)} channels>"


# --------------------------------------------------------------------------- #
class WiffFile:
    """A .wiff file (with its matching .wiff.scan alongside)."""

    def __init__(self, path: str | os.PathLike):
        api = _api()
        self.path = os.path.realpath(str(path))
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        # ReadOnlyShared is essential: on the managed path (OpenMcdf) the
        # default mode takes an exclusive lock, which stops a second window —
        # or Analyst itself — from opening the same .wiff.
        self._provider = api["Provider"](api["OpenFileMode"].ReadOnlyShared)
        self._batch = api["Factory"].CreateBatch(self.path, self._provider)
        self.sample_names = [str(n) for n in self._batch.GetSampleNames()]
        self._samples: dict[int, Sample] = {}

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    def sample(self, index: int = 0) -> Sample:
        if index not in self._samples:
            self._samples[index] = Sample(self, index)
        return self._samples[index]

    def close(self) -> None:
        try:
            self._provider.Close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"<WiffFile {self.filename}: {self.sample_names}>"
