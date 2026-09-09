"""
Mass recalibration from the internal standards.

`mass_drift` asks whether the axis moved during the run and answers against
the batch's own median, which is the only reference a run can supply for
itself. This module asks the other half of the question — *is the axis in the
right place at all* — and that needs a reference the run cannot supply: a
theoretical mass.

So a lock mass here is an internal standard that carries a **formula and an
adduct**. The written precursor is deliberately refused: `647.5` typed into a
method is good to about 800 ppm at that mass and correcting towards it would
recalibrate the instrument onto somebody's rounding.
`Component.precursor_from_formula` — the monoisotopic mass of the formula
through the adduct, which is what `MassTrend.exact` carries — is the only
number worth correcting towards.

What is fitted, per injection:

* an **offset** in ppm, the median of the lock masses' errors, sign flipped;
* a **linear term** in ppm per dalton, and only where `MIN_SLOPE_LOCK_MASSES`
  lock masses spread over `MIN_MASS_SPAN` daltons justify one *and* it is
  measured to help. A line through the points it is then scored on is exact
  and says nothing — the same trap `processing.fit_gaussian` fell into — so
  the slope is kept only when **leave-one-out** prediction of a held-out lock
  mass beats the plain offset's. That is also why the floor is four lock
  masses rather than three: hold one of three out and the line is fitted
  through two points, which is exact again.

Nothing is refitted from corrected data and nothing rewrites a file. The
correction is a function of m/z (`MassCorrection.apply`), and where it
reaches quantitation it moves the **extraction window**, not the instrument's
arithmetic: `quantify.extract_xic` asks the reader for a window shifted by
`MassCorrection.undo` and the vendor sums exactly the points it would have
summed for that window. See CLAUDE.md on never substituting our arithmetic
for the instrument's.

## What the real batch says

Measured on the 26-injection sphingolipid batch this was written against
(TripleTOF 5600, one 50–700 TOF MS survey, one scan every 14.6 s):

* **As the project ships, the batch has no lock mass at all.** None of its
  eleven internal standards carries a formula, so `MassTrend.exact` is None
  for every one of them and all 26 injections come back "no usable lock mass
  — left as measured". The feature is dormant, correctly, until somebody
  types a formula into the method.
* Given one formula — `SM(d18:1/12:0)`, C35H71N2O6P, [M+H]+ = 647.5123 —
  that standard is also the only one whose survey signal holds together
  across the run: `mass_drift` puts the other ten between 98 and 534 ppm of
  spread, which fails `same_ion`, and one has no survey covering it at all.
  So the fit is **one lock mass, offset only, in 25 of 26 injections** and
  every row says so.
* Those offsets: median **+4.8 ppm**, from −4.4 to +11.7, a spread of
  16.1 ppm — which is the same 16 ppm this batch's one standard scatters by
  between injections. **The correction is the size of its own uncertainty.**
  The lock mass's residual goes from a median −4.8 ppm to 0.0 by
  construction; with one lock mass there is nothing left over to check it
  against, which is why the verdict names the count.
* The figure that matters is the other components. Fifteen analytes inside
  the survey have a theoretical mass derivable from the lipid shorthand in
  their own names, independent of anything measured. Over 369 measurements
  of them the median error is −275 ppm before and −270 ppm after: those are
  interferences, not the compound, and no ppm-scale correction touches them.
  Over the 66 measurements that were within 25 ppm to begin with — where the
  survey plausibly found the right ion — the median error goes from
  **−8.7 ppm to −3.3 ppm** and the median magnitude from **9.9 to 7.0 ppm**,
  smaller on 43 of 66. It moves the centre in the right direction and it
  cannot do better than the one lock mass it was fitted from.
* And it is **not cosmetic**. Reprocessing the whole batch both ways, over
  ±20 ppm extraction windows, a median shift of 5 ppm moved 1,769 of 2,593
  integrated areas: median |Δ| 1.3%, 830 rows past 5%, and ten rows lost
  their peak. A TOF stores few points across a window that narrow, so
  shifting its edge takes whole points in or out — the same edge effect
  CLAUDE.md records about the vendor's extraction. Switching this on is a
  quantitative decision, not a display preference, which is why the switch
  is saved with the project and off by default.

A batch with four or more formula-bearing standards spread across the mass
range is what a linear term needs, and no such batch was available to
measure. Until one is, `MIN_SLOPE_LOCK_MASSES`, `MIN_MASS_SPAN` and the
leave-one-out test are written and tested but have never fired on real data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .mass_drift import MassDrift, mass_drift

#: fewest lock masses before a linear term is even considered. Four, not
#: three, because the slope is only kept when leave-one-out prediction says
#: it helps: hold one of three out and the line is fitted through two points,
#: which is exact and predicts nothing. Four is the first count at which
#: dropping one still leaves an over-determined fit.
MIN_SLOPE_LOCK_MASSES = 4

#: daltons the lock masses must span before a linear term is considered. A
#: slope fitted over ten daltons and used over six hundred is extrapolation
#: wearing a fit's clothes.
MIN_MASS_SPAN = 100.0

#: how much better, in ppm of leave-one-out median absolute residual, the
#: line has to predict a held-out lock mass before its slope is kept. The
#: median rather than a root mean square for the same reason the offset is a
#: median: one lock mass caught on an interference should not decide the
#: shape of the correction for the rest.
SLOPE_MARGIN_PPM = 0.5

#: iterations of the fixed point that inverts `apply`. The perturbation is
#: parts per million, so this converges to machine precision immediately;
#: three is belt and braces for a steep linear term.
UNDO_ITERATIONS = 3


@dataclass(frozen=True)
class LockMass:
    """One standard's measured mass in one injection, against its formula."""

    component: str
    #: from formula and adduct — never the method's written precursor
    theoretical: float
    #: what the survey scan read, uncorrected
    measured: float
    intensity: float = 0.0

    @property
    def error_ppm(self) -> float:
        """How far the instrument read it from where it belongs."""
        return (self.measured - self.theoretical) / self.theoretical * 1e6


