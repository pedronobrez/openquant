"""
The files the installers are built from are only ever read by a build machine.

A mistake in one of them surfaces minutes into a release run, on a system the
author may not have, as an error about something else — WiX reports a stray
double hyphen in a comment as "not a valid source file". These read them here
instead.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WXS = ROOT / "packaging" / "openquant.wxs"


def test_the_windows_installer_source_is_valid_xml():
    ET.parse(WXS)


def test_the_windows_installer_pins_its_toolset():
    """WiX 7 will not build without accepting a paid maintenance-fee EULA."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    install = [line for line in workflow.splitlines()
               if "dotnet tool install" in line and "wix" in line]
    assert install, "the workflow no longer installs WiX"
    assert all(re.search(r"--version\s+5\.", line) for line in install), install


def test_the_spec_and_the_package_agree_on_the_version():
    import openquant

    spec = (ROOT / "packaging" / "openquant.spec").read_text()
    assert "__version__" in spec, "the spec should read the version, not repeat it"
    assert openquant.__version__ not in spec, "the spec has a version written into it"


def test_the_wine_shim_stays_out_of_the_installer():
    """
    It must never be packaged.

    On real Windows an application-local icuuc.dll is found before the one in
    System32, so shipping the stub would replace working ICU with a stub for
    every user who has the real thing. It exists to be copied into a Wine
    prefix by hand.
    """
    stub = ROOT / "packaging" / "wine" / "icuuc_stub.c"
    assert stub.exists(), "the shim's source is gone but its guard is still here"

    spec = (ROOT / "packaging" / "openquant.spec").read_text()
    wxs = WXS.read_text()
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for name, text in (("spec", spec), ("wxs", wxs), ("workflow", workflow)):
        assert "icuuc" not in text.lower(), f"the {name} references the ICU shim"

    # and nothing built by PyInstaller may carry one either
    built = ROOT / "dist"
    if built.is_dir():
        found = [p for p in built.rglob("icuuc*") if p.is_file()]
        assert not found, f"an ICU shim reached the build: {found}"
