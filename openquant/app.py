"""Application entry point."""

from __future__ import annotations

import argparse
import sys

from PyQt6 import QtWidgets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openquant",
        description="Open source quantitation for SCIEX LC-MS data (.wiff).",
    )
    parser.add_argument("files", nargs="*", help=".wiff files to open")
    args = parser.parse_args(argv)

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
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
