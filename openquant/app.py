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
    args = parser.parse_args(argv)

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
