---
title: LIPID MAPS
---
The **LIPID MAPS** tab of the [[explorer]] works against a local copy of the
LIPID MAPS Structure Database (LMSD), so that a mass can be turned into
candidate lipids, a lipid name into its ions, and a structure into the
fragments it could produce — none of it needing the network once the index
is built.

## The database

The first use offers **Download the database**. One 21 MB file from
lipidmaps.org becomes a 1.3 MB index of 49,969 curated structures, stored
under `~/.openquant/lipidmaps/`. Lookups take under a millisecond. LMSD is
redistributed by LIPID MAPS under CC BY 4.0 and is downloaded on request,
not bundled.

Searches are restricted to structures built from C, H, N, O, P, S and Se.
LMSD holds organoarsenic and fluorinated lipids; they are valid records and
absurd candidates for a plasma panel, and a rounded precursor mass matches
one happily.

## Mass → lipid

Type an m/z, pick the adduct, set a tolerance in ppm or Da, and **Search
LIPID MAPS**. Results are grouped **by species, then by structure**: a
species — `PC 34:1`, say — with the isomers that share its formula listed
underneath, because a mass cannot separate them and a list that pretended
otherwise would be claiming more than was measured. Each row carries the
formula, the error in mDa and ppm, and the LM_ID; the tooltip gives the
systematic name.

Right-clicking a spectrum peak and choosing **Find formula for this peak**
sends its mass here as well as to the [[formula-finder]].

## Lipid → mass

Type a name (`SM(d18:1/16:0)`, `Cer(d18:1/16:0)`) or an LM_ID
(`LMSP03010003`) and **Find the precursor**: the matching records are listed
with formula and neutral mass, and selecting one lists its ions — every
adduct, its m/z and charge. Double-click an ion to use its m/z as the
precursor elsewhere in the panel.

## Fragments

Given a lipid and a polarity, **Predict fragments** enumerates what
cleaving its bonds would leave. The structure comes from the database's
molfile — a plain connection table with 2D coordinates, which is everything
needed to enumerate cleavages and to picture one, so no chemistry toolkit is
involved. Hydrogens, implicit in the file, are counted from the valence
left on each atom and checked against the published formula: a structure
whose hydrogens do not add up is marked unreliable rather than allowed to
produce fragment masses that look exact and are wrong.

Up to two bonds are cut at once — what a ring needs to come apart; three is
a combinatorial explosion nobody would look for — and each piece may shed
the small neutrals the **losses** option lists (water, ammonia, and so on).
The table gives each fragment's m/z, the piece, the route that made it, how
many cuts it took, and how many other routes reach the same mass
(**Rivals**). A **target** m/z filters to the routes that land on it.

What this does *not* do is say which cleavages actually happen.
Enumerating bonds is arithmetic; predicting a spectrum is not. The list is
the set of masses worth looking for.

## Explain

**Explain this spectrum** takes the spectrum on screen and the precursor
(filled in from the active channel, or typed), looks the precursor up in
LIPID MAPS, predicts the fragments of every candidate structure, and scores
each by **the share of the spectrum's intensity it accounts for**. Counting
matched peaks instead would reward a candidate that explains forty specks
of noise over one that explains the base peak, which is backwards: a
product spectrum is mostly a handful of ions that matter.

Peaks below 1% of the base peak are not counted against a candidate — a
product spectrum's baseline is full of them and nothing explains them — and
a predicted mass matches a measured one within 20 ppm. The candidates are
listed with what each explains; selecting one lists the matched peaks with
their measured mass, error, route and, where several losses form a ladder,
the ladder. The unexplained peaks are reported too: several candidates
usually explain the same peaks, because isomers fragment alike, and the
unexplained ones are the honest part of the answer.

**Explain spectrum** on the Processing toolbar does the same from the
chromatogram: it takes the spectrum of the current scan and its channel's
precursor.

### A structure or formula of your own

