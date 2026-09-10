---
title: Direct infusion
---
In a direct infusion there is no column. The sample is sprayed into the
source for a minute or two and every scan is the same spectrum plus noise,
so the chromatogram carries no information and the thing worth looking at
is the average of the whole run. Opened as though it were a chromatographic
run, an infusion asks the reader to pick the product-ion channel out of the
tree, Shift-drag a range over a flat line, and only then get a spectrum
worth sending to [[lipid-maps]] or the [[spectral-library]].

The [[explorer]] recognises an infusion when a sample is opened and starts
from the average instead.

## How it is detected

Two figures, both from chromatograms — no spectrum is read, so the verdict
costs nothing extra and holds on a `.wiff` whose `.wiff.scan` is missing
and on the same acquisition converted to mzML:

- the fraction of the **sample's total ion chromatogram** sitting at or
  above half its own maximum;
- the same measure on **the strongest channel** — the product-ion channel
  carrying the most signal, or the survey if the method has no product
  scan.

That maximum is the **99th-percentile scan, not the largest one**, taken
over the scans left after the **first second of acquisition**. The largest is
a single scan, and so is a spray transient: three of the nine real infusions
measured carry one at the very start of the acquisition, of two to four times
the run's median, and half of that spike is above every other scan in a
perfectly flat run. Setting the top one per cent of scans aside costs nothing
on a run with a real peak in it — a peak is many scans — and it is the
difference between reading those three infusions at 0.002 and reading them at
1.00. The first second goes because one per cent of a *short* run is one scan
again; see below. The figures on the sample's hover say which reference was
used.

Both have to be at least **75%**. A peak is by definition narrow against the
run it sits in, so a run with any peak in it spends most of its scans well
under half the apex; a spray that merely drifts stays above it from the first
scan to the last. Both figures are needed rather than one: a scheduled method
acquires each transition over its own window, and the sum of many peaks at
different times is flatter than any one of them, while a single transition of
a blank is flat because it is empty.

And a flat run of fewer than **120 scans** is not called an infusion at all.
It is reported as **too short to tell**, with both figures, and treated as
not an infusion. Why, and why 120, is the last section on this page.

## The figures behind the thresholds

Measured on every acquisition to hand — forty-eight of them, both
populations, whole runs, **none of the forty-eight miscalled**:

| acquisition set | n | sample TIC | strongest channel |
|---|---|---|---|
| ZenoTOF 7600, 0.6 – 2.0 min, 146 – 473 scans, product-ion infusions of bile-acid standards | 9 | 0.9936 – 1.0000 | 0.9936 – 1.0000 |
| TripleTOF 5600, 21.4 min, 577 scans, 81 channels, MRM-HR | 5 | 0.019 – 0.057 | 0.030 – 0.097 |
| TripleTOF 5600, 14.6 min, 61 scans, 144 channels | 26 | 0.033 – 0.433 | 0.017 – 0.383 |
| ZenoTOF 7600, 24.0 min, 482 – 490 scans, 25 channels, DIA | 8 | 0.031 – 0.364 | 0.015 – 0.060 |

The hardest chromatographic cases are both caught by the second figure. A
column equilibration with no injection at all — solvent spraying for 24
minutes, the nearest thing in the set to an infusion — measures 0.364 on the
sample total against 0.060 on its strongest channel. A blank measuring 0.383
on its strongest channel measures 0.050 on the sample total. Across all
thirty-nine chromatographic runs the smaller of the two figures never exceeds
**0.1167**, and across the nine infusions it never falls below **0.9936**.
The threshold of 0.75 therefore sits 0.633 above the worst chromatographic
run and 0.244 below the worst infusion, in a gap of 0.877.

That gap did not exist until the reference was changed. Read against the
largest scan, three of the nine infusions measured 0.0021, 0.0039 and
0.0063 — **lower than every one of the thirty-nine chromatographic runs**.
The two populations were not merely overlapping but the wrong way round,
and no threshold at all would have separated them. One scan did it: a
transient at 0.008 min, 2.8 to 4.4 times the run's median, and in one file
two more bursts part way through. The statistic was wrong rather than the
threshold, which is why the reference is now the 99th-percentile scan.