@dataclass
class MassCorrection:
    """One injection's correction: what to add to a mass, in ppm."""

    sample_key: str = ""
    sample_name: str = ""
    #: ppm added at the pivot
    offset_ppm: float = 0.0
    #: ppm added per dalton away from the pivot; zero unless a slope was kept
    slope_ppm_per_da: float = 0.0
    pivot: float = 0.0
    lock_masses: list[LockMass] = field(default_factory=list)
    #: why there is no correction, or what the slope decision was
    note: str = ""

    # -- the correction itself ------------------------------------------------ #
    @property
    def usable(self) -> bool:
        return bool(self.lock_masses)

    @property
    def linear(self) -> bool:
        return self.slope_ppm_per_da != 0.0

    def ppm_at(self, mz):
        """The correction in ppm at one mass, or over an array of them."""
        mz = np.asarray(mz, dtype=float)
        if not self.usable:
            return np.zeros_like(mz)
        return self.offset_ppm + self.slope_ppm_per_da * (mz - self.pivot)

    def apply(self, mz):
        """
        Measured masses to corrected ones.

        Adding k ppm is one multiplication by (1 + k/10⁶), so a mass that
        was k ppm out lands k²/10¹² short of exact — 0.000036 ppm at 6 ppm,
        which is 1·10⁻⁸ Da at m/z 300. That is why the residual after a
        single lock mass reads 0.0 rather than being identically zero.
        """
        mz = np.asarray(mz, dtype=float)
        if not self.usable:
            return mz
        return mz * (1.0 + self.ppm_at(mz) * 1e-6)

    def undo(self, mz):
        """
        Corrected masses back to measured ones — what a raw file holds.

        This is what the extraction uses: the window a component asks for is
        written in corrected space and the reader only knows measured space.
        A constant offset inverts in one step; a linear term makes `apply`
        quadratic, so the inverse is a fixed point, which converges at
        parts-per-million strengths immediately.
        """
        mz = np.asarray(mz, dtype=float)
        if not self.usable:
            return mz
        guess = mz
        for _ in range(UNDO_ITERATIONS):
            guess = mz / (1.0 + self.ppm_at(guess) * 1e-6)
        return guess

    # -- how well it did ------------------------------------------------------ #
    @property
    def before_ppm(self) -> list[float]:
        return [lock.error_ppm for lock in self.lock_masses]

    @property
    def after_ppm(self) -> list[float]:
        out = []
        for lock in self.lock_masses:
            corrected = float(self.apply(lock.measured))
            out.append((corrected - lock.theoretical) / lock.theoretical * 1e6)
        return out

    @property
    def median_before(self) -> float | None:
        return float(np.median(self.before_ppm)) if self.lock_masses else None

    @property
    def median_after(self) -> float | None:
        return float(np.median(self.after_ppm)) if self.lock_masses else None

    @property
    def worst_before(self) -> float | None:
        values = self.before_ppm
        return max(values, key=abs) if values else None

    @property
    def worst_after(self) -> float | None:
        values = self.after_ppm
        return max(values, key=abs) if values else None

    @property
    def verdict(self) -> str:
        """
        One line saying what happened to this injection.

        The count of lock masses is part of the sentence, because a
        correction from one of them is an offset with nothing left over to
        check it against, and reading "corrected by +2.2 ppm" without that
        would suggest a measurement it is not.
        """
        if not self.usable:
            return self.note or "no usable lock mass — left as measured"
        count = len(self.lock_masses)
        if count == 1:
            shape = "offset only, from one lock mass — nothing checks it"
        elif self.linear:
            shape = (f"a slope of {self.slope_ppm_per_da * 1000:+.2f} ppm "
                     f"per 1,000 Da")
        else:
            shape = "offset only"
        plural = "es" if count != 1 else ""
        return (f"corrected by {self.offset_ppm:+.1f} ppm from "
                f"{count} lock mass{plural} ({shape})")

    def to_dict(self) -> dict:
        return {"sample_key": self.sample_key, "sample_name": self.sample_name,
                "offset_ppm": self.offset_ppm,
                "slope_ppm_per_da": self.slope_ppm_per_da,
                "pivot": self.pivot, "note": self.note,
                "lock_masses": [lock.component for lock in self.lock_masses]}


