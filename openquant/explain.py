"""
Reading a product spectrum against what a structure could produce.

Enumerating cleavages says which masses are *possible*; it says nothing about
which happen. The spectrum in front of the analyst does. Matching one against
the other turns an unranked list of arithmetic into a ranked one, and the
ranking is evidence from this sample rather than a general model.

The score is the share of the spectrum's intensity that a candidate accounts
for. Counting matched peaks instead would reward a candidate that explains
forty specks of noise over one that explains the base peak, which is backwards:
a product spectrum is mostly a handful of ions that matter.

What this cannot do is prove a structure. Several candidates usually explain
the same peaks, because isomers fragment alike and because a long enough list
of possible masses will cover a spectrum by accident. The unexplained peaks are
the honest part of the answer, so they are reported too.

Everything here is scored *as an adduct*, and which one is not a detail: a
channel written 430.35 is the ammonium adduct of cholic acid-d4, and the same
spectrum scored as a protonated molecule predicts every fragment 17 Da away
from anything in it. `chemistry` holds the model — what each kind of adduct
does when the ion breaks up — and `chemistry.identify_adduct` reads the
adduct off the written precursor and refuses rather than guessing. This
module turns that into ions: `precursor_ions` for what a formula alone can
say, `structure_ions` for a drawing, `resolve_name` for a compound written
by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .lipidmaps import LipidDatabase, LipidRecord
from .structure import (NEUTRAL_LOSSES, PredictedIon, Structure, parse_molblock,
                        predict, suppress_hydrogens)

#: how close a predicted mass has to be to a measured one, in ppm. A TripleTOF
#: holds a few ppm on a strong product ion and rather less on a weak one.
TOLERANCE_PPM = 20.0

#: peaks below this share of the base peak are not counted against a candidate:
#: a product spectrum's baseline is full of them and nothing explains them
NOISE_SHARE = 0.01


@dataclass(frozen=True)
class PeakMatch:
    """One measured peak, and the predicted ion that lands on it."""

    mz: float
    intensity: float
    ion: PredictedIon
    #: the route the spectrum supports best, when it can tell them apart
    route: "Route | None" = None

    @property
    def best_route(self) -> str:
        return self.route.description if self.route else self.ion.description

    @property
    def error_ppm(self) -> float:
        if not self.ion.mz:
            return 0.0
        return (self.mz - self.ion.mz) / self.ion.mz * 1e6

    @property
    def error_mda(self) -> float:
        return (self.mz - self.ion.mz) * 1000.0


@dataclass
class Explanation:
    """What one candidate structure accounts for in a spectrum."""

    record: LipidRecord
    matches: list[PeakMatch] = field(default_factory=list)
    explained: float = 0.0        # intensity accounted for
    total: float = 0.0            # intensity that was there to account for
    considered: int = 0           # peaks above the noise share
    #: how many ions the prediction offered at all — the denominator of
    #: "n of m found". Without it `matched` is a count with nothing to be a
    #: share of, and a report that says "12 fragments found" has said how
    #: many were looked for only if it also says this.
    predicted: int = 0
    #: everything that was matched against, kept because a match means less
    #: on its own than it does beside the rivals that reach the same mass
    ions: list[PredictedIon] = field(default_factory=list)

    @property
    def share(self) -> float:
        """The fraction of the spectrum's intensity this accounts for."""
        return self.explained / self.total if self.total else 0.0

    @property
    def matched(self) -> int:
        return len(self.matches)

    @property
    def name(self) -> str:
        return self.record.name or self.record.abbrev

    def unexplained(self, peaks) -> list[tuple[float, float]]:
        """The peaks it does not account for — the honest half of the answer."""
        taken = {round(m.mz, 4) for m in self.matches}
        return [(mz, height) for mz, height in peaks
                if round(mz, 4) not in taken]


@dataclass(frozen=True)
class Route:
    """One way of reaching a mass, and how the spectrum treats it."""

    description: str
    companions: tuple[float, ...] = ()      # masses it also predicts
    seen: tuple[float, ...] = ()            # of those, the ones measured

    @property
    def support(self) -> float:
        """The share of a route's companion ions that the spectrum shows."""
        return len(self.seen) / len(self.companions) if self.companions else 0.0


def companion_masses(structure: Structure, ion: PredictedIon,
                     description: str | None = None) -> list[float]:
    """
    The ions a route implies besides the one it explains.

    Losing two waters means the single-water ion exists too; losing carbon
    dioxide means something carrying that carboxyl should show up. A route
    that leaves no trace of its own intermediates is a worse explanation than
    one whose whole ladder is in the spectrum, and the spectrum is the only
    thing that can tell them apart.
    """
    if description is None or description == ion.description:
        # the ion's own route is on the ion; only a rival route has to be read
        # back out of the words, and an ion written as a form of the
        # precursor — `[M+H-3H2O]+` — has no words to read it out of
        losses = ion.losses
    else:
        losses = _losses_of(description)
    if not losses:
        return []
    charge = ion.charge or 1
    masses = []
    running = ion.mz
    for loss in reversed(losses):
        running += _loss_mass(loss) / abs(charge)
        masses.append(running)
    return masses


def routes_for(structure: Structure, ion: PredictedIon, peaks,
               tolerance_ppm: float = TOLERANCE_PPM) -> list[Route]:
    """
    Every route to one mass, ranked by how much of its ladder is present.

    This is what the enumerator alone could not settle: two routes reach the
    same number, and only the companion ions separate them.
    """
    measured = np.array(sorted(mz for mz, _height in peaks), dtype=float)
    found = []
    for description in (ion.description, *ion.alternatives):
        companions = companion_masses(structure, ion, description)
        seen = tuple(m for m in companions if _is_present(m, measured,
                                                          tolerance_ppm))
        found.append(Route(description=description,
                           companions=tuple(companions), seen=seen))
    found.sort(key=lambda r: (-r.support, len(r.companions)))
    return found


def _losses_of(description: str) -> tuple[str, ...]:
    return tuple(part[1:] for part in description.split()
                 if part.startswith("-") and part[1:] in NEUTRAL_LOSSES)


def _loss_mass(loss: str) -> float:
    from .chemistry import monoisotopic_mass, parse_formula

    return monoisotopic_mass(parse_formula(NEUTRAL_LOSSES[loss]))


def _is_present(mass: float, measured, tolerance_ppm: float) -> bool:
    if not len(measured):
        return False
    window = mass * tolerance_ppm * 1e-6
    index = int(np.searchsorted(measured, mass))
    for candidate in measured[max(index - 1, 0):index + 2]:
        if abs(candidate - mass) <= window:
            return True
    return False


