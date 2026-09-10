---
title: The Method workspace
---
The Method workspace (Ctrl+3) is the component table — the equivalent of
MultiQuant's component table. A component says what to extract (precursor,
fragment, tolerance), where the peak is expected (retention time and half
window), and how its result is reported (area, ratio to an internal
standard, or concentration).

## Columns

| Column | Meaning |
|---|---|
| Name | the component's name; how it is referred to everywhere else |
| Group | a free-text grouping — ceramides, sphingomyelins — that folds the component tree in Analytics and lets integration settings be applied to a group at once |
| Precursor | the precursor m/z; the channel is matched on it |
| Fragment | the product ion extracted; empty means the precursor itself is extracted |
| RT | the expected retention time in minutes; empty means the whole run is searched |
| ± RT | the half window: the apex must land within RT ± this. The default is 0.5 min |
| Tol. and Unit | the mass window's half width, in Da or ppm; the method default when left blank |
| Formula and Adduct | optional; with both and no precursor, the precursor is computed — `C18H30D4O4` with [M−H]⁻ is how a labelled standard is entered. With both, an internal standard can also be a lock mass for the [[mass-recalibration]]; *Fill formulas from names* fills them in from the names, see below |
| IS | ticked when the component **is** an internal standard |
| Internal standard | the name of the internal standard this component is reported against |
| Response | what the results table reports: `area`, `ratio` to the internal standard, or `concentration` |
| Conc. unit | the concentration unit shown for this component, when it differs from the method's |
| Qualifier of | the quantifier this transition confirms, when it is a qualifier |
| Ion ratio % and ± ratio % | the expected qualifier/quantifier area ratio, and the tolerance that overrides the method's |
| Min. response | for an internal standard: the smallest area it has to give in an injection before a ratio to it means anything — see [[internal-standards-and-qualifiers]] |

The internal-standard and qualifier columns are explained in
[[internal-standards-and-qualifiers]].

## Building the table

- **Add** and **Remove** edit rows by hand.
- **Generate from acquisition method** reads the first open sample's method
  and makes one component per product-ion channel, named after its
  precursor, with the precursor and mass range the channel declares. An
  eighty-transition method arrives in one click; naming it is what
  [[annotate-from-lipid-maps]] is for.
- **Import CSV…** and **Export CSV…** read and write the table as a
  spreadsheet, see below.
- **Export for Skyline…** writes the method as a small-molecule transition
  list, see [[export]].
- **Suggest from data…** proposes retention times and window widths from the
  open injections, see [[suggest-from-data]].
- **Check method** reads the method against itself and the open files,
  see [[check-method]].
- **Annotate from LIPID MAPS…** proposes species names, see
  [[annotate-from-lipid-maps]].
- **Fill formulas from names** reads the lipid shorthand the names already
  carry and fills the empty Formula cells with it, see below.
- **Repair precursors…** is the way out of what that refuses: where a formula
  and the precursor written beside it disagree, it offers the formula's mass
  for the precursor, row by row, see below.
- **Export schedule…** writes the scheduled acquisition the method implies,
  with the dwell a target cycle leaves each transition, see
  [[acquisition-schedule]].

## Fill formulas from names

A formula is what turns a component into a lock mass for the
[[mass-recalibration]], and a method that names its components in lipid
shorthand has already said what they are made of. **Fill formulas from
names** does the arithmetic: `SM(d18:1/12:0)`, `Cer(d18:1/16:0)`, `PC 34:1`,
`LPC 18:0`, `TG 52:2`, `FA 18:1`, the class written after the chain
(`C16:0-Ceramide`, `C14_SM`), a hydroxyl as `h24:0`, `(2OH)` or `;O3`, a
double-bond position in brackets that says nothing about the composition,
and unplaced deuterium as `-d4`, `d7` or `(d9)`.

Three rules make it safe to press:

- **only empty cells are filled.** A formula somebody typed is the method's;
  a reading of a name is a guess about it.
- **nothing else moves** — in particular no precursor. A formula and an
  adduct can stand in for a precursor when a row is typed by hand, and here
  they must not: the precursor is what this was checked against, and moving
  it would move every extraction window in the batch without anybody asking.
