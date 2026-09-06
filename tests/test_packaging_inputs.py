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
