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

## Scans a spray lost

An electrospray is not steady for the whole of a run. It arcs, a droplet
reaches the cone, the needle wets: the total ion current leaves the level it
was holding for a scan or a few and comes back. Those scans are not what the
compound looks like, and averaging them in with the rest raises the answer.

So a whole-run average leaves them out, and says how many and where. A scan
is **unstable** when its total ion current departs from the running median of
its **21 neighbouring scans** by more than **50%**, and the scans after it stay
unstable until the current is back inside **25%**. Everything else is
averaged. The pane's title, the [[infusion-report]]'s header, the Infusions
tab's *Scans* column and the comment on a record written to a library of your
own all carry the same line:

> 473 scans, 464 averaged; 9 left out: 0.008 min; 1.069–1.099 min, 8 scans

A single scan is named by its time and a stretch is given by its ends. Where
nothing was left out the title reads *average of N scans* exactly as before.

**Process ▸ Include unstable scans** averages the run as it came off the
instrument. It is off by default and remembered between sessions; with it on,
the report says how many unstable scans were kept and where they were, so a
document made either way says which it is.

### The figures behind it

Measured on the nine real infusions. Every scan's departure from its own
running median was read off, and the two populations do not overlap: the
widest departure of a spray that never faltered is **0.316** (a CID run whose
spray wanders), and the smallest departure inside a real burst is **0.870**.
The count of excluded scans is the same at every threshold from 0.35 to 0.85,
so 50% is the middle of a plateau rather than a fitted value. The window is 21
scans because a running median survives a disturbance up to half its width and
the longest measured is eight scans: at 11 scans the burst decides its own
baseline and six scans are found, at 15 eight, and from 21 upwards nine and it
stops moving.

The base peak was measured beside the total and is not used. It is four to
eight times the noisier — on the six infusions with no burst at all it departs
from its own running median by up to 0.585 where the total never passes 0.164
— so any threshold on it that catches a burst also catches ordinary scans of a
steady spray, and every scan it flags on the files that do burst the total
flags too.

The recovery band is what catches the scans in the middle of a burst that are
neither the spike nor the spray: one real burst runs 0.01, 0.03, 0.64, 2.57,
0.63, 0.13, 0.74, 4.68 of its level over eight scans, and three of those never
pass 50% on their own. What it does *not* buy is a tail — on every burst and
every transient measured, the scan after the last excluded one is already
within 13% of the level, so a spray here comes back inside one scan.

The first second of acquisition is **not** dropped. The settling window
described above exists because a percentile sets aside a share of the scans;
this measures each scan against its neighbours instead, and the transient at
scan 1 comes out at 4.5, 5.1 and 5.0 times its own baseline on the three files
that carry one — thirteen times the widest ordinary departure. Dropping four
scans of every run to catch what is already caught would throw away data no
measurement objects to.

### What it does to the answer

Three of the nine files lose anything at all; six come back **byte for byte
the reader's own average**, because a mask that excludes nothing asks the
reader for the whole run in one call and does not touch what comes back.

| | scans left out | of the run's ion current | base peak |
|---|---|---|---|
| CA-d4 CID | 1 | 0.61% | −0.62% |
| TDCA-d4 CID | 1 | 1.66% | −1.99% |
| DCA-d4 CID | 9 | 2.78% | **−2.90%** |
| the other six | 0 | — | 0.00% |

What changes is the height, not the shape: scored as a record of your own
against the same average taken the old way, the worst of the three comes back
at **99.999**. That is the point of it. A spectrum is the same compound either
way, and the [[standard-history]] chart holds the same standard's base peak
to 4.5% between thirds of one run — so a burst worth 2.9% of it is over half
that, and it is a burst rather than the compound.

The mask reads one chromatogram, which is 3 ms a file. Averaging the surviving
stretches is no slower than averaging the whole run: on those nine, 15.0 s
against 19.4 s, because there are fewer scans in it.

### On a run that is not an infusion

The rule is applied only where the sample reads as an infusion. A
chromatographic peak departs from its neighbours much further than any spray
does — that is what a peak is — so on a twenty-minute gradient the same
arithmetic leaves out the only scans worth keeping. **Average whole run** is
offered on any channel, so the verdict above is the gate: on anything not read
as an infusion, every scan is averaged.

## What changes

For a sample read as an infusion:

- the tree writes **infusion** beside the instrument name, and hovering the
  sample gives the figures that decided it;
- its strongest product-ion channel comes in checked and becomes the
  **active channel**, instead of the survey the Explorer would otherwise
  land on;
- the spectrum pane opens on the average of every scan the spray was
  steady for, titled *average of N scans (infusion)* — or, where scans
  were left out, *N scans, M averaged; K left out: …* — and **infusion**
  appears beside the retention time;
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

## Putting one on paper

**Process ▸ Report this infusion…** writes the averaged spectrum, its peaks,
the accurate precursor and whatever was run against it as a document of two
to four pages — see [[infusion-report]]. It is offered only on an infusion,
because everything in it is the average of a whole run.