The 99th is where it is because it was measured. The 99.5th is not enough —
one file's three spiked scans are 0.63% of its 473, so they survive it and
it reads 0.639 — while the 95th and the 90th lift the chromatographic
figures to 0.262 and 0.410 by setting aside real peak apices. The widest
margin measured is 0.895 at the 99.2nd percentile and 0.879 at the 99th.

## Short runs, and the answer "too short to tell"

A percentile sets aside a *share* of the scans, and one per cent of a short
run is one scan. Every one of the forty-eight acquisitions was truncated to
its first 20, 30, 50, 75 and 100 scans and read again. Under the percentile
alone, the worst infusion of the nine reads:

| first N scans | worst infusion | worst chromatographic run |
|---|---|---|
| 20 | **0.0500** | 0.9500 |
| 30 | **0.0333** | 0.9667 |
| 50 | **0.0200** | 0.6735 |
| 75 | **0.3333** | 0.8919 |
| 100 | 0.9900 | 0.9394 |
| the whole run | 0.9937 | 0.1148 |

The three infusions with a transient are inverted all over again, out to
eighty scans rather than the hundred that had been supposed. Leaving the
**first second of acquisition** out of both the reference and the count fixes
it outright, because that is where the transient is — scan 1, half a second
in — and after it the infusion side stops moving with the length at all:
**1.0000 at every one of those truncations**, and 0.9936 on the whole run.
Two other rules were measured and are worse. Dropping the first second while
going back to the largest scan as the reference fails on a whole run, where
one file has two more bursts a minute in and reads 0.0043. Making the
reference the median of the top few scans, with "few" tied to the run's
length, survives one spike but not three, and reads 0.0100 on that same file.

The right-hand column above is the part no reference fixes, and it is why
short flat runs are refused. A gradient cut off before anything elutes is
flat, and flat is the whole of what these two figures measure. One real run
in the set carries nothing at all until 8.9 minutes in: **its first hundred
scans read 1.0000 on the sample total and 0.9388 on its strongest channel**,
which is an infusion's signature exactly. Nothing on a chromatogram tells
those apart, because there is nothing there to tell apart — both are a flat
line.

So the threshold of 0.75 does not separate the two populations at any length
below 240 scans, which is more than the shortest real infusion has. The floor
goes where the rest of the measurement supports it: apart from that one file,
no chromatographic run of the thirty-nine reads flat past **35** scans, and
the shortest infusion measured has **146** — so the floor is **120**, between
them. Below it a flat run is reported as *too short to tell* and treated as
not an infusion.

The floor gates the flat answer only. A run that shows structure is
chromatographic at any length, which is why the twenty-six 61-scan runs still
read "chromatographic" with their figures rather than "too short to tell".
And the loss is real and stated: a genuine infusion of fewer than 120 scans
would be refused, and so is that one gradient in the stretch between 154 and
234 scans where it is still flat. Getting the verdict wrong is cheap on
purpose — it only decides what is shown first.

Three other rules were tried and rejected, with figures, in
`openquant/infusion.py`: the scan-to-scan spectral correlation (0.85 – 0.99
on the product-ion channels of ordinary gradient runs, which is the channel
that matters), the coefficient of variation of the total ion chromatogram
(no margin against a blank, and it punishes spray drift), and the absence of
a detected peak (a flat trace with 3% noise still yields three).

## What changes

For a sample read as an infusion:

- the tree writes **infusion** beside the instrument name, and hovering the
  sample gives the figures that decided it;
- its strongest product-ion channel comes in checked and becomes the
  **active channel**, instead of the survey the Explorer would otherwise
  land on;
- the spectrum pane opens on the average of every scan, titled *average of
  N scans (infusion)*, and **infusion** appears beside the retention time;
- everything downstream sees that average, because it is the live spectrum:
  background subtraction, *Explain spectrum*, the library search, the peak
  table, *Pin spectrum* and the CSV export.

