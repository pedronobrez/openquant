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

## Against a library

The **Library** tab beside this one asks the other question — what
somebody recorded from the compound, rather than what its structure could
produce — and the two are worth reading together: [[spectral-library]].

## Annotating a whole method

**Annotate from LIPID MAPS…** in the Method workspace proposes a species for
every component still named after its precursor, using the mass measured
from the survey scan where it can. See [[annotate-from-lipid-maps]] and
[[accurate-precursor]].
