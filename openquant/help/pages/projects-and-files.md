---
title: Projects and files
---
## The project file

A project is one file, `name.oqproj`, JSON, readable by anything. It holds:

| Key | Content |
|---|---|
| `version` | the file format's version, currently 3 |
| `method` | the component table, the integration and acceptance defaults, the tolerance and units, the ion-ratio bands — everything on the [[method-workspace]] |
| `samples` | one entry per injection: the raw file's path and sample index, the display name, type, group, expected concentration, dilution and comment — everything on the [[samples-workspace]] |
| `results` | every row of the [[results-table]], including manual integrations, notes, the algorithm that produced each area, the points on the peak and, for a fitted peak, the model |
| `calibrations` | every curve: regression, weighting, coefficients, r², and each standard with whether it is used |

It does **not** hold the raw data — the project points at the files by
path — nor the last algorithm comparison, which is derived and rebuilt on
request. A file that has moved is reported by name when the project opens,
and the project opens without it; see [[starting-a-project]].

Projects written by the program under its earlier name, `.opvproj`, are
opened; nothing new is written with that suffix. A project written by an
older version opens in a newer one: fields the newer one added take their
defaults — a method saved before integration algorithms existed reads back
as *valley*, which is what it ran.

## Raw data

`.wiff` with its `.wiff.scan`, and mzML. Never modified. See [[formats]].
What a folder holds and what would go wrong in it — a companion that is
not there, a `.scan` under the wrong name, files no reader here can open —
is answered before anything is opened by *File ▸ Check a folder…*; see
[[checking-files]], which is also where the one repair, renaming a stray
`.scan`, is offered.

## CSV files

**The component table** — `Import CSV…` and `Export CSV…` in the Method
workspace; the layout and the accepted headers are on [[method-workspace]].

**Results** — `Export CSV…` under the results table writes the visible
columns of the visible rows; under the Statistics tab, the summary as
shown; in the Explorer, the Results tab's rows.

**Chromatograms and spectra** — `File ▸ Export chromatograms (CSV)…` writes
every trace on the Explorer's chromatogram as columns of time and
intensity; `Export spectrum (CSV)…` the spectrum on screen as m/z and
intensity.

## mzML

`File ▸ Export sample as mzML…` writes the selected sample spectrum for
spectrum; what survives the trip is on [[formats]].

## The report and the manual

`File ▸ Export report…` writes PDF or HTML — see [[report]]. `Help ▸ Export
manual as PDF…` writes this manual.

## Where the application keeps its own files

| What | Where |
|---|---|
| preferences | the platform's settings store, organisation `OpenQuant`, application `OpenQuant`: window geometry, last folder, folded panels, the start prompt |
| the .NET runtime, when installed by the bootstrap | `~/.dotnet` |
| downloaded NuGet assemblies, the LIPID MAPS index | `~/.openquant`, or the directory named by the `OPENPEAKVIEW_HOME` environment variable |

Deleting `~/.openquant` costs a download of the assemblies and the lipid
index the next time each is needed; nothing about any batch is in it.