def match_peaks(peaks, ions: list[PredictedIon],
                tolerance_ppm: float = TOLERANCE_PPM) -> list[PeakMatch]:
    """
    Pair measured peaks with predicted ions, nearest first.

    Each peak takes at most one ion and each ion at most one peak, so a dense
    prediction cannot claim the same peak several times over and look better
    for it.
    """
    if not len(peaks) or not ions:
        return []
    ordered = sorted(ions, key=lambda i: i.mz)
    masses = np.array([i.mz for i in ordered])
    used: set[int] = set()
    matches: list[PeakMatch] = []
    for mz, intensity in peaks:
        window = mz * tolerance_ppm * 1e-6
        lo = int(np.searchsorted(masses, mz - window, side="left"))
        hi = int(np.searchsorted(masses, mz + window, side="right"))
        best, distance = None, window
        for index in range(lo, hi):
            if index in used:
                continue
            gap = abs(masses[index] - mz)
            if gap <= distance:
                best, distance = index, gap
        if best is not None:
            used.add(best)
            matches.append(PeakMatch(mz=float(mz), intensity=float(intensity),
                                     ion=ordered[best]))
    return matches


def explain(record: LipidRecord, peaks, charge: int = 1,
            tolerance_ppm: float = TOLERANCE_PPM,
            max_cuts: int = 1, max_losses: int = 2,
            adduct=None) -> Explanation | None:
    """
    How much of a spectrum one candidate structure accounts for.

    `adduct` is how the precursor was ionised; a database candidate found at
    an ammonium precursor is scored with the ammonium ion on the list, which
    the cleavages alone cannot reach. Without one the charge is a proton,
    which is what `charge` alone can say.
    """
    molecule = record.molecule()
    if molecule is None:
        return None
    ions = structure_ions(molecule, adduct=adduct, charge=charge,
                          max_cuts=max_cuts, max_losses=max_losses)
    matches = match_peaks(peaks, ions, tolerance_ppm)
    # where a mass has rival routes, let the spectrum pick between them: the
    # route whose own intermediates are present is the better explanation
    matches = [
        PeakMatch(mz=m.mz, intensity=m.intensity, ion=m.ion,
                  route=routes_for(molecule, m.ion, peaks, tolerance_ppm)[0])
        for m in matches
    ]
    total = sum(height for _mz, height in peaks)
    explained = sum(m.intensity for m in matches)
    return Explanation(record=record, matches=matches, explained=explained,
                       total=total, considered=len(peaks), predicted=len(ions), ions=ions)


# --------------------------------------------------------------------------- #
# a structure, or a formula, that is not in the database
# --------------------------------------------------------------------------- #
#: what a deuterium adds over the hydrogen it replaces
D_MINUS_H = 2.01410177785 - 1.00782503223

#: the losses a formula alone can be asked about, up to this many at once.
#: One more than a structure gets, because a structure has cleavages as well
#: and a formula has only these.
FORMULA_LOSSES = 3


def with_labels(ions: list[PredictedIon], deuterium: int,
                at_least: int = 0) -> list[PredictedIon]:
    """
    The same ions carrying 0 to `deuterium` labels, when the structure was
    drawn unlabelled and nobody knows which hydrogens are heavy.

    A d4 bile acid bought as a standard is drawn by its vendor with four
    heavy hydrogens somewhere on the steroid; a fragment keeps between none
    and all of them. Enumerating every placement would be honest and
    useless; enumerating the count is what the spectrum can actually
    confirm — the ion at +2.0126 is a piece that kept two. A piece cannot
    keep more labels than it has hydrogens.
    """
    if deuterium <= 0:
        return list(ions)
    out: list[PredictedIon] = []
    for ion in ions:
        hydrogens = _hydrogen_count(ion.fragment.formula) + ion.hydrogens
        most = min(deuterium, max(hydrogens, 0))
        for k in range(at_least, most + 1):
            shift = k * D_MINUS_H / abs(ion.charge or 1)
            out.append(replace(ion, mz=ion.mz + shift, labels=k))
    return out


def _hydrogen_count(formula: str) -> int:
    from .chemistry import FormulaError, parse_formula

    try:
        counts = parse_formula(formula)
    except FormulaError:
        return 0
    return counts.get("H", 0) + counts.get("D", 0)


def custom_record(name: str, formula: str, molecule: Structure | None = None
                  ) -> LipidRecord:
    """A record for a structure or formula the database does not hold."""
    from .chemistry import FormulaError, monoisotopic_mass, parse_formula

    try:
        mass = monoisotopic_mass(parse_formula(formula)) if formula else 0.0
    except FormulaError:
        mass = 0.0
    return LipidRecord(lm_id="", name=name or formula or "your structure",
                       abbrev=name or formula, formula=formula, exact_mass=mass,
                       category="your own",
                       structure=molecule.to_compact() if molecule else None)


@dataclass(frozen=True)
class NamedCompound:
    """What a written name resolved to, and where it came from."""

    written: str
    #: the name with any label suffix taken off
    compound: str
    formula: str
    #: deuterium the name declares but does not place — the `4` of `-d4`
    labels: int = 0
    #: in words, for the basis line: a name resolved from a table is not the
    #: same evidence as one the analyst typed a formula for
    source: str = ""
    record: LipidRecord | None = None

    def molecule(self) -> Structure | None:
        return self.record.molecule() if self.record is not None else None


def resolve_name(text: str, database: "LipidDatabase | None" = None,
                 use_installed: bool = True) -> NamedCompound | None:
    """
    A compound written by name, resolved to a formula and — where there is
    one — a drawing.

    Three places are asked, in order. A **table of standards** the analyst
    buys by their trivial names: bile acids and their conjugates, by name or
    by the abbreviation on the bottle, because nothing in LIPID MAPS answers
    to `TDCA` and a `.wiff` is named after the bottle. What that table gives
    is the LIPID MAPS spelling, so the drawing still comes from the database
    when it is installed and the formula it also carries is the fallback for
    a machine without one. Then **LIPID MAPS itself**, by name or LM_ID.
    Then the **lipid shorthand**, which is a formula and no structure.

    A `-d4` on the end is read as four labels the name does not place — the
    number `explain.with_labels` enumerates — and is stripped before any of
    the three are asked. `None` means none of them knew the name, which the
    caller should say rather than guess at.
    """
    from . import lipidmaps
    from .chemistry import formula_from_name, split_labels, standard_named

    written = str(text or "").strip()
    if not written:
        return None
    compound, labels = split_labels(written)
    if database is None and use_installed:
        database = lipidmaps.database()

    def with_record(name: str, formula: str, source: str) -> NamedCompound:
        found = database.find_by_name(name, limit=1) if database else []
        record = found[0] if found else None
        if record is not None and record.formula:
            formula = record.formula
        return NamedCompound(written=written, compound=compound,
                             formula=formula, labels=labels, source=source,
                             record=record)

    known = standard_named(compound)
    if known is not None:
        formula, lm_name = known
        return with_record(lm_name, formula, "the standards table")
    if database is not None:
        found = database.find_by_name(compound, limit=1)
        if found and found[0].formula:
            return NamedCompound(written=written, compound=compound,
                                 formula=found[0].formula, labels=labels,
                                 source="LIPID MAPS", record=found[0])
    shorthand = formula_from_name(compound)
    if shorthand:
        return NamedCompound(written=written, compound=compound,
                             formula=shorthand, labels=labels,
                             source="the lipid shorthand")
    return None


