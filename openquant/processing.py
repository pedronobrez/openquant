"""Numeric helpers: smoothing, baseline removal, peak picking and integration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Noise floor. In low-count XICs the measured noise is exactly zero (most
# points are 0), which would make every signal-to-noise ratio infinite and let
# a single-count spike pass the peak filter. One count is the smallest noise
# that is physically meaningful in that data.
NOISE_FLOOR = 1.0

#: where a peak is taken to have ended, as a fraction of its height above the
#: baseline it sits on. Below this it is the baseline, and walking further only
#: widens the boundary without changing the area.
EDGE_FRACTION = 0.05


def moving_average(y: np.ndarray, window: int) -> np.ndarray:
    """Centred moving average; a `window` of 1 or less returns the input."""
    if window <= 1 or y.size < window:
        return y
    kernel = np.ones(window, dtype=np.float64) / window
    padded = np.pad(y, (window // 2, window - 1 - window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def gaussian_kernel(sigma: float) -> np.ndarray:
    """Normalised Gaussian kernel truncated at +-3 sigma."""
    radius = max(int(round(3.0 * sigma)), 1)
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (offsets / sigma) ** 2)
    return kernel / kernel.sum()


def gaussian_smooth(y: np.ndarray, sigma: float) -> np.ndarray:
    """
    Gaussian smoothing with `sigma` given in points. This is the right filter
    for chromatograms: unlike a rectangular moving average it preserves peak
    position and area.
    """
    if sigma <= 0 or y.size < 3:
        return y
    kernel = gaussian_kernel(sigma)
    radius = kernel.size // 2
    padded = np.pad(y, radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def local_maxima(y: np.ndarray) -> np.ndarray:
    """Indices of local maxima (strict on the left, non-strict on the right)."""
    if y.size < 3:
        return np.zeros(0, dtype=int)
    return np.nonzero((y[1:-1] > y[:-2]) & (y[1:-1] >= y[2:]))[0] + 1


def rolling_minimum(y: np.ndarray, window: int) -> np.ndarray:
    """
    Lower envelope of `y`, in O(n): block minima over `window` points, linearly
    interpolated between block centres.
    """
    n = y.size
    window = int(np.clip(window, 2, max(n, 2)))
    if n < 3:
        return y.copy()
    centres, minima = [], []
    for start in range(0, n, window):
        stop = min(start + window, n)
        if stop <= start:
            continue
        centres.append((start + stop - 1) / 2.0)
        minima.append(float(y[start:stop].min()))
    if len(centres) < 2:
        return np.full(n, min(minima) if minima else 0.0)
    return np.interp(np.arange(n, dtype=np.float64), np.array(centres),
                     np.array(minima))


def subtract_baseline(x: np.ndarray, y: np.ndarray,
                      window: float = 1.0) -> np.ndarray:
    """
    Remove the baseline of a chromatogram. `window` is the width, in units of
    `x` (minutes), used to estimate the lower envelope: it must be wider than
    the broadest peak worth keeping.
    """
    if y.size < 3 or x.size != y.size:
        return y
    span = float(x[-1] - x[0])
    if span <= 0:
        return y
    points = max(int(round(window / span * y.size)), 2)
    baseline = rolling_minimum(y, points)
    baseline = gaussian_smooth(baseline, max(points / 4.0, 1.0))
    return y - baseline


def estimate_noise(y: np.ndarray) -> float:
    """
    Robust noise from the median absolute deviation of point-to-point
    differences, scaled to a standard deviation. Insensitive to peaks.

    In low-count XICs the signal is quantised and more than half the
    differences are exactly zero, which zeroes the MAD. The fallback is the
    standard deviation of the lower half of the points, which rarely contains a
    peak. Returning zero would make every signal-to-noise ratio infinite and
    the peak filter would accept anything.
    """
    if y.size < 3:
        return 0.0
    diffs = np.diff(y)
    mad = float(np.median(np.abs(diffs - np.median(diffs))))
    if mad > 0:
        return mad * 1.4826 / np.sqrt(2.0)
    lower_half = np.sort(y)[: max(y.size // 2, 3)]
    return float(np.std(lower_half))


def centroid_mz(mz: np.ndarray, intensity: np.ndarray, apex: int,
                span: int = 2) -> float:
    """
    Refine a peak mass in profile data using the centre of gravity of the
    points around the apex.
    """
    lo = max(apex - span, 0)
    hi = min(apex + span + 1, mz.size)
    weights = intensity[lo:hi]
    total = weights.sum()
    if total <= 0:
        return float(mz[apex])
    return float((mz[lo:hi] * weights).sum() / total)


def pick_peaks(mz: np.ndarray, intensity: np.ndarray, max_peaks: int = 15,
               min_relative: float = 0.01, centroid: bool = True,
               min_distance: float = 0.03) -> list[tuple[float, float]]:
    """
    The most intense peaks as (m/z, intensity), strongest first.

    `min_relative` is the fraction of the base peak height below which peaks
    are dropped. `min_distance` (in Da) merges neighbouring local maxima: in
    profile data the top of a single peak usually yields several maxima, which
    would otherwise show up as repeated masses.
    """
    if mz.size == 0 or intensity.size == 0:
        return []
    idx = local_maxima(intensity)
    if idx.size == 0:
        idx = np.array([int(intensity.argmax())])
    threshold = intensity.max() * min_relative
    idx = idx[intensity[idx] >= threshold]
    if idx.size == 0:
        return []
    order = idx[np.argsort(intensity[idx])[::-1]]
    peaks: list[tuple[float, float]] = []
    for i in order:
        m = centroid_mz(mz, intensity, int(i)) if centroid else float(mz[i])
        if any(abs(m - kept) < min_distance for kept, _ in peaks):
            continue
        peaks.append((m, float(intensity[i])))
        if len(peaks) >= max_peaks:
            break
    return peaks


def centroid_spectrum(mz: np.ndarray, intensity: np.ndarray,
                      min_relative: float = 0.0005,
                      min_distance: float = 0.005) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert a profile spectrum into centroids: one stick per peak, placed at
    the intensity-weighted centre of mass and as tall as the profile apex.

    Returns two arrays, so the m/z axis of the result is shorter than the
    input — centroided data is not a per-point transform of the profile.
    """
    peaks = pick_peaks(mz, intensity, max_peaks=100_000,
                       min_relative=min_relative, centroid=True,
                       min_distance=min_distance)
    if not peaks:
        return np.zeros(0), np.zeros(0)
    peaks.sort(key=lambda p: p[0])
    return (np.array([p[0] for p in peaks], dtype=np.float64),
            np.array([p[1] for p in peaks], dtype=np.float64))


