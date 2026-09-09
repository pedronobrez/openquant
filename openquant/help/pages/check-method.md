---
title: Check method
---
**Check method** in the [[method-workspace]] reads the method against itself
and against the open files, and says what it will fail at before a batch is
processed. Everything it reports would otherwise be learned from the
results, which is later and harder.

## What is checked

| Finding | Severity | Meaning |
|---|---|---|
| shared transition | serious | two components declare the same precursor and fragment and have nothing — no retention time, or the same one — to separate them; the integration will return the same peak under both names |
| missing internal standard | serious | a component names a standard that no component carries, or one that is not ticked IS |
| internal standard without a time | serious | a standard with no retention time is searched over the whole run, and takes the largest peak anywhere in it; every component it normalises inherits that. The count of components it carries is given |
| internal standard without a response floor | warning | a standard that serves components declares no **Min. response**, so the quality charts and the acceptance fall back to a signal-to-noise of ten — which on a scheduled acquisition is an absolute height against an arbitrary constant. See [[internal-standards-and-qualifiers]] |
| no retention time | warning | the component's window is the whole run, so the largest peak in the run is the component whatever it is |
| precursor outside the survey scan | warning | with files open: components whose precursor no survey scan covers, and the ranges the surveys do cover. The accurate mass, the LIPID MAPS annotation and the [[mass-drift]] cannot be measured for them; the transition itself is unaffected. An acquisition with no survey scan at all is reported under the skipped checks instead |
| window too narrow | warning | at the sampling interval measured from the open files, the ±window holds fewer than eight points; below five the detector declines outright |

Severities: a **serious** finding will produce wrong numbers; a **warning**
will produce numbers that are harder to defend.

## What is skipped, and said

Checks that need the files — the sampling interval, hence the window
check — are skipped when no sample is open, and the dialog lists what it
could not check rather than staying quiet about it. A method that "passes"
with half the checks unrun has not passed.

## Acting on the findings

- A shared transition needs a retention time on each component, and
  different ones.
- A standard with no time needs one: [[suggest-from-data]] estimates times
  from the open injections and says how far each estimate can be trusted.
- A window too narrow for the sampling can be widened by the same dialog,
  which computes the half-width that gives eight points.
- A missing standard is a spelling mistake or a missing tick, fixed in the
  table.

The check runs on the method as it is, so it can be run again after each
correction. The same findings appear at the head of the [[report]]'s
method section, so a report carries its own warnings.
