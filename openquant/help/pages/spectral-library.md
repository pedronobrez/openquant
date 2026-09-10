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

## Your own library

A deuterated internal standard infused on purpose is in no public library.
The spectrum on screen is the only record of it there will ever be, so
**Add spectrum to library…** writes it into a library of your own: an MSP
file you choose once, appended to, and readable by anything that reads MSP
— including this program, MS-DIAL and MSPepSearch.

The first time, a file is asked for; after that the panel says how many
records it holds. The dialog asks only for what the acquisition cannot
supply and prefills everything it can:

| Field | Where it comes from |
|---|---|
| **Name** | yours. It is what a search will show, and a record without one is not read back at all |
| **Precursor m/z** | the active channel, or whatever is typed in **Precursor** above |
| **Adduct** | the polarity that was run — `[M-H]-` for a negative method, `[M+H]+` for a positive one — and any other adduct may be typed |
| **Formula** | yours, if it is known; a record does not need one |
| **Collision energy** | the channel information, where the instrument recorded one |
| **Comment** | the spectrum pane's own title — sample, channel, and the scans the average was taken over — with the file and today's date |

The spectrum is written as **centroids**: sticks, one per ion, not the
profile points. If the [[chromatograms-and-spectra]] pane is showing a
profile spectrum it is centroided on the way out, the same as for a search.
Peaks under one per cent of the base peak are dropped — the baseline of a
product scan is thousands of them, and a record carrying them matches
anything — and at most two hundred of what is left is kept, strongest
first. Intensities are stored relative to the base peak, as a percentage,
which is how every library format holds them.

The record goes into the file as NIST-style MSP: `Name`, `PrecursorMZ`,
`Precursor_type`, `Formula`, `Collision_energy`, `Comment`, `Num Peaks`,
then the peak list. If the library loaded is the file just written to, it
is read again straight away, so the new record can be searched for
immediately — which is also the check that it was written in a form the
parser reads back.

### Measured on three infused standards

The acquisitions this was written for: cholic acid-d4, deoxycholic acid-d4
and taurodeoxycholic acid-d4, infused one at a time into a ZenoTOF 7600 in
negative mode, product-ion scans, one channel each and no column. The
[[direct-infusion]] verdict calls all of them infusions, so each record is
the average of **every scan of the run** — 473, 473 and 257 of them, over
1.98, 1.98 and 1.07 minutes — centroided:

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| profile points in the average | 255,113 | 242,308 | 192,688 |
| centroids | 811 | 1,059 | 455 |
| at or above 1% of the base peak | 204 | 226 | 25 |
| peaks in the record | 200 | 200 | 25 |
| what bound it | the 200 ceiling | the 200 ceiling | the 1% floor |
| base peak | 359.2870 | 361.3017 | 468.3072 |

A search of a spectrum against a record of the same compound is one of the
three checks an [[infusion-report]] sums up, and its score, reverse score and
the record's own provenance are printed there beside the head-to-tail
picture.

Three records, 8,144 bytes, written in under a second. Read back, all three
returned with every field they were written with, the masses within
5·10⁻⁶ Da and the relative intensities within 5·10⁻⁷ — the rounding of the
text, and nothing else.

Then each compound was **re-acquired with electron-activated dissociation at
22 eV** and that average searched against the three records, which were
written from collision-induced dissociation at 45, 40 and 30 eV. This is a
harder question than the same channel of a different injection: the record
and the query are not merely two measurements, they are two ways of breaking
the molecule.

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| its own record came first | yes | yes | yes |
| its score | 29.2 | 33.3 | 61.5 |
| its reverse score | 38.8 | 43.8 | 68.7 |
| matched peaks | 22 of 200 | 19 of 200 | 8 of 25 |
| the best *wrong* record | 14.1 | 14.0 | 10.3 |
| Δ ppm to the recorded precursor | −23.2 | +0.0 | +0.0 |

**A different compound does not match.** Searched against the other two
records with no precursor filter, the best wrong score anywhere is 14.1 with
a reverse of 31.2 — half to a sixth of what the compound's own record gives
— and CA-d4's spectrum returns **no match at all** against TDCA-d4's record,
fewer than two peaks in common. With the precursor filter the panel applies
by default there was exactly one record in the ±0.02 Da window each time and
it was the right one; the filter changes no score and no order here, only
which records were scored at all. A search takes 0.1 – 1.6 ms.

CA-d4's Δ of −23.2 ppm is the rule about written precision doing its work:
the record says `430.35`, which is good to ±0.005 Da, and the channel that
queried it says `430.34`. Both are the same ion written to two decimals.

**A record is one energy, and one way of breaking the molecule.** The same
CA-d4 spectrum re-acquired at 12 eV instead of 22, against the same
CID record, scores **6.4 with a reverse of 21.3 on 8 matched peaks** — from
29.2, 38.8 and 22 at 22 eV. Splitting the two causes apart: a record written
from CA-d4's own EAD 22 eV average scores 100.0 against itself (which is the
round trip, exact), **67.4** against its 12 eV average, and 29.1 with a
reverse of 55.7 against the CID 45 eV average. So the change of energy costs
about a third of the score and the change of activation costs most of the
rest. The ranking survives all of it — the right record was first every
time — but the number beside it does not travel between methods, and a
threshold picked on one is not a threshold on another.

### Measured on a sphingolipid batch

On a real batch of product-ion acquisitions — 26 injections of a method
whose 144 channels are one compound each, at its own collision energy,
which is the same shape as an infusion of a standard:

Fourteen records were written from the first injection, each the average
of all 61 scans of one channel, centroided. Eleven thousand to twenty-one
thousand profile points became 84 to 3,650 centroids and 7 to 82 peaks in
the record; the file is fourteen records in 13.9 kB, built in under two
seconds. Read back, all fourteen returned with every field they were
written with, the masses within 5·10⁻⁶ Da and the relative intensities
within 5·10⁻⁷ — the rounding of the text, and nothing else.

Then the **same channels of a different injection** were searched against
that library, with no precursor filter, so the match is spectral alone:

| | Injection 02 | Injection 13 |
|---|---|---|
| the right record came first | 14 of 14 | 14 of 14 |
| its score | 13–95, median 60 | 33–95, median 63 |
| its reverse score | 45–96, median 87 | 61–99, median 83 |
| the best *wrong* record | 42 | 42 |

A different compound does not match. The record made from the standard at
354.3 was searched against every one of the other thirteen channels of the
second injection: nine of them returned **no match at all** — fewer than
two peaks in common — and the best of the rest scored 19 with a reverse of
67, against 95 and 96 for its own channel. With the precursor filter the
panel applies by default, each search had exactly one record in the window
and found it.

The scores read low for the same reason as the MassBank figures above: a
product-ion scan on a TOF carries the precursor, its isotopes and the whole
low-mass region as well as the fragments, and none of that is in a record
built from a cleaner average. The reverse score is the one to read.

## What the library does not know

A record is one instrument's spectrum at one collision energy. A match is
evidence that the measured spectrum resembles that record; how much
resemblance is enough is the analyst's call, and the [[accurate-precursor]]
and the [[formula-finder]] are the independent checks on the precursor that
a library match does not make.

## Reading your own library back

A library of your own accumulates one record per verification of the same
standard. **History…**, beside the record count, reads those records back as
a control chart of the standard over time — see [[standard-history]].