def structure_ions(molecule: Structure, adduct=None, charge: int = 1,
                   max_cuts: int = 1, max_losses: int = 2,
                   deuterium: int = 0) -> list[PredictedIon]:
    """
    Everything a drawing plus an adduct can produce: the precursor as it was
    ionised, and every cleavage under the charge form its fragments carry.

    The enumerator's own arithmetic is already the protonated — or
    deprotonated — piece, which is exactly right for a proton adduct and for
    a labile one, whose adduct has left before anything breaks. So a
    labile adduct adds one ion the cleavages cannot reach, the intact
    [M+NH4]+ itself, and changes nothing else. A metal adduct runs the
    enumeration twice, once with the metal carrying the charge and once with
    a proton, because which piece keeps the metal is not something
    arithmetic can decide.

    The whole molecule's own ions are then relabelled as forms of the
    precursor — `[M+H-3H2O]+` rather than `C24H31D4O2` — since that is the
    name they are read by; a piece keeps the formula it is.

    That one ion is worth measuring. PubChem's cholic acid-d4 against its own
    infusions, two cuts and three losses at 10 ppm: 1,080 ions before and
    1,081 after, and what the extra one buys is 60.3% to 82.0% of the
    intensity under EAD at 22 eV and 9.7% to 92.0% at 12 eV, where the
    ammonium adduct *is* the base peak. Under CID at 45 eV it buys nothing —
    25 of 1,081 and 56.5% either way — because by then the precursor is
    gone.
    """
    from .chemistry import LABILE, adduct_from_name, fragment_adducts

    if isinstance(adduct, str):
        adduct = adduct_from_name(adduct)
    sign = adduct.polarity if adduct is not None else (1 if charge >= 0 else -1)
    carriers = fragment_adducts(adduct) if adduct is not None else (None,)
    ions: list[PredictedIon] = []
    for carrier in carriers:
        ions.extend(predict(molecule, charge=sign, max_cuts=max_cuts,
                            max_losses=max_losses,
                            carrier=carrier.carrier if carrier else ""))
    ions = [_as_precursor_form(ion, adduct, len(molecule.atoms))
            for ion in ions]
    # a metal adduct's own precursor is the uncut molecule the enumeration
    # already produced, carrying the metal; a labile one's is not reachable
    # from a cleavage at all, since the adduct has left by then
    if adduct is not None and adduct.behaviour == LABILE:
        intact = _intact_ion(molecule, adduct)
        if intact is not None:
            ions.append(intact)
    return with_labels(ions, deuterium)


def _intact_ion(molecule: Structure, adduct) -> PredictedIon | None:
    """The precursor as it was ionised — the one ion no cleavage reaches."""
    from .chemistry import FormulaError, monoisotopic_mass, parse_formula
    from .structure import Fragment

    try:
        counts = parse_formula(molecule.formula)
    except (FormulaError, ValueError):
        return None
    mass = monoisotopic_mass(counts)
    piece = Fragment(atoms=frozenset(range(len(molecule.atoms))),
                     formula=molecule.formula, mass=mass, cuts=())
    return PredictedIon(fragment=piece, mz=adduct.mz(mass),
                        charge=adduct.charge, hydrogens=0,
                        carrier=adduct.carrier, form=adduct.name)


def _as_precursor_form(ion: PredictedIon, adduct, atoms: int) -> PredictedIon:
    """
    An uncut molecule carrying the expected charge, renamed as the form of
    the precursor it is. A piece is left alone, and so is a whole molecule
    that reached its mass by moving hydrogens the charge cannot account
    for — `[M-H]+` is not a form anybody writes, and pretending it is would
    hide an assumption inside a tidy name.
    """
    from .chemistry import ADDUCTS_BY_NAME

    if ion.fragment.cuts or len(ion.fragment.atoms) != atoms:
        return ion
    if ion.carrier:
        carrier = next((a for a in ADDUCTS_BY_NAME.values()
                        if a.carrier == ion.carrier
                        and (a.charge > 0) == (ion.charge > 0)), None)
        if carrier is None or ion.hydrogens:
            return ion
    else:
        if ion.hydrogens != (1 if ion.charge > 0 else -1):
            return ion
        carrier = ADDUCTS_BY_NAME["[M+H]+" if ion.charge > 0 else "[M-H]-"]
    form = ion_form(carrier, ion.losses)
    if (adduct is not None and not ion.losses
            and adduct.name != carrier.name and adduct.leaves):
        form = f"{carrier.name} (-{adduct.leaves})"
    return replace(ion, form=form)


def explain_structure(molecule: Structure, peaks, name: str = "",
                      charge: int = 1, tolerance_ppm: float = TOLERANCE_PPM,
                      max_cuts: int = 1, max_losses: int = 2,
                      deuterium: int = 0, adduct=None) -> Explanation:
    """
    What a structure of one's own accounts for — a molfile from PubChem, a
    vendor's drawing, anything the database lacks.

    `deuterium` is the number of labels the drawing does not place; a
    drawing that places them (an `M  ISO` block, or explicit D atoms) needs
    none, and its fragments come out with the right masses by themselves.
    `adduct` is how the precursor was ionised; without one the charge is
    taken to be a proton, which is what `charge` alone can say.
    """
    record = custom_record(name, molecule.formula, molecule)
    ions = structure_ions(molecule, adduct=adduct, charge=charge,
                          max_cuts=max_cuts, max_losses=max_losses,
                          deuterium=deuterium)
    matches = match_peaks(peaks, ions, tolerance_ppm)
    matches = [
        PeakMatch(mz=m.mz, intensity=m.intensity, ion=m.ion,
                  route=routes_for(molecule, m.ion, peaks, tolerance_ppm)[0])
        for m in matches
    ]
    total = sum(height for _mz, height in peaks)
    explained = sum(m.intensity for m in matches)
    return Explanation(record=record, matches=matches, explained=explained,
                       total=total, considered=len(peaks), predicted=len(ions), ions=ions)


def loss_text(losses: tuple[str, ...]) -> str:
    """`("H2O", "H2O", "H2O")` written as `-3H2O`, keeping the loss order."""
    out, seen = [], {}
    for loss in losses:
        if loss not in seen:
            seen[loss] = 0
            out.append(loss)
        seen[loss] += 1
    return "".join(f"-{seen[loss]}{loss}" if seen[loss] > 1 else f"-{loss}"
                   for loss in out)


def ion_form(adduct, losses: tuple[str, ...] = ()) -> str:
    """
    An adduct and what it then shed, written the way a method writes it:
    `[M+NH4]+`, `[M+H-3H2O]+`, `[M-H-CO2]-`.

    The losses go inside the bracket because that is where they belong: the
    thing that lost the water is the ion, not the charge.
    """
    name = adduct.name
    if "]" not in name:
        return name
    body, sign = name[1:].split("]", 1)
    return f"[{body}{loss_text(losses)}]{sign}"


def _with_losses(counts: dict[str, int], losses: tuple[str, ...]
                 ) -> dict[str, int] | None:
    """What is left of a composition after a combination of losses."""
    from .chemistry import parse_formula

    remaining = dict(counts)
    for loss in losses:
        for element, n in parse_formula(NEUTRAL_LOSSES[loss]).items():
            remaining[element] = remaining.get(element, 0) - n
            if remaining[element] < 0:
                return None
    return {element: n for element, n in remaining.items() if n > 0}


