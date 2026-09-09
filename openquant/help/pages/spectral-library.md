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
**Precursor ±** of it. Records with no precursor are scored anyway, with
their Δ ppm shown as `—`, so the reader knows the filter could not apply to
them rather than believing it did. Widen the precursor tolerance for a
nominal-mass library. Measured peaks under one per cent of the base peak
are not matched against; the baseline of a product spectrum is full of
them.

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

## What the library does not know

A record is one instrument's spectrum at one collision energy. A match is
evidence that the measured spectrum resembles that record; how much
resemblance is enough is the analyst's call, and the [[accurate-precursor]]
and the [[formula-finder]] are the independent checks on the precursor that
a library match does not make.
