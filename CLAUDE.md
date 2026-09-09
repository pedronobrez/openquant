# OpenQuant — status and working notes

Open source review and quantitation for LC-MS data. A working replacement for
SCIEX PeakView (qualitative) and MultiQuant (quantitative), reading `.wiff`
directly and `.mzML` from any instrument.

This file is for picking the work up in a new session without rereading the
history. It records what is true, what was measured, and what is not settled.
`README.md` is for someone using the application; this is for someone changing
it.

**Version 0.7.5 released. 777 tests. Public repository.**

The repository was recreated on 2026-09-07 to drop a history that showed a
person's name and unpublished results in its screenshots. Rewriting was not
enough: GitHub keeps `refs/pull/*` forever and two diagnostic pull requests
still pointed at the old commits. The previous repository is
`pedronobrez/openquant-archive`, private, and the installers built from it are
saved outside any repository in `~/Documents/OpenQuant-releases/v0.6.1`.
**Do not open a pull request from a branch carrying anything that must not be
public: closing it does not remove the ref.**

---

## Ground rules that came out of the work

These were learned the expensive way. Breaking one has cost a day before.

- **Measure before claiming.** Every performance and fidelity number in this
  file was produced by running something, not by reading code. Two attempts at
  reverse-engineering a vendor algorithm were made and both were wrong; the
  second looked right until it was tested on data it had not been fitted to.
- **A stated difference beats an invented rule.** Where behaviour could not be
  reproduced faithfully, the plain version ships with the measured gap written
  down. See the extraction note below.
- **Never substitute our arithmetic for the instrument's.** Totals, retention
  times and areas come from the vendor where the vendor reports them. Summing
  the stored points instead moved every integrated area by 2%.
- **Raw data is never committed.** `.wiff`, `.wiff.scan`, `.mzML`, `.csv` are
  ignored. Verified: no raw file has ever been in the history.
- **The manual ships with every version.** `openquant/help/pages` is the
  reference the user feeds to NotebookLM; a release that changes what the
  application does changes the page that describes it, adds itself to
  `version-history.md`, and regenerates the PDF for the user (never
  committed). `tests/test_manual.py` fails on an unresolved `[[link]]`, a
  page under six hundred characters, or a file the index does not list.
- **`x or default` is a trap for a measured zero.** A scan with a total ion
  current of zero was read as missing metadata and dropped a whole channel
  onto a fallback, on three of five real files.

---

## Layout

```
openquant/
  raw.py          open_raw(path) → the right reader by extension. The only
                  place that knows formats exist.
  wiff.py         SCIEX, through Clearcore2 over .NET
  mzml.py         mzML reader and writer
  bootstrap.py    brings up .NET and the SCIEX assemblies off Windows
  processing.py   smoothing, baselines, peak detection, centroiding,
                  restore_profile_zeros, and the three integration
                  algorithms: valley, summation, Gaussian fit
  quantify.py     extraction and integration of a component in a sample
  compare.py      the batch integrated every way, and the differences
  calibration.py  regressions and weightings
  statistics.py   grouped means, SD, %CV
  qc.py           control charts through the run, drift, replicate precision
  sampling.py     points per peak, per component, and the cycle time the
                  peaks would need
  mass_drift.py   each standard's measured mass through the run: did the
                  axis hold
  schedule.py     the scheduled acquisition the method implies, and what a
                  target cycle leaves each transition
  library.py      MSP/MGF spectral libraries, and a spectrum searched
                  against one: plain and reverse cosine
  batches.py      two batches of one method side by side, the reference
                  read from its project without opening raw files
  contour.py      the run as a retention time by m/z grid
  health.py       what the method will fail at, before it is run
  suggest.py      retention times and windows the batch can supply
  components.py   the component table; method.py the processing method
  samples.py      SampleEntry, sample types and groups, name shortening
  matching.py     which channel serves a component
  chemistry.py    formulae, adducts, isotope patterns
  lipidmaps.py    LMSD index, name → precursor, mass → candidates
  structure.py    molfile parsing, bond cleavage enumeration
  explain.py      scores candidate structures against a measured spectrum
  precursor.py    confirms a precursor in the survey and product scans
  session.py      the open batch; project save and load (.oqproj)
  manual.py       the built-in manual: help/pages/*.md with [[wiki links]],
                  the search index, and the PDF (through report.print_document)
  help/pages/     the manual's pages, one Markdown file per page
  app.py          CLI: --selftest, --digest
  ui/             shell.py owns the window; explorer / analytics /
                  method_workspace / samples_workspace are the four tabs;
                  help_window.py is Help ▸ Manual
packaging/        PyInstaller spec, DMG script, WiX source, wine/ shim; icons/ is the
                  suite's mark (the two co-eluting peaks), drawn by OpenDIAL's
                  tools/make_icon.py through packaging/make_icon.py and committed —
                  rerun it when the shared mark changes
```