def integrate(x: np.ndarray, y: np.ndarray, x0: float, x1: float) -> dict:
    """
    Integrate the range [x0, x1] of a chromatogram, subtracting a straight
    baseline drawn between the ends of the selection.
    """
    lo, hi = sorted((float(x0), float(x1)))
    mask = (x >= lo) & (x <= hi)
    if mask.sum() < 2:
        return {"area": 0.0, "height": 0.0, "apex_rt": 0.0, "n_points": int(mask.sum())}
    xs, ys = x[mask], y[mask]
    baseline = np.linspace(ys[0], ys[-1], xs.size)
    corrected = np.clip(ys - baseline, 0, None)
    apex = int(corrected.argmax())
    return {
        "area": float(np.trapezoid(corrected, xs)),
        "height": float(corrected[apex]),
        "apex_rt": float(xs[apex]),
        "n_points": int(xs.size),
    }


def signal_to_noise(x: np.ndarray, y: np.ndarray, x0: float, x1: float,
                    noise_floor: float = NOISE_FLOOR) -> float:
    """Rough signal-to-noise: peak height over the spread outside the range."""
    lo, hi = sorted((float(x0), float(x1)))
    inside = (x >= lo) & (x <= hi)
    outside = ~inside
    if inside.sum() == 0 or outside.sum() < 5:
        return 0.0
    noise = max(float(np.std(y[outside])), noise_floor)
    return float((y[inside].max() - np.median(y[outside])) / noise)


#: how the noise behind a signal-to-noise ratio is measured
SNR_PEAK_TO_PEAK = "peak-to-peak"
SNR_STANDARD_DEVIATION = "standard deviation"
SNR_MODES = (SNR_PEAK_TO_PEAK, SNR_STANDARD_DEVIATION)


def noise_in_region(x: np.ndarray, y: np.ndarray, start: float, end: float,
                    mode: str = SNR_PEAK_TO_PEAK) -> float | None:
    """
    Noise measured over a stretch of baseline the user picked.

    Peak-to-peak takes the full swing of the region and is the stricter, more
    conservative reading; the standard deviation is the gentler one. Both are
    in use, so which one a number came from has to be stated alongside it.
    """
    lo, hi = sorted((float(start), float(end)))
    window = (x >= lo) & (x <= hi)
    if window.sum() < 3:
        return None
    region = y[window]
    if mode == SNR_STANDARD_DEVIATION:
        return float(np.std(region))
    return float(region.max() - region.min())


@dataclass(frozen=True)
class ChromPeak:
    """An integrated chromatographic peak."""

    apex_rt: float
    apex_index: int
    start_rt: float
    end_rt: float
    height: float
    area: float
    width: float
    snr: float