def precursor_ions(formula: str, adduct, deuterium: int = 0,
                   max_losses: int = FORMULA_LOSSES) -> list[PredictedIon]:
    """
    Every ion a precursor of this composition can give without cutting a
    bond: the intact adduct, the form its fragments carry, and the ladder of
    small neutrals that form can shed.

    Which ions those are is the adduct's business rather than arithmetic's,
    and the rule is in `chemistry`'s docstring. An ammoniated precursor is
    seen intact at [M+NH4]+ and then as [M+H]+, because the ammonia leaves
    as a neutral and hands over a proton; the ladder hangs off the [M+H]+,
    not off the ammonium, so `[M+NH4-H2O]+` is never offered. A sodiated one
    keeps its sodium, and the ladder is offered twice — once on the sodium
    and once on a proton — each ion saying which was assumed.

    The intact ion carries every label; a loss ion may have shed some of
    them with the leaving group, and `LOSS_TAKES` says how many each loss
    could take. The residual formula is corrected for the ones that left, so
    a rung written `+3D` is the composition it claims to be. Labels spelt
    into the formula (`C24H36D4O5`) count the same as labels declared as
    unplaced (`C24H40O5` with `deuterium=4`); before that they did not, and
    writing them out quietly switched the -1D rungs off.

    Measured on the ZenoTOF cholic acid-d4 infusions, whole run averaged and
    centroided, at 10 ppm: under EAD at 22 eV this finds 8 of the 56 ions it
    offers and 63.6% of the intensity — the whole ladder, 430.3489,
    413.3217, 395.3118, 377.3015, 359.2897, and 394.3035, 376.2935, 358.2836
    beside them, each having lost a label with a water. Scored as the
    ammonium adduct without this rule it found 1 of 31 and 21.7%, and as
    `[M+H]+` 4 of 31 and 34.2% — the ladder but not the precursor, which is
    98% of the base peak.
    """
    from .chemistry import (LABILE, FormulaError, adduct_from_name,
                            format_formula, fragment_adducts,
                            monoisotopic_mass, parse_formula)
    from .structure import Fragment, _loss_combinations

    if isinstance(adduct, str):
        adduct = adduct_from_name(adduct)
    if adduct is None:
        return []
    try:
        counts = dict(parse_formula(formula))
    except (FormulaError, ValueError):
        return []
    if not counts:
        return []
    if deuterium:
        counts["D"] = counts.get("D", 0) + deuterium
        counts["H"] = counts.get("H", 0) - deuterium
        if counts["H"] < 0:
            return []
    # a label is a label however it was written. `C24H36D4O5` typed out and
    # `C24H40O5` with four unplaced labels are the same four deuteriums, and
    # a dehydration can take one either way; before this, spelling them into
    # the formula quietly switched the -1D rungs off
    labelled = counts.get("D", 0)

    def ion(composition, carrier_adduct, losses, kept, form) -> PredictedIon:
        mass = monoisotopic_mass(composition)
        piece = Fragment(atoms=frozenset(), formula=format_formula(composition),
                         mass=mass, cuts=())
        return PredictedIon(
            fragment=piece, mz=carrier_adduct.mz(mass),
            charge=carrier_adduct.charge, hydrogens=0, losses=losses,
            labels=kept, carrier=carrier_adduct.carrier, form=form)

    ions = [ion(counts, adduct, (), labelled, adduct.name)]
    seen = {adduct.name}
    for carrier in fragment_adducts(adduct):
        if carrier.name not in seen:
            # the intact molecule under the fragments' own charge form. It is
            # a real ion when the adduct simply left — an ammonium hands over
            # its proton — and not one for a metal, where [M+H]+ would be a
            # different precursor rather than a product of this one.
            if adduct.behaviour == LABILE:
                ions.append(ion(counts, carrier, (), labelled,
                                f"{carrier.name} (-{adduct.leaves})"))
            seen.add(carrier.name)
        for combo in _loss_combinations(max_losses):
            if not combo:
                continue
            remaining = _with_losses(counts, combo)
            if remaining is None:
                continue
            shed = min(sum(LOSS_TAKES.get(loss, 0) for loss in combo), labelled)
            taken = sum(_hydrogen_count(NEUTRAL_LOSSES[loss]) for loss in combo)
            for kept in range(labelled - shed, labelled + 1):
                lost = labelled - kept
                composition = dict(remaining)
                if lost:
                    # a label that left went with the neutral, so the piece
                    # has one fewer D and one more ordinary H than it would
                    if composition.get("D", 0) < lost or taken < lost:
                        continue
                    composition["D"] -= lost
                    composition["H"] = composition.get("H", 0) + lost
                    composition = {k: v for k, v in composition.items() if v > 0}
                ions.append(ion(composition, carrier, tuple(combo), kept,
                                ion_form(carrier, tuple(combo))))
    return _collapse(ions)


def _collapse(ions: list[PredictedIon]) -> list[PredictedIon]:
    """
    One ion per mass, the simplest route first and the rivals kept beside it.

    Losing formic acid and losing water then carbon monoxide reach the same
    number to the fourth decimal, and offering both would count one ion
    twice: the denominator of "n of m found" would grow while nothing new
    became findable. `predict` collapses the cleavage routes for the same
    reason; this is that rule for the precursor's own.
    """
    routes: dict[int, list[PredictedIon]] = {}
    for candidate in ions:
        routes.setdefault(round(candidate.mz, 4), []).append(candidate)
    out = []
    for candidates in routes.values():
        candidates.sort(key=lambda i: (len(i.losses), i.description))
        head = candidates[0]
        others = tuple(name for name in
                       dict.fromkeys(i.description for i in candidates[1:])
                       if name != head.description)
        out.append(replace(head, alternatives=others))
    return sorted(out, key=lambda i: i.mz)


def formula_ions(formula: str, adduct_name: str, deuterium: int = 0,
                 max_losses: int = FORMULA_LOSSES) -> list[PredictedIon]:
    """
    The ions a formula alone allows — `precursor_ions` under the name the
    formula route has always called it by.

    A formula has no bonds to cut, so this is the whole of what can be said
    without a drawing: the precursor as it was ionised, the form its
    fragments carry, and the ladder of waters, ammonias and carbon dioxides
    that form could shed.
    """
    return precursor_ions(formula, adduct_name, deuterium, max_losses)


def explain_formula(formula: str, adduct_name: str, peaks, name: str = "",
                    deuterium: int = 0, tolerance_ppm: float = TOLERANCE_PPM,
                    max_losses: int = FORMULA_LOSSES) -> Explanation:
    """What a formula alone accounts for: the precursor and its losses."""
    ions = formula_ions(formula, adduct_name, deuterium, max_losses)
    record = custom_record(name, formula)
    matches = match_peaks(peaks, ions, tolerance_ppm)
    matches = [
        PeakMatch(mz=m.mz, intensity=m.intensity, ion=m.ion,
                  route=routes_for(None, m.ion, peaks, tolerance_ppm)[0])
        for m in matches
    ]
    total = sum(height for _mz, height in peaks)
    explained = sum(m.intensity for m in matches)
    return Explanation(record=record, matches=matches, explained=explained,
                       total=total, considered=len(peaks), predicted=len(ions), ions=ions)