### The reader protocol

Everything above `raw.py` asks a file for samples, a sample for channels, and
a channel for chromatograms and spectra. `MzmlChannel`, `MzmlSample` and
`MzmlFile` implement exactly the surface of `wiff.Channel`, `Sample` and
`WiffFile`, **signatures included** — checked by reflection, not by eye. No
code anywhere does `isinstance` on a reader or touches a reader's private
attributes. Keep it that way; a third format should need nothing but a new
module and an entry in `raw.FORMATS`.

---

## Verified facts

Run against five real acquisitions (81 channels each, ~24,000 spectra).

**Builds agree.** `--digest` prints a numeric fingerprint of what a build
reads. From source on macOS, from the CI disk image, and from the Windows
installer under CrossOver: byte-identical output, sha256 `ebdeebc2…`. 405
channel chromatograms, 25 spectra, 125 integrated peaks with areas to nine
decimals. All 405 channel hashes differ from one another, so those were five
different acquisitions rather than one read five times.

**Formats agree, except in one place.** Exporting a `.wiff` to mzML and
reading it back:

| | |
|---|---|
| spectra | identical, every channel |
| channel chromatograms | identical, every channel |
| the run's total ion chromatogram | identical, 577 points |
| chromatographic peak areas | identical |
| extracted ion chromatograms | **differ** |

The extraction is the exception and it reaches quantitation. SCIEX counts part
of a peak whose measured points fall just outside the mass window; this sums
the points inside. Median 0.58% of peak height, at most 12%, always lower.
End to end, quantifying one component from `.wiff` and from its mzML gives the
same retention time and the same peak width with the area differing by 0.54%.
**Quantify a series in one format.** Two attempts at reproducing the vendor's
edge rule are in the history and neither survived being tested on windows
other than the ones it was derived from — the second was a coin toss, better
on 41 channels and worse on 38.

**ProteoWizard agrees.** msconvert reads what this writes, and its own mzML
written from that reads back here with identical spectra and chromatograms.
Converting a `.wiff` with msconvert itself fails under Wine (`getTWC()`, the
UV detector, is not implemented there) — untested on real Windows.

---

## Things that are subtle and will look like bugs

- **A profile spectrum from mzML has fewer points than the same one from
  `.wiff`.** SCIEX strips the zeros when storing and puts them back when
  drawing. `processing.restore_profile_zeros` does the same for anything else,
  measuring the sampling interval from the file — the smallest quarter of the
  gaps are the ones inside peaks. Without it the baseline appears raised, and,
  worse, peak labels were centroids taken across the gaps: one read 184.8466
  for a peak at 185.0077.
- **mzML has no idea of an experiment.** Channels are inferred. Scan
  properties alone gave 69 channels where the acquisition has 81, because a
  method can have two entries agreeing on MS level, precursor, collision
  energy and mass range. `mzml.acquisition_cycles` recovers them from the
  order of acquisition: a scheduled method repeats a fixed cycle, and position
  in it is the entry. This file is a cycle of 44 run 339 times then one of 37
  run 238 times — 44 + 37 = 81 channels, 44·339 + 37·238 = 23,722 spectra.
  Data-dependent acquisition has no cycle; a cycle must repeat four times to
  be believed, and otherwise the properties are all there is.
- **The run's total ion chromatogram is summed by cycle, not by time.** The
  experiments of one cycle are measured one after another, so the union of
  their times is one point per spectrum — 23,722 where the instrument reports
  577.
- **`sWindows = False`.** `bootstrap` flips a private static field in
  Clearcore2 by reflection to force the managed structured-storage path.
  Without it nothing opens off Windows.
- **`OpenFileMode.ReadOnlyShared`.** Anything else takes an exclusive lock and
  a second window — or Analyst — cannot open the same file.
