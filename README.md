# OpenPeakView

A Python viewer for SCIEX LC-MS data (`.wiff` + `.wiff.scan`) that follows
PeakView's way of working: TIC, BPC, the individual channels of the acquisition
method, extracted ion chromatograms, and mass spectra scan by scan or averaged
over a selected region of a peak.

Runs on **macOS (Apple Silicon included)**, Linux and Windows.

![screenshot](docs/screenshot.png)

## What it does

### Navigation and display

| Feature | How |
|---|---|
| Open several `.wiff` files and overlay them | `File ▸ Open .wiff` (multi-select) |
| TIC of the whole sample | the “Sample TIC” node in the tree |
| TIC or BPC per channel | check the channels and pick `TIC`/`BPC` |
| Individual method channels | every experiment is listed with precursor, mass range and CE |
| Filter channels | search box (type `313.2`, for instance) |
| Spectrum of one scan | single click on the chromatogram |
| Step scan by scan | ← → or the ◀ ▶ buttons |
| Average spectrum of a region | Shift + drag on the chromatogram |
| Live preview | the spectrum follows the highlight while you drag or resize it |
| Integration of the selection | area, height, apex and S/N in the status bar |
| **Stack** | one pane per trace with the time axes locked together |
| **Overview** | navigator showing the full range and where the current zoom sits |
| **Mirror** | flips every other trace — sample against blank |
| **Cascade** | offsets the overlaid traces in x (min) and y (%) |
| Sample and method information | **Sample** tab (vial, volume, method, batch, DP/CE) |
| Preferences | everything is remembered between sessions |

### Extraction and quantification

| Feature | How |
|---|---|
| Target compound list | **Compounds** tab: name, precursor, fragment, RT, window, tolerance |
| Import/export the list | CSV, headers in English or Portuguese |
| Batch extraction | **Extract and integrate all** runs the list over every checked sample |
| Show one compound | double-click a row for its XIC across all samples |
| Results table | RT, area, height, width, S/N and a note; sortable and exportable |
| Automatic peak detection | **Detect peaks** integrates everything on the chromatogram |
| Manual XIC | **Manual XIC** tab: list of m/z plus a tolerance in Da or ppm |
| XIC from the spectrum | Shift + drag on the spectrum → right-click → *Extract XIC* |
| XIC from the peak list | double-click a row of the **Spectrum peaks** tab |
| Export | `File ▸ Export chromatograms / spectrum (CSV)` |

### Processing and interpretation

| Feature | How |
|---|---|
| Gaussian smoothing | **Smooth (σ, scans)**; 0 turns it off |
| Baseline removal | **Baseline (min)**; use a window wider than the broadest peak |
| Background subtraction | select a blank range → **Set background** |
| **Centroid** | turns the profile spectrum into sticks |
| **Markers** | drop a marker on a peak; the others are then labelled with their distance to it, which is how neutral losses and isotope spacings are read |

Smoothing and baseline removal apply to the drawing, the integration and the
export alike, so area and height always match what is on screen.

Mouse conventions in both panes: drag = rubber-band zoom, double-click = fit,
right-click = pyqtgraph menu (export image, axis options and so on).

## Installation

```bash
python3 -m pip install -r requirements.txt
python3 -m openpeakview.bootstrap --install   # fetches the .NET runtime (~30 MB) into ~/.dotnet
```

The second command is needed once, and only if there is no .NET 8 runtime on
the machine yet.

## Usage

```bash
python3 run.py
```

or open files directly:

```bash
python3 run.py demo_QC01.wiff demo_STD_L1.wiff
```

## Compound list

The **Compounds** tab reads a CSV with these columns (only `name` and
`precursor` are required):

```csv
name,precursor,fragment,rt,window,tolerance,unit
12,13-DiHOME,313.2384,183.1391,14.7,0.6,0.02,Da
9,10-DiHOME,313.2384,201.1496,14.2,0.6,20,ppm
```

With no `fragment` the XIC uses the precursor itself. With no `rt` the search
covers the whole run. The method channel is picked by precursor **and** by
retention time — necessary in scheduled methods, where the same precursor
appears in more than one period. When the matched channel does not cover the
requested time window, the result comes back with zero area and a note, rather
than a peak from some other time.

## How the .wiff file is read

The `.wiff`/`.wiff.scan` format is proprietary and has no public
specification. The only libraries able to decode it are SCIEX's own
**Clearcore2** assemblies — the same ones ProteoWizard/msconvert uses. They are
redistributed by the open source package
[`alpharaw`](https://github.com/MannLabs/alpharaw) (MIT) and are managed .NET
assemblies.

Off Windows they normally do not work, because `Clearcore2.StructuredStorage`
opens the file through the Windows-only COM API `StgOpenStorageEx`. The module
[`openpeakview/bootstrap.py`](openpeakview/bootstrap.py) works around that:

1. it locates (or installs) a .NET 8 runtime;
2. it downloads from NuGet the compatibility assemblies .NET Core does not ship
   (`System.Configuration.ConfigurationManager` and its dependencies) and
   registers a resolver for them;
3. by reflection it flips the static field `StgStorage.sWindows` to `False`,
   making Clearcore2 use its managed implementation (OpenMcdf) instead of the
   COM path.

With that, `.wiff` files are read natively on Apple Silicon, with no Docker, no
Wine and no Analyst installed. Files are opened with
`OpenFileMode.ReadOnlyShared`, so a second window — or Analyst itself — can
still open the same file.

**On licensing:** the code in this project is MIT. The Clearcore2 libraries
belong to SCIEX and are *not* open source — they are redistributable, the same
arrangement ProteoWizard relies on. There is no fully vendor-free `.wiff`
reader today. If that matters in your context, the alternative is to convert
the files to mzML with `msconvert` and read the mzML with
[`pyteomics`](https://github.com/levitsky/pyteomics).

## Layout

```
openpeakview/
  bootstrap.py           .NET runtime setup and the Clearcore2 patch
  wiff.py                WiffFile / Sample / Channel → numpy arrays
  compounds.py           target compound list (CSV)
  processing.py          smoothing, baseline, centroiding, peak detection, S/N
  ui/plots.py            chromatogram and spectrum panes (pyqtgraph)
  ui/chrom_area.py       stacked panes with linked time axes
  ui/compound_panel.py   compound manager
  ui/results_panel.py    results table
  ui/sample_info.py      sample information
  ui/main_window.py      main window
  app.py                 entry point
tests/                   pytest suite
```

Run the tests with `python3 -m pytest tests`, and check the reader against your
own files with `python3 selftest.py`.

The data layer works on its own, without any UI:

```python
from openpeakview import WiffFile

sample = WiffFile("demo_QC01.wiff").sample(0)
channel = sample.channels[65]                        # TOF PI, precursor 325.20
rt, tic = channel.tic()
rt, xic = channel.xic(183.0137, tolerance=0.02)      # fragment
mz, i = channel.spectrum(channel.scan_at_rt(13.14))  # one scan
mz, i = channel.spectrum_rt_range(13.0, 13.3)        # average over a region
```

## Data

The `.wiff`/`.wiff.scan` files are not tracked (see `.gitignore`): they are
large binaries that change with every run. Keep them wherever you like and open
them from the menu.

The files used during development come from a TripleTOF 5600 in negative mode,
a targeted MRM-HR method with 81 experiments across 2 periods: `TOF MS`
(100–2000) plus 80 `TOF PI` channels, one per precursor.
