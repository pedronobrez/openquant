---
title: Standard history
---
A record written into your own library is a verification that has already
happened. Every time the standard is sprayed to check the vial, one more
record of the same compound goes into the same MSP — and after a few
months that file holds the only measurement of that standard over time
anybody has.

**History…**, beside the record count in the [[spectral-library]] tab,
reads it back. It is [[batch-qc]] asked of a library instead of a batch:
the same robust centre, the same two conditions a point has to meet before
it is called out, the same trend that needs both a size and a direction —
with the records in the order they were **acquired** rather than the order
they were typed in.

## What is grouped with what

The records of one compound are cut into **series** by collision energy and
activation, and nothing is ever compared across a series boundary. A
spectrum measured at another energy has other fragments and often another
base peak, so a cosine against it measures the method and not the standard;
an absolute intensity is comparable only within one method anyway. Measured
on one real infused standard, cholic acid-d4, the same compound in the same
vial scored **67 at EAD 12 eV against EAD 22 eV, 29 at EAD 22 eV against
CID 45 eV, and 6 at EAD 12 eV against CID 45 eV** — three numbers that say
nothing about the vial and everything about the collision cell.

The compound is the part of the record's name before the first separator,
as in the [[infusion-report]]. The activation is read from an
`Activation` field where an exporter wrote one and from the record's name
otherwise — `..._EAD_22CE_...` — because no field this program reads from a
`.wiff` carries it: the nine ZenoTOF infusions to hand all say `TOF PI` and
`Product`, and the electron energy appears only in the file name. A record
whose name does not say is grouped as *unstated*, never as CID.

## The three charts

The first record of a series is the **reference**, and everything is
measured against it.

| Chart | What it asks | Flagged past |
|---|---|---|
| Score against the first record | does it still look like itself | 20% from the centre and 3σ, or 50% outright |
| Base peak, ppm from the first record | is the base peak still the same ion, in the same place | 20 ppm and 3σ, or 40 ppm outright |
| Base peak intensity | is it still giving what it gave | 20% and 3σ, or 50% outright |

The score is the cosine the library search itself uses, so "how alike are
these two spectra" has one answer in this program and not two; the reverse
cosine is kept beside it, because a standard that has picked up an impurity
has kept everything it had and gained something. The table also carries the
score against the **previous** record, which is what says whether a change
happened at one verification or crept in over several.

The mass chart is the one metric that cannot be a percentage of its own
centre — a median of zero ppm has no percentage of itself — so its limits
are written in ppm and its trend is a plain difference. A base peak more
than 50 ppm from the reference's is not charted at all: that is a different
ion, not a mass error, and the row says `not the same ion` with both masses
beside it. This is the [[mass-drift]] lesson in another place — a
measurement that cannot be shown to be of the same ion is not judged.

## Three records, not two

No limit is drawn through fewer than three records. Below that every chart
says **too few to chart** and the records are still listed, because a median
and a spread taken from two points are a line through two points and a
reader shown limits will read them. A batch gets six, and can: it is
acquired in an afternoon. A history accumulates one record per
verification, and six of those is a year.

## What a record has to carry

Two fields are written into every record made from this version onwards,
and neither can be recovered afterwards:

- **Acquired** — the day the instrument measured, taken from the file, not
  the day the record was typed in. A folder acquired over three months and
  written into a library in one afternoon is three months of history, and
  `added 2026-09-10` says nothing about the standard. It is shown, read
  only, in the *Add spectrum to library* dialog.
- **Base peak intensity** — the base peak's height in counts. Every library
  format holds peaks as a share of the base peak, so how big the spectrum
  was is lost the moment the record is written unless it is written too.

A record made before those existed is still read: it sorts by the order the
file holds it in, its intensity is left off that chart, and both facts are
said on the chart rather than passed over.

A third field is written by [[new-standard]] and by nothing else: the
**lot**, in the record's comment. It is not a measurement and nothing in an
acquisition holds it, which is exactly why it has to be typed when the
standard is entered — a history that spans a change of bottle is two
histories drawn as one, and the lot is the only thing that says where the
join is.

A standard entered through that dialog has its first history entry the moment
it is created, because the entry *is* the record: this page is the library
read back, and nothing writes a history separately.

## What was measured

Nine ZenoTOF bile-acid infusions, written into a library of their own and
read back: nine records, seven series, all acquired on one day. **Two
records at one energy is what the folder holds** — the `_TESTEARTIGO`
acquisitions were expected to be repeats of the `_mix1` ones at the same
energies, and are not. They isolated m/z 839.56 over a 100–1000 survey
where the `_mix1` infusions isolated 430.34 over 50–500, and the history
says so without being told: at EAD 22 eV the second record scored **8** with
a base peak at 839.2343 against 377.3015 — *not the same ion* — at 2.4% of
the first record's height; at 12 eV it scored **0** at 0.9% of it.

Because no real series reaches three records, the limits were exercised by
cutting six of the infusions into three consecutive thirds each — eighteen
records, six series, one standard at one energy per series, nothing changed
between them. That is the floor of the measurement: the score against the
first third was **98.7 to 100.0**, the base peak held to **0.4 ppm**, and
the base-peak height varied by **up to 4.5%**, which put one of the six
intensity charts one point past two sigma. One third of the cholic acid-d4
EAD 22 eV spray had its base peak change from the fragment at 377.3014 to
the precursor at 430.3489 — two peaks of nearly equal height, and which is
taller changes through a run. That record left the mass chart as *not the
same ion*, which is the intended answer.

Reading a library of nine records into a full history takes about 3 ms.

## What it is not

It is a control chart of one standard against itself, and shares the limit
[[batch-qc]] states: it cannot tell an instrument that changed from a vial
that did. Several standards falling together at one verification is what
says which, and that judgement is the analyst's — this draws the charts
that make it possible. **Export CSV…** writes every record with what each
chart said above the rows.

It also needs records, which means somebody has to have written them. The
same two rules — fifty ppm for *the same ion*, twenty per cent for *the
same response* — are applied to a whole tray at once by
[[compare-infusions]], which reads a reference day out of its project file
instead of out of a library, and needs nothing to have been added to one.
