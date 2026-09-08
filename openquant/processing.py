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


def estimate_noise(y: np.ndarray) -> float | None:
    """
    Robust noise from the median absolute deviation of point-to-point
    differences, scaled to a standard deviation. Insensitive to peaks.

    In low-count XICs more than half the differences are exactly zero, which
    zeroes the MAD; the fallback is the standard deviation of the lower half
    of the points, which rarely contains a peak.

    **None means the noise could not be measured**, which is not the same as
    zero and is the ordinary case on a scheduled acquisition: measured over
    846 real traces, the median had three non-zero points in sixty-one, and
    nine per cent had a baseline that varied at all. A trace the instrument
    reports as exact zeros has a baseline below its reporting threshold and
    there is nothing there to measure. Saying so is the point — a caller that
    substitutes a constant is welcome to, but it must not then call what it
    computes a signal-to-noise ratio.
    """
    if y.size < 3:
        return None
    diffs = np.diff(y)
    mad = float(np.median(np.abs(diffs - np.median(diffs))))
    if mad > 0:
        return mad * 1.4826 / np.sqrt(2.0)
    lower_half = np.sort(y)[: max(y.size // 2, 3)]
    spread = float(np.std(lower_half))
    return spread if spread > 0 else None


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


#: a gap this many times the local sampling interval is empty spectrum rather
#: than the inside of a peak
PROFILE_GAP = 2.5


def restore_profile_zeros(mz: np.ndarray, intensity: np.ndarray,
                          gap_factor: float = PROFILE_GAP
                          ) -> tuple[np.ndarray, np.ndarray]:
    """
    Put back the zero points a vendor stripped out of a profile spectrum.

    Instruments record a profile at a fixed sampling rate, but the file
    usually keeps only the points where something was detected. Drawn as they
    come, a straight line runs from the last point of one peak to the first
    point of the next, and the empty stretch between two peaks appears as a
    slope descending across it — signal where there is none.

    SCIEX's own library repairs this on the way out, using the sampling
    interval it knows. An mzML records no such thing, so the interval is
    measured from the file: the smallest quarter of the gaps are the ones
    inside peaks, and interpolating those across the mass axis gives the
    interval at any mass. No instrument physics is assumed — the spacing of a
    time-of-flight grows with the square root of mass and an Orbitrap's grows
    faster, and reading it off the data covers both.

    This is for drawing. It changes no intensity and creates no peak: every
    point added is a zero, at a mass where the instrument reported nothing.
    A spectrum that already carries its zeros has no gap wide enough to
    trigger it, and comes back untouched.
    """
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if mz.size < 3:
        return mz, intensity

    gaps = np.diff(mz)
    positive = gaps > 0
    if not positive.any():
        return mz, intensity
    inside_peaks = positive & (gaps <= np.quantile(gaps[positive], 0.25))
    if int(inside_peaks.sum()) < 2:
        # nothing is densely sampled: this is a peak list, not a profile
        return mz, intensity

    midpoints = (mz[:-1] + mz[1:]) / 2.0
    step = np.interp(mz, midpoints[inside_peaks], gaps[inside_peaks])

    out_mz: list[float] = []
    out_y: list[float] = []
    if intensity[0] != 0 and step[0] > 0:
        out_mz.append(mz[0] - step[0])
        out_y.append(0.0)
    for index in range(mz.size - 1):
        out_mz.append(float(mz[index]))
        out_y.append(float(intensity[index]))
        width = step[index]
        if width > 0 and gaps[index] > gap_factor * width:
            out_mz.extend((float(mz[index] + width), float(mz[index + 1] - width)))
            out_y.extend((0.0, 0.0))
    out_mz.append(float(mz[-1]))
    out_y.append(float(intensity[-1]))
    if intensity[-1] != 0 and step[-1] > 0:
        out_mz.append(float(mz[-1] + step[-1]))
        out_y.append(0.0)
    return np.array(out_mz), np.array(out_y)


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



#: how a peak's area is arrived at once the peak has been found
#:
#: `valley` is what this always did: walk out from the apex to the valleys
#: either side, draw a straight baseline between them and take the trapezoid
#: area above it. It stays the default so that no saved project changes its
#: numbers. `summation` does no peak finding at all — the component's
#: retention-time window is the boundary, the baseline is the line between
#: its two ends, and whatever is above it is the area, which is what
#: MultiQuant's algorithm of the same name does and what an operator does by
#: hand. `gaussian` finds the peak as `valley` does and then fits a Gaussian
#: to the points inside its boundaries, reporting the model's area rather
#: than the trapezoid's: on a trace sampled every fifteen seconds a peak is
#: two or three points wide, and a trapezoid over them depends on where the
#: scans happened to land relative to the apex in a way a fitted curve does
#: not.
ALGORITHM_VALLEY = "valley"
ALGORITHM_SUMMATION = "summation"
ALGORITHM_GAUSSIAN = "gaussian"
ALGORITHMS = (ALGORITHM_VALLEY, ALGORITHM_SUMMATION, ALGORITHM_GAUSSIAN)
ALGORITHM_LABELS = {
    ALGORITHM_VALLEY: "Valley to valley",
    ALGORITHM_SUMMATION: "Summation over the window",
    ALGORITHM_GAUSSIAN: "Gaussian fit",
}

#: the smallest a fitted peak may be, as a multiple of the sampling interval.
#: Below this the model is narrower than anything the instrument could have
#: resolved and its area is an artefact of one tall point.
MIN_SIGMA_STEPS = 0.25
#: the most Levenberg-Marquardt steps a fit is given before it is called off
MAX_FIT_STEPS = 80
#: points above the baseline a fit needs before it is determined by them
MIN_FIT_POINTS = 3
#: and how tall those points have to be, as a fraction of the apex. Below
#: this a point is on the peak's feet, not its flanks: measured on a real
#: batch, an internal standard of 52,000 counts had neighbours of 44 and 98,
#: which is what the baseline blips elsewhere on the same trace looked like.
#: A width that rests on such points is a width taken from the noise, and
#: the fit was exact through them — three points, three parameters — while
#: being a third smaller than the trapezoid.
MIN_SHAPE_FRACTION = 0.01

#: the ratio of a Gaussian's full width at half height to its sigma
FWHM_PER_SIGMA = 2.0 * np.sqrt(2.0 * np.log(2.0))
#: the area under a unit-height, unit-sigma Gaussian
GAUSSIAN_AREA = np.sqrt(2.0 * np.pi)


@dataclass(frozen=True)
class GaussianModel:
    """The curve a Gaussian fit settled on, and how well it fitted."""

    centre: float
    sigma: float
    height: float
    #: coefficient of determination over the fitted points; 1 is exact
    r2: float
    #: points above the baseline the fit rests on
    points: int

    @property
    def exact(self) -> bool:
        """
        Three points and three parameters: the curve passes through them
        whatever they are, and its r² says nothing about the peak.
        """
        return self.points <= 3

    @property
    def quality(self) -> str:
        """How well it fitted, worded so that an exact fit is not a good one."""
        if self.exact:
            return f"exact through {self.points} points"
        return f"r\u00b2 {self.r2:.3f} over {self.points} points"

    @property
    def area(self) -> float:
        return float(self.height * self.sigma * GAUSSIAN_AREA)

    @property
    def width(self) -> float:
        """Full width at half height, in the units of the time axis."""
        return float(FWHM_PER_SIGMA * self.sigma)

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        return self.height * np.exp(-0.5 * ((np.asarray(x, dtype=float) - self.centre)
                                            / self.sigma) ** 2)

    def to_dict(self) -> dict:
        return {"centre": self.centre, "sigma": self.sigma, "height": self.height,
                "r2": self.r2, "points": self.points}

    @classmethod
    def from_dict(cls, data: dict | None) -> "GaussianModel | None":
        if not data:
            return None
        try:
            return cls(float(data["centre"]), float(data["sigma"]),
                       float(data["height"]), float(data.get("r2", 0.0)),
                       int(data.get("points", 0)))
        except (KeyError, TypeError, ValueError):
            return None


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
    #: None when the baseline could not be measured, so no ratio exists
    snr: float | None
    #: which algorithm produced the area — what actually ran, so a fit that
    #: could not be made and left the valley area standing says so here
    algorithm: str = ALGORITHM_VALLEY
    #: the fitted curve, when the area came from one
    model: GaussianModel | None = None


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
    measured = noise if noise is not None else estimate_noise(y)
    return ChromPeak(
        apex_rt=float(x[apex]),
        apex_index=apex,
        start_rt=float(xs[0]),
        end_rt=float(xs[-1]),
        height=height,
        area=float(np.trapezoid(corrected, xs)),
        width=width,
        snr=float(height / measured) if measured else None,
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


#: which peak in the retention-time window is the component
#:
#: `largest` takes the biggest peak in the window, which is what this always
#: did and stays the default so that no existing project changes its numbers.
#: It is the right answer when the window holds one real peak and some noise,
#: and the wrong one when it holds two: an isobaric or isomeric species
#: co-eluting inside a ±0.6 min window is ordinary in lipidomics, and there
#: the taller peak wins whether or not the method's retention time points at
#: it. `nearest` uses that retention time to decide instead.
PEAK_LARGEST = "largest"
PEAK_NEAREST = "nearest the expected RT"
PEAK_CHOICES = (PEAK_LARGEST, PEAK_NEAREST)


def choose_peak(peaks: list["ChromPeak"], expected_rt: float | None,
                rule: str = PEAK_LARGEST) -> tuple["ChromPeak | None", str]:
    """
    Which of the peaks found in the window is the component.

    Proximity is decided among the peaks that already passed the height and
    signal-to-noise gates, so those gates are what stops `nearest` picking
    noise that happens to sit on the expected retention time. A method whose
    window is full of small peaks needs `min_relative_height` raised, not a
    different rule.

    Returns the peak and a note, which is empty unless the rule actually
    changed the answer. A policy that silently picks the smaller of two peaks
    is a policy nobody can review, so when proximity overrules size the result
    says what it passed over.
    """
    if not peaks:
        return None, ""
    largest = max(peaks, key=lambda peak: peak.area)
    if rule != PEAK_NEAREST:
        return largest, ""
    if expected_rt is None:
        return largest, "no expected retention time; took the largest peak"
    # equally close, take the larger: proximity has said all it can
    nearest = min(peaks, key=lambda peak: (abs(peak.apex_rt - expected_rt),
                                           -peak.area))
    if nearest is largest:
        return nearest, ""
    times = (largest.area / nearest.area) if nearest.area > 0 else float("inf")
    return nearest, (f"chosen by proximity; the largest peak in the window is "
                     f"at {largest.apex_rt:.3f} min and {times:.1f}\u00d7 the area")


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

    # what was measured, and what the filter runs on. Where the baseline
    # cannot be measured the floor takes over, and the filter is then an
    # absolute intensity threshold wearing a signal-to-noise name: it still
    # rejects the smallest peaks, which is worth keeping, but the number it
    # rejects on is not a ratio to anything and is not reported as one.
    measured = noise if noise is not None else estimate_noise(y)
    noise_used = max(measured or 0.0, noise_floor)
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
        floor = base + max(noise_used, (float(smoothed[apex]) - base) * EDGE_FRACTION)
        left = _walk_to_edge(smoothed, apex, -1, floor, noise_used)
        right = _walk_to_edge(smoothed, apex, +1, floor, noise_used)
        if right - left < 2:
            continue
        xs, ys = x[left:right + 1], y[left:right + 1]
        baseline = np.linspace(ys[0], ys[-1], xs.size)
        corrected = np.clip(ys - baseline, 0.0, None)
        height = float(corrected.max())
        if height <= 0:
            continue
        if height / noise_used < min_snr:
            continue
        snr = float(height / measured) if measured else None
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


# --------------------------------------------------------------------------- #
# the other two ways of arriving at an area
# --------------------------------------------------------------------------- #
def _log_parabola(x: np.ndarray, y: np.ndarray, apex: int
                  ) -> tuple[float, float, float] | None:
    """
    A Gaussian through the apex and its two neighbours, exactly.

    The logarithm of a Gaussian is a parabola, so three positive points
    determine one without iteration. Used as the starting point of the fit
    when the apex has a positive point on each side; anything less starts
    from moments instead.
    """
    if apex < 1 or apex + 1 >= x.size:
        return None
    t = x[apex - 1:apex + 2]
    v = y[apex - 1:apex + 2]
    if not np.all(v > 0):
        return None
    a, b, c = np.polyfit(t, np.log(v), 2)
    if a >= 0:
        return None
    sigma = float(np.sqrt(-1.0 / (2.0 * a)))
    centre = float(-b / (2.0 * a))
    height = float(np.exp(c - b * b / (4.0 * a)))
    return centre, sigma, height


def fit_gaussian(x: np.ndarray, y: np.ndarray,
                 max_steps: int = MAX_FIT_STEPS) -> GaussianModel | None:
    """
    Fit `height * exp(-(x - centre)^2 / 2 sigma^2)` to points already
    corrected to their baseline.

    Levenberg-Marquardt with the analytic Jacobian, in numpy. The starting
    point is the parabola through the logarithms of the apex and its
    neighbours where all three are positive, and the moments of the positive
    points otherwise. A step that takes the centre outside the points or the
    width below a quarter of a sampling interval is refused rather than
    clamped, so a fit that wants to be degenerate fails instead of returning
    a model at the edge of what it was allowed.

    Three points on the peak are required — above the baseline and at least
    `MIN_SHAPE_FRACTION` of the apex. Two determine a Gaussian only together
    with a width, and the zeros beside them say no more than that the width
    is small, so a fit to two settles wherever it started: measured at
    14.6 s sampling, biased low by seven per cent. And a third point at a
    fraction of a per cent of the apex is the peak's foot, where a real
    peak is tailing and baseline rather than Gaussian: the curve through it
    is exact and its width is taken from the noise. A fit that is not
    determined by the peak is not made. At 14.6 s between scans that means
    a peak at least about 17 s wide at half height can always be fitted,
    and a narrower one only when the scans happen to land on its flanks.

    Returns None when fewer than three points qualify, when the fit does
    not converge, or when what it converged to is not a peak.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 3 or x.size != y.size:
        return None
    positive = y > 0
    strong = y >= MIN_SHAPE_FRACTION * float(y.max())
    if int(strong.sum()) < MIN_FIT_POINTS:
        return None
    step = float(np.median(np.diff(x))) if x.size > 1 else 0.0
    if step <= 0:
        return None
    lo, hi = float(x[0]), float(x[-1])
    min_sigma = MIN_SIGMA_STEPS * step
    max_sigma = max(hi - lo, min_sigma * 2)

    apex = int(y.argmax())
    start = _log_parabola(x, y, apex)
    if start is None:
        w, t = y[positive], x[positive]
        centre = float((w * t).sum() / w.sum())
        spread = float(np.sqrt((w * (t - centre) ** 2).sum() / w.sum()))
        start = centre, max(spread, step / 2.0), float(y[apex])
    centre, sigma, height = start
    if not (lo <= centre <= hi):
        centre = float(x[apex])
    sigma = float(np.clip(sigma, min_sigma, max_sigma))
    height = max(height, float(y[apex]) * 0.5)

    def model(c, s, h):
        return h * np.exp(-0.5 * ((x - c) / s) ** 2)

    def cost(c, s, h):
        r = y - model(c, s, h)
        return float(r @ r)

    lam = 1e-3
    current = cost(centre, sigma, height)
    converged = False
    refusals = 0
    for _ in range(max_steps):
        g = model(centre, sigma, height)
        r = y - g
        d = x - centre
        jac = np.column_stack((g * d / sigma ** 2,
                               g * d * d / sigma ** 3,
                               g / height if height else g))
        normal = jac.T @ jac
        gradient = jac.T @ r
        try:
            delta = np.linalg.solve(normal + lam * np.diag(np.diag(normal)), gradient)
        except np.linalg.LinAlgError:
            return None
        trial = (centre + delta[0], sigma + delta[1], height + delta[2])
        inside = (lo <= trial[0] <= hi and min_sigma <= trial[1] <= max_sigma
                  and trial[2] > 0)
        attempt = cost(*trial) if inside else float("inf")
        if attempt < current:
            improvement = current - attempt
            centre, sigma, height = trial
            current = attempt
            lam = max(lam / 3.0, 1e-12)
            refusals = 0
            if improvement <= 1e-12 * max(current, 1.0) or \
                    float(np.abs(delta).max()) <= 1e-9:
                converged = True
                break
        else:
            lam *= 4.0
            refusals += 1
            if refusals >= 12:
                # the step has shrunk to nothing: as converged as it gets
                converged = True
                break
    if not converged or height <= 0:
        return None
    # a width pinned to its floor is one tall point, not a peak
    if sigma <= min_sigma * 1.0001:
        return None
    total = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - current / total if total > 0 else 1.0
    return GaussianModel(centre=float(centre), sigma=float(sigma),
                         height=float(height), r2=float(r2),
                         points=int(positive.sum()))


def refine_gaussian(x: np.ndarray, y: np.ndarray, peak: ChromPeak,
                    noise: float | None = None) -> tuple[ChromPeak, str]:
    """
    Replace a valley-integrated peak's area with that of a Gaussian fitted
    to the points inside its boundaries.

    The baseline is the one the valley integration drew, so the two
    algorithms differ only in what they do above it. When no fit can be made
    — fewer than two points above the baseline, or a fit that does not
    settle — the valley peak comes back unchanged, still labelled `valley`,
    with the reason in the note. What it does not do is quietly return the
    trapezoid under the fit's name.
    """
    inside = (x >= peak.start_rt) & (x <= peak.end_rt)
    xs, ys = x[inside], y[inside]
    if xs.size < 3:
        return peak, "Gaussian fit needs three points; valley area kept"
    baseline = np.linspace(ys[0], ys[-1], xs.size)
    corrected = ys - baseline
    fit = fit_gaussian(xs, corrected)
    if fit is None:
        above = int(np.sum(corrected > 0))
        strong = int(np.sum(corrected >= MIN_SHAPE_FRACTION * float(corrected.max()))) \
            if above else 0
        if above < MIN_FIT_POINTS:
            why = f"{above} point(s) above the baseline, {MIN_FIT_POINTS} needed"
        elif strong < MIN_FIT_POINTS:
            why = (f"narrower than the sampling resolves: {strong} point(s) "
                   f"above {MIN_SHAPE_FRACTION:.0%} of the apex, "
                   f"{MIN_FIT_POINTS} needed")
        else:
            why = "the fit did not settle on a peak"
        return peak, f"Gaussian fit not possible ({why}); valley area kept"
    measured = noise if noise is not None else estimate_noise(y)
    return ChromPeak(
        apex_rt=fit.centre,
        apex_index=peak.apex_index,
        start_rt=peak.start_rt,
        end_rt=peak.end_rt,
        height=fit.height,
        area=fit.area,
        width=fit.width,
        snr=float(fit.height / measured) if measured else None,
        algorithm=ALGORITHM_GAUSSIAN,
        model=fit,
    ), ""


def summation_peak(x: np.ndarray, y: np.ndarray, start: float, end: float,
                   noise: float | None = None, min_snr: float = 0.0,
                   noise_floor: float = NOISE_FLOOR) -> tuple[ChromPeak | None, str]:
    """
    Everything above a straight baseline across the retention-time window.

    No apex is looked for and no boundary decided: the window the method
    declares is the boundary. It is the arithmetic of manual integration
    applied to the declared window, which makes it the one algorithm whose
    answer cannot move with a detection setting — and also the one that
    counts whatever noise the window holds. `min_snr` is honoured, measured
    the way `detect_peaks` measures it, so that a window of baseline is not
    reported as a peak; an operator who wants the sum regardless sets it to
    zero.
    """
    peak = integrate_window(x, y, start, end, noise, noise_floor)
    if peak is None:
        return None, "fewer than three points in the window"
    if peak.height <= 0:
        return None, "nothing above the baseline in the window"
    measured = noise if noise is not None else estimate_noise(y)
    noise_used = max(measured or 0.0, noise_floor)
    if min_snr and peak.height / noise_used < min_snr:
        return None, "no peak above noise"
    return ChromPeak(
        apex_rt=peak.apex_rt, apex_index=peak.apex_index,
        start_rt=peak.start_rt, end_rt=peak.end_rt,
        height=peak.height, area=peak.area, width=peak.width, snr=peak.snr,
        algorithm=ALGORITHM_SUMMATION,
    ), ""
