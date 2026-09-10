---
title: File formats
---
Two formats are read: SCIEX `.wiff` and mzML. One is written: mzML.

## .wiff

A SCIEX acquisition is two files, `name.wiff` and `name.wiff.scan`, and
both are needed — the first holds the method and the index, the second the
spectra. The `.wiff` alone opens: the sample list, the method, the total
ion chromatogram of every channel and the acquisition parameters are in
it, and the tree fills as if nothing were wrong. What is not in it is the
scan data, so the first spectrum asked for fails — and with it every
extracted ion chromatogram, the base peak chromatogram, the contour and
the quantitation, which all read the scans. OpenQuant tries one spectrum
when the file is opened and, if it fails, says so at once: a warning when
the file is added, a *⚠* in front of the sample in the tree, with the reason on hover, the reason in the spectrum pane's title where a spectrum would be,
and a note on any result row that could not be extracted. The message
names the file that has to be beside the `.wiff` and, when the folder
holds a `.scan` that belongs to no `.wiff` there, names that too — a
companion renamed by hand (`name.wiff_mix1.scan` next to `name_mix1.wiff`)
is the usual way the pair comes apart, and renaming it to
`name_mix1.wiff.scan` is the whole repair — which [[checking-files]] finds
and offers before the file is opened at all. A `.wiff2` beside the pair is
not read here, and nothing is lost by that — see the section below for what
was measured. They are read through SCIEX's own Clearcore2 libraries, which are
the only software able to decode the format and are redistributed by the
open-source package alpharaw. How they are made to work off Windows is
described in [[how-wiff-is-read]].

A `.wiff` can hold several samples; each is opened as its own entry. Files
are opened in shared read-only mode, so Analyst or a second OpenQuant window
can open the same file at the same time.

Every acquisition channel — every experiment of the method — is listed
with its type, precursor, mass range and collision energy, as the file
declares them. Totals, retention times and integrated areas that the vendor
library reports are used as reported; nothing is recomputed from the stored
points where the instrument's own figure exists, because summing the stored
points instead was measured to move every integrated area by 2%.

## .wiff2

A SCIEX OS instrument writes a third file beside the pair, `name.wiff2`,
and on a ZenoTOF 7600 an acquisition arrives as a trio. It is not opened
here, and the reason is measured rather than assumed.

It is not the same kind of file. A `.wiff` is an OLE compound document; a
`.wiff2` is a password-protected SQLite database. Asked to open one,
Clearcore2 says `Invalid OLE structured storage file`, and its own
`CheckDataFileIntegrity` calls it `NotWiffFile`. That was true of all nine
`.wiff2` in the folder this was tested on, with the companions beside them
and with each companion taken away in turn, and it stayed true when the
file was renamed to `.wiff` — so it is the container, not the extension.

More to the point, there is nothing in it to read. The Clearcore2 assembly
that writes a `.wiff2` declares the whole schema, and it is seven tables:
`header`, `sample`, `method`, `device_method`, `device_descriptor`,
`device_identifier` and `method_parameters_info`. Not one column holds a
spectrum, a peak, an intensity or a chromatogram. What the `header` table
holds is `wiff_hash`, `scan_hash` and `scan_size` — the identity and size
of the two files beside it. The `.wiff2` is the acquisition's method and
its record of its companions, not its data.

The file sizes say the same thing. Across those nine acquisitions the
`.wiff.scan` — which really does hold the spectra — spans 1.67 to 9.88 MB,
a factor of 5.9, while the `.wiff2` spans 303 to 406 kB, a factor of 1.34,
over five distinct values. The `.wiff2` tracks the `.wiff` (correlation
0.989), not the scan data (0.748).

So the `.wiff` of the same name holds the acquisition, and opening it
loses nothing: read with the `.wiff2` beside it and with the `.wiff2`
deleted, the same file gave the same sample, the same single experiment,
the same 473-point total ion chromatogram and the same 13,705-point first
spectrum. A `.wiff2` with no `.wiff` beside it is an acquisition that
cannot be opened here at all, and no reader could be written for it from
this container — the spectra are not in it. [[checking-files]] says which
of the two cases a folder is in before anything is opened.

## mzML

mzML is the open format ProteoWizard's `msconvert` writes from any vendor's
files, so a Thermo `.raw`, an Agilent `.d` or a Bruker `.tdf` gets in by
being converted first. Both profile and centroid spectra are read, and
zero-intensity points a vendor stripped from a profile are restored — see
[[chromatograms-and-spectra]] for why that matters.

mzML has no notion of an acquisition *channel*. The channels are inferred,
and inferred from the order of acquisition rather than only from the
properties of the scans: a method can have two experiments that agree on MS
level, precursor, collision energy and mass range, and grouping by
properties alone gave 69 channels where the acquisition had 81. A scheduled
method repeats its experiments in a fixed cycle, so position in the cycle is
the experiment. The file this was developed against is a cycle of 44 run
339 times followed by a cycle of 37 run 238 times — 44 + 37 = 81 channels,
44 × 339 + 37 × 238 = 23,722 spectra. A cycle has to repeat at least four
times to be believed; data-dependent acquisition has no cycle and falls back
to the scan properties.

## Writing mzML

`File ▸ Export sample as mzML…` in the Explorer writes the selected sample
spectrum for spectrum, with the total ion current the instrument reported
rather than one recomputed here. What survives the trip was measured on
five real 81-channel acquisitions read back through this program, and
cross-checked against ProteoWizard in both directions:

| | |
|---|---|
| spectra | identical, every channel, to the last digit |
| channel chromatograms | identical, every channel |
| the run's total ion chromatogram | identical, 577 points |
| integrated peak areas | identical |
| extracted ion chromatograms | **differ**, see below |

## The one difference: extracted ion chromatograms

SCIEX's own extraction counts part of a peak whose measured points fall
just outside the mass window; this program sums the points inside it. On
that acquisition the difference is a median 0.58% of peak height, at most
12%, and always lower here. End to end, quantifying one component from the
`.wiff` and from its mzML gives the same retention time and peak width and
an area 0.54% apart.

Two attempts were made at reproducing the vendor's edge rule. Both were
wrong: the second looked right on the windows it was derived from and, on
other windows, was better on 41 channels and worse on 38 — a coin toss. So
the plain rule ships and this paragraph is the warning. **Quantify a series
in one format.** See [[measured-facts]].

## Which format for what

| Task | Use |
|---|---|
| review and quantify SCIEX data | `.wiff` directly |
| data from another vendor | msconvert to mzML, then open the mzML |
| a series that must be compared over time | one format for the whole series |
| handing data to software that cannot read `.wiff` | export as mzML |

Raw files are never modified. Everything the program adds — sample types,
concentrations, the method, results — lives in the project file, see
[[projects-and-files]].
