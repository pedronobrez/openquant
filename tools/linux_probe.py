"""
Why does building a plot widget crash on Linux?

The suite segfaults inside pyqtgraph's PlotWidget constructor, in a different
test on each run, on both Python versions and under both the offscreen
platform and a real X server. The location moving suggests accumulation
rather than a bad call, but that is a guess, and this measures it.

Two questions, in one process each so a crash in one still leaves the other's
answer:

    python tools/linux_probe.py grow     widgets kept alive, forever
    python tools/linux_probe.py churn    widgets created and destroyed

If `grow` dies at a repeatable count and `churn` does not, the cause is
accumulation and the fix belongs in the tests, which never destroy anything.
If both die, or `grow` dies at a random count, it is something else.
"""

import os
import resource
import sys

import pyqtgraph as pg
from PyQt6 import QtWidgets


def current_rss_mb() -> float:
    """
    Resident memory now — not the peak.

    getrusage reports ru_maxrss, a high-water mark that never falls, which
    would show the churn run growing even if every widget were being freed.
    """
    try:
        for line in open("/proc/self/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576


def report(n: int) -> None:
    try:
        fds = len(os.listdir("/proc/self/fd"))
    except OSError:
        fds = -1
    print(f"{n:5d}  rss={current_rss_mb():8.1f} MB  fds={fds}", flush=True)


def grow(app, limit: int) -> None:
    kept = []
    for n in range(1, limit + 1):
        kept.append(pg.PlotWidget())
        if n % 25 == 0:
            report(n)
    print(f"survived {limit} kept alive", flush=True)


def churn(app, limit: int) -> None:
    for n in range(1, limit + 1):
        widget = pg.PlotWidget()
        widget.setParent(None)
        widget.deleteLater()
        del widget
        app.processEvents()
        if n % 25 == 0:
            report(n)
    print(f"survived {limit} created and destroyed", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "grow"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    application = QtWidgets.QApplication([])
    print(f"platform: {application.platformName()}  mode: {mode}", flush=True)
    {"grow": grow, "churn": churn}[mode](application, limit)