# --------------------------------------------------------------------------- #
# fitting
# --------------------------------------------------------------------------- #
def _offset_loo(errors: np.ndarray) -> float:
    """Leave-one-out median absolute residual of the plain offset."""
    residuals = []
    for index in range(errors.size):
        others = np.delete(errors, index)
        residuals.append(abs(errors[index] - float(np.median(others))))
    return float(np.median(residuals))


def _line_loo(masses: np.ndarray, errors: np.ndarray) -> float | None:
    """
    Leave-one-out median absolute residual of a straight line through the rest.

    Each fit uses every lock mass but one and is asked to predict the one it
    never saw. That is the whole test: a line drawn through the points it is
    then scored on is exact and says nothing, which is why
    `MIN_SLOPE_LOCK_MASSES` is four rather than three.
    """
    residuals = []
    for index in range(masses.size):
        x = np.delete(masses, index)
        y = np.delete(errors, index)
        if x.size < 3 or float(np.ptp(x)) == 0.0:
            return None
        slope, intercept = np.polyfit(x, y, 1)
        residuals.append(abs(errors[index] - (slope * masses[index] + intercept)))
    return float(np.median(residuals))


def fit_correction(sample_key: str, sample_name: str,
                   lock_masses: list[LockMass]) -> MassCorrection:
    """
    One injection's correction from its lock masses.

    The offset is the median error rather than the mean: two lock masses
    agreeing and a third caught on an interference should not drag the axis
    a third of the way towards the interference.
    """
    correction = MassCorrection(sample_key=sample_key, sample_name=sample_name,
                                lock_masses=list(lock_masses))
    if not lock_masses:
        correction.note = "no usable lock mass — left as measured"
        return correction

    masses = np.array([lock.theoretical for lock in lock_masses], dtype=float)
    errors = np.array([lock.error_ppm for lock in lock_masses], dtype=float)
    correction.pivot = float(np.median(masses))
    correction.offset_ppm = -float(np.median(errors))

    span = float(np.ptp(masses))
    if len(lock_masses) < MIN_SLOPE_LOCK_MASSES:
        plural = "es" if len(lock_masses) != 1 else ""
        correction.note = (f"{len(lock_masses)} lock mass{plural}: fewer than "
                           f"{MIN_SLOPE_LOCK_MASSES}, so an offset is all that "
                           f"can be fitted and checked")
        return correction
    if span < MIN_MASS_SPAN:
        correction.note = (f"lock masses span {span:,.0f} Da; a slope needs "
                           f"{MIN_MASS_SPAN:,.0f} Da before it is anything "
                           f"but extrapolation")
        return correction

    plain = _offset_loo(errors)
    line = _line_loo(masses, errors)
    if line is None or line + SLOPE_MARGIN_PPM >= plain:
        held = "—" if line is None else f"{line:.2f}"
        correction.note = (f"a slope did not help: leave-one-out {held} ppm "
                           f"against {plain:.2f} ppm for the offset alone")
        return correction

    slope, intercept = np.polyfit(masses, errors, 1)
    correction.slope_ppm_per_da = -float(slope)
    correction.offset_ppm = -float(slope * correction.pivot + intercept)
    correction.note = (f"a slope helped: leave-one-out {line:.2f} ppm against "
                       f"{plain:.2f} ppm for the offset alone")
    return correction


