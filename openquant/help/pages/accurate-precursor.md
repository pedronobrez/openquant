---
title: Accurate precursor mass
---
A method's precursor list is written by hand — `351.20`, `313.24` — and is
only good to the decimals it was typed with. Looking a lipid up from that
is asking a database for digits the number does not carry: at ±0.005 Da a
mass near 350 is uncertain by 14 ppm, and the search window fills with
whatever happens to sit nearby.

The survey scan holds the real number. Before a lipid search on behalf of a
component, the program finds the precursor ion in the full-scan (TOF MS)
channel **at the time the product-ion channel actually sees the peak**, and
uses the mass the instrument measured.

## How it is measured

1. The component's own transition is integrated to find when it elutes; that
   time anchors the search.
2. In the survey channel, the spectrum at that time is searched within
   ±0.25 Da of the written precursor — wide enough to absorb a hand-rounded
   value, well inside the roughly 1 Da that Q1 isolates, so a neighbouring
   nominal mass can never be picked up.
3. The peak found is centroided; a peak weaker than 100 counts is not
   trusted as a mass measurement.
4. The same is done in every open sample. The samples have to agree to
   within 25 ppm to be measuring the same ion; the consensus is the median.
5. The **surviving precursor** in the product-ion scan — the unfragmented ion
   that passed Q1 — is measured too, and the two must agree to within
   25 ppm.

That last check matters. The survey sees everything eluting at that moment,
so a strong interference inside the search window can win; whatever
survives fragmentation must have passed through Q1's isolation window
first, which is the confirmation that the survey peak is the transition's
own precursor.

## What the mass is then used for

Where the survey can measure a precursor, a lipid search uses that mass at
±10 ppm. Where it cannot, the window falls back to the precursor's own
precision as written: a mass written as `351.20` is known to ±5 mDa, and
asking for 10 ppm of it would be inventing digits.

On real data the difference decides the answer. A transition written as
`325.20` matches `FA 18:3;O3` at nominal precision; the survey scan puts the
ion at 325.1887 and the product-ion scan agrees to within 1 ppm, which
rules that species out at 41 ppm.

## Where it appears

- [[annotate-from-lipid-maps]] — each proposal says whether its mass came
  from the survey or was written, and what window was used.
- the [[lipid-maps]] tab's Explain — the precursor typed there is what the
  candidates are looked up by;
- [[mass-drift]] — the same measurement made in every injection, to see
  whether the mass axis held through the run;
- [[mass-recalibration]] — correcting the axis from the standards that carry
  a formula. With it on, this measurement is reported raw and corrected side
  by side: the measured value is never overwritten, because the correction
  was fitted from it.
