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
  never anything but a proposal. The *Isolated* column now says it before
  anything is measured, and what the two files actually are is the section
  *When the name and the method disagree*, below.
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

## A folder at once

**File ▸ Report infusions in a folder…** asks the same question of a folder
that came off the instrument this morning, with nothing opened in the
[[explorer]] and no batch on screen. Point it at the folder, say where the
document goes, and — if you have them — an MSP of your own and a component
table, either a project or a components CSV; it writes the same per-compound
document, and the same summary table as a CSV if that is ticked.

Nothing is added to what is open. Each file is opened into a session of its
own, measured, and closed again before the next one is opened, so a folder of
thirty infusions never holds thirty readers; and a project already open is
left exactly as it was, with one line in its [[audit-trail]] saying a folder
was reported. With no project open there is no trail to write into, and none
is made.

The folder is looked over by [[checking-files]] before anything is opened. A
`.wiff` whose `.wiff.scan` is not beside it is **skipped**, because its
spectra cannot be read and the report is a spectrum; a `.wiff2` is reported as
ignored; a run that does not read as a [[direct-infusion]] is left out with
the flatness figures that say why. Every skip is listed with its reason: a
folder of nine reported as eight is only honest if the other one comes back
with the reason.

The same run is on the command line, for a folder that arrives every week —
see [[command-line]]:

```
OpenQuant --infusion-report ~/data/bile-acids --out ~/reports/bile.pdf \
          --library ~/library/own-bileomics.msp --csv ~/reports/bile.csv
```

### Measured, on the same nine files

The whole folder from the command line, with the three CID runs as the own
library and the three formulas as a components CSV: **9 files read, nothing
skipped, one 48-page PDF in 32 s** on an otherwise idle machine at 890 MB
peak memory; `--per-compound` gives three documents, 46 pages, 28.0 s. Every row is the one the Infusions
tab measured with the nine files open — 2 of 56 ions under CID and 8 of 56
under EAD for CA-d4, 29 and 6 and 61 against the own records, +14.6 to
+30.3 ppm where the precursor survived — which is the point: the folder route
and the open-batch route are the same measurement, and they agree to the
digit.

The two `_TESTEARTIGO` acquisitions are **not** skipped, and that is the
answer to the obvious question about them. They read as infusions, because
they are: 294 and 311 scans of a steady spray. What is wrong with them is not
visible from the chromatogram at all — their method isolates 839.56, their
base peak is 839.23, nine and seventeen counts sit in the precursor window,
and their explanation cell says *839.56 is none of the adducts of C24H36D4O5
within ±0.05 Da — closest [M+K]+ at 451.2758*. A rule that dropped them would
have to have known that in advance; the report is where it is found.

## When the name and the method disagree

A `.wiff` written by a manual acquisition names its own sample `sample` and
its method `Untitled 1.msm`. Read by reflection, its experiment offers a
polarity, a mass range, a fixed mass, DP, CE, DPS and CES — and a
`TargetedCompoundInfo` that is empty, which is the field SCIEX OS writes a
compound into when a method has one. **On the nine real infusions nothing in
the file says what was sprayed.** The compound is in the file name and
nowhere else.

So the name is a proposal, and the precursor the method isolates is the one
measurement of the same question the file actually holds. OpenQuant compares
them. The compound the name starts with is resolved to a formula — the
standards table of bile acids and their conjugates, then LIPID MAPS, then
the lipid shorthand, the same three [[lipid-maps]] uses, with a trailing
`-d4` read as four labels the formula does not carry — and every adduct of
that formula is measured against the written precursor, at the precision the
precursor was typed with. Where the name fits, the **Isolated** column of the
Infusions tab and the report's header read *430.35 = [M+NH4]+ of CA-d4*.
Where it does not, the same precursor is offered to the component table and
to your own library, and the answer is one of two sentences:

> The file is named CA-d4 but the method isolates 839.56 over 100–1000,
> which is no adduct of C24H36D4O5 within ±0.05 Da; it fits nothing in the
> component table or the library.

> …it fits DCA-d4 [M+NH4]+ (414.3516, +2.0 ppm) from the component table.