# --------------------------------------------------------------------------- #
# where the labels are
# --------------------------------------------------------------------------- #
#: how many carbon-bound hydrogens a neutral loss can take away with it.
#: A dehydration leaves with the hydroxyl's own hydrogen and one more from a
#: carbon beside it, which is measured rather than assumed — the three-water
#: loss of cholic acid-d4 is in the spectrum twice, once keeping four labels
#: and once keeping three. A decarboxylation takes no carbon-bound hydrogen
#: at all, so an ion that shed CO2 says exactly how many labels its piece had.
LOSS_TAKES: dict[str, int] = {"H2O": 1, "NH3": 1, "CO": 0, "CO2": 0,
                              "HCOOH": 1}

#: whether a hydrogen a piece *lost* on cleavage may have been a label.
#: Measured both ways against a drawing whose labels are known — PubChem's
#: cholic acid-d4 — and left on: with it off, a piece written `-2H` cannot
#: have shed a label, and on that CID spectrum the true placement satisfied
#: 43% of the evidence rather than 78% and was beaten by 96% of the
#: possibilities rather than 79%. It also stopped the inference naming a
#: position: with it off, every top placement agreed on a methyl that has
#: no label on it.
TRANSFERS_MOVE_LABELS = True

#: placements are enumerated over the positions the observations cannot tell
#: apart, so the count is far below the raw combinations; past this many the
#: molecule is too big to place and the inference says so instead of guessing
MAX_PLACEMENTS = 200_000

#: how many top placements are described
TOP_PLACEMENTS = 5


@dataclass(frozen=True)
class LabelSite:
    """
    Positions no matched ion can tell apart, and how many labels sit there.

    Two hydrogens that are inside exactly the same fragments are the same
    position as far as this spectrum is concerned. Grouping them is what
    keeps the enumeration small, and it is also the honest unit of the
    answer: nothing measured here separates them.
    """

    atoms: tuple[int, ...]          # indices into Structure.atoms
    capacities: tuple[int, ...] = ()   # what each of them could hold
    labels: int = 0                 # labels this placement puts on it
    description: str = ""

    @property
    def capacity(self) -> int:
        return sum(self.capacities)

    @property
    def single(self) -> bool:
        return len(self.atoms) == 1

    def text(self) -> str:
        if self.single:
            return f"{self.labels}× {self.description}"
        return (f"{self.labels} among {len(self.atoms)} positions nothing "
                f"here separates ({self.description}, …)")


@dataclass(frozen=True)
class LabelObservation:
    """
    One matched ion, read as a constraint on where the labels are.

    A piece that kept `kept` of the labels had that many of them inside it —
    exactly, when the ion is a cleavage, and at least that many when it also
    shed a neutral that could have carried one off (`shed`).
    """

    mz: float
    intensity: float
    description: str
    kept: int
    inside: frozenset[int]
    shed: int = 0
    weight: float = 0.0
    informative: bool = False
    #: nothing else within the tolerance reaches this peak with a different
    #: number of labels, so the count is read rather than picked
    decisive: bool = True

    def allows(self, count: int) -> bool:
        return self.kept <= count <= self.kept + self.shed


@dataclass(frozen=True)
class Placement:
    """One way of putting the labels on the molecule, and what it satisfies."""

    sites: tuple[LabelSite, ...]        # only the sites carrying a label
    score: float                        # share of matched intensity satisfied
    satisfied: int
    ways: int                           # position-by-position placements

    def text(self) -> str:
        return "; ".join(site.text() for site in self.sites)


@dataclass(frozen=True)
class AgreedPosition:
    """A position every top placement labels, and how many times."""

    atom: int
    labels: int
    description: str


@dataclass(frozen=True)
class LabelInference:
    """Where the labels can be, given what the fragments kept."""

    deuterium: int
    positions: tuple[int, ...] = ()
    observations: tuple[LabelObservation, ...] = ()
    placements: tuple[Placement, ...] = ()
    tied: int = 0
    agreed: tuple[AgreedPosition, ...] = ()
    unconstrained: tuple[int, ...] = ()
    #: labels the drawing itself places (`M  ISO`, or explicit D atoms)
    declared: tuple[int, ...] = ()
    #: the placement scored against the evidence rather than inferred from it:
    #: the drawing's own, or one handed in to be checked
    checked: tuple[int, ...] = ()
    checked_score: float | None = None
    checked_top: bool = False
    #: placements that satisfy strictly more of the evidence than it does
    checked_beaten: int = 0
    #: placements in all, position by position
    total: int = 0
    #: how much of the evidence there was to satisfy
    available: float = 0.0
    #: peaks only a different number of labels would explain
    shifted: tuple[tuple[float, str, int], ...] = ()
    heteroatoms: bool = False
    #: matched ions left out because something else within the tolerance
    #: reaches them carrying a different number of labels
    undecided: int = 0
    note: str = ""

    @property
    def informative(self) -> int:
        return sum(1 for o in self.observations if o.informative)

    @property
    def placed(self) -> bool:
        return bool(self.declared)

    @property
    def agreement(self) -> float:
        """The share of the evidence the best placement satisfies."""
        if not self.placements or not self.available:
            return 0.0
        return self.placements[0].score / self.available

    @property
    def checked_agreement(self) -> float:
        if self.checked_score is None or not self.available:
            return 0.0
        return self.checked_score / self.available

    @property
    def best(self) -> Placement | None:
        return self.placements[0] if self.placements else None

    def summary(self) -> str:
        """The finding in a sentence or two, for a panel or a report."""
        if self.note and not self.placements:
            return self.note
        n = self.deuterium
        parts = [
            f"{n} label(s) over {len(self.positions)} position(s): "
            f"{len(self.observations)} ion(s) say how many labels their piece "
            f"kept, {self.informative} of them tell placements apart."
        ]
        if self.undecided:
            parts.append(f"{self.undecided} more matched ion(s) are left out: "
                         "something else within the tolerance reaches them "
                         "with a different number of labels.")
        if self.tied > 1:
            parts.append(f"{self.tied:,} of {self.total:,} placements fit them "
                         f"equally well, at {self.agreement * 100:.0f}% of the "
                         "evidence.")
        elif self.tied == 1:
            parts.append(f"One placement of {self.total:,} fits them alone, at "
                         f"{self.agreement * 100:.0f}% of the evidence.")
        if self.agreed:
            parts.append("Every one of them labels " + ", ".join(
                f"{a.description} ({a.labels}×)" for a in self.agreed) + ".")
        else:
            parts.append("No position is in all of them.")
        if self.unconstrained:
            parts.append(f"{len(self.unconstrained)} position(s) are inside "
                         "every fragment or outside every one, so nothing "
                         "here places a label on them.")
        if self.checked:
            whose = ("The drawing places its labels itself"
                     if self.declared else "The placement asked about")
            where = ("is among the best" if self.checked_top else
                     f"is beaten by {self.checked_beaten:,} of them")
            parts.append(
                f"{whose}: that placement satisfies "
                f"{self.checked_agreement * 100:.0f}% of the evidence and "
                f"{where}.")
        if self.shifted:
            parts.append(f"{len(self.shifted)} peak(s) fit the same piece "
                         "carrying a different number of labels.")
        if self.note:
            parts.append(self.note)
        return " ".join(parts)


