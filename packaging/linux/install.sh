#!/bin/sh
# Registers the unpacked OpenQuant with the desktop: a launcher entry and its
# icon, for the current user only, nothing under /usr. The application runs
# from wherever this folder was unpacked; move the folder and run this again.
#
#     tar xzf OpenQuant-<version>-linux-x86_64.tar.gz
#     ./OpenQuant/install.sh
#
# Undo with:  ./OpenQuant/install.sh --remove
set -e
here=$(cd "$(dirname "$0")" && pwd)
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
if [ "$1" = "--remove" ]; then
    rm -f "$apps/openquant.desktop" "$icons/openquant.png"
    echo "launcher entry and icon removed"
    exit 0
fi
[ -x "$here/OpenQuant" ] || { echo "OpenQuant binary not found beside this script" >&2; exit 1; }
mkdir -p "$apps" "$icons"
sed "s|INSTALLDIR|$here|g" "$here/openquant.desktop" > "$apps/openquant.desktop"
cp "$here/openquant.png" "$icons/openquant.png"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$apps" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "${icons%/256x256/apps}" 2>/dev/null || true
echo "OpenQuant registered: $apps/openquant.desktop -> $here/OpenQuant"
