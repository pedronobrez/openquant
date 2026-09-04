"""Application entry point."""

from __future__ import annotations

import argparse
import sys

import pyqtgraph as pg
from PyQt6 import QtWidgets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openpeakview",
        description="Open source viewer for SCIEX LC-MS data (.wiff).",
    )
    parser.add_argument("files", nargs="*", help=".wiff files to open")
    args = parser.parse_args(argv)

    pg.setConfigOptions(antialias=True, background="w", foreground="#222")

    app = QtWidgets.QApplication(sys.argv[:1])
    app.setApplicationName("OpenPeakView")

    from .ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    for path in args.files:
        window.load_file(path)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
