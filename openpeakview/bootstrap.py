"""
Bootstrap of the .NET runtime used to read SCIEX WIFF files.

The .wiff/.wiff.scan format is proprietary. SCIEX's managed Clearcore2
libraries (redistributed by the open source `alpharaw` package, MIT) are the
only ones able to decode it. This module does the work needed to run them off
Windows:

1. locate (or install) a .NET runtime;
2. download the compatibility assemblies that .NET Core does not ship;
3. register an assembly resolver for those shims;
4. switch Clearcore2's structured storage from the COM path (the Windows-only
   `StgOpenStorageEx` API) to the managed OpenMcdf path, which works on macOS
   and Linux.

After `ensure()` the `Clearcore2` namespace imports normally.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen as _urlopen

CACHE_DIR = Path(os.environ.get("OPENPEAKVIEW_HOME", Path.home() / ".openpeakview"))
SHIM_DIR = CACHE_DIR / "shim"
DOTNET_CHANNEL = "8.0"

# Assemblies that Clearcore2 (built for .NET Framework) expects to find and
# that are not part of .NET Core. From NuGet, MIT licensed.
SHIM_PACKAGES = [
    ("system.configuration.configurationmanager", "8.0.1"),
    ("system.diagnostics.eventlog", "8.0.1"),
    ("system.security.cryptography.protecteddata", "8.0.0"),
    ("system.security.permissions", "8.0.0"),
    ("system.windows.extensions", "8.0.0"),
]

_READY = False
_IS_WINDOWS = platform.system() == "Windows"


def urlopen(url):
    """urlopen with certifi's CA bundle (macOS python.org builds ignore the system one)."""
    context = None
    try:
        import ssl

        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        context = None
    return _urlopen(url, context=context) if context else _urlopen(url)


class BootstrapError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# .NET runtime
# --------------------------------------------------------------------------- #
def find_dotnet_root() -> Path | None:
    """Look for a usable .NET runtime installation."""
    env = os.environ.get("DOTNET_ROOT")
    candidates = [Path(env)] if env else []
    candidates += [
        Path.home() / ".dotnet",
        Path("/usr/local/share/dotnet"),
        Path("/usr/share/dotnet"),
        Path("/opt/homebrew/opt/dotnet/libexec"),
    ]
    exe = shutil.which("dotnet")
    if exe:
        candidates.append(Path(exe).resolve().parent)
    for c in candidates:
        if (c / "shared" / "Microsoft.NETCore.App").is_dir():
            return c
    return None


def install_dotnet(channel: str = DOTNET_CHANNEL) -> Path:
    """Install the .NET runtime into ~/.dotnet (no sudo, about 30 MB)."""
    target = Path.home() / ".dotnet"
    print(f"[openpeakview] installing .NET runtime {channel} into {target} ...")
    if _IS_WINDOWS:
        raise BootstrapError(
            "Install the .NET Desktop Runtime from Microsoft: "
            "https://dotnet.microsoft.com/download"
        )
    script = CACHE_DIR / "dotnet-install.sh"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with urlopen("https://dot.net/v1/dotnet-install.sh") as r:
        script.write_bytes(r.read())
    script.chmod(0o755)
    subprocess.run(
        [str(script), "--channel", channel, "--runtime", "dotnet",
         "--install-dir", str(target)],
        check=True,
    )
    return target


# --------------------------------------------------------------------------- #
# compatibility assemblies
# --------------------------------------------------------------------------- #
def ensure_shims() -> Path:
    """Download the compatibility assemblies from NuGet if not cached yet."""
    marker = SHIM_DIR / "System.Configuration.ConfigurationManager.dll"
    if marker.exists():
        return SHIM_DIR
    SHIM_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_DIR / "nuget"
    tmp.mkdir(parents=True, exist_ok=True)
    for name, version in SHIM_PACKAGES:
        pkg = tmp / f"{name}.{version}.nupkg"
        if not pkg.exists():
            url = f"https://www.nuget.org/api/v2/package/{name}/{version}"
            print(f"[openpeakview] downloading {name} {version} ...")
            with urlopen(url) as r:
                pkg.write_bytes(r.read())
        with zipfile.ZipFile(pkg) as z:
            for entry in z.namelist():
                if entry.startswith("lib/net8.0/") and entry.endswith(".dll"):
                    dest = SHIM_DIR / Path(entry).name
                    dest.write_bytes(z.read(entry))
    return SHIM_DIR


