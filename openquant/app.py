"""Application entry point."""

from __future__ import annotations

import argparse
import sys

from PyQt6 import QtCore, QtWidgets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openquant",
        description="Open source quantitation for SCIEX LC-MS data (.wiff).",
    )
    parser.add_argument("files", nargs="*", help=".wiff files to open")
    parser.add_argument(
        "--selftest", action="store_true",
        help="open the files, report what was read, and exit without a window")
    parser.add_argument(
        "--digest", action="store_true",
        help="print a numeric fingerprint of each file, for comparing one "
             "build against another; implies --selftest's silence")
    args = parser.parse_args(argv)

    if args.digest:
        return _digest(args.files)
    if args.selftest:
        return _selftest(args.files)

    app = QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName("OpenQuant")

    from .ui import style
    from .ui.theme import apply_defaults

    style.apply(app)
    apply_defaults()

    from .ui.shell import MainShell

    window = MainShell()
    window.show()
    for path in args.files:
        window.load_file(path)
    if not args.files:
        window.offer_start()
    status = app.exec()
    _shut_down(app, window)
    return status


def _shut_down(app, window) -> None:
    """
    Take the window down before the interpreter does.

    PyQt registers an atexit hook that walks every Python wrapper it still
    holds and cleans up the Qt object behind it. If Qt has already destroyed
    that object — which it does for every child of a window as the window
    goes — the hook dereferences freed memory. On Linux that segfaults on
    quit: the application has done its work and printed its output, and the
    process still dies with signal 11, which is what a user sees and what a
    script reads.

    Deleting the window here, and letting Qt finish, leaves the hook nothing
    to trip over.
    """
    import gc

    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    app.processEvents()
    del window
    gc.collect()


def _digest(files: list[str]) -> int:
    """
    A numeric fingerprint of what this build reads, line by line.

    --selftest answers whether a build can open a file at all. This answers
    the harder question: whether two builds, on two systems, get the same
    numbers out of it. The output is plain text, one fact per line, meant to
    be diffed — so it carries every channel's totals at full precision and a
    hash of each array, rather than a summary that could hide a difference in
    the middle of a trace.

    The integrated areas are here too. Those are the numbers a result is made
    of, and a build that reads the same raw points but integrates them
    differently is not the same build.
    """
    import hashlib
    import os

    import numpy as np

    from . import __version__
    from .bootstrap import ensure
    from .processing import detect_peaks
    from .wiff import WiffFile

    def line(*parts) -> None:
        print("\t".join(str(p) for p in parts), flush=True)

    def fingerprint(values) -> str:
        """A hash of the array, to six decimals — the precision anyone reads."""
        rounded = np.round(np.asarray(values, dtype=float), 6)
        return hashlib.sha256(rounded.tobytes()).hexdigest()[:16]

    print(f"# openquant {__version__} digest")
    try:
        ensure()
    except Exception as exc:
        print(f"# cannot read: {exc}")
        return 1

    for path in files:
        name = os.path.basename(str(path).replace("\\", "/"))
        wiff = WiffFile(path)
        try:
            sample = wiff.sample(0)
            channels = sample.channels
            line("file", name, "channels", len(channels))

            time, total = sample.tic()
            line("sample.tic", name, len(time),
                 f"{float(np.sum(total)):.6f}", f"{float(np.max(total)):.6f}",
                 fingerprint(time), fingerprint(total))

            for index, channel in enumerate(channels):
                x, y = channel.tic()
                line("channel", index, channel.info.label, len(x),
                     f"{float(np.sum(y)):.6f}", f"{float(np.max(y)):.6f}",
                     fingerprint(x), fingerprint(y))

            # a few channels in full: spectra, extracted traces, and the
            # integration that a quantitative result is actually made of
            for index in [i for i in (0, 1, 20, 40, 80) if i < len(channels)]:
                channel = channels[index]
                x, y = channel.tic()
                if not len(x):
                    continue
                apex = int(np.argmax(y))
                scan = channel.scan_at_rt(float(x[apex]))
                mz, intensity = channel.spectrum(scan)
                line("spectrum", index, scan, len(mz),
                     f"{float(np.sum(mz)):.6f}", f"{float(np.sum(intensity)):.6f}",
                     fingerprint(mz), fingerprint(intensity))

                xic_x, xic_y = channel.xic(264.2686, 0.02)
                line("xic", index, len(xic_x), f"{float(np.sum(xic_y)):.6f}",
                     fingerprint(xic_y))

                for peak in detect_peaks(x, y)[:5]:
                    line("peak", index, f"{peak.apex_rt:.9f}",
                         f"{peak.start_rt:.9f}", f"{peak.end_rt:.9f}",
                         f"{peak.area:.9f}", f"{peak.height:.9f}")
        finally:
            wiff.close()
    return 0


def _selftest(files: list[str]) -> int:
    """
    Report what this build can actually do, and exit.

    A packaged application either reads a .wiff or it does not, and the only
    honest way to know is to make it read one. Nothing here opens a window, so
    it runs the same on a build machine as on a desk.
    """
    import platform

    from . import __version__

    print(f"OpenQuant {__version__} on {platform.system()} "
          f"{platform.machine()}, Python {platform.python_version()}")

    from .lipidmaps import is_installed
    print(f"LIPID MAPS index: {'installed' if is_installed() else 'not installed'}")

    from . import bootstrap
    try:
        bootstrap.ensure()
        print(f"SCIEX libraries: ready (.NET at {bootstrap.find_dotnet_root()})")
    except Exception as exc:
        print(f"SCIEX libraries: unavailable — {exc}")
        return 1 if files else 0

    from .wiff import WiffFile
    for path in files:
        wiff = None
        try:
            wiff = WiffFile(path)
            sample = wiff.sample(0)
            x, y = sample.channels[0].tic()
            print(f"{path}: {len(wiff.sample_names)} sample(s), "
                  f"{len(sample.channels)} channel(s), "
                  f"first TIC {x.size} points, max {y.max():,.0f}")
        except Exception as exc:
            print(f"{path}: FAILED — {type(exc).__name__}: {exc}")
            return 1
        finally:
            if wiff is not None:
                wiff.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