- **the precursor has to agree.** The formula's mass through the row's
  adduct is compared with the precursor already written down, to that
  precursor's own last decimal — one written `647.5` is good to a tenth, one
  written `806.5624` to a ten-thousandth. Where they disagree the cell is
  left empty and both numbers are listed, because a wrong formula is a wrong
  lock mass, which is worse than no lock mass. A whole unit in the last
  place is allowed rather than half, since a written mass is as often
  truncated as rounded; the readings that are actually in question differ by
  a double bond, a methylene or a hydroxyl, never by a tenth.

A row with no adduct cannot be checked and so is not filled. The dialog
gives the counts and lists, name by name, what was refused and why — and
which internal standards are still without a formula, and therefore without
a lock mass.

On the method this was written against: 125 of 141 components and 10 of 11
internal standards, in milliseconds. Thirteen of the 16 refusals were the
written precursor, typed to fewer places than it deserved; the other three
are a whole dalton or more out, and on that batch the instrument had acquired
the mass as it was written, which makes the *name* the thing in question.
*Repair precursors…*, below, is where either is settled.
[[mass-recalibration]] carries the figures.

## Repair precursors from formulas

A refusal leaves a stand-off: the formula and the precursor cannot both be
right, and *Fill formulas from names* deliberately declines to guess which.
**Repair precursors…** — also offered on the refusals dialog — is where that
is settled, by hand. It lists every component whose formula contradicts its
precursor, from either direction: one the method already carries, and one the
name implies that the fill refused to write.

Each row shows the name, the precursor as written, the mass the formula gives
through the row's adduct, the difference in mDa and in ppm, the extraction
window before and after, and a note. **Apply** writes the formula *and* the
precursor for the ticked rows, one [[audit-trail|audit]] entry each —
`precursor 484.465 → 484.4724`, with the formula in the note. A row that is
not ticked is not touched, and neither is any row that was not listed.

The ticking is the argument of the dialog:

- **under half a dalton, ticked.** That is one compound written down to fewer
  places — `484.465` for 484.4724, a mass typed to one decimal — and taking
  the formula's is arithmetic.
- **half a dalton or more, offered unticked.** That is two different
  compounds: a hydrogen, a double bond, a dropped digit. Which of the name
  and the mass is the mistake is not something arithmetic can settle, and
  the row says so rather than deciding.

### What a precursor actually moves

Two things, and the smaller one is the obvious one:

- the **extraction window**, but only where the row has no fragment. A row
  that names one extracts on the fragment, so the window stays exactly where
  it was; the dialog shows both windows so this is visible rather than
  assumed.
- **which acquisition channel is read.** The channel is chosen by precursor,
  within 0.7 Da of the channel's own. A repair larger than that moves the
  component onto a different channel — or off every product-ion channel, in
  which case it falls back to the survey scan and reports a number that is
  not the compound at all.

So process the batch again afterwards, and run [[check-method]] again too.

### Measured, on the 26-injection batch

Sixteen components refused; thirteen under half a dalton, three whole.
Applying the thirteen:

| | |
|---|---|
| components repaired | 13 of 16 |
| how far the written mass was out | 3.0 to 260 mDa, −235 to +392 ppm |
| acquisition channel changed | none — every one stayed within 0.7 Da |
| extraction windows moved | none — all 141 rows carry a fragment |
| rows with a peak, before → after | identical, component by component |
| median area, before → after | identical, component by component |
| rows that moved at all | 0 of 338, the largest area difference 0.000 |

That is the honest result: on this batch the thirteen repairs do not move a
single number. What they buy is the formula beside them. The method goes from
125 formulas to 138 of 141, and from 10 of its 11 internal standards carrying
one to all 11 — the last standard without a possible lock mass for the
[[mass-recalibration]] was `dHCer(d18:0/12:0)`, the row 15 ppm out. Eight of
the thirteen repaired precursors lie inside the 50–700 survey, which is where
a lock mass has to be measurable at all; whether any of them is strong enough
to measure is a separate question, and [[mass-drift]] answers it.

The *formula against precursor* finding in [[check-method]] does not change
here, and cannot: it reads a formula the table already carries, and *Fill
formulas from names* refuses to write the sixteen. The refusals dialog is
where they are reported on this batch; the finding is what a typed or
imported formula produces.

