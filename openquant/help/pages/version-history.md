---
title: Version history
---
The public repository begins at 0.6.1, after being recreated to drop a
history whose screenshots showed a person's name and unpublished results;
earlier versions exist as installers only. Every version below carries the
three installers described on [[installation]].

| Version | Date | What came in |
|---|---|---|
| 0.7.6 | 2026-09-09 | a `.wiff` without its `.wiff.scan` says so instead of leaving the spectrum pane empty — a warning when the file is added, the sample marked *⚠* in the tree, the reason written where the spectrum would be, and a note on the row instead of a stopped batch; the message names the `.scan` the file needs and any stray one in the folder — see [[formats]] and [[troubleshooting]]; the application icon on the bundle, the Windows executable and the window; the test suite keeps its settings in a file of its own rather than in the real preferences |
| 0.7.5 | 2026-09-08 | Explain with a structure or formula of one's own — a molfile from PubChem scored like a record, a formula's precursor and losses, and unplaced deuterium enumerated by count — see [[lipid-maps]]; **Pin spectrum** to draw one sample's spectrum over another's, with Normalise and Mirror for head-to-tail — see [[chromatograms-and-spectra]] |
| 0.7.4 | 2026-09-08 | the [[spectral-library]] measured on MassBank's 139,006 records — two matched peaks minimum, records without a precursor left out of a filtered search unless asked, the precursor tolerance at least the written precision, and an index that answers in milliseconds; the [[compare-batches]] result printed in the [[report]] while it stands |
| 0.7.3 | 2026-09-08 | the [[spectral-library]] tab of the Explorer — MSP and MGF libraries searched with the spectrum on screen, plain and reverse scores, the record overlaid; [[compare-batches]] — a reference project against the open batch, component by component, the reference read without opening a raw file |
| 0.7.2 | 2026-09-08 | **Export schedule…** in the [[method-workspace]]: the scheduled acquisition the method implies, with the dwell a target cycle leaves each transition at the busiest moment — [[acquisition-schedule]]; [[check-method]] names the precursors no survey scan covers |
| 0.7.1 | 2026-09-08 | **Suggest floors…** in [[batch-qc]]: a Min. response proposed per internal standard from the injections that were not failures, with its basis; the [[mass-drift]] tab and report section — every standard's precursor read from the survey in every injection, the change across the run, and the rule that a spread over 25 ppm is not the same ion twice |
| 0.7.0 | 2026-09-08 | F1 opens the page for the panel that has the focus, and every dialog has a Help button; the *Sampling* tab of [[batch-qc]] and its report section — points per peak counted at integration, the cycle times the peaks would need, one point per peak on the batch this was written for; the response floor an internal standard declares (**Min. response**), read by the control chart, the acceptance and [[check-method]] — see [[internal-standards-and-qualifiers]] |
| 0.6.9 | 2026-09-08 | this manual: forty-four pages linked like a vault, with search, backlinks and a printed copy from **Help ▸ Export manual as PDF…**; the orphan-heading rule of the [[report]] fixed for a heading whose next block was itself pushed to a new page |
| 0.6.8 | 2026-09-07 | three [[integration-algorithms]] — valley, summation, Gaussian fit — with every row saying which produced its number; [[compare-algorithms]] with the one-trace view, adoption, and a report section; the fit's three-points-on-the-flanks rule, measured on a real standard |
| 0.6.7 | 2026-09-07 | [[suggest-from-data]]: retention times calibrated per height band, windows from the sampling; **Exclude failed injections** in Batch QC; the [[check-method]] dialog; S/N reported as unmeasured rather than as a constant — [[signal-to-noise]] |
| 0.6.6 | 2026-09-07 | the injection response index and the unusable-chart verdict in [[batch-qc]]; a signal-to-noise condition on the charts; the detector given a margin either side of the window, which took a real batch from 1,771 to 2,665 peaks — [[integration-parameters]] |
| 0.6.5 | 2026-09-07 | the [[contour-view]]; the *nearest the expected RT* peak rule |
| 0.6.4 | 2026-09-07 | [[batch-qc]]: control charts against injection order with robust limits, drift, and QC precision |
| 0.6.3 | 2026-09-07 | the [[report]] fixed and redesigned — A4 portrait, contents with page numbers, running furniture; [[detection-limits-and-carryover]] |
| 0.6.2 | 2026-09-07 | the batch report, PDF and HTML; the screenshots from a synthetic batch |
| 0.6.1 | 2026-09-06 | the recreated public repository; one design system in the project's blue; sample groups and statistics by group; the metric plot coloured by group; the New Project wizard; renamed to OpenQuant from OpenPeakView |
| 0.6.0 | 2026-09-06 | the Windows and Linux installers alongside the macOS disk image; the Wine ICU shim documented |
| 0.5.x | 2026-09-06 | the Analytics workspace — peak review, results, calibration, acceptance, statistics; the Method and Samples workspaces; projects; LIPID MAPS annotation, structure explanation and the accurate precursor measurement; mzML reading and writing with the fidelity measurements on [[measured-facts]] |

The manual is part of every release: a version that changes what the
application does changes the page that describes it, and the printed copy
is regenerated from the same pages.
