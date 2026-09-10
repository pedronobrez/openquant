---
title: The infusion report
---
**Process ▸ Report this infusion…** writes one compound on two to four
pages: the document that goes in the notebook when a standard is validated.
A [[report]] answers what a batch measured; this answers something smaller
and older — *is this vial what the label says it is?* — and it answers it by
listing what was checked, not by passing or failing anything.

The action is offered only while the active sample is a [[direct-infusion]],
because everything on the page is the average of a whole run, which is a lie
about a chromatographic sample. **Process ▸ Report every infusion…** does the
same for every infusion open, one section per compound in one document, each
compound starting a fresh page.

## What each block holds

**The header** comes from the file rather than from its name: the
acquisition, the sample, the instrument, the polarity, the product-ion
channel with the precursor as the method wrote it, the collision energy, how
many scans were averaged and over what time — and the accurate precursor,
with its error in ppm and where it was measured. Where the acquisition has a
survey scan the measurement is [[accurate-precursor]]'s, with the product-ion
scan as the same-ion check. Where it has none — which is every one of the
nine real infusions this was built against; they carry one product-ion
channel each and nothing else — the precursor is read from the averaged
product-ion spectrum itself and the report says so in those words.

**The averaged spectrum**, drawn for paper at the label floor the pane was
left at, so the masses printed are the masses that were on screen — see
[[chromatograms-and-spectra]] for the floor and how labels are placed. Under
it, the twenty-five strongest peaks above that floor with their intensities
and their share of the base peak.

**The structural explanation**, when one was run in the [[lipid-maps]] tab —
a curated record, a drawing of one's own, or a formula and its losses. Every
matched ion with its theoretical mass, the measured mass, the error in ppm
and, for an unplaced label, how many deuterium the fragment kept. Then, in a
table of its own, **the peaks it does not account for**: the honest half of
the answer, and where a co-infused impurity or the wrong compound shows
itself.

**The library result**, when a search was run in the [[spectral-library]]
tab: the best record, its score and reverse score, how many of its peaks
matched, the precursor difference in ppm, the two spectra head to tail, and
the record's own fields as they were written — the file it was made from, the
collision energy and the date. A record whose provenance is not on the page
cannot be checked against the acquisition it came from.

**Other infusions of the same compound**, when any are open: each averaged
over its own whole run and drawn head to tail against this one, with the same
cosine a library search takes. The dialog ticks those whose file name starts
with the same compound and lets any of them be ticked or unticked, because a
naming convention is not a measurement.

## What the verdict does and does not claim

*What was measured* is one sentence per check, and a check that was not run
gets no sentence:

- **"Precursor confirmed at +20.7 ppm…"**, or **"Precursor not confirmed:
  …"** with the reason. A window that holds less than a hundred counts is not
  a mass: it is reported as too little to measure, with the height that was
  found, rather than as a centroid taken over noise.
- **"8 of the 56 ions predicted for … were found"** — the denominator is how
  many ions the prediction offered, so the reader can see what the count is a
  share of, and the strongest unexplained peak is named beside it.
- **"Best library record … at score 29, reverse 39"**, with the precursors'
  difference in ppm.
- **"Collision energy differs from the record's (22 against 45 eV)"** — a
  spectrum taken at another energy has other fragments, so a low score there
  is the energy and not necessarily the compound.

There is no pass, no fail and no badge. Whether the vial holds what it should
is a judgement made from evidence by somebody who knows what was weighed into
it, and a green tick invites nobody to read the rest of the page. Where
nothing at all was run the verdict says exactly that, and the document is a
spectrum and a peak table — which is a fair description of it.

Every report written is recorded in the [[audit-trail]]: what was reported,
into which file, and which of the three checks stood behind it.

## Every infusion at once: the Infusions tab

A report of one vial answers one question. A folder of nine asks a different
one — which of them measured its precursor, which found its fragments, which
matched the record made of the same compound last month — and that is a
table. The **Infusions** tab of the [[analytics-workspace]] is it: one row per
infused sample, grouped by the compound its file name starts with.

Nothing is measured until **Measure** is pressed: averaging a whole run,
centroiding a quarter of a million points, searching a library and scoring
every infusion of a compound against the others is a few seconds per compound,
and a tab that did that whenever the results changed is a tab nobody keeps
open. The row count appears in the tab's own name once it has.