# --------------------------------------------------------------------------- #
# bootstrap
# --------------------------------------------------------------------------- #
def ensure(auto_install_dotnet: bool = False) -> None:
    """Make the `Clearcore2` namespace ready to use. Idempotent."""
    global _READY
    if _READY:
        return

    if not _IS_WINDOWS:
        root = find_dotnet_root()
        if root is None:
            if not auto_install_dotnet:
                raise BootstrapError(
                    "No .NET runtime found. Run:\n"
                    "    python -m openpeakview.bootstrap --install\n"
                    "or install .NET 8 and point DOTNET_ROOT at it."
                )
            root = install_dotnet()
        os.environ["DOTNET_ROOT"] = str(root)
        os.environ.setdefault("ALPHARAW_DOTNET_RUNTIME", "coreclr")
        shim_dir = ensure_shims()

    # Load the runtime through alpharaw BEFORE any other `import clr`, because
    # pythonnet's runtime choice is process-wide.
    try:
        import alpharaw.raw_access.clr_utils as clr_utils  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise BootstrapError(
            "the `alpharaw` package is missing. Install it with: pip install alpharaw"
        ) from exc

    import System
    from System.Reflection import Assembly, BindingFlags

    if not _IS_WINDOWS:
        _register_shim_resolver(System, Assembly, shim_dir)
        _use_managed_structured_storage(Assembly, BindingFlags, clr_utils.ext_dir)

    from alpharaw.raw_access import pysciexwifffilereader as reader

    if not reader.HAS_DOTNET:
        raise BootstrapError(
            "Could not load the SCIEX Clearcore2 libraries. "
            "Check the .NET and pythonnet installation."
        )
    _READY = True


def _register_shim_resolver(System, Assembly, shim_dir: Path) -> None:
    """Resolve the NuGet compatibility assemblies by simple name."""
    loaded: dict[str, object] = {}
    for dll in sorted(shim_dir.glob("*.dll")):
        try:
            asm = Assembly.LoadFile(str(dll))
            loaded[str(asm.GetName().Name)] = asm
        except Exception:
            continue

    def resolve(sender, args):
        name = str(args.Name).split(",")[0]
        if name in loaded:
            return loaded[name]
        path = shim_dir / f"{name}.dll"
        if path.exists():
            asm = Assembly.LoadFile(str(path))
            loaded[name] = asm
            return asm
        return None

    System.AppDomain.CurrentDomain.add_AssemblyResolve(
        System.ResolveEventHandler(resolve)
    )
    # keep a live reference so the GC does not collect the delegate
    _register_shim_resolver.__dict__["_keepalive"] = resolve


def _use_managed_structured_storage(Assembly, BindingFlags, ext_dir: str) -> None:
    """
    Clearcore2.StructuredStorage picks between the Windows COM API
    (`StgOpenStorageEx`) and a managed implementation (OpenMcdf) through the
    private static field `StgStorage.sWindows`. On macOS/Linux the field comes
    up True and the COM call fails, so we force the managed path.
    """
    dll = Path(ext_dir) / "sciex" / "Clearcore2.StructuredStorage.dll"
    asm = Assembly.LoadFile(str(dll))
    field = asm.GetType("Clearcore2.StructuredStorage.StgStorage").GetField(
        "sWindows", BindingFlags.NonPublic | BindingFlags.Static
    )
    if field is None:  # pragma: no cover
        raise BootstrapError(
            "Unexpected Clearcore2.StructuredStorage layout "
            "(field sWindows not found)."
        )
    field.SetValue(None, False)


def _main(argv: list[str]) -> int:
    if "--install" in argv:
        if find_dotnet_root() is None:
            install_dotnet()
        ensure_shims()
    ensure(auto_install_dotnet=True)
    print("[openpeakview] .NET runtime and SCIEX libraries ready.")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
