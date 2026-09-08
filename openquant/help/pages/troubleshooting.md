---
title: Troubleshooting
---
The status bar usually says why something did not happen. When it does
not, this table is the next place to look.

## Opening files

| Symptom | Look at |
|---|---|
| A `.wiff` will not open; *SCIEX libraries: unavailable* | run `OpenQuant --selftest file.wiff` for the reason. From source, `python3 -m openquant.bootstrap --install` fetches the .NET runtime and the assemblies. See [[how-wiff-is-read]] |
| *the .wiff.scan file is missing* | the acquisition is two files and both must be beside each other |
| Windows: *DLL load failed while importing QtCore* | the machine is older than Windows 10 1703, or the build is running under Wine — see [[installation]] |
| macOS: *"OpenQuant" cannot be opened* | the quarantine flag; right-click and Open, or `xattr -dr com.apple.quarantine /Applications/OpenQuant.app` |
| A project opens with files listed as missing | they moved; put them back or add them again from the same place, then reprocess. See [[starting-a-project]] |
| An mzML has the wrong number of channels | the file has no repeating cycle and the channels were inferred from scan properties alone. See [[formats]] |
| An mzML spectrum looks as if its baseline is raised | the file is centroided, or the zeros could not be restored. See [[chromatograms-and-spectra]] |

## Integration

| Symptom | Look at |
|---|---|
| *no matching channel* | no channel carries the precursor within 0.7 Da with the target in range and, if a time is set, acquired at that time. See [[method-workspace]] |
| *channel does not cover 5.10–6.10 min* | the channel was not acquired over the window; the retention time or the channel is wrong |
| *only 4 points to detect in* | the window is narrower than the sampling; widen it — [[suggest-from-data]] computes the width |
| *no peak above noise* on a panel that plainly shows a peak | the gates: Min. height relative to the tallest in the range, or Min. S/N. See [[integration-parameters]] |
| The wrong of two peaks was taken | switch **Peak** to *nearest the expected RT*, and raise Min. height if the window is full of small peaks |
| S/N shows `—` | the baseline could not be measured, which is normal on a scheduled acquisition. See [[signal-to-noise]] |
| *Gaussian fit not possible* | the peak has fewer than three points on its flanks; the valley area stands. See [[integration-algorithms]] |
| Areas differ between a `.wiff` and its mzML | expected, about half a per cent; check it is not fifty. See [[formats]] |
| A row I integrated by hand keeps coming back | it is kept on purpose; right-click the panel → *Back to automatic integration* |

## Calibration and review

| Symptom | Look at |
|---|---|
| *No curve yet* | no samples typed Standard with a concentration, or fewer than the regression needs. See [[calibration]] |
| Every status is empty | no acceptance criteria are set; that is not a pass. See [[acceptance-criteria]] |
| An internal standard shows a problem in the IS column | the name does not match a component, or that component is not ticked IS. See [[internal-standards-and-qualifiers]] |
| Batch QC says the order is the opening order | some files carry no acquisition time |
| Every internal standard is flagged | look at their median response; standards of a few counts cannot normalise anything. See [[batch-qc]] |

## The application

| Symptom | Look at |
|---|---|
| The application will not quit | a modal dialog is open somewhere, possibly behind the window |
| *All components* in the grid is slow | it extracts every trace of every component; it pages as it goes, and a real batch is about a hundred seconds for the first page |
| The report is blank or tiny | it should not be — that bug is fixed and tested; if it recurs, the PDF viewer is the next suspect. See [[report]] |
| The LIPID MAPS download fails | the network, or a certificate store the bundled `certifi` does not know; the file can be placed by hand under `~/.openquant/lipidmaps/` |
| Two builds give different numbers | `--digest` both and compare; the Windows build writes CRLF. See [[command-line]] |

## Reporting a problem

The repository is `github.com/pedronobrez/openquant`. The output of
`--selftest` on the file concerned, the version, the platform and the
project file — never the raw data, which is yours — are what an issue
needs.
