---
title: Signal-to-noise
---
Signal-to-noise appears in four places — the detector's gate, the
[[acceptance-criteria]], the [[batch-qc]] charts and the [[results-table]] —
and in all of them it is the peak's height divided by a measurement of the
noise. What the noise is, and when it cannot be measured, is the whole
subject of this page.

## Where the noise is measured

**Over the whole chromatogram**, when no noise region is set. It is
deliberately *not* measured inside the retention-time window: that stretch
is mostly peak, so its point-to-point spread reports the peak's own slope.
On real data that read 16,944 where the trace's actual noise was 505, and
the same peak came out at S/N 19 automatically against 531 by hand.

**Over a noise region**, when one is set from the [[peak-review]] grid:
right-click a panel with a stretch of baseline shaded and choose *Set noise
region from the shaded range*. **Noise as** in the Integration panel picks
the measure: *peak-to-peak* takes the full swing of the region and is the
stricter, more conservative reading; *standard deviation* is the gentler
one. Both are in use in laboratories, so which one a number came from has
to be stated alongside it, and the panel does.

## How the automatic estimate works

The noise is the median absolute deviation of the point-to-point
differences, scaled to a standard deviation — a robust estimator that a
peak cannot inflate. In a low-count XIC more than half the differences are
exactly zero, which zeroes the median; the fallback is the standard
deviation of the lower half of the points, which rarely contains a peak.

## When it cannot be measured

**The estimate is "not measured" when there is nothing to measure**, and
that is the ordinary case on a scheduled acquisition rather than the
exception. Over 846 real traces, the median trace had three non-zero points
in sixty-one, and only 9% had a baseline that varied at all. A trace the
instrument reports as exact zeros has a baseline below its reporting
threshold; there is no noise there to measure, and a number invented for
it would not be a ratio to anything.

So the signal-to-noise of a row is empty, shown as `—`, when the baseline
could not be measured. On the batch this was measured on, it could be for
23% of the peaks found.

## What the gates do without it

The detector still needs a floor to reject the smallest peaks, so where the
noise cannot be measured it uses one count as the noise. That keeps the
gate — a single-count spike on an otherwise zero trace is still rejected —
but it means **Min. S/N** is then an absolute intensity threshold wearing a
signal-to-noise name: a peak of 30 counts on a trace of zeros clears
S/N 3 at "S/N 30". Measured on a real batch, an internal standard of 30
counts and one of 42,400 counts would have reported S/N 30 and 42,400 under
that rule. The gate is kept; the number it rejects on is not reported as a
ratio.

The same applies to the acceptance criteria's minimum S/N and to the QC
charts' quantifiable threshold: both are gated on absolute height with an
arbitrary constant when the baseline is zero. What that question actually
needs is a per-method floor on the internal standard's absolute response,
and a batch of the kind this was developed on does not supply one — its
precision does not track its response. See [[batch-qc]].

## Acceptance

An acceptance criterion on S/N that cannot be evaluated flags the row **S/N
not measured** rather than passing it quietly: a criterion that could not be
checked is not a criterion that passed, and saying nothing would let it read
as one.