- **`processEvents()` does not drain deferred deletions.** `setCellWidget`
  marks the widget it replaces for `deleteLater`, and until a real event loop
  runs it the old one is still a visible child at the origin. Opening ten
  files rebuilds the samples table ten times and leaves ninety combo boxes
  piled on the first row's first cell — which is what the screenshots caught
  before they were regenerated with
  `sendPostedEvents(None, QEvent.Type.DeferredDelete)` first. The application
  is fine; anything that grabs or asserts on a widget tree is not, unless it
  flushes. `tests/conftest.py` does this after every test.
- **A control chart compares a standard against itself, and that is not
  enough on its own.** One standard's chart cannot tell an injection that
  failed from a compound that misbehaved: both are a point far from the
  centre. `qc.response_index` divides each internal standard by its own median
  and takes the median of those per injection, so all-standards-down-together
  is separable from one-standard-down-alone. On the batch it was written for,
  the standards taken separately scattered between 32% and 228% and looked
  hopeless; taken together the injections sat within ±18% with three
  exceptions, one of them at 0.08 where every standard had gone at once.
- **Flagging needs a floor and a ceiling, for opposite reasons.**
  `OUT_PERCENT` stops a batch that repeats itself well from flagging ordinary
  scatter. `ALWAYS_OUT_PERCENT` is its mirror: a batch whose own scatter is
  wide swallows a real failure, and an injection where every standard came
  back at a fifth of normal sat at 2.6 robust standard deviations. And when a
  third of a chart is out, `unusable` reports the chart rather than the
  injections — seventeen bad injections out of twenty-six is not a list of
  outliers, it is a standard that cannot normalise anything.
- **A proposal's confidence is measured, not asserted.** `suggest.suggest_times`
  runs the estimator on the components that already declare a retention time
  and reports, per peak-height band, how often it landed within one sampling
  interval — then attaches that band's figure to each proposal. On the real
  method it was 88% above ten thousand counts and 45% below a hundred, and
  because nothing offered was above ten thousand, **nothing was pre-ticked**.
  That is the intended outcome: the estimator did not prove itself at the
  heights that need it, and saying so is the point of calibrating at all.
- **A Gaussian fit through three points is exact, and that is a warning,
  not a result.** The fit was written because a trapezoid over a peak two
  or three points wide moves with where the scans landed: measured at 14.6 s
  sampling, 5% with the phase for a peak 14 s wide at half height, and the
  fit 0.00% wherever it could be made. Then it was run on the real batch
  and the one internal standard with a response — 52,000 counts — came back
  a third smaller than the trapezoid with r² = 1.000. The peak was one
  point; the neighbours were 44 and 98, the same size as the baseline blips
  further along the trace, and a curve through three points with three
  parameters passes through them whatever they are. So `fit_gaussian` needs
  three points at or above `MIN_SHAPE_FRACTION` of the apex — flanks, not
  feet — and `GaussianModel.exact` says when there were only three, so the
  dialog writes "exact through 3 points" where it would otherwise write an
  r² that means nothing. With that, on the batch: 400 of 2,638 rows fitted,
  2,238 fell back with the reason on the row, 2,169 of them because the
  peak was fewer than three points wide; where the fit was made its area
  was a median 0.977 of the trapezoid and no component moved by more than
  20%. The choice of algorithm does not move this batch's numbers; the
  sampling does, and the comparison is what says so with figures rather
  than with an opinion. `compare.py` runs every algorithm on the batch,
  each run calibrated on its own results, and reports per component the
  median |Δ| against the reference and the %CV over the rows meant to
  agree — the only figure that can call an algorithm better rather than
  different, since the files and the noise are the same and only the
  arithmetic changed.
- **The batch is one point per peak, and now says so.** `sampling.py`
  reads the point count every integrated peak carries (`ChromPeak.points`,
  `PeakResult.points`: points inside the boundaries at or above
  `MIN_SHAPE_FRACTION` of the height) and the cycle from the channel's own
  time axis. On the 26-injection batch: one scan every 14.6 s, a median of
  **one** point on the peak, 129 of 139 components typically under the three
  a fit needs, and 2,206 of 2,638 peaks (84%) with one point above half
  height — so their width cannot be measured, only bounded, and every cycle
  time the report recommends for that batch is an upper bound. The Batch QC
  tab *Sampling* and the report section of the same name carry it. Two
  things in the count that look wrong and are not: the valley walk's
  boundary is the first point at or below five per cent of the apex and
  becomes the baseline's end, so it never counts; and summation's
  boundaries are the window's ends, so a four-scan window leaves two.
