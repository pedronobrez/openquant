"""
Does the main window come up on this system?

Run as a script in a process of its own, not collected by pytest: building
the whole shell is not something to do in the middle of a suite, and a crash
here should take down only itself. CI runs it on every system, which is the
only thing that can answer the question for Linux and Windows.

    python -X faulthandler tests/smoke_start.py
"""

import platform
import sys

from PyQt6 import QtWidgets

import openquant
from openquant.ui import style
from openquant.ui.theme import apply_defaults


def main() -> int:
    app = QtWidgets.QApplication([])
    style.apply(app)
    apply_defaults()
    print("style applied", flush=True)

    from openquant.ui.shell import MainShell

    window = MainShell()
    print("shell built", flush=True)
    window.show()
    print("shown", flush=True)
    app.processEvents()
    print("events processed", flush=True)
    window.close()
    print(f"OpenQuant {openquant.__version__} started on {platform.system()}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