def label_positions(structure: Structure,
                    heteroatoms: bool = False) -> list[tuple[int, int]]:
    """
    Where a label could sit: (atom, how many it could hold).

    A heavy atom offers as many as it carries; a hydrogen still written out
    as an atom of its own offers itself. Heteroatom-bound hydrogens are left
    out by default: an O–D or an N–D exchanges with the solvent long before
    the spectrum is recorded, so a label drawn there is not one that survives
    to be measured.
    """
    out = []
    for index, atom in enumerate(structure.atoms):
        if atom.element in ("H", "D"):
            parents = structure.neighbours(index)
            if not parents:
                continue
            if heteroatoms or structure.atoms[parents[0]].element == "C":
                out.append((index, 1))
            continue
        capacity = atom.hydrogens + atom.deuterium
        if capacity > 0 and (heteroatoms or atom.element == "C"):
            out.append((index, capacity))
    return out


def placed_labels(structure: Structure) -> tuple[int, ...]:
    """
    The atoms a drawing marks as heavy hydrogen itself, one entry per label.

    An atom drawn with two of them is named twice, because that is what the
    placement says.
    """
    out: list[int] = []
    for index, atom in enumerate(structure.atoms):
        if atom.element == "D":
            out.append(index)
        out.extend([index] * atom.deuterium)
    return tuple(out)


def describe_position(structure: Structure, index: int) -> str:
    """
    A position named the way somebody reading a structure would name it.

    There is no ring lettering in a molfile, so this is the molfile's own
    numbering plus what the atom is next to — which is what actually matters
    when the question is whether the labels sit beside a hydroxyl.
    """
    atom = structure.atoms[index]
    if atom.element in ("H", "D"):
        parents = structure.neighbours(index)
        if not parents:
            return f"{atom.element}{index + 1}"
        return (f"{atom.element}{index + 1} on "
                f"{_describe_heavy(structure, parents[0])}")
    return _describe_heavy(structure, index)


def _describe_heavy(structure: Structure, index: int) -> str:
    atom = structure.atoms[index]
    hydrogens = atom.hydrogens + atom.deuterium + sum(
        1 for n in structure.neighbours(index)
        if structure.atoms[n].element in ("H", "D"))
    shape = f"{atom.element}H{hydrogens}" if hydrogens > 1 else (
        f"{atom.element}H" if hydrogens == 1 else atom.element)
    groups = structure.functional_groups([index])
    near = []
    if groups.get("carboxyl"):
        near.append("carboxyl")
    elif groups.get("carbonyl"):
        near.append("carbonyl")
    if any(structure.atoms[n].element == "O"
           and (structure.atoms[n].hydrogens
                or any(structure.atoms[h].element in ("H", "D")
                       for h in structure.neighbours(n)))
           for n in structure.neighbours(index)):
        near.append("bears the O–H")
    else:
        for neighbour in structure.neighbours(index):
            if structure.atoms[neighbour].element != "C":
                continue
            if any(structure.atoms[o].element == "O"
                   and (structure.atoms[o].hydrogens
                        or any(structure.atoms[h].element in ("H", "D")
                               for h in structure.neighbours(o)))
                   for o in structure.neighbours(neighbour)):
                near.append(f"next to C{neighbour + 1}–OH")
                break
    label = f"{atom.element}{index + 1} ({shape}"
    if near:
        label += ", " + ", ".join(near)
    return label + ")"


def infer_labels(explanation: Explanation, molecule: Structure,
                 deuterium: int = 0, peaks=None, heteroatoms: bool = False,
                 tolerance_ppm: float = TOLERANCE_PPM,
                 top: int = TOP_PLACEMENTS, ambiguous: bool = False,
                 transfers: bool = TRANSFERS_MOVE_LABELS,
                 proposed: tuple[int, ...] = ()) -> LabelInference:
    """
    Where the labels are, inferred from which fragments kept them.

    `with_labels` asks the spectrum how many labels a piece kept. That answer
    is also a statement about *which* labels: a piece that kept none of four
    contains none of them, and a piece that kept all four contains all four.
    Take a placement to be a set of positions and a fragment's observation to
    be a count, and every matched ion either agrees with a placement or rules
    it out.

    An ion only counts when it *says* a number. A deuterium is 1.55 mDa
    heavier than the hydrogen it replaced, so the same piece with one more
    label and one fewer hydrogen sits 1.55 mDa away, and a window wider than
    that holds both: the matcher takes the nearer, which decides nothing.
    Those ions are counted (`undecided`) and left out, unless `ambiguous`
    says to use them anyway.

    Two things a piece can do with a label on the way out, and both are
    allowed rather than assumed away. A neutral loss may carry one off where
    it can (`LOSS_TAKES`): a dehydration leaves with the hydroxyl's own
    hydrogen and one more from the carbon beside it, so it bounds the count
    rather than fixing it, while a decarboxylation takes no carbon-bound
    hydrogen and says exactly. And a hydrogen the piece *lost* on cleavage
    may have been a label (`TRANSFERS_MOVE_LABELS`), which is looser and was
    measured to be the honest reading.

    What comes back is the best placements, how many are tied, the positions
    every top placement agrees on, and the ones nothing here constrains.
    Where the drawing places the labels itself — or where `proposed` names a
    placement to check — that placement is scored against the same evidence
    and ranked against the rest rather than replaced by a guess.
    """
    declared = placed_labels(molecule)
    labels = deuterium or len(declared)
    if labels <= 0:
        return LabelInference(deuterium=0, heteroatoms=heteroatoms,
                              note="No labels to place.")

    positions = label_positions(molecule, heteroatoms)
    if not positions:
        return LabelInference(
            deuterium=labels, declared=declared, heteroatoms=heteroatoms,
            note="The drawing has no position a label could sit on.")
    if sum(capacity for _atom, capacity in positions) < labels:
        return LabelInference(
            deuterium=labels, declared=declared, heteroatoms=heteroatoms,
            positions=tuple(a for a, _c in positions),
            note=f"{labels} labels will not fit on the positions the drawing "
                 "offers.")

    every = _observations(explanation, molecule, declared, positions,
                          tolerance_ppm, transfers)
    observations = tuple(o for o in every if o.decisive or ambiguous)
    undecided = len(every) - len(observations)
    if not observations:
        return LabelInference(
            deuterium=labels, declared=declared, heteroatoms=heteroatoms,
            positions=tuple(a for a, _c in positions), observations=every,
            undecided=undecided,
            note=(f"None of the {len(every)} matched ion(s) says how many "
                  "labels its piece kept: something else within the tolerance "
                  "reaches each of them with a different number. A label is "
                  "1.55 mDa from the hydrogen it replaced, and at "
                  f"{tolerance_ppm:g} ppm that gap is inside the window from "
                  f"m/z {1550 / max(tolerance_ppm, 1e-9):.0f} upwards: "
                  "narrow the tolerance and ask again."
                  if every else
                  "No matched ion carries a piece of the drawing, so there is "
                  "nothing to place the labels from."))

    sites = _sites(positions, observations, molecule)
    counted = _count_placements([s.capacity for s in sites], labels)
    if counted > MAX_PLACEMENTS:
        return LabelInference(
            deuterium=labels, declared=declared, heteroatoms=heteroatoms,
            positions=tuple(a for a, _c in positions),
            observations=observations,
            note=f"{counted:,} placements over {len(sites)} distinguishable "
                 f"site(s) is past the {MAX_PLACEMENTS:,} this will enumerate "
                 "— too big a molecule to place this way.")

    found, satisfied_per_observation = _score_placements(sites, observations,
                                                         labels)
    observations = tuple(
        replace(o, informative=count < len(found))
        for o, count in zip(observations, satisfied_per_observation))

    best = max(score for score, _distribution in found)
    winners = [d for score, d in found if round(score, 9) >= round(best, 9)]
    tied = sum(_placement_ways(sites, distribution) for distribution in winners)

    placements = tuple(
        Placement(sites=tuple(
            replace(site, labels=count)
            for site, count in zip(sites, distribution) if count),
            score=best,
            satisfied=sum(1 for o in observations
                          if o.allows(_inside(o, sites, distribution))),
            ways=_placement_ways(sites, distribution))
        for distribution in winners[:top])

    agreed = _agreed(sites, winners, molecule)
    informative = [o for o in observations if o.informative]
    unconstrained = tuple(
        atom for site in sites
        if _constant(site, informative) for atom in site.atoms)

    checked = tuple(declared or proposed)
    checked_score, checked_top, beaten = None, False, 0
    if checked:
        checked_score = _score_of(checked, observations)
        checked_top = round(checked_score, 9) >= round(best, 9)
        beaten = sum(_placement_ways(sites, distribution)
                     for score, distribution in found
                     if round(score, 9) > round(checked_score, 9))

    shifted = _shifted_peaks(explanation, peaks, labels, tolerance_ppm)
    return LabelInference(
        deuterium=labels, positions=tuple(a for a, _c in positions),
        observations=observations, placements=placements, tied=tied,
        agreed=agreed, unconstrained=unconstrained, declared=declared,
        checked=checked, checked_score=checked_score, checked_top=checked_top,
        checked_beaten=beaten,
        total=sum(_placement_ways(sites, d) for _s, d in found),
        available=sum(o.weight for o in observations),
        shifted=shifted, heteroatoms=heteroatoms, undecided=undecided)