The row's **Compound** cell then stops repeating the name: it reads *not
CA-d4*, or *DCA-d4, not CA-d4* where something fits, with the whole sentence
in the tooltip. The grouping does not change — two files named for the same
compound are worth scoring against each other whatever their methods isolate,
and the pair below is only visible *as* a pair because they still were.

The same check runs when a file is opened, and warns once per file, beside
the warning for a `.wiff` with no `.wiff.scan`. **It reads no spectrum**, so
it arrives before anything has been measured: on the nine real infusions it
takes **32 ms a file**, nearly all of it looking the name up in LIPID MAPS,
against the seconds the file itself takes to open. The component table costs
nothing measurable on top — 125 formulas through every adduct came to the
same 32 ms.

**A name is only accepted when it is the compound exactly.** LIPID MAPS is
searched by substring, which is right for somebody typing into a box and
wrong for a check that fires by itself: against the installed database `PC`
answers *PCTR3*, `CE` answers *cedrol*, `Cer` answers *Cerasin* and `TESTOL`
answers *testolactone*. Four sample names of the most ordinary kind, each
resolved to a compound nobody was infusing, and each would then have
contradicted whatever its method isolated. So a database name counts only
when the record's own name, abbreviation or LM_ID *is* the name; the
standards table is an exact lookup and the shorthand is parsed rather than
searched. A name nothing recognises is reported as *not checked* — which is
a different finding from *the name is wrong*, and the two are never
conflated.

### What the two `TESTEARTIGO` files are

They are the acquisitions this check was written for, and they are not
cholic acid-d4.

| | the two `_TESTEARTIGO` | `CA-d4_TOFMSMS_EAD_12CE_…_mix1` |
|---|---|---|
| isolated precursor | **839.56** | 430.34 |
| mass range | 100 – 1000 | 50 – 500 |
| declaration factor | 80 and 44 | 44 |
| base peak | 839.2316 / 839.2343 | 430.3490 |
| base peak height | **109 / 234 counts** | **12,271 counts** |
| centroids in the averaged spectrum | 7,101 / 5,281 | 234 |
| total ion current of the average | 18,537 / 40,453 | 156,716 |

Thousands of centroids at tens of counts each is what an empty acquisition
looks like: a spectrum of noise, centroided. The real infusion beside it has
234 centroids and one of them is fifty times taller than everything in the
other two files put together.

**Nothing anywhere fits 839.56 and nothing in the file supports what does.**
Every positive adduct of cholic, deoxycholic and taurodeoxycholic acid,
their glycine and taurine conjugates, each labelled and unlabelled, as
monomer and as dimer — seventy-two masses — gives exactly one hit at ±0.05
Da: **[2M+Na]+ of *unlabelled* cholic acid, 839.5644, −5.2 ppm**. LIPID MAPS
at ±0.01 Da adds seventeen records over two formulas, `C43H83O13P` as
`[M+H]+` and `C45H76NO10P` as `[M+NH4]+` — phosphatidylinositols and
phosphatidylserines, which nobody was infusing. And the file itself refuses
all of them: within ±0.05 Da of 839.56 the tallest centroid is **9 counts**
in one file and **17** in the other, 8% and 7% of a base peak that is itself
109 and 234. The one ion in the isolation window that is really there sits at
839.23, a third of a dalton — some four hundred parts per million — below
what the method asked for, so it is a neighbour the ±0.5 Da window caught and
not the target.

The conclusion the tab draws is the one the arithmetic supports: **the method
isolated a mass that was typed for something else, and got nothing.** The two
score 73 against each other — two noise spectra from the same source, taken
two minutes apart — and 5 to 10 against the three real CA-d4 files. The file
name is the only thing in either of them that says CA-d4, and it is wrong.

One smaller disagreement of the same kind, visible in the table above: the
12 eV file is named `…_44DP_…` and its method carries a declaration potential
of **80**. The name is a note somebody typed, in both cases, and the method
is what the instrument did.

## The same standard, next month

This report is one verification. The record it names is written into your
own library, and [[standard-history]] reads the accumulated records of one
compound back as a control chart: the cosine against the first record, the
base peak's ppm from it, and the base peak's height, over the days they
were acquired.
