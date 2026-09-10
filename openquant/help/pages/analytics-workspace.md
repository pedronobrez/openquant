---
title: The Analytics workspace
---
The Analytics workspace (Ctrl+2) is the batch, quantitatively: every
component across every sample, the integration of each, the curves, the
statistics and the quality of the run. It is built the way MultiQuant is —
a component chosen on the left, one chromatogram per sample for it in the
middle, and the table underneath.

## Layout

**Left.** The component tree, grouped by the method's groups, with **All
components** at the top; a filter box above it; and two folding panels
beneath: **Integration** ([[integration-parameters]]) and **Acceptance**
([[acceptance-criteria]]). The panels start folded, because open they leave
the tree a few rows tall, and whether they were open is remembered.

**Centre.** The [[peak-review]] grid: one panel per sample for the selected
component, with the integrated area shaded.

**Bottom.** Eight tabs: [[results-table|Results]],
[[calibration|Calibration]], [[statistics|Statistics]],
[[metric-plot|Metric plot]], [[batch-qc|Batch QC]], [[mass-drift|Mass drift]],
[[infusion-report|Infusions]] and [[audit-trail|Audit trail]]. The last two
measure nothing until asked — *Infusions* carries its row count in the tab
name once it has, and is empty on a batch that holds no infused standard.

## The toolbar

| Button | Effect |
|---|---|
| **Process batch** | extract and integrate every valid component in every open sample, then fit the curves, read the concentrations and score the acceptance criteria. Rows integrated by hand in an earlier run are kept |
| **Recalibrate** | refit every curve from the samples marked Standard and read the unknowns back off them, without reintegrating |
| **Compare algorithms…** | integrate the batch with every algorithm and put the answers side by side — see [[compare-algorithms]] |
| **Compare batches…** | a reference project against this batch, component by component — see [[compare-batches]] |
| **Magnify peak** | one panel filling the pane; double-clicking a panel does the same |

The status line to the right reports what was last done: how many rows
across how many samples, how many integrated, which standard and qualifier
the selected component has.

## What "processing" does, in order

1. For each sample and component, the channel is matched and the XIC
   extracted and conditioned (smoothing, baseline) with that component's
   integration settings.
2. The peak is found and integrated by the component's algorithm — see
   [[integration-parameters]] and [[integration-algorithms]].
3. Internal-standard ratios and qualifier ion ratios are computed — after
   the whole batch, since a standard's own peak has to exist before anything
   can be divided by it.
4. Curves are fitted from the standards, concentrations read off them and
   multiplied by each sample's dilution, and accuracies computed.
5. Every row is scored against its acceptance criteria.

A change to one component's integration settings reprocesses only that
component (or its group); everything downstream — ratios, curves,
concentrations, statuses — is recomputed each time.

## Two-way linking

Clicking a panel in the grid selects its row in the results table;
selecting a row brings up that component in the tree and highlights its
panel; clicking a point on the metric plot or a row in Batch QC does the
same. The results table follows the tree: with one component selected it
shows that component's rows, with **All components** it shows everything.

## Reviewing a whole batch

**All components** in the tree puts every peak of every component in the
grid, a page at a time. Extracting all of them — 141 components across 26
samples — is around a hundred seconds of work to put nine on screen, so the
pages are built as they are turned rather than all at once.
