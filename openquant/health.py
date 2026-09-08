"""
What the method itself will fail at, before a batch is processed.

Everything reported here was found by hand on a real method over the course
of a day, and every one of them is mechanically detectable: eighty-two
components with no retention time, twenty-four sharing a transition with
nothing to separate them, an internal standard for a third of the panel with
no time of its own, windows narrower than the sampling can resolve.

None of it is about the data being bad. It is about the method asking for
something the acquisition cannot deliver, which is a different problem and
has a different fix — and one worth learning about before a batch is
processed rather than from the results afterwards.

The checks that need a batch open are skipped without one and say so, rather
than passing quietly.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .components import Component
from .method import ProcessingMethod
from .samples import SampleEntry

SERIOUS = "serious"
WARNING = "warning"

#: the fewest points across a retention-time window for a peak to be found in
#: it. Below five `detect_peaks` declines outright; below about eight there is
#: not enough of a peak to place its edges with any confidence.
COMFORTABLE_POINTS = 8


@dataclass(frozen=True)
class Finding:
    """One thing wrong with the method, and who it affects."""

    check: str
    severity: str
    summary: str
    components: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def count(self) -> int:
        return len(self.components)


@dataclass
class MethodHealth:
    findings: list[Finding] = field(default_factory=list)
    #: checks that could not run, and why
    skipped: list[str] = field(default_factory=list)
    components: int = 0

    @property
    def serious(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SERIOUS]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def sound(self) -> bool:
        return not self.findings


def _served_by(method: ProcessingMethod) -> dict[str, list[str]]:
    served: dict[str, list[str]] = defaultdict(list)
    for component in method.components:
        if component.internal_standard:
            served[component.internal_standard].append(component.name)
    return served


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def shares_transition(a: Component, b: Component) -> bool:
    """
    Whether the mass spectrometer sees these two as the same measurement.

    Both windows have to overlap: two components with the same precursor but
    different fragments are separate channels and are not in question.
    """
    if not _overlap(a.mass_window(), b.mass_window()):
        return False
    span = max(a.tolerance, b.tolerance)
    half = (a.precursor * span * 1e-6 if a.unit.lower() == "ppm" else span)
    return abs(a.precursor - b.precursor) <= half


def check_method(method: ProcessingMethod,
                 entries: list[SampleEntry] | None = None) -> MethodHealth:
    """
    Read the method against itself, and against the batch where one is open.

    The order of the findings is the order they cost somebody time in: what
    silently produces a wrong number first, then what produces no number.
    """
    components = [c for c in method.components if c.is_valid]
    health = MethodHealth(components=len(components))
    served = _served_by(method)
    internal = {c.name for c in method.components if c.is_internal_standard}

    # -- the method against itself ------------------------------------------ #
    shared: list[str] = []
    for index, a in enumerate(components):
        for b in components[index + 1:]:
            if not shares_transition(a, b):
                continue
            windows = (a.rt_window(), b.rt_window())
            if None in windows or _overlap(*windows):
                shared.extend([a.name, b.name])
    if shared:
        names = sorted(set(shared))
        health.findings.append(Finding(
            "shared transition", SERIOUS,
            f"{len(names)} components cannot be told apart",
            names,
            "They share a precursor and a fragment within tolerance, and "
            "their retention-time windows overlap or are missing. The "
            "instrument measures one trace for both, so both report the same "
            "number. Only a retention time separates them."))

    unnamed = [c.name for c in components
               if c.internal_standard and c.internal_standard not in internal]
    if unnamed:
        health.findings.append(Finding(
            "missing internal standard", SERIOUS,
            f"{len(unnamed)} components name an internal standard the method "
            f"does not have",
            sorted(unnamed),
            "Their ratios cannot be formed, so nothing they report is "
            "normalised."))

    blind = sorted(name for name in internal
                   if not next((c for c in components if c.name == name),
                               Component("", 1, 1)).rt and served.get(name))
    if blind:
        detail = "; ".join(f"{name} serves {len(served[name])}" for name in blind)
        health.findings.append(Finding(
            "internal standard without a time", SERIOUS,
            f"{len(blind)} internal standards have no retention time",
            blind,
            f"Each is searched over the whole run and the largest peak "
            f"anywhere wins, so the standard everything is divided by may be "
            f"a different peak in every injection. {detail}."))

    untimed = [c.name for c in components if not c.rt]
    if untimed:
        health.findings.append(Finding(
            "no retention time", WARNING,
            f"{len(untimed)} of {len(components)} components have no "
            f"retention time",
            sorted(untimed),
            "The window is the whole run and the largest peak in it is taken, "
            "whether or not it is the analyte."))

    # -- the method against the acquisition ---------------------------------- #
    if not entries:
        health.skipped.append(
            "how many points fall in each retention-time window — open a "
            "file and the window can be measured against the sampling")
        return health

    narrow = _narrow_windows(components, method, entries)
    if narrow:
        health.findings.append(Finding(
            "window too narrow", SERIOUS,
            f"{len(narrow)} components have a window the sampling cannot "
            f"resolve",
            sorted(narrow),
            f"Fewer than {COMFORTABLE_POINTS} scans fall inside it. A peak "
            f"cannot be placed, let alone integrated, on that few points; "
            f"widen the window or accept that the area is an estimate."))
    return health


def _narrow_windows(components: list[Component], method: ProcessingMethod,
                    entries: list[SampleEntry]) -> list[str]:
    """Components whose window holds too few scans to find a peak in."""
    from .matching import match_channel

    loaded = [e for e in entries if e.is_loaded]
    if not loaded:
        return []
    sample = loaded[0].sample
    narrow = []
    for component in components:
        window = component.rt_window()
        if window is None:
            continue
        try:
            channel = match_channel(sample, component)
        except Exception:
            channel = None
        if channel is None:
            continue
        times = np.asarray(channel.rt, dtype=float)
        if times.size == 0:
            continue
        inside = int(np.sum((times >= window[0]) & (times <= window[1])))
        if inside < COMFORTABLE_POINTS:
            narrow.append(component.name)
    return narrow
