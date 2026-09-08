---
title: Welcome
---
OpenQuant is open-source software for reviewing and quantifying liquid
chromatography – mass spectrometry data. It reads SCIEX `.wiff` files
directly and **mzML** from any instrument, and it does the two jobs that
SCIEX ships as two programs: qualitative review the way PeakView does it —
chromatograms, spectra, extracted ions, chemistry — and batch quantitation
the way MultiQuant does it — a component table, one chromatogram per sample
for every component, calibration curves, statistics and quality control.

This manual describes every part of the application, what each control
does, what each number means and, where a number was measured rather than
assumed, what was measured and on what. It is the same text in the
application's **Help ▸ Manual** window and in the printed copy that
**Help ▸ Export manual as PDF…** writes.

## How the manual is organised

| Section | What it covers |
|---|---|
| Getting started | [[installation]], [[formats]], [[starting-a-project]], and [[workspaces]] |
| Explorer | qualitative review: [[chromatograms-and-spectra]], the [[contour-view]], [[manual-xic]] |
| Chemistry and annotation | the [[mass-calculator]], the [[formula-finder]], [[lipid-maps]] and the [[accurate-precursor]] |
| Samples | the batch: [[samples-workspace]] |
| Method | the component table: [[method-workspace]], [[internal-standards-and-qualifiers]], [[check-method]], [[suggest-from-data]] |
| Analytics | quantitation: [[peak-review]], [[integration-parameters]], [[integration-algorithms]], [[calibration]], [[batch-qc]], the [[report]] |
| Reference | [[projects-and-files]], the [[command-line]], [[keyboard-shortcuts]], [[troubleshooting]], the [[glossary]] and the [[version-history]] |

## Reading it

Pages link to one another the way notes in a vault do. A link is drawn in
the accent colour; clicking it opens that page, and **Back** returns. Every
page ends with the list of pages that link to it, so a topic can be
approached from either end of any link.

The search box at the top of the window matches words by prefix — typing
`integr` finds integration, integrated and integrator — and a page is listed
only when it contains every word typed. The first hit is opened with Enter,
and the page scrolls to the first occurrence of the query.

## Conventions

- **Bold** names a control as it appears on screen: a button, a menu entry,
  a checkbox.
- `Code` is something typed, a file name, or a value exactly as the
  application shows it.
- Where a figure is quoted — a percentage, a count, a time — it was measured
  on real data, and the page says on what. Nothing in this manual is a
  vendor's claim repeated.
- Menu paths are written `File ▸ Export report…`.

## What OpenQuant is not

It is not a vendor-certified replacement for MultiQuant in a regulated
laboratory: there is no audit trail and no electronic signature. It is not
a spectral library search. And it does not reproduce SCIEX's own extraction
rule exactly — see [[measured-facts]] for the one place the two disagree,
by how much, and why the plain rule ships. Everything else in the feature
lists of both vendor programs is here, and the [[design-principles]] say
what was chosen when the two could not both be had.
