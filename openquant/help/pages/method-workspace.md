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
internal standards, in milliseconds; the 16 refusals were all the written
precursor being wrong, not the name. [[mass-recalibration]] carries the
figures.

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
