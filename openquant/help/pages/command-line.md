---
title: Command line
---
The installed application and the source tree answer to the same
arguments. From the source tree the command is `python3 run.py`; from an
installer it is the executable inside the application — on macOS
`/Applications/OpenQuant.app/Contents/MacOS/OpenQuant`.

```
OpenQuant [files...] [--selftest] [--digest]
```

| Argument | Effect |
|---|---|
| `files` | raw data files to open — `.wiff`, `.mzML` — into the window, in place of the start prompt |
| `--selftest` | open the files, report what was read, and exit without a window |
| `--digest` | print a numeric fingerprint of each file, for comparing one build against another, and exit |

## --selftest

Prints the version and the platform, whether the LIPID MAPS index is
installed, whether the SCIEX libraries are ready and where the .NET runtime
was found — or why they are unavailable — and then, for each file, how many
samples and channels were read, or the exception that stopped it. It is
what the installers run on themselves before being shipped, and the first
thing to run when a file will not open.

## --digest

For each file, one line per channel with a short hash of its time axis and
its total chromatogram, one per spectrum sampled, and one per integrated
peak with its area to nine decimals. Two builds that read the same file
should print byte-identical output; the release process compares the macOS
build, the Windows build and the source tree this way. From source on
macOS, from the CI disk image and from the Windows installer under
CrossOver, five real acquisitions gave the same output to the last digit.
The Windows build writes CRLF line endings, which is the only difference
`diff` will show.

## The bootstrap

```
python3 -m openquant.bootstrap --install
```

installs a .NET 8 runtime into `~/.dotnet` when the machine has none, and
fetches the compatibility assemblies Clearcore2 needs. It is needed once,
from source; the installers carry what they need. See [[installation]] and
[[how-wiff-is-read]].

## Scripting the data layer

The reader and the numerics work without the interface:

```
from openquant import WiffFile

sample = WiffFile("run.wiff").sample(0)
channel = sample.channels[65]
rt, tic = channel.tic()
rt, xic = channel.xic(183.0137, tolerance=0.02)
mz, i = channel.spectrum(channel.scan_at_rt(13.14))
mz, i = channel.spectrum_rt_range(13.0, 13.3)
```

`openquant.raw.open_raw(path)` returns the right reader for either format
with the same surface. `openquant.quantify.process(entries, method)` runs
a method over a batch and returns the results set; `openquant.report`
writes a report from a session; `openquant.compare.compare_algorithms` runs
the comparison. The chemistry layer — `openquant.chemistry` — parses
formulas, computes masses and isotope patterns and searches compositions,
and depends on neither the interface nor the vendor libraries.

Those are the modules themselves, and they are free to move. For a surface
that will not — a batch reprocessed and exported, a spectrum explained, a
library searched, a report written, in ten lines and with a stability
promise attached — use [[python-api]] instead.