- **A response floor is declared, not derived.** `Component.min_response`
  (CSV `min_response`, aliases in `_ALIASES`) is what an internal standard
  has to give before a ratio to it means anything. `ControlChart.floor`
  decides `quantifiable` outright when set and the S/N 10 rule stands only
  without one; `evaluate_acceptance` fails a row whose standard gave less
  than its floor in that injection; `health.check_method` warns of a serving
  standard with none. The batch cannot supply the number — measured, its
  precision did not track its response — which is why it is a method field.
- **A mass "drift" of −351 ppm is not a drift.** `mass_drift.py` reads
  every internal standard's precursor from the survey scan in every
  injection (`precursor.measure`, once per injection) and fits the change
  across the run against the batch's own median. On the 26-injection batch
  the first run called one standard drifting by −351 ppm with a spread of
  476 ppm between injections: a survey signal too weak, the ±0.25 Da window
  catching a different neighbour each time. So `MassTrend.same_ion` gates
  on `precursor.CONSENSUS_SPREAD_PPM` (25) — the limit the consensus already
  uses to say samples disagree — and a trend that fails it is not judged,
  says why, and stays out of the index. With that, the batch says what it
  can: `SM(d18:1/12:0)`, the one standard strong enough in a 50–700 survey,
  held to −4.0 ppm across the run with a 16 ppm spread; nine others cannot
  be measured; no index, since fewer than three standards qualify. The
  measurement is not saved with the project (a few seconds to repeat; three
  on that batch) and the report carries it only while it stands.
- **A floor is proposed, never derived.** `qc.suggest_floors` offers each
  standard half its median area over the spiked injections with the failed
  injections left out, to three figures, with its basis on the row; the
  dialog (`ui.floor_dialog`) pre-ticks only rows with `MIN_INJECTIONS`
  behind them. On the real batch that is 5,240 for the one usable standard
  and 2–25 counts for the others — which is what their medians are, and the
  dialog shows the median so nobody accepts a floor of 3 by mistake.
- **The schedule is where the sampling finding lands.** `schedule.py`
  takes every component with a retention time over its window, counts how
  many are acquired at once at the busiest moment (a sweep over window
  starts and ends, ends first at a tie), and turns a target cycle into the
  dwell each gets there — or, under the dwell floor, into the shortest cycle
  the busiest moment allows. On the real method: 59 transitions scheduled,
  82 left out for having no time, at most 24 at once at 4.70 min, and a
  cycle of 3 s still leaves 120 ms of dwell — against the 14.6 s the batch
  was acquired at with all 144 transitions running unscheduled the whole
  run. The starting cycle comes from `sampling.py`'s median width and is
  labelled an upper bound when the batch's peaks were narrower than a
  cycle, since it is going to be typed into an instrument. The CSV's
  columns are named to map onto the vendor's table; it is not claimed to
  import into Analyst, whose detection window is one method-wide setting.
- **`check_method` now says which precursors the survey cannot see.** On
  the real method 72 of 141 lie outside the 50–700 survey; the accurate
  mass, the annotation and the mass drift are not measurable for them. An
  acquisition with no survey at all is a skipped check, not 141 findings.
- **A library match has two scores because impurities exist.** `library.py`
  pairs each library peak, strongest first, to the nearest free measured
  peak within a ppm tolerance and reports the cosine over everything both
  spectra hold and the cosine over the library's peaks only; a high
  reverse with a low score is the compound with company. Records with no
  precursor are scored when a precursor filter is on and say so with an
  empty Δ ppm — the filter did not apply, which is not the same as passing
  it. Run against MassBank's 139,006 records (5 s to read, 1.3 GB held):
  three rules came out of it. Two matched peaks minimum, because a
  spectrum that was mostly 184.07 scored 83 against a laxative on that one
  peak. Records without a precursor left out of a filtered search unless
  asked, because 24,000 of them dominated every search. And the precursor
  tolerance at least the written value's precision, since the channel says
  `647.5`. With those, the batch's product spectra named the C16 and C18
  sphingomyelins and the C16 and C24:1 ceramides the library holds, at
  reverse scores of 79–96, in milliseconds; an unfiltered search walks a
  bin index of the peaks and takes 2–7 s.