The database does not hold everything — not a deuterated bile acid bought
as an internal standard, not a compound drawn last week. The group under
the Explain button takes one of two things:

- **A structure**, from a `.mol` or `.sdf` file (PubChem's download, a
  drawing program's save; MDL V2000). It gets the full treatment: the
  cleavages and the losses of the drawing, scored against the spectrum
  exactly as a database record is. A drawing that places its labels — an
  `M  ISO` block, or explicit D atoms, which is how a vendor's structure of
  a d4 standard is written — needs nothing more; its fragments come out at
  the right masses by themselves. Hydrogens written out as atoms of their
  own are folded into the atoms that carry them: PubChem writes all forty
  of a bile acid's, and cutting forty C–H bonds only produces forty pieces
  that differ from the whole molecule by one hydrogen, which a hydrogen
  shift already covers. The formula is unchanged by the folding, and
  deuterium the drawing places stays on the atom it was drawn on.
- **A formula**, when there is no drawing. A formula has no bonds to cut,
  so what can be said is the precursor ion and the ladder of small neutral
  losses it could shed — water, ammonia, carbon monoxide and dioxide,
  formic acid, up to three at once, each only where the formula has the
  atoms for it. Less than a structure gives, and said to be.

**Deuterium, unplaced** is for a drawing or formula of the *unlabelled*
compound and a standard whose labels sit somewhere unknown. Each fragment
is then offered carrying none to all of the labels, and the spectrum says
how many it kept: a match at +2.0126 is a piece that kept two, written
`+2D` on its route. Enumerating every placement would be honest and
useless; enumerating the count is what the spectrum can confirm. A piece
is never offered more labels than it has hydrogens.

**Limits** sets how far the enumeration goes and how close a mass has to
be. Two cuts, because a steroid cut once is still in one piece; three
losses, because a trihydroxy bile acid sheds three waters and the
three-water ion is its base peak. The tolerance is **± 5 ppm** rather than
the 20 ppm a database candidate is scored at, and that is not a matter of
taste — see below.

The result lands in the same two tables as a database candidate — the
share of the spectrum explained, the matched peaks with their routes and
ladders — and the unexplained peaks remain the honest half of it.

### Where the labels are

A piece that kept two of four labels contains two of them; a piece that
kept none contains none. Every matched ion is therefore a statement about
*which* hydrogens are heavy, not only how many, and the block under the
tables collects those statements. A placement is a set of positions, one
per label; a placement survives an ion when the labels it puts inside that
piece are the number the piece kept. What comes back is how many placements
survive, which positions every survivor agrees on, and which positions
nothing separates.

Positions the observations cannot tell apart are grouped, because a tie
between two hydrogens that are inside exactly the same fragments is not a
result. Cholic acid offers 21 carbon-bound positions and **8,391** ways of
putting four labels on them.

Three rules decide what counts, and all three were measured rather than
assumed:

- **A hydrogen bound to oxygen or nitrogen is not offered.** It exchanges
  with the solvent long before the spectrum is recorded. The checkbox puts
  those positions back for anyone who wants to see what the spectrum would
  say if it did.
- **A neutral loss may take a label with it.** A dehydration leaves with
  the hydroxyl's own hydrogen and one more from the carbon beside it, so an
  ion that shed water bounds the count rather than fixing it; a
  decarboxylation takes no carbon-bound hydrogen and so says exactly. This
  is measured: in the CID spectrum below the base peak at m/z 359.2870 is
  the three-water loss keeping all four labels, and 358.2808 beside it at
  12.5% is the same ion keeping three. The two are 1.0062 apart, which is
  the 1.00628 of a deuterium against a hydrogen and not the 1.00783 of a
  hydrogen against nothing.
- **A hydrogen the piece lost on cleavage may also have been a label.**
  Assuming otherwise is tidier and wrong: with it assumed, an ion written
  `-2H` cannot have shed a label, and on the spectrum below the true
  placement then satisfied 43% of the evidence rather than 78% and was
  beaten by 96% of the possibilities rather than 79% — and the block named
  a methyl that carries no label as a position every survivor agreed on.

**A peak only counts when it says a number.** A deuterium is 1.55 mDa
heavier than the hydrogen it replaced, so the same piece with one more
label and one fewer hydrogen sits 1.55 mDa away — at m/z 359 that is
4.3 ppm. A window wider than the gap holds both and the match is decided by
which is nearer, which is a coin toss; those ions are counted and left out.
On the cholic acid-d4 spectrum, of the matched ions left out for this
reason: 48 of 53 at 20 ppm, 24 of 47 at 10 ppm, 4 of 26 at 5 ppm, none of
19 at 3 ppm. That is why the tolerance here defaults to 5 ppm.

### What it did on a real standard

Cholic acid-d4 infused on a ZenoTOF 7600 — the product-ion channel of the
ammonium adduct at m/z 430.35, CE 45, the whole 1.98 min run averaged (473
scans, flat throughout, an infusion by the test in [[direct-infusion]]) and
centroided: 811 centroids, 60 peaks above 1% of the base peak. The
structure is PubChem's cholic acid (CID 221493) with four unplaced labels;
the answer is known, because PubChem also holds the labelled standard (CID
16217616), whose `M  ISO` block puts the four on C2 and C4 — either side of
the C3 hydroxyl on ring A.

| | CID, CE 45 | EAD, 22 eV |
|---|---|---|
| peaks explained | 59.0% | 60.7% |
| ions matched | 26 | 24 |
| of those, saying a label count | 22 | 15 |
| left out as undecided | 4 | 9 |
| placements tied at the top | 580 | 2,625 |
| of 8,391, at | 93% of the evidence | 100% |
| positions every survivor agrees on | none | none |
| the vendor's own placement | 78% of the evidence | 92% |
| placements beating it | 6,589 (79%) | 6,224 (74%) |

The EAD column is a second infusion of the same standard, 22 eV, read the
same way: 146 scans over 0.61 min, 424 centroids, 42 peaks.

**It does not recover the answer.** Under CID the top placements put two
labels on a methyl and one on a carbon beside a different hydroxyl; under
EAD they spread over four positions in the middle of the ring system.
Neither is ring A, and the vendor's 2,2,4,4 is beaten by three quarters of
the possibilities in both activations. Read the tie — 580 and 2,625 placements — as the spectrum
bounding the labels rather than placing them, which is what the block says
when it reports that no position is in all of them. The reason is that a
matched mass is not a settled assignment: a piece reached by two cuts and three
losses is one of thousands of arithmetic possibilities, and the placement
that fits best is the one that rationalises whichever of those the matcher
picked.

Handed the labelled drawing instead, with nothing to infer, the same
spectra agree with it: every ion the placement predicts is where it should
be, 100% of the evidence in both files. What that costs is reach — the
placed drawing explains 35.5% of the CID spectrum against the unplaced
version's 59.0%, because the unplaced version is offered five times as many
masses to match. And the disagreement is reported rather than hidden: three
peaks in the CID spectrum and two in the EAD one fit a piece the placement
predicts *carrying a different number of labels*, one of them the 358.2836
already named above.

What the spectrum does say plainly is that a dehydration takes a label.
Under EAD the ladder is complete, and the share of each rung that has lost
one grows as the hydroxyls leave: 5.2% at the precursor, 5.0% after one
water, 8.0% after two, and 104% after three — the ion that lost a label is
then larger than the one that kept them all. Which hydroxyl left at which
rung would place the labels; the enumeration does not track that yet.

## Against a library

The **Library** tab beside this one asks the other question — what
somebody recorded from the compound, rather than what its structure could
produce — and the two are worth reading together: [[spectral-library]].

## Annotating a whole method

**Annotate from LIPID MAPS…** in the Method workspace proposes a species for
every component still named after its precursor, using the mass measured
from the survey scan where it can. See [[annotate-from-lipid-maps]] and
[[accurate-precursor]].