def lock_masses_from_drift(drift: MassDrift | None) -> dict[str, list[LockMass]]:
    """
    Reuse the mass-drift measurement: every trend that measured the same ion
    throughout and knows what mass it should have been.

    A trend that failed `same_ion` is left out entirely. Its points are not
    one ion measured badly, they are different ions measured well, and
    averaging them would recalibrate onto whatever happened to be nearest.
    """
    out: dict[str, list[LockMass]] = {}
    if drift is None:
        return out
    for trend in drift.trends:
        if trend.exact is None or trend.median is None or not trend.same_ion:
            continue
        for point in trend.points:
            out.setdefault(point.key or point.sample, []).append(LockMass(
                component=trend.component, theoretical=trend.exact,
                measured=point.mz, intensity=point.intensity))
    return out


def fit_batch(session, drift: MassDrift | None = None,
              progress=None) -> dict[str, MassCorrection]:
    """
    A correction per injection, keyed by sample key.

    The measurements come from `mass_drift` — the session's if one stands,
    otherwise one measured here — so a fit costs nothing after the drift has
    been looked at, and the two always agree about what was measured.

    Every loaded injection gets an entry, including the ones with no lock
    mass: an injection missing from the table would read as an injection
    nobody looked at.
    """
    if drift is None:
        drift = getattr(session, "mass_drift", None)
    if drift is None:
        drift = mass_drift(session.entries, session.method, progress=progress)
    if drift is None:                       # the operator cancelled
        return {}
    by_key = lock_masses_from_drift(drift)
    out: dict[str, MassCorrection] = {}
    for entry in session.entries:
        if not entry.is_loaded:
            continue
        out[entry.key] = fit_correction(entry.key, entry.name,
                                        by_key.get(entry.key, []))
    return out


def describe(corrections: dict[str, MassCorrection]) -> str:
    """One line about the whole batch, for a status bar or a report."""
    if not corrections:
        return "Not fitted yet."
    usable = [c for c in corrections.values() if c.usable]
    if not usable:
        return (f"No lock mass in any of {len(corrections)} injection(s). A "
                f"lock mass is an internal standard carrying a formula and an "
                f"adduct, measuring the same ion throughout the run; nothing "
                f"here does, so nothing is corrected.")
    counts = {len(c.lock_masses) for c in usable}
    offsets = np.array([c.offset_ppm for c in usable], dtype=float)
    spread = ("{}–{}".format(min(counts), max(counts)) if len(counts) > 1
              else f"{min(counts)}")
    said = [f"{len(usable)} of {len(corrections)} injection(s) corrected",
            f"{spread} lock mass(es) each",
            f"median offset {float(np.median(offsets)):+.1f} ppm"]
    if max(counts) == 1:
        said.append("an offset from one lock mass has nothing to check it")
    return " · ".join(said)
