---
title: The batch report
---
`File ▸ Export report…` writes the whole batch as a document: PDF for
handing over, HTML for keeping — the second opens in a browser long after
this application is gone, which is the point of a report as against an
export. It is built from the session rather than from the screen, so it
holds what was measured and not what happened to be on show.

## Sections

Numbered in the order printed; leaving one out closes the gap rather than
leaving a hole.

| Section | Holds |
|---|---|
| Summary | rows, samples, components; how many passed, were marginal, failed; excluded rows; and the findings — every failed row with its flags |
| Samples | the batch table: name, type, group, concentration, dilution, acquisition time |
| Method | the component table, the defaults, and the findings of [[check-method]] |
| Calibration | each curve's regression, weighting, equation, r², and its standards with accuracies; an internal standard's curve labelled as meaningless |
| Detection and quantitation limits | LOD and LOQ per component, with the notes of [[detection-limits-and-carryover]] |
| Carryover | the blank after the top standard, or why it was not measured |
| Batch quality | the control charts' verdicts, the injection response index, drift, and the precision of the QCs — [[batch-qc]] |
| Mass drift | only when the [[mass-drift]] tab has measured: each standard's mass through the run and whether the axis held |
| Sampling | points per peak for every component, the cycle times the peaks would need, and how many peaks were narrower than a cycle — the *Sampling* tab of [[batch-qc]] |
| Integration algorithms | only when [[compare-algorithms]] has been run: the totals per algorithm and the components that moved most |
| Batch comparison | only when [[compare-batches]] has been run: the totals side by side and the components in the order of how much they moved |
| Results | every row: sample, component, RT, area, ratio, concentration, accuracy, status and flags |
| Statistics | the grouped summary of the [[statistics]] page, by sample type |

Two markers on sample names are explained in a legend under the table that
uses them: `†` for a row excluded from the statistics, `‡` for a row
integrated by hand. A column of "yes / no / by hand" costs more width than
it earns.

A section with nothing to show says so — *no standards, so there is nothing
to carry over* — rather than printing an empty table.

## The printed layout

A4 portrait; a title block; a table of contents with page numbers; a
running header naming the report from page two and a footer with the
version, the date and *Page n of N* on every page, because a page that
comes loose has to say what it belongs to. Table heading rows repeat on
every page a table spans.

The document is laid out more than once. A heading left stranded at the
foot of a page with its content overleaf is pushed to the next page and the
document laid out again — up to three times, since moving one heading can
strand another — and the table of contents needs a pass of its own because
page numbers do not exist until the pages do. A hundred-page report is
therefore laid out three times and takes about seventeen seconds, which is
why the export shows a wait cursor rather than looking hung.

## A note on what was once wrong

The first version of the report printed at a twelfth of its size: eight
sections in the top corner of a single otherwise blank page. The layout was
being measured at the screen's resolution and printed at the writer's. It is
fixed, and two tests open every PDF written — one counts pages, one looks
for ink below the half-way line — because nothing about it was visible in
the HTML.

The same printing machinery produces this manual's PDF, from
**Help ▸ Export manual as PDF…**.

A report is what you keep. What you carry on working in is the Excel
workbook of the same sections — see [[export]], which also covers the
Skyline transition list.