def _observations(explanation: Explanation, molecule: Structure,
                  declared: tuple[int, ...], positions, tolerance_ppm: float,
                  transfers: bool = False) -> tuple[LabelObservation, ...]:
    """Each matched ion, as what it says about the labels inside its piece."""
    candidates = {atom for atom, _capacity in positions}
    total = sum(m.intensity for m in explanation.matches) or 1.0
    masses, rivals = _constraints(explanation.ions, declared, candidates,
                                  transfers)
    out = []
    for match in explanation.matches:
        atoms = match.ion.fragment.atoms
        if not atoms:
            continue                       # a formula has no piece to speak of
        kept = match.ion.labels + sum(1 for a in declared if a in atoms)
        closeness = max(0.0, 1.0 - abs(match.error_ppm) / tolerance_ppm)
        shed = _shed_by(match.ion, transfers)
        inside = frozenset(candidates & set(atoms))
        out.append(LabelObservation(
            mz=match.mz, intensity=match.intensity,
            description=match.ion.description, kept=kept, inside=inside,
            shed=shed, weight=match.intensity / total * closeness,
            decisive=_decisive(masses, rivals, match.mz, (kept, shed, inside),
                               tolerance_ppm)))
    return tuple(out)


def _shed_by(ion: PredictedIon, transfers: bool) -> int:
    """How many labels the piece could have let go of on the way out."""
    shed = sum(LOSS_TAKES.get(loss, 0) for loss in ion.losses)
    if transfers:
        shed += max(-ion.hydrogens, 0)
    return shed


def _constraints(ions, declared, candidates, transfers: bool):
    """What each predicted ion would say about the labels, sorted by mass."""
    if not ions:
        return np.zeros(0), []
    rows = []
    for ion in ions:
        atoms = ion.fragment.atoms
        rows.append((ion.mz,
                     (ion.labels + sum(1 for a in declared if a in atoms),
                      _shed_by(ion, transfers),
                      frozenset(candidates & set(atoms)))))
    rows.sort(key=lambda row: row[0])
    return (np.array([mz for mz, _c in rows], dtype=float),
            [c for _mz, c in rows])


def _decisive(masses, rivals, mz: float, constraint, tolerance_ppm: float
              ) -> bool:
    """
    Whether a peak says something about the labels or merely gets an answer.

    Two ways a peak can fail to say anything, and both are common. A
    deuterium is 1.55 mDa heavier than the hydrogen it replaced, so the same
    piece with one more label and one fewer hydrogen sits 1.55 mDa away and
    a wider window holds both — the matcher then takes the nearer, which is
    a coin toss. And two different pieces can reach one mass while
    disagreeing about which atoms they contain, in which case the peak
    cannot say where anything is even when both agree on the count.

    So a peak counts only when every ion inside its window says the same
    thing: the same number of labels, shed the same way, over the same
    positions.
    """
    if not masses.size:
        return True
    window = mz * tolerance_ppm * 1e-6
    lo = int(np.searchsorted(masses, mz - window, side="left"))
    hi = int(np.searchsorted(masses, mz + window, side="right"))
    return all(rivals[index] == constraint for index in range(lo, hi))


def _sites(positions, observations, molecule: Structure) -> list[LabelSite]:
    """Positions grouped by the fragments they are inside — the real unit."""
    groups: dict[tuple[bool, ...], list[tuple[int, int]]] = {}
    for atom, capacity in positions:
        signature = tuple(atom in o.inside for o in observations)
        groups.setdefault(signature, []).append((atom, capacity))
    sites = []
    for members in groups.values():
        atoms = tuple(a for a, _c in members)
        sites.append(LabelSite(
            atoms=atoms, capacities=tuple(c for _a, c in members),
            description=describe_position(molecule, atoms[0])))
    sites.sort(key=lambda s: s.atoms[0])
    return sites


def _count_placements(capacities: list[int], labels: int) -> int:
    poly = _polynomial(capacities, labels)
    return poly[labels] if labels < len(poly) else 0


def _polynomial(capacities, limit: int) -> list[int]:
    """How many ways each number of labels fits, by generating polynomial."""
    poly = [1] + [0] * limit
    for capacity in capacities:
        out = [0] * (limit + 1)
        for index, value in enumerate(poly):
            if not value:
                continue
            for k in range(min(capacity, limit - index) + 1):
                out[index + k] += value
        poly = out
    return poly


def _placement_ways(sites, distribution) -> int:
    """How many position-by-position placements one distribution stands for."""
    total = 1
    for site, count in zip(sites, distribution):
        if not count:
            continue
        total *= _ways(site, count)
    return total


def _ways(site: LabelSite, count: int) -> int:
    """How many ways `count` labels fit on the positions of one site."""
    if len(site.atoms) == 1:
        return 1
    poly = _polynomial(list(site.capacities), count)
    return poly[count] if count < len(poly) else 0


