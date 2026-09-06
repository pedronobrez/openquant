"""
Reading a product spectrum against what a structure could produce.

Enumerating cleavages says which masses are *possible*; it says nothing about
which happen. The spectrum in front of the analyst does. Matching one against
the other turns an unranked list of arithmetic into a ranked one, and the
ranking is evidence from this sample rather than a general model.

The score is the share of the spectrum's intensity that a candidate accounts
for. Counting matched peaks instead would reward a candidate that explains
forty specks of noise over one that explains the base peak, which is backwards:
a product spectrum is mostly a handful of ions that matter.

What this cannot do is prove a structure. Several candidates usually explain
the same peaks, because isomers fragment alike and because a long enough list
of possible masses will cover a spectrum by accident. The unexplained peaks are
the honest part of the answer, so they are reported too.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .lipidmaps import LipidDatabase, LipidRecord
from .structure import PredictedIon, predict

#: how close a predicted mass has to be to a measured one, in ppm. A TripleTOF
#: holds a few ppm on a strong product ion and rather less on a weak one.
TOLERANCE_PPM = 20.0

#: peaks below this share of the base peak are not counted against a candidate:
#: a product spectrum's baseline is full of them and nothing explains them
NOISE_SHARE = 0.01


@dataclass(frozen=True)
class PeakMatch:
    """One measured peak, and the predicted ion that lands on it."""

    mz: float
    intensity: float
    ion: PredictedIon

    @property
    def error_ppm(self) -> float:
        if not self.ion.mz:
            return 0.0
        return (self.mz - self.ion.mz) / self.ion.mz * 1e6

    @property
    def error_mda(self) -> float:
        return (self.mz - self.ion.mz) * 1000.0


@dataclass
class Explanation:
    """What one candidate structure accounts for in a spectrum."""

    record: LipidRecord
    matches: list[PeakMatch] = field(default_factory=list)
    explained: float = 0.0        # intensity accounted for
    total: float = 0.0            # intensity that was there to account for
    considered: int = 0           # peaks above the noise share

    @property
    def share(self) -> float:
        """The fraction of the spectrum's intensity this accounts for."""
        return self.explained / self.total if self.total else 0.0

    @property
    def matched(self) -> int:
        return len(self.matches)

    @property
    def name(self) -> str:
        return self.record.name or self.record.abbrev

    def unexplained(self, peaks) -> list[tuple[float, float]]:
        """The peaks it does not account for — the honest half of the answer."""
        taken = {round(m.mz, 4) for m in self.matches}
        return [(mz, height) for mz, height in peaks
                if round(mz, 4) not in taken]


def match_peaks(peaks, ions: list[PredictedIon],
                tolerance_ppm: float = TOLERANCE_PPM) -> list[PeakMatch]:
    """
    Pair measured peaks with predicted ions, nearest first.

    Each peak takes at most one ion and each ion at most one peak, so a dense
    prediction cannot claim the same peak several times over and look better
    for it.
    """
    if not len(peaks) or not ions:
        return []
    ordered = sorted(ions, key=lambda i: i.mz)
    masses = np.array([i.mz for i in ordered])
    used: set[int] = set()
    matches: list[PeakMatch] = []
    for mz, intensity in peaks:
        window = mz * tolerance_ppm * 1e-6
        lo = int(np.searchsorted(masses, mz - window, side="left"))
        hi = int(np.searchsorted(masses, mz + window, side="right"))
        best, distance = None, window
        for index in range(lo, hi):
            if index in used:
                continue
            gap = abs(masses[index] - mz)
            if gap <= distance:
                best, distance = index, gap
        if best is not None:
            used.add(best)
            matches.append(PeakMatch(mz=float(mz), intensity=float(intensity),
                                     ion=ordered[best]))
    return matches


def explain(record: LipidRecord, peaks, charge: int = 1,
            tolerance_ppm: float = TOLERANCE_PPM,
            max_cuts: int = 1, max_losses: int = 2) -> Explanation | None:
    """How much of a spectrum one candidate structure accounts for."""
    molecule = record.molecule()
    if molecule is None:
        return None
    ions = predict(molecule, charge=charge, max_cuts=max_cuts,
                   max_losses=max_losses)
    matches = match_peaks(peaks, ions, tolerance_ppm)
    total = sum(height for _mz, height in peaks)
    explained = sum(m.intensity for m in matches)
    return Explanation(record=record, matches=matches, explained=explained,
                       total=total, considered=len(peaks))


def significant_peaks(mz, intensity, noise_share: float = NOISE_SHARE,
                      limit: int = 60) -> list[tuple[float, float]]:
    """The peaks worth explaining: above the noise share, strongest first."""
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if not mz.size:
        return []
    ceiling = float(intensity.max())
    if ceiling <= 0:
        return []
    keep = intensity >= ceiling * noise_share
    pairs = sorted(zip(mz[keep], intensity[keep]), key=lambda p: -p[1])
    return [(float(a), float(b)) for a, b in pairs[:limit]]


def candidates_for(database: LipidDatabase, precursor: float, adduct: str,
                   tolerance: float, unit: str = "ppm",
                   limit: int = 12) -> list[LipidRecord]:
    """
    Structures whose mass fits the precursor, one per species.

    A mass search answers with a family of isomers; taking one of each keeps
    the spectrum from being scored twelve times against the same formula.
    """
    seen: set[str] = set()
    chosen: list[LipidRecord] = []
    for match in database.search_mz(precursor, adduct, tolerance, unit):
        record = match.record
        if not record.structure:
            continue
        key = record.species
        if key in seen:
            continue
        seen.add(key)
        chosen.append(record)
        if len(chosen) >= limit:
            break
    return chosen


def rank_candidates(database: LipidDatabase, precursor: float, peaks,
                    adduct: str = "[M+H]+", tolerance: float = 20.0,
                    unit: str = "ppm", charge: int = 1,
                    max_cuts: int = 1, max_losses: int = 2,
                    limit: int = 12) -> list[Explanation]:
    """
    Every candidate for the precursor, ordered by what it accounts for.

    This is the whole point of the exercise: the enumerator cannot say which
    cleavage happens, and the spectrum can.
    """
    found = []
    for record in candidates_for(database, precursor, adduct, tolerance, unit,
                                 limit):
        explanation = explain(record, peaks, charge, TOLERANCE_PPM,
                              max_cuts, max_losses)
        if explanation is not None:
            found.append(explanation)
    found.sort(key=lambda e: (-e.share, -e.matched))
    return found