- **A reference batch is read, not opened.** `batches.read_project` builds
  a snapshot from the JSON alone, so a batch whose acquisitions moved to
  another disk still compares. Reusing it on the real batch reproduced the
  corrected-method gain of 2026-09-07 as a comparison rather than a script.
- **Unplaced deuterium is enumerated by count, not by position.**
  `explain.with_labels` offers every predicted ion carrying 0 to n labels
  (`PredictedIon.labels`, written `+kD`), never more than the piece has
  hydrogens; the spectrum then says how many a fragment kept. A drawing
  that places its labels — PubChem's cholic acid-d4 carries an `M  ISO`
  block, and `structure._isotopes` reads it — needs n = 0 and gets the same
  intact mass (411.3054 checked both ways). `explain_structure` takes a
  molfile of one's own through the same scoring as a database record;
  `explain_formula` takes a formula alone and offers the precursor and up
  to three neutral losses, each only where the formula has the atoms, and
  says that a formula has no bonds to cut. Loss ions are written as what is
  left and how it got there: `C24H38O4 -H2O`.
- **A `.wiff` without its `.wiff.scan` opens and looks whole.** The method,
  the metadata and every channel's TIC are in the `.wiff`; the scans are
  not, so the first spectrum throws, and so do BPC, XIC, the contour and
  the quantitation. Found on an infusion folder where one companion had
  been renamed by hand (`name.wiff_mix1.scan` beside `name_mix1.wiff`):
  the Explorer drew the chromatogram, and every attempt at a spectrum left
  the pane as it was, with the .NET exception on a console nobody has —
  PyQt6 printed it and carried on. `wiff.Sample.problem` reads one scan
  when the sample is opened and, on failure, `scan_problem` names the
  companion and any stray `.scan` in the folder; `SampleEntry.problem`
  carries it (never saved), the shell warns on open, the tree marks the
  sample, `_spectrum_unreadable` writes it where the spectrum would be,
  and an XIC or an integration reports it as the row's note. The probe is
  the only way to know: nothing in the `.wiff` says the companion is
  absent.
- **Pinned spectra are traces after the live one.** `explorer.pin_spectrum`
  copies the live trace (`key == "spec"`) with the pane's title as its
  label and appends it; `_with_pins` keeps the live one first, so every
  panel that reads `traces[0]` still reads the live spectrum and the base
  plot's Mirror — which flips odd-indexed traces — draws one pin head to
  tail with it. Normalise is per trace, which is what two samples need.
- **F1 walks the widget tree.** `ui.help_window.describe(widget, page)` sets
  a dynamic property; `help_page_for` walks up from the focused widget to
  the first one that has it; the shell installs an application-wide event
  filter so F1 pressed in a dialog — a separate window, out of reach of the
  menu's shortcut — resolves the same way. `tests/test_help_context.py`
  fails if a widget names a page the manual does not have.
- **`estimate_noise` returns None when it cannot measure**, and that is the
  ordinary case, not the exception. Over 846 real traces the median had three
  non-zero points in sixty-one and only 9% had a baseline that varied at all;
  a trace the instrument reports as exact zeros has a baseline below its
  reporting threshold and there is nothing there to measure. `ChromPeak.snr`
  and `PeakResult.snr` are `float | None` accordingly, and on that batch the
  S/N was measurable for 23% of the peaks found. `NOISE_FLOOR` still filters —
  it is an absolute intensity threshold wearing a signal-to-noise name, and it
  still rejects the smallest peaks — but what it rejects on is no longer
  reported as a ratio. An acceptance criterion on S/N that cannot be evaluated
  now flags "S/N not measured" rather than passing quietly.
  `estimate_noise` returns 0.000 for an XIC that is 85–97% zeros, which is
  what a scheduled MRM channel looks like, so `detect_peaks` falls back to
  `NOISE_FLOOR = 1.0` and the reported S/N becomes **the peak height divided
  by one** — measured on a real batch, an internal standard of 30 counts
  reported S/N 30, and one of 42,400 counts reported 42,400. Anything gated on
  S/N is therefore gated on absolute height with an arbitrary constant, which
  includes `IntegrationParams.min_snr`, `AcceptanceLimits.min_snr` and
  `qc.MIN_SNR`. The last of those was added specifically to stop control
  charts flagging standards that are barely present, and on that batch it
  changes nothing for exactly this reason. What that question actually needs
  is a per-method floor on the internal standard's absolute response; S/N
  cannot stand in for it.
