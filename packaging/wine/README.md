# Running the Windows build under Wine or CrossOver

The Windows installer needs **Windows 10 1703 or newer** and will not start
under Wine as it stands. It fails at import with

    ImportError: DLL load failed while importing QtCore: Module not found.

which reads like a broken installer and is not one. `Qt6Core.dll` in the
PyQt6 wheel statically imports eighteen `ucnv_*` symbols from `icuuc.dll` —
ICU's converter API — and the wheel carries no ICU of its own, because
Windows has shipped one in `System32` since that release: a 36 KB
`icuuc.dll` forwarding to a 2.7 MB `icu.dll`. Wine implements neither, and a
static import that cannot be resolved fails the whole library. CrossOver's
own loader says so plainly:

    err:module:import_dll Library icuuc.dll (which is needed by
      ...\_internal\PyQt6\Qt6\bin\Qt6Core.dll) not found

`icuuc_stub.c` here exports those eighteen symbols and nothing else, and
answers as ICU does when it has no converter to offer. Qt then uses the
codecs it implements itself — UTF-8, UTF-16, UTF-32, Latin-1, the system
locale — which is everything this application reads or writes. What is given
up is the long tail of legacy encodings in file dialogs and text import.

## Building and installing it

    x86_64-w64-mingw32-gcc -O2 -shared -o icuuc.dll icuuc_stub.c \
        -nostdlib -Wl,--entry=0 -Wl,--no-seh

Copy the 8 KB result next to `Qt6Core.dll` in the installed application:

    <bottle>/drive_c/users/crossover/AppData/Local/OpenQuant/
        _internal/PyQt6/Qt6/bin/icuuc.dll

## Do not ship this in the installer

On a real Windows machine an application-local `icuuc.dll` is found before
the one in `System32`, so putting this in the MSI would take working ICU away
from every user who has it. It belongs only in a Wine prefix, added by hand
by someone who has read the paragraph above. A test in the suite checks that
the packaging never picks it up.

## What it was verified to do

With the stub in place, CrossOver 26.3 on macOS ran the Windows build and
read a real acquisition:

    OpenQuant 0.5.2 on Windows AMD64, Python 3.13.15
    SCIEX libraries: ready
    demo_Sample_01.wiff: 1 sample(s), 81 channel(s),
        first TIC 339 points, max 5,355,040

The same numbers the macOS build gives for that file, and the window opens.
Nothing about that is a promise: it is one bottle, on one machine, once.
