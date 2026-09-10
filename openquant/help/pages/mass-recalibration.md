---
title: Mass recalibration
---
[[mass-drift|Mass drift]] asks whether the instrument's mass axis *moved*
during the run, and answers against the batch's own median because that is
the only reference a run can supply for itself. Recalibration asks the other
half of the question — **is the axis in the right place at all** — and
corrects it if it is not.

The switch is *Recalibrate m/z from the internal standards*, on the
**Mass drift** tab of the Analytics workspace. It is off by default and is
saved with the project.

## What counts as a lock mass

A lock mass here is an internal standard that meets three conditions:

1. it carries a **formula and an adduct** in the [[method-workspace|method]],
   so its true mass is known. *Fill formulas from names* fills the empty
   Formula cells from the lipid shorthand in the names themselves —
   `SM(d18:1/12:0)`, `C16:0-Ceramide`, `PC 34:1` — and keeps each one only
   where it agrees with the precursor already written down;
2. its precursor lies inside the survey scan's mass range, so it can be
   measured — [[check-method|Check method]] lists the ones that do not;
3. its measured ion held together across the run, which is the same
   `same_ion` test the [[mass-drift|drift]] measurement applies: injections
   disagreeing by more than 25 ppm were not measuring one ion, and averaging
   them would recalibrate the instrument onto whatever happened to be
   nearest.

The **written precursor is deliberately refused**. A method that says `647.5`
is good to about 800 ppm at that mass; correcting a mass axis towards
somebody's rounding is worse than not correcting it. Type the formula.

## What is fitted

One correction per injection:

- an **offset** in ppm — the median of that injection's lock-mass errors,
  sign flipped;
- a **linear term** in ppm per dalton, but only where **four or more** lock
  masses span at least 100 Da *and* a leave-one-out test says the line
  predicts a held-out lock mass better than the plain offset does. A line
  through the points it is then scored on is exact and says nothing, which is
  the same warning the [[integration-algorithms|Gaussian fit]] carries; four
  rather than three, because holding one of three out leaves a line through
  two points, which is exact again.

A correction from **one** lock mass is an offset and the table says so: there
is no second measurement left over to check it against, and its residual goes
to zero by construction rather than by agreement.

## Where it applies

While the switch is on:

- the m/z axis of spectra in the [[explorer|Explorer]], whose title then
  reads `· recalibrated +3.2 ppm`;
- the [[accurate-precursor|accurate precursor]] measurement, which reports
  the raw and the corrected mass side by side — the measured value is never
  overwritten, because the correction was fitted from it;
- the extraction window of every [[manual-xic|XIC]] and every integrated
  peak. The window moves; the reader's own arithmetic does not. Rows carry
  the correction that was applied to them.

With the switch off nothing changes at all, and a project saved before this
existed reopens with it off.

## What the real batch said

Measured on the 26-injection sphingolipid batch this was written against
(TripleTOF 5600, a single 50–700 survey, one scan every 14.6 s).

**Formulas.** The method carried none. *Fill formulas from names* read 125 of
its 141 component names and 10 of its 11 internal standards, in
milliseconds and without opening a file:

| | |
|---|---|
| filled from the name | **125** of 141 |
| refused — the name's formula is not the written precursor | 16 |
| names that are not lipid shorthand | 0 |
| internal standards given a formula | **10** of 11 |

All sixteen refusals are the *precursor* being wrong rather than the name:
`dHCer(d18:0/12:0)` is written 484.465 against its formula's 484.4724
(15 ppm), `LacCER(d18:1/18:1(9Z))` exactly 2.0000 Da low, the thirteen
`HexCer_2OH` and long-chain ceramide rows about 0.13 Da. Each is listed with
both numbers, and the cell is left empty — see [[check-method]].

**Lock masses.** A formula was the missing half of the question and turns
out not to be the binding one. Of the 60 components that now carry a formula *and* lie
inside the survey, exactly **one** measures the same ion in injection after
injection:

| | |
|---|---|
| injections corrected | 25 of 26 |
| lock masses each | **1** (offset only) |
| median offset | **+4.8 ppm** (−4.4 to +11.7) |
| spread of the offsets | 16.1 ppm |

The other ten standards fail for a reason no formula can fix: their survey
signal is too weak, so the ±0.25 Da search window catches a different
neighbour in each injection and they scatter by 98 to 534 ppm across the run
— and one lies outside the survey altogether. `C17:0_Ceramide` was found in
only five injections and its median sits 238 ppm from its own formula, which
is a different ion rather than a badly measured one. **Several lock masses
are not available on this batch at any formula coverage**, so the linear
term has still never fired on real data.

The figure that matters is what happens to *other* components. Fifty-one
analytes inside the survey now carry a formula — against fifteen when this
was first measured — and were measured in every injection: 1,228
measurements in all. Over all of them the median error is −247 ppm before and
−241 ppm after, because most are interferences rather than the compound and
nothing at the ppm scale touches those. Over the 197 measurements that were
within 25 ppm to begin with:

| | before | after |
|---|---|---|
| median error | −7.0 ppm | **−1.4 ppm** |
| median magnitude | 8.6 ppm | **6.8 ppm** |
| smaller after | | 122 of 197 |

So it moves the centre in the right direction, and it cannot be better than
the single lock mass it came from — whose own scatter of 16 ppm across the
run is larger than the 4.8 ppm it corrects by.

## It changes the numbers

Reprocessing that whole batch both ways, over ±20 ppm extraction windows, a
median 5 ppm shift moved **1,769 of 2,593 integrated areas**: a median
absolute change of 1.3%, 830 rows past 5%, and ten rows that no longer found
a peak. A time-of-flight instrument stores few points across a window that
narrow, so moving the window's edge takes whole points in or out.

Turning this on is a quantitative decision, not a display preference. Fit it,
read the per-injection table, and switch it on only when the lock masses
justify it — then process the batch again so the results follow.

## See also

- [[mass-drift]] — the measurement this is fitted from
- [[accurate-precursor]] — the survey measurement of one component's mass
- [[check-method]] — which precursors the survey can see at all
- [[report]] — the corrections table is printed under the mass section