- **The retention-time window is not what the detector may see.** It says
  where the apex may be. Handing `detect_peaks` exactly that window meant two
  things, both found by reprocessing a real batch: peaks were truncated at the
  boundary, and — worse — `detect_peaks` returns nothing below five points, so
  a ±0.5 min window on a method sampling one transition every 14.6 s holds
  four scans and came back empty **whatever was in it**. A peak of 44,875
  counts read as "no peak above noise". Whether a component was integrated at
  all depended on whether its window happened to catch four scans or five,
  which is set by the channel's start offset. `quantify.detection_range`
  gives the detector `MARGIN_SCANS` either side and the apex is required to
  land inside the declared window afterwards. On that batch it took the rows
  with a peak from 1,771 to 2,665 and the components with any peak at all from
  89 to 139 of 141. The margin is small on purpose: everything inside it
  competes on relative height with the real peak.
- **A contour averages the scans it cannot draw, it does not skip them.**
  A long run has more scans than a screen has rows. Sampling every k-th scan
  is faster and loses a one-scan peak entirely, so `build_contour` averages
  each group into its row — the mean rather than the sum, because the last
  group is usually short and a row that is dimmer only for that is a lie
  about the data. It also asks for spectra with `add_zeros=False`: a
  histogram of intensities cannot be changed by adding points of intensity
  zero, and restoring them triples the reading for the same grid.
- **`Contour.at` searches its bin edges to the right**, because that is where
  numpy's histogram puts a value sitting exactly on an edge. Searching left
  reads the cell next door and the readout under the cursor disagrees with
  the picture under it — caught by a test, not by eye.
- **Nothing is quantified off the contour.** Its m/z bins are wider than the
  instrument's steps and its rows may be several scans averaged, so
  `Extract this view` goes back to the reader for both the XIC and the
  spectrum. `Contour.slice_rt` and `slice_mz` exist for drawing, and say so.
- **The window does not always hold one peak.** Integration used to take
  `peaks[0]` — `detect_peaks` sorts by area, so the largest in the window,
  with nothing consulting the expected retention time. With a co-eluting
  isomer or isobar inside a ±0.6 min window, which is ordinary in lipidomics,
  the taller peak won whether or not the method pointed at it.
  `processing.choose_peak` now takes a rule from `IntegrationParams`:
  `PEAK_LARGEST` stays the default so no saved project moves, and
  `PEAK_NEAREST` decides by the method's retention time among the peaks that
  already cleared the height and S/N gates — those gates, not the rule, are
  what stops it picking noise sitting on the expected time. When proximity
  overrules size the result carries a note saying what it passed over,
  because a policy that silently takes the smaller peak cannot be reviewed.
- **A control chart needs a floor under its spread, not just a sigma.**
  Measured on the demo batch: eleven injections repeating to within half a
  per cent give a median absolute deviation of about 0.8%, and three of those
  is an internal standard 2.4% low — an ordinary injection. Two of eleven came
  out as four-sigma outliers, and would have on almost every real batch. So
  `qc.Injection.out` needs both conditions, past 3σ **and** at least
  `OUT_PERCENT` from the centre; drift needs both a magnitude and a Spearman
  correlation for the same reason. A flag that fires on every batch is not
  read on any of them.
- **A `QTextDocument` printed to a `QPdfWriter` needs the writer as its
  layout's paint device.** Without one it measures type at the screen's 96
  dots to the inch while the page is sized in the writer's 1200, so every
  point size comes out at a twelfth of itself: the first version of the
  report put eight sections into the top corner of a single otherwise blank
  page. `report.write_pdf` sets it, and two tests open the PDF — one counts
  pages, one looks for ink below the half-way line — because nothing about
  this is visible in the HTML.
- **Qt's HTML is a subset and it fails silently.** `padding` on a table cell
  and `width` on a table do nothing; the `cellpadding` and `width`
  *attributes* do, the first in pixels at 96 dpi. `<thead>` repeats on every
  printed page, `page-break-before` works, `tr.alt td` works, and anything
  cleverer than `tag.class` does not. Every rule in `report._STYLE` was
  rendered and looked at.
- **Nothing in Qt keeps a heading with what it introduces.** `write_pdf`
  lays the document out, asks which headings ended a page with their content
  on the next, and lays it out again with those pushed over — up to
  `MAX_REFLOWS` times, since moving one heading can strand another. The table
  of contents needs its own pass for the same reason: page numbers do not
  exist until the pages do. A hundred-page report is therefore laid out three
  times and takes about seventeen seconds, which is why the export puts up a
  wait cursor.