Each row carries the compound and the sample, the mode and collision energy,
how many scans were averaged, the base peak, the precursor as the method wrote
it and as it was measured back with its error in ppm and its height, the ions
found of those predicted, the best record of your own library with both scores
and the record's collision energy against this acquisition's, and the other
infusions of the same compound with the cosine each way.

Two of those come from somewhere the report of one vial gets them from a
person:

- **the explanation.** Where the [[lipid-maps]] tab has already explained the
  spectrum on screen, that explanation is used. Otherwise the compound is
  looked up in the component table by name and explained from its formula —
  [[annotate-from-lipid-maps]]'s formula path, run with nobody at the tab. Two
  things are read rather than taken as written, both for the same reason —
  a component table has no column for either. The **labels**: a component
  named `CA-d4` whose formula is the unlabelled `C24H40O5` is explained as
  `C24H36D4O5`, because the name says four and the arithmetic is otherwise
  out by 4.025 Da. And the **adduct**: the component's own is used where it
  agrees with the channel's written precursor, and where it does not, the
  precursor wins and the basis line says so — see *Adducts* in
  [[lipid-maps]]. A compound the method does not hold is not guessed at, and
  a precursor no adduct of the formula reaches is not explained at all: the
  cell says which.
- **the library.** The library of your own — the MSP that *Add spectrum to
  library…* appends to, see [[spectral-library]] — searched at the written
  precursor's own precision. A record made from one of these very infusions
  will match itself at 100, which says the file was written and read back and
  nothing else; the row worth reading is the same compound under another
  activation.

**A cell that could not be filled says why rather than being blank.** *only
84 counts survive* is not the same answer as *nothing within ±0.25 Da*, and
neither is the same as *CA-d4 is not a component of the method* — a table of
dashes cannot tell the three apart, and which one it is decides what to do
next. The whole sentence behind a shortened one is in the cell's tooltip.

The column headings sort on their numbers where they have them, so the
weakest precursor or the worst score is one click away.

**Report…** writes the per-compound document — the same one *Process ▸ Report
this infusion…* writes — for the rows selected, or for every row when none is
selected, one section per compound. Rows of the same compound chosen together
are drawn head to tail against each other in it; a row left unselected is left
out of the comparison as well as out of the document. **Export CSV…** writes
the whole table, every column, selection or no selection: a summary with rows
left out is not the thing it claims to be.

The summary line under the table is the one sentence the table adds up to —
*3 compound(s) in 9 infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm;
34 of 458 predicted ion(s) found across 7; 4 with an own record above 60 in
own-bileomics.msp* — counts only, each with what it was counted against. The
batch report prints the table and that line as its *Infusions* section, while
the measurement stands: see [[report]].

## Measured

Cholic acid-d4 infused into a ZenoTOF 7600, the same vial under two
activations, explained from the component table's `C24H40O5` — read as
`C24H36D4O5` from the four labels the name declares, and as `[M+NH4]+`
because that is what the channel's 430.35 is — and searched against a record
made from the CID run:

| | CID, 45 eV, 473 scans | EAD, 22 eV, 146 scans |
|---|---|---|
| base peak | 359.2870 | 377.3015 |
| precursor 430.35 in the product-ion spectrum | 84 counts, 1.49% — too little | 430.3489 at 9,415 counts, **+20.7 ppm** |
| ions found, of 56 predicted | 2 — 24.2% of the intensity | 8 — 63.6% |
| against the CID record | 100 / 100, its own record | **29 / 39**, 22 of 200 peaks |
| collision energy against the record | same | **22 against 45 eV** |
| against the same compound at 12 eV | 7 / 29 | 67 / 81 |

Measured on the EAD run, adding one block at a time: the spectrum and its
peaks alone, **two pages**; with the precursor, two; with the structural
explanation and its unexplained peaks, two; with the library record and its
head-to-tail picture, **three**; with one other infusion compared as well,
**four**. Each took between 0.3 and 1.0 s to lay out and print. Two compounds
in one document came to eight pages in two seconds.


The two rows worth reading twice are the last two of the CID column. Its
library score of 100 is a record matched against the spectrum it was made
from, which proves the file was written and read back and nothing else; and
2 of 56 ions is what a formula with three neutral losses can say about a CID
spectrum whose ladder has already run to completion — the two it finds are
the three-water loss and the same ion with a label gone. Neither is a
failure of the compound, and the report is built so that the page says which
is which.

