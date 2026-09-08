---
title: Compare algorithms
---
A peak area is a measurement and a decision: where the peak begins and
ends, and what is done with the points in between. If the number moves
with the decision, the size of that movement is part of the result.
**Compare algorithms…** on the [[analytics-workspace]] toolbar measures it.

## What it does

The batch is integrated once with each of the three
[[integration-algorithms]], every run automatic — a row the operator
integrated by hand is not any algorithm's answer — and every run calibrated
on its own results, so a curve's r² is that algorithm's. The reference is
the algorithm the method's defaults name, which is what the batch is
currently reported with. A progress dialog runs through the three; on the
batch this was written for, 3,666 rows three ways took under four seconds.

## The dialog

**Summary.** One paragraph: rows found by each algorithm, how many fell
back to the valley area and why, the median %CV of each over the components
with replicates, and how many components moved by more than 20%.

**Component table.** One row per component:

| Column | Meaning |
|---|---|
| Found | rows with a peak, per algorithm; for the fit, how many fell back |
| Δ median % | the median over the rows both algorithms found of \|area − reference area\| / reference area; a component past **20%** is marked, since its number depends on the decision as much as on the sample |
| Δ max % | the largest such difference |
| %CV | the coefficient of variation of each algorithm's areas over the rows that were meant to agree |
| Note | rows found only by the reference, or only by the other algorithm |

**%CV** is the one figure that can call an algorithm *better* rather than
merely *different*: same files, same noise, same instrument, only the
arithmetic changed. The rows meant to agree are every spiked injection for
an internal standard — spiked into every vial at one amount — and the
quality controls for an analyte; unknowns differ by design and standards by
construction, so neither says anything about precision. A component with
fewer than three replicates shows no %CV.

**One sample, every way.** Select a component, then a sample: the trace is
drawn with every algorithm's integration on it — the boundaries and
baseline of each in its own colour, the shaded area of each, the fitted
curve where there was one with its area and *exact through 3 points* or its
r² in the legend. A number that says two algorithms disagree by seventy per
cent is only the start; this is what shows which one is looking at the
peak.

**Adopt and reprocess.** Puts the batch on the chosen algorithm — the
method's defaults and every component override alike, so that a component
carrying its own settings does not keep the old algorithm quietly — and
integrates the batch again with it. Rows integrated by hand are kept.

## What the comparison said on a real batch

| Algorithm | Rows found | Fell back | Moved > 20% | Median %CV |
|---|---|---|---|---|
| Valley to valley | 2,638 | — | — | 87.7 |
| Summation over the window | 857 | — | 8 | 92.6 |
| Gaussian fit | 2,638 | 2,238 (2,169 too few points) | 0 | 88.2 |

Where the fit could be made it agreed with the trapezoid — median 0.977 of
it — and no component moved by more than 20%; where it could not, the peak
was one or two points wide. Summation lost rows, because 85 components had
no window and because a window whose ends land on a peak's flanks has
nothing above the line between them. The algorithm did not move that
batch's numbers; the sampling did — and the comparison is what says so with
figures. See [[measured-facts]].

## In the report

When a comparison has been run, the [[report]] carries an *Integration
algorithms* section with the totals table and the components that moved
most. The comparison is not saved in the project — it is three
integrations of the whole batch and is rebuilt on request.