The three whole-dalton rows are why the rest are offered unticked. Applied,
against a batch acquired with the masses as they were written:

| Component | Written → repaired | What the repair did |
|---|---|---|
| `C18:1 Cer` | 464.4 → 564.5350 | left the acquired 464.6 channel for no channel at all; fell back to the survey scan, and 22 rows with a peak of median 9 counts became 10 rows of median 55 — a number that is not the compound |
| `LacCER(d18:1/18:1(9Z))` | 886.6407 → 888.6407 | the same: 888.64 was never acquired, 886.6 was; 21 rows of median 2 became 25 rows of median 32, off the survey |
| `LacCER(d18:0/18:1)` | 889.6563 → 890.6563 | landed on a real channel — the one the method's own `LacCER(d18:1/18:0)` already uses, the same formula and the same fragment. 16 rows of median 2 became 25 of median 4, indistinguishable from its isomer |

Each of those says the same thing: the instrument acquired the mass as it was
written, so the written mass is the one the data is under and the *name* is
what wants correcting. No arithmetic could have known that, which is why
nothing there is ticked.

## Method defaults

Below the table: the **default tolerance** and its unit, which every
component without its own uses; the **concentration unit** for the batch;
and the **ion ratio** tolerance that passes and the wider band that is
*marginal* rather than a fail (20% and 30% to begin with). The integration
defaults every component inherits — smoothing, baseline, gates, the
algorithm — are edited in the [[analytics-workspace]]'s Integration panel
with **Back to method defaults**, and the [[acceptance-criteria]] likewise.

## The CSV layout

Only `name` and `precursor` are required. Headers are matched in English or
Portuguese, so a list written by an earlier version keeps working.

```
name,precursor,fragment,rt,window,tolerance,unit
12,13-DiHOME,313.2384,183.1391,14.7,0.6,0.02,Da
9,10-DiHOME,313.2384,201.1496,14.2,0.6,20,ppm
```

| Field | Accepted headers |
|---|---|
| name | name, compound, component, analyte, nome, composto, analito |
| group | group, grupo |
| precursor | precursor, q1, precursor_mz, parent, precursormz |
| fragment | fragment, q3, product, fragment_mz, productmz, fragmento, produto |
| rt | rt, retention_time, rt_min, tr, tempo |
| rt_halfwidth | window, rt_window, rt_halfwidth, half_window, janela, meia_janela, tolerancia_rt |
| tolerance, unit | tolerance, tol, mz_tolerance, tolerancia; unit, tol_unit, unidade |
| formula, adduct | formula, chemical_formula, molecular_formula, elemental_formula, composition; adduct, aduto, ion |
| is_internal_standard | is, is_internal_standard, internal_standard?, istd, is_istd, e_padrao_interno — true for 1, true, yes, y, sim, is, istd, x |
| internal_standard | internal_standard, is_name, istd_name, padrao_interno |
| response | response, response_type, resposta |
| concentration_unit | concentration_unit, conc_unit, units, unidade_concentracao |
| qualifier_of, ion_ratio, ion_ratio_tolerance | qualifier_of, qualifier, qualificador_de, quantifier; ion_ratio, expected_ion_ratio, razao_ionica; ion_ratio_tolerance, ion_ratio_tol |
| regression, weighting | regression, curve, fit, regressao; weighting, weight, ponderacao, peso |
| lm_id | lm_id, lipidmaps, lipidmaps_id, lmid |
| min_response | min_response, response_floor, min_area, floor, piso_resposta, resposta_minima, area_minima |

A component's own integration settings and acceptance criteria are not in
the CSV; they are saved in the project.

## How a component finds its channel

For each sample, the channel that carries a component is chosen by three
conditions: its precursor is within 0.7 Da of the component's; its mass
range contains the target (the fragment, or the precursor when there is no
fragment); and, when the component declares a retention time, the channel
was acquired at that time. The last condition is why the time is part of
the method: a scheduled method repeats the same precursor in different
periods — 313.24 in an experiment covering 0–13 min and another covering
13–21.5 — and matching on precursor alone picks a channel that was not even
acquired when the compound elutes. Failing all that, a full-scan channel
whose range holds the target is used; failing that, the row says
*no matching channel*. When the matched channel does not cover the
requested window, the row says so rather than reporting a peak from some
other time.