### The tab, on the same nine files

All nine opened at once — three compounds, five of them called `CA-d4` — with
the three CID runs written into a library of one's own and the three formulas
in the component table. **Measure** took **14.1 s**, 1.6 s an infusion; the
document of all nine came to 61 pages in 18 s, most of it the twenty
head-to-tail pictures that five infusions of one compound make.

| | precursor found | ions of predicted | own record |
|---|---|---|---|
| CA-d4 CID 45 eV | 84 counts — too little | 2 of 56 | 100, its own |
| CA-d4 EAD 22 eV | 430.3489, **+20.7 ppm** | 8 of 56 | **29** at 45 eV |
| CA-d4 EAD 12 eV | 430.3488, +20.4 ppm | 3 of 56 | **6** at 45 eV |
| DCA-d4 CID 40 eV | 33 counts — too little | 3 of 41 | 99, its own |
| DCA-d4 EAD 22 eV | 414.3525, +30.3 ppm | 8 of 41 | **33** at 40 eV |
| TDCA-d4 CID 30 eV | 504.3273, +14.6 ppm, 124 counts | 5 of 104 | 100, its own |
| TDCA-d4 EAD 22 eV | 504.3325, +24.9 ppm | 5 of 104 | **61** at 30 eV |

*3 compound(s) in 9 infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm;
34 of 458 predicted ion(s) found across 7; 4 with an own record above 60.*

Four things in that table are worth reading rather than skipping:

- **the two rows not in it.** `CA-d4_TOFMSMS_EAD_12CE_…_TESTEARTIGO` and its
  22 eV twin carry the CA-d4 name and are not CA-d4 acquisitions: their method
  targets **839.56** over 100–1000, their base peak is 839.23, nine and
  seventeen counts sit in the precursor window, and no record of the library
  comes within ±0.02 Da of 839.56. Their explanation cell now says the thing
  outright — *839.56 is none of the adducts of C24H36D4O5 within ±0.05 Da —
  closest [M+K]+ at 451.2758* — rather than reporting nought ions of
  thirty-one, which was true and left the reader to work out why. The
  *across 7* in the line above is those two rows: an infusion nothing was
  explained for is not counted as one that found nothing. They score
  **73** against each other and **5 to 10** against the three real CA-d4
  files. The name prefix said one compound and the method said another, and
  the row is where that shows — which is the whole reason the compound is
  never anything but a proposal.
- **the precursor survives the soft activations and not the hard ones.** Every
  EAD run measured its precursor; two of the three CID runs had too little
  left to call a mass. That is an ordinary finding about collision energy, and
  the cell says *only 84 counts survive* rather than reporting a centroid over
  noise.
- **the errors are all the same sign**, +14.6 to +30.3 ppm. One of them,
  DCA-d4 at +30.3, is past the 25 ppm the line counts and is on the page all
  the same: the count is a sentence, not a verdict.
- **a formula finds two to eight ions, and which ones depends on the
  activation.** A formula offers the precursor, the form its fragments carry
  and their neutral losses, and nothing else; the rest of these spectra is
  ring cleavages. That is what the denominator is for. Over the seven real
  acquisitions: **34 of 458** predicted ions found, 2 of 56 on CA-d4 under
  CID against 8 of 56 under EAD at 22 eV, 3 of 41 and 8 of 41 for DCA-d4, 5
  of 104 both ways for TDCA-d4 — the soft activations keep the ladder and the
  hard ones have finished it. The row to compare against is the
  [[lipid-maps]] tab's, where the same compound as a *drawing* is scored
  against thousands of masses instead of dozens.

The library column is the one that says something the rest does not. A record
made from a run matches that run at 100, which proves the file was written and
read back; the figures that mean anything are 6, 29, 33 and 61 — the same
compound, the same vial, under another activation, and a record does not
travel between them.

## The same standard, next month

This report is one verification. The record it names is written into your
own library, and [[standard-history]] reads the accumulated records of one
compound back as a control chart: the cosine against the first record, the
base peak's ppm from it, and the base peak's height, over the days they
were acquired.

The tray as a whole is the other half of that question, and
[[compare-infusions]] is where it is asked: this table against the one a
reference project saved, matched by compound and by conditions. Press
**Measure** before saving a project and the project keeps these figures and
every row's averaged peak list, which is what a later day is compared
against.
