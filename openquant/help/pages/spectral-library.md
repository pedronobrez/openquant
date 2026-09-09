---
title: Spectral library
---
The **Library** tab of the [[explorer]] searches the spectrum on screen
against a spectral library — MassBank, MoNA, GNPS or NIST records, or a
laboratory's own — and lists the records that match.

It sits beside [[lipid-maps]] rather than replacing it. The *Explain* tab
there asks what a structure *could* produce; a library asks what somebody
*recorded* from the compound on an instrument. The two answer different
questions and disagree in useful ways: a structure explains a spectrum its
compound has never been measured for, and a library carries the intensity
pattern no enumeration of bonds predicts.

## Loading a library

**Load library…** takes an MSP file — the format NIST defines and MassBank,
MoNA and GNPS all export — or an MGF. The file is read once, the count of
records and how many carry a precursor is shown, and the path is
remembered so the library is there at the next start. Field names vary by
exporter (`PrecursorMZ`, `PRECURSORMZ`, `Precursor_type`, `Formula`) and are
read without regard to case; fields the program does not know are kept and
shown on hover.

## Searching

**Search the spectrum on screen** takes the spectrum the Explorer is
showing — centroided if it was a profile — and the active channel's
precursor, and scores every record whose precursor sits within
**Precursor ±** of it. The tolerance is at least the precision the channel's
precursor was written with: a method value of `647.5` is known to ±0.05,
and a filter of ±0.02 around it would be asking for digits it lacks.
Records with no precursor are left out of a filtered search unless **Also
records with no precursor** is ticked — measured on MassBank, 24,000 of
139,000 records carry none, and a filter that admitted them all had every
search dominated by them; ticked, they are scored with their Δ ppm shown
as `—`, so the reader knows the filter could not apply to them. Measured
peaks under one per cent of the base peak are not matched against; the
baseline of a product spectrum is full of them.

A record has to land at least **Matched peaks ≥** of its peaks to be
listed, two by default. One peak in common is a coincidence: on the same
batch a spectrum that was mostly the phosphocholine ion at 184.07 scored
83 against a laxative whose fragment sits 13 ppm away, and a one-peak
record matched on it was a perfect score for nothing.

Each library peak, strongest first, is paired to the nearest measured peak
still free within **Peaks ±** ppm, so a strong library ion is never robbed
of its match by a weak one listed earlier.

## The two scores

| Score | What it asks |
|---|---|
| **Score** | the cosine between the two spectra, over everything both hold, intensities square-rooted so that one base peak does not decide everything |
| **Reverse** | the same cosine, but only over the library's peaks: whether they are in the measured spectrum, with the measured spectrum's other peaks ignored |

A high reverse with a low score is a compound present with company — a
co-eluting impurity, or a survey scan with more than one ion in the
isolation window. A high score with everything matched is the record
itself. Both are shown as percentages; **Matched** is how many of the
record's peaks found a partner.

## The matched peaks, and the overlay

Selecting a record lists its peaks against the measured ones — mass, mass,
ppm, and the share of each spectrum's base peak — and **Overlay on
spectrum** draws the record's peaks over the spectrum pane, scaled to its
base peak, the way the [[mass-calculator]] overlays an isotope pattern.
**Clear overlay** removes it.

## Measured on MassBank

The full MassBank export in NIST format — 139,006 records, 137 MB — reads
in five seconds and takes about 1.3 GB of memory, since every record's
peaks are held as arrays ready to match. A filtered search answers in
milliseconds; one with no precursor filter, which has to consider every
record sharing two peaks with the query, in two to seven seconds.

Against the product-ion spectra of a real batch, the filtered search
returned the compound where the library had it — a C16 sphingomyelin at
score 46 and reverse 79, a C16 ceramide at 32 and 94, a C24:1 ceramide at
11 and 90, a C18 sphingomyelin at 48 and 96 — and nothing for the C17
internal standards, which are not in MassBank. The scores are low and the
reverse scores high because a product-ion scan on a TOF carries the
precursor, its isotopes and the whole low-mass region as well as the
fragments the record lists: on such spectra the reverse score is the one
to read, and the plain score says how much else was there.

## What the library does not know

A record is one instrument's spectrum at one collision energy. A match is
evidence that the measured spectrum resembles that record; how much
resemblance is enough is the analyst's call, and the [[accurate-precursor]]
and the [[formula-finder]] are the independent checks on the precursor that
a library match does not make.
