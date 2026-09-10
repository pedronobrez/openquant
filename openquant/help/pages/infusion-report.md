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
- **"7 of the 97 ions predicted for … were found"** — the denominator is how
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

## Measured

Cholic acid-d4 infused into a ZenoTOF 7600, the same vial under two
activations, explained from the formula `C24H40O5` as `[M+H]+` with four
unplaced deuterium and searched against a record made from the CID run:

| | CID, 45 eV, 473 scans | EAD, 22 eV, 146 scans |
|---|---|---|
| base peak | 359.2870 | 377.3015 |
| precursor 430.35 in the product-ion spectrum | 84 counts, 1.49% — too little | 430.3489 at 9,415 counts, **+20.7 ppm** |
| ions found, of 97 predicted | 2 — 24.2% of the intensity | 7 — 41.9% |
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
2 of 97 ions is what a formula with three neutral losses can say about a
spectrum whose base peak needs four. Neither is a failure of the compound,
and the report is built so that the page says which is which.