Nothing else changes. The chromatogram pane still draws the total ion
current over time, the scan controls still step scan by scan, and the
[[contour-view]] still builds — as a film, with the run's total ion current
beside it and a Play that steps through the scans. See below.

## Seeing the run scan by scan

The average is the right thing to read an infusion from and the wrong thing
to check it with: a transient at the first scan, a burst part way through and
a fragment that only appears once the spray settles all disappear into it.
Two things put the run back.

**The film.** Switch *View* to *Contour* on an infusion and the surface comes
with the run's total ion current as a strip on the same time axis, the scans
left out of the average marked ✕, and **Play**, which steps the spectrum pane
through every scan of the run. A fragment is a ridge running the length of
the run; a spray transient is a column one scan wide. See [[contour-view]] for
what it showed on the real acquisitions.

**Δ from the average.** *Process ▸ Δ from average*, off by default and offered
only on an infusion, draws the current scan **minus** the average of the whole
run, with the average mirrored underneath it — through the same *Mirror*
switch as a pinned spectrum, which it turns on and puts back afterwards.
Every scan of a spray is meant to be the same spectrum, so what is left is
what changed.

The average is interpolated onto the scan's own m/z axis first, the way a
background is, because the two grids do not line up: on `DCA-d4_TOFMSMS_Mix1`
a single scan carries 8,815 to 21,960 points against the average's 242,308,
which is every scan's grid unioned. Nothing is clipped at zero — a scan
*short* of the average is exactly what this is for.

While it is on, the difference **is** the live spectrum: the peak table, the
comparison and a pin all read it. Turn it off before *Explain spectrum*, a
library search or a report, which want the spectrum and not the residual.

### What it showed

Read by nominal mass on `DCA-d4_TOFMSMS_Mix1`, against a channel whose total
sits at 373,000 counts:

| the scan | what the difference says |
|---|---|
| **scan 1**, 0.0042 min, 0.67× the median total | the whole ladder short of the average — −1,997 at 153, −1,897 at 247, −1,843 at 167. The spray had not settled |
| **scan 262**, 1.0988 min, 4.36× | the whole ladder up together — **+118,209 at 361**, +25,520 at 219, +24,949 at 95, and a peak difference of +21,674 counts. A spray event, not a new species: a new species would be one mass |
| **scan 237**, 0.9938 min, 0.91× | almost nothing: the largest single point differs by −523 counts against an average peak of 2,795 |

**Read it by mass, not by point.** The profile grid moves by a fraction of a
point between scans, so a peak's residual comes out as a dipole either side of
it: on the CA-d4 EAD file the three largest differences at scan 1 are
+2,457, −2,052 and +1,978 counts within 0.010 Da of 377.30, which is the same
peak arriving slightly early rather than three findings. Summed over a whole
nominal mass that cancels, and what is left is the change.

## Doing it by hand, and overriding

**Average whole run** in the Processing toolbar does the same thing on any
sample and any channel, infusion or not — useful for a channel other than
the one chosen, and for a run the rule did not call an infusion.

To override the choice, work as usual: pick another channel in the tree or
in the **Active channel** selector, and step scans or Shift-drag a range on
the chromatogram as on [[chromatograms-and-spectra]]. Any of those replaces
the average with what was asked for; nothing is locked.

## The accurate precursor

[[accurate-precursor]] anchors its survey-scan measurement on a peak in the
product-ion channel, or on a component's retention time. An infusion has
neither: there is no peak, and a retention time copied in from a
chromatographic method points outside a run that lasts a minute. On an
infusion the measurement takes the middle of the run as its anchor and
averages the whole run for both the survey and the product-ion spectrum,
which is the most signal the acquisition can give it.

## Putting one on paper

**Process ▸ Report this infusion…** writes the averaged spectrum, its peaks,
the accurate precursor and whatever was run against it as a document of two
to four pages — see [[infusion-report]]. It is offered only on an infusion,
because everything in it is the average of a whole run.