- **The Windows build needs Windows 10 1703+ and will not run under Wine**
  without the shim in `packaging/wine/`. Qt6Core imports eighteen `ucnv_*`
  symbols from `icuuc.dll`, which Windows ships in System32 and the PyQt6
  wheel does not carry. The shim must never go in the installer: on real
  Windows an application-local copy is found before the genuine one, and a
  test enforces this.

---

## What is missing against PeakView and MultiQuant

Checked against the code, not the README. Everything in the README's feature
tables exists. These do not:

Since done: LOD/LOQ (`validation.detection_limits`), carryover
(`validation.carryover`), the report (`report.py`, `File ▸ Export report…`),
batch QC (`qc.py`, the `Batch QC` tab, and a report section), the contour
view (`contour.py`), and integration algorithms with a comparison mode
(`processing.ALGORITHMS`, `compare.py`, `Compare algorithms…`).

| Missing | Which tool | Worth it? |
|---|---|---|
| **Spectral library search** | PeakView | Structure-based annotation covers lipids better; a library would cover everything else |
| **Mass recalibration** | PeakView | Only matters if the instrument drifts |
| **Audit trail, e-signatures** | MultiQuant | Only for a regulated laboratory |

---

## Open questions

- **An internal standard's retention time does not match its method**, in the
  batch this was developed against. Recorded in `NOTES.local.md`, which is not
  tracked: it is an observation about somebody's unpublished method rather
  than about this software.
- **The Windows installer has never been run on real Windows.** CI builds it
  and proves the bundle starts and reads a `.wiff` on a GitHub runner; nobody
  has installed the MSI on a machine.
- **Reading a `.wiff` has only ever been done on macOS.** Linux and Windows
  run the suite and start the application; the SCIEX path is checked only as
  far as "the assemblies load".
- **The portability plan had phases 1, 2 and 4** which were described in an
  earlier session and are not written down anywhere in the repository. Phase 0
  (CI) and phase 3 (packaging) are done.

---

## Continuous integration

Private repositories get 2,000 free minutes a month and this was at 98%,
nearly two thirds of it macOS, which bills at ten times a Linux minute
(Windows at two). So:

- a push to `main` runs **Linux only** — about 6 billable minutes
- macOS and Windows run on a pull request, on a tag, and on request
- the `.NET bootstrap` check runs **weekly**, on a tag, or on request; it
  asks whether SCIEX's assemblies still load, which does not depend on
  anything committed here
- markdown, `docs/` and the licence start nothing
- only the newest run for a ref finishes

A tag runs everything and publishes the three installers. Estimated: 40 pushes,
2 releases and 4 weeks come to about 20% of the allowance.

**Releasing is one command.** `git tag -a vX.Y.Z -m "…" && git push origin
vX.Y.Z`. Bump `openquant/__init__.py` in the same commit — `pyproject` and the
PyInstaller spec read it from there, and a tag whose version disagrees with the
package produces installers named after the wrong one.

---

## Where to look when something breaks

| Symptom | Look at |
|---|---|
| A `.wiff` will not open | `bootstrap.ensure()`; run `python -m openquant.bootstrap --install` |
| Two builds disagree | `--digest` on both, `diff` the output; the Windows build writes CRLF |
| An mzML has the wrong number of channels | `mzml.acquisition_cycles`; a file with no repeating cycle falls back to scan properties |
| A spectrum looks like it has a raised baseline | `restore_profile_zeros` did not fire; the file is probably centroided |
| Areas differ between formats | expected, see above; check it is 0.5% and not 50% |
| The application will not quit | a modal dialog. `offer_start` used to do this and no longer does |
| CI burns minutes | check nothing added macOS to a push trigger |

---

## Test suite

777 tests, one skipped. `QT_QPA_PLATFORM=offscreen python3 -m pytest -q`.

`tests/conftest.py` collects and flushes Qt's deferred deletions after every
test. Without it the suite segfaults on Linux in a different place on every
run: the modules share one `QApplication`, and Python's collector was freeing
C++ widgets it still held. macOS and Windows read the same freed memory
without noticing, which is luck rather than correctness.

Static analysis runs in CI: `ruff check openquant tests --select F,E9,B019`.
It found a `NameError` that had been sitting in the statistics table.
