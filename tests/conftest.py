"""
A clean slate between tests, because Qt and Python disagree about lifetimes.

Qt allows one QApplication per process, so every test module shares the same
one however many fixtures ask for it. A widget built inside a test is then
left to Python's garbage collector, which runs at moments Qt knows nothing
about — including in the middle of building an unrelated widget.

On Linux that was fatal. The collector freed a C++ widget the application
still had a pointer to, and the next thing to walk a QObject's children
dereferenced it: a segfault inside PyQt's own attribute lookup, landing in a
different test on every run and never in the test that caused it. macOS and
Windows read the same freed memory and survived, which is luck, not
correctness.

Proved by exhaustion before being fixed: every test file passes alone, and
the whole suite passes with each test in its own process. Nothing here is
about what a test does — only about what it leaves behind.
"""

import gc
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

# Every settings object the suite constructs would otherwise write to the
# person's real preferences: a test of the library panel left a pytest
# temporary path as the remembered library, and a test that closes the
# shell saves its window layout over the real one. The native store on
# macOS ignores setPath and setDefaultFormat applies only to the
# no-argument constructor, so ui.settings reads this variable instead —
# set before any widget exists, and inherited by a subprocess.
os.environ["OPENQUANT_SETTINGS"] = os.path.join(
    tempfile.mkdtemp(prefix="openquant-test-settings-"), "OpenQuant.ini")


@pytest.fixture(autouse=True)
def _settle_qt():
    """Collect and let Qt finish its deletions, between tests rather than during."""
    yield
    application = QtWidgets.QApplication.instance()
    if application is None:
        return
    gc.collect()
    application.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    application.processEvents()