def _inside(observation: LabelObservation, sites, distribution) -> int:
    return sum(count for site, count in zip(sites, distribution)
               if count and site.atoms[0] in observation.inside)


def _score_placements(sites, observations, labels: int):
    """Every distribution of the labels over the sites, scored."""
    masks = np.array([[1 if site.atoms[0] in o.inside else 0
                       for o in observations] for site in sites], dtype=int)
    low = np.array([o.kept for o in observations])
    high = np.array([o.kept + o.shed for o in observations])
    weights = np.array([o.weight for o in observations])
    capacities = [site.capacity for site in sites]
    room = [0] * (len(sites) + 1)
    for index in range(len(sites) - 1, -1, -1):
        room[index] = room[index + 1] + capacities[index]

    found: list[tuple[float, tuple[int, ...]]] = []
    satisfied = np.zeros(len(observations), dtype=int)
    distribution = [0] * len(sites)

    def walk(index: int, left: int, counts) -> None:
        if left == 0:
            for rest in range(index, len(sites)):
                distribution[rest] = 0
            hit = (counts >= low) & (counts <= high)
            satisfied[hit] += 1
            found.append((float(weights[hit].sum()), tuple(distribution)))
            return
        if index >= len(sites) or room[index] < left:
            return
        for count in range(min(capacities[index], left) + 1):
            distribution[index] = count
            walk(index + 1, left - count,
                 counts + count * masks[index] if count else counts)
        distribution[index] = 0

    walk(0, labels, np.zeros(len(observations), dtype=int))
    return found, satisfied


def _score_of(atoms, observations) -> float:
    """What one named placement — the drawing's own — satisfies."""
    chosen = list(atoms)
    counts = np.array([sum(1 for a in chosen if a in o.inside)
                       for o in observations])
    low = np.array([o.kept for o in observations])
    high = np.array([o.kept + o.shed for o in observations])
    weights = np.array([o.weight for o in observations])
    hit = (counts >= low) & (counts <= high)
    return float(weights[hit].sum())


def _agreed(sites, winners, molecule: Structure) -> tuple[AgreedPosition, ...]:
    """
    The positions every top placement labels, and how many times.

    A site holding more labels than the rest of it can take forces the
    remainder onto a named atom, which is the only way a position is
    pinned down when the site has several.
    """
    if not winners:
        return ()
    guaranteed: dict[int, int] = {}
    for site_index, site in enumerate(sites):
        for atom, capacity in zip(site.atoms, site.capacities):
            others = site.capacity - capacity
            least = min(max(0, distribution[site_index] - others)
                        for distribution in winners)
            if least > 0:
                guaranteed[atom] = least
    return tuple(
        AgreedPosition(atom=atom, labels=count,
                       description=describe_position(molecule, atom))
        for atom, count in sorted(guaranteed.items()))


def _constant(site: LabelSite, observations) -> bool:
    """A site inside every informative fragment, or outside every one."""
    if not observations:
        return True
    seen = {site.atoms[0] in o.inside for o in observations}
    return len(seen) == 1


def _shifted_peaks(explanation: Explanation, peaks, labels: int,
                   tolerance_ppm: float, limit: int = 12):
    """
    Peaks that fit a matched piece carrying a different number of labels.

    For a drawing that places its own labels this is the disagreement: the
    spectrum shows the piece with a count the placement does not allow. The
    three-water loss of cholic acid-d4 is the example — it is there twice.
    """
    if not peaks or not explanation.matches:
        return ()
    taken = {round(m.mz, 4) for m in explanation.matches}
    rest = [(mz, height) for mz, height in peaks if round(mz, 4) not in taken]
    if not rest:
        return ()
    out = []
    for mz, _height in sorted(rest, key=lambda p: p[0]):
        for match in explanation.matches:
            charge = abs(match.ion.charge or 1)
            for step in range(-labels, labels + 1):
                if step == 0:
                    continue
                predicted = match.ion.mz + step * D_MINUS_H / charge
                if abs(mz - predicted) <= predicted * tolerance_ppm * 1e-6:
                    out.append((float(mz), match.ion.description, step))
                    break
            else:
                continue
            break
        if len(out) >= limit:
            break
    return tuple(out)


def read_molfile(text: str) -> tuple[Structure | None, str]:
    """
    A structure from a `.mol` or `.sdf` file's text, and its name.

    The first record of an SDF; the name is the file's first line, which is
    where every drawing program and PubChem put it.

    Explicit hydrogens are folded into the atoms that carry them — PubChem
    writes all forty of a bile acid's — because a C–H cleavage is not a
    fragment anybody looks for and a table full of them matches a spectrum by
    accident. Deuterium the drawing places is kept, on the atom it sits on.
    """
    block = text.split("$$$$")[0]
    lines = block.splitlines()
    name = lines[0].strip() if lines else ""
    molecule = parse_molblock(block)
    return (suppress_hydrogens(molecule) if molecule is not None else None), name


def significant_peaks(mz, intensity, noise_share: float = NOISE_SHARE,
                      limit: int = 60) -> list[tuple[float, float]]:
    """The peaks worth explaining: above the noise share, strongest first."""
    mz = np.asarray(mz, dtype=float)
    intensity = np.asarray(intensity, dtype=float)
    if not mz.size:
        return []
    ceiling = float(intensity.max())
    if ceiling <= 0:
        return []
    keep = intensity >= ceiling * noise_share
    pairs = sorted(zip(mz[keep], intensity[keep]), key=lambda p: -p[1])
    return [(float(a), float(b)) for a, b in pairs[:limit]]


def candidates_for(database: LipidDatabase, precursor: float, adduct: str,
                   tolerance: float, unit: str = "ppm",
                   limit: int = 12) -> list[LipidRecord]:
    """
    Structures whose mass fits the precursor, one per species.

    A mass search answers with a family of isomers; taking one of each keeps
    the spectrum from being scored twelve times against the same formula.
    """
    seen: set[str] = set()
    chosen: list[LipidRecord] = []
    for match in database.search_mz(precursor, adduct, tolerance, unit):
        record = match.record
        if not record.structure:
            continue
        key = record.species
        if key in seen:
            continue
        seen.add(key)
        chosen.append(record)
        if len(chosen) >= limit:
            break
    return chosen


def rank_candidates(database: LipidDatabase, precursor: float, peaks,
                    adduct: str = "[M+H]+", tolerance: float = 20.0,
                    unit: str = "ppm", charge: int = 1,
                    max_cuts: int = 1, max_losses: int = 2,
                    limit: int = 12) -> list[Explanation]:
    """
    Every candidate for the precursor, ordered by what it accounts for.

    This is the whole point of the exercise: the enumerator cannot say which
    cleavage happens, and the spectrum can.
    """
    from .chemistry import adduct_from_name

    ionised = adduct_from_name(adduct)
    found = []
    for record in candidates_for(database, precursor, adduct, tolerance, unit,
                                 limit):
        explanation = explain(record, peaks, charge, TOLERANCE_PPM,
                              max_cuts, max_losses, adduct=ionised)
        if explanation is not None:
            found.append(explanation)
    found.sort(key=lambda e: (-e.share, -e.matched))
    return found