def integrate_window(x: np.ndarray, y: np.ndarray, start: float, end: float,
                     noise: float | None = None,
                     noise_floor: float = NOISE_FLOOR) -> ChromPeak | None:
    """
    Integrate exactly the stretch the user marked, with no peak finding.

    This is what manual integration does: the operator has decided where the
    peak begins and ends, so the only job left is the arithmetic — a straight
    baseline between the two edges and the area above it.
    """
    lo, hi = sorted((float(start), float(end)))
    window = (x >= lo) & (x <= hi)
    if window.sum() < 3:
        return None
    xs, ys = x[window], y[window]
    baseline = np.linspace(ys[0], ys[-1], xs.size)
    corrected = np.clip(ys - baseline, 0.0, None)
    height = float(corrected.max())
    apex_local = int(corrected.argmax())
    apex = int(np.nonzero(window)[0][apex_local])
    half = corrected >= height / 2.0
    width = float(xs[half][-1] - xs[half][0]) if half.any() else 0.0
    reference = max(noise if noise is not None else estimate_noise(y), noise_floor)
    return ChromPeak(
        apex_rt=float(x[apex]),
        apex_index=apex,
        start_rt=float(xs[0]),
        end_rt=float(xs[-1]),
        height=height,
        area=float(np.trapezoid(corrected, xs)),
        width=width,
        snr=float(height / reference),
    )


def _walk_to_edge(smoothed: np.ndarray, apex: int, step: int,
                  floor: float, noise: float) -> int:
    """
    Where a peak ends on one side of its apex.

    Walking out "while not going up" treats a flat stretch as still descending,
    and an XIC is mostly flat baseline — a peak was being given boundaries
    minutes wide, taking the baseline into its area with it. The walk stops at
    a genuine valley, meaning the signal has climbed back by more than the
    noise, or once it has come down to the baseline, whichever comes first.
    """
    index = apex
    lowest = float(smoothed[apex])
    while 0 <= index + step < smoothed.size:
        value = float(smoothed[index + step])
        if value > lowest + noise:
            break
        index += step
        lowest = min(lowest, value)
        if value <= floor:
            break
    return index


def detect_peaks(x: np.ndarray, y: np.ndarray, min_relative: float = 0.02,
                 min_snr: float = 3.0, smooth_sigma: float = 1.0,
                 max_peaks: int = 50,
                 noise_floor: float = NOISE_FLOOR,
                 noise: float | None = None) -> list[ChromPeak]:
    """
    Detect and integrate the peaks of a chromatogram.

    Each apex is expanded on both sides to the nearest valley (or until the
    slope reverses), the baseline is the line joining the edges, and the area
    is integrated above it. `min_relative` is the minimum height as a fraction
    of the tallest peak; `min_snr` drops peaks indistinguishable from noise.
    Noise is never taken as smaller than `noise_floor`, otherwise an almost
    entirely zero XIC would give infinite signal-to-noise for its largest
    spike.
    """
    if x.size != y.size or y.size < 5:
        return []
    smoothed = gaussian_smooth(y, smooth_sigma) if smooth_sigma > 0 else y
    if float(smoothed.max()) <= 0:
        return []

    noise = max(noise if noise is not None else estimate_noise(y), noise_floor)
    threshold = float(smoothed.max()) * min_relative
    apexes = local_maxima(smoothed)
    apexes = apexes[smoothed[apexes] >= threshold]
    if apexes.size == 0:
        return []
    apexes = apexes[np.argsort(smoothed[apexes])[::-1][:max_peaks]]

    peaks: list[ChromPeak] = []
    for apex in apexes:
        apex = int(apex)
        # measured from the baseline the peak sits on, not from zero: two per
        # cent of a tall apex can still be under the trace's own background,
        # and then nothing stops the walk
        base = float(np.median(smoothed))
        floor = base + max(noise, (float(smoothed[apex]) - base) * EDGE_FRACTION)
        left = _walk_to_edge(smoothed, apex, -1, floor, noise)
        right = _walk_to_edge(smoothed, apex, +1, floor, noise)
        if right - left < 2:
            continue
        xs, ys = x[left:right + 1], y[left:right + 1]
        baseline = np.linspace(ys[0], ys[-1], xs.size)
        corrected = np.clip(ys - baseline, 0.0, None)
        height = float(corrected.max())
        if height <= 0:
            continue
        snr = float(height / noise)
        if snr < min_snr:
            continue
        half = corrected >= height / 2.0
        width = float(xs[half][-1] - xs[half][0]) if half.any() else 0.0
        peaks.append(
            ChromPeak(
                apex_rt=float(x[apex]),
                apex_index=apex,
                start_rt=float(xs[0]),
                end_rt=float(xs[-1]),
                height=height,
                area=float(np.trapezoid(corrected, xs)),
                width=width,
                snr=snr,
            )
        )
    return sorted(peaks, key=lambda p: p.area, reverse=True)
