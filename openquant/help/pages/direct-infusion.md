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

That maximum is the **99th-percentile scan, not the largest one**. The
largest is a single scan, and so is a spray transient: three of the nine
real infusions measured carry one at the very start of the acquisition, of
two to four times the run's median, and half of that spike is above every
other scan in a perfectly flat run. Setting the top one per cent of scans
aside costs nothing on a run with a real peak in it — a peak is many scans —
and it is the difference between reading those three infusions at 0.002 and
reading them at 1.00. The figures on the sample's hover say which reference
was used.

Both have to be at least **75%**. A peak is by definition narrow against
the run it sits in, so a run with any peak in it spends most of its scans
well under half the apex; a spray that merely drifts stays above it from
the first scan to the last. Both figures are needed rather than one: a
scheduled method acquires each transition over its own window, and the sum
of many peaks at different times is flatter than any one of them, while a
single transition of a blank is flat because it is empty.

## The figures behind the thresholds

Measured on every acquisition to hand — forty-eight of them, both
populations, **none of the forty-eight miscalled**:

| acquisition set | n | sample TIC | strongest channel |
|---|---|---|---|
| ZenoTOF 7600, 0.6 – 2.0 min, product-ion infusions of bile-acid standards | 9 | 0.9937 – 1.0000 | 0.9937 – 1.0000 |
| TripleTOF 5600, 21.4 min, 81 channels, MRM-HR | 5 | 0.019 – 0.057 | 0.029 – 0.097 |
| TripleTOF 5600, 14.6 min, 144 channels | 26 | 0.033 – 0.426 | 0.016 – 0.377 |
| ZenoTOF 7600, 24.0 min, 25 channels, DIA | 8 | 0.031 – 0.361 | 0.014 – 0.059 |

The hardest chromatographic cases are both caught by the second figure. A
column equilibration with no injection at all — solvent spraying for 24
minutes, the nearest thing in the set to an infusion — measures 0.361 on
the sample total against 0.059 on its strongest channel. A blank measuring
0.377 on its strongest channel measures 0.049 on the sample total. Across
all thirty-nine chromatographic runs the smaller of the two figures never
exceeds **0.1148**, and across the nine infusions it never falls below
**0.9937**. The threshold of 0.75 therefore sits 0.635 above the worst
chromatographic run and 0.244 below the worst infusion, in a gap of 0.879.

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

Below about a hundred scans the 99th percentile is the largest scan again,
so one spike could still call a very short infusion chromatographic. That
is a stated gap and not a fixed one; the shortest infusion measured has 146
scans, and getting the verdict wrong is cheap on purpose — it only decides
what is shown first.

Three other rules were tried and rejected, with figures, in
`openquant/infusion.py`: the scan-to-scan spectral correlation (0.85 – 0.99
on the product-ion channels of ordinary gradient runs, which is the channel
that matters), the coefficient of variation of the total ion chromatogram
(no margin against a blank, and it punishes spray drift), and the absence
of a detected peak (a flat trace with 3% noise still yields three).

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
[[contour-view]] still builds.

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
