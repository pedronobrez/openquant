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

Both have to be at least **75%**. A peak is by definition narrow against
the run it sits in, so a run with any peak in it spends most of its scans
well under half the apex; a spray that merely drifts stays above it from
the first scan to the last. Both figures are needed rather than one: a
scheduled method acquires each transition over its own window, and the sum
of many peaks at different times is flatter than any one of them, while a
single transition of a blank is flat because it is empty.

## The figures behind the thresholds

Measured on every chromatographic acquisition to hand — thirty-nine of
them, none flagged:

| acquisition set | n | sample TIC | strongest channel |
|---|---|---|---|
| TripleTOF 5600, 21.4 min, 81 channels, MRM-HR | 5 | 0.016 – 0.043 | 0.025 – 0.088 |
| TripleTOF 5600, 14.6 min, 144 channels | 26 | 0.033 – 0.213 | 0.016 – 0.295 |
| ZenoTOF 7600, 24.0 min, 25 channels, DIA | 8 | 0.012 – 0.267 | 0.004 – 0.010 |

The two hardest cases are both caught by the second figure. A column
equilibration with no injection at all — solvent spraying for 24 minutes,
the nearest thing in the set to an infusion — measures 0.267 on the sample
total against 0.006 on its strongest channel. A blank measuring 0.295 on
its strongest channel measures 0.049 on the sample total. Across all
thirty-nine the smaller of the two figures never exceeds **0.098**, against
a threshold of 0.75; an infusion is expected at 0.95 – 1.00 on both.

The infusion side of that comparison has not been measured on real files,
and the module says so in as many words. The thresholds are therefore
placed where the chromatographic margin is largest rather than half way
between two measured populations — which is also why getting the verdict
wrong is made cheap: it only decides what is shown first.

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
