---
title: What was measured
---
Every figure in this manual was produced by running something on real
data, not by reading code or repeating a vendor's claim. This page collects
them, with what they were measured on, so that a reader can decide how
far each one carries to their own instrument. Unless said otherwise the
data is five real acquisitions from a TripleTOF 5600 in negative mode — a
targeted MRM-HR method of 81 experiments across two periods, about 24,000
spectra each — and a batch of 26 injections of a scheduled sphingolipid
method of 141 components and 11 internal standards, sampled every 14.6 s.

## The reader

- **Builds agree.** The `--digest` fingerprint from source on macOS, from
  the CI disk image and from the Windows installer under CrossOver is
  byte-identical: 405 channel chromatograms, 25 spectra, 125 integrated
  peaks with areas to nine decimals. All 405 channel hashes differ from one
  another, so those were five different acquisitions rather than one read
  five times.
- **Formats agree, except in one place.** Exported to mzML and read back:
  spectra, channel chromatograms, the run's TIC (577 points) and integrated
  areas identical; extracted ion chromatograms differ by a median 0.58% of
  peak height, at most 12%, always lower here, because SCIEX counts part of
  a peak whose points fall just outside the window. End to end, one
  component quantified from both formats: same retention time, same width,
  area 0.54% apart. Two attempts at the vendor's edge rule failed; the
  second was better on 41 channels and worse on 38.
- **ProteoWizard agrees.** msconvert reads what this writes, and its own
  mzML written from that reads back here with identical spectra and
  chromatograms.
- **Summing stored points instead of taking the vendor's total** moved
  every integrated area by 2%. The vendor's figure is used.
- **Channels from scan properties alone** gave 69 where the acquisition had
  81; from the cycle of acquisition, 81.
- **A stripped profile's zeros**, drawn without restoring them, put a peak
  label at 184.8466 for a peak at 185.0077.

## Integration

- **A window narrower than five points returned nothing**, whatever was in
  it; a peak of 44,875 counts read as noise. Giving the detector three scans
  either side took the rows with a peak from 1,771 to 2,665 and the
  components with any peak from 89 to 139 of 141.
- **The peak rule changed nothing on that method**: of 896 windows with a
  retention time, none held two peaks (a ±0.5 min window at 14.6 s is four
  points); the 593 windows that did hold two belonged to components with
  no time, where *nearest* has nothing to be near.
- **Phase sensitivity at 14.6 s** on synthetic peaks: a trapezoid varies
  with the scans' phase by 16.8% at 11.3 s width at half height, 5.1% at
  14.1 s, 1.1% at 17 s; a Gaussian fit is exact wherever it can be made,
  and can be made for 34 of 60 phases at 14.1 s and all 60 at 17 s. With
  Poisson noise on a thousand counts, at 14.1 s: trapezoid 5.8%, fit 3.0%.
- **A fit to two points** is biased low by seven per cent; a fit through
  three with three parameters is exact whatever the points are, and on the
  real batch that put a curve through an apex of 52,000 counts and
  neighbours of 44 and 98 and reported an area a third smaller. Hence the
  rule that the fit needs three points at or above 1% of the apex.
- **The three algorithms on the real batch**: valley 2,638 rows found;
  summation 857; Gaussian 2,638 with 2,238 fallen back, 2,169 because the
  peak was fewer than three points wide. Where fitted, the fit's area was
  a median 0.977 of the trapezoid's; no component moved by more than 20%.
  The internal standards' %CV was the same under all three. The algorithm
  does not move that batch's numbers; the sampling does.

## Noise

- Over 846 real traces, the median had three non-zero points in sixty-one
  and 9% had a baseline that varied at all. The noise could be measured for
  23% of the peaks found.
- With the one-count floor standing in for an unmeasurable noise, a
  standard of 30 counts reported S/N 30 and one of 42,400 reported 42,400.
- Noise measured inside the retention-time window read 16,944 where the
  trace's noise was 505: S/N 19 automatic against 531 by hand.

## Quality control

- A median absolute deviation of 0.8% made a standard 2.4% low a four-sigma
  outlier; hence the per-cent floors.
- An injection where every standard came back at a fifth of normal sat at
  2.6σ in a batch that varied by a third; hence the 50% rule.
- Of eleven internal standards, eight had a median response between 4 and
  52 counts and produced almost every flag; hence the S/N 10 gate.
- The standards separately scattered between 32% and 228%; the injection
  response index put the injections within ±18% with three exceptions.
- The batch supports no response floor: successive-injection scatter did
  not track median response.

## Retention-time estimation

Checked against the 54 components that already declared a time, the
estimate landed within one sampling interval for 45% of components under
100 counts, 54% between 100 and 1,000, 54% between 1,000 and 10,000, and
88% above 10,000. Nothing offered was above 10,000, so nothing was
pre-ticked.

## The report

The first version printed at a twelfth of its size. A hundred-page report
is laid out three times and takes about seventeen seconds.

## Where the rest is written down

The source repository's `CLAUDE.md` records the same facts for whoever
changes the program, with the commit each one came from; the tests assert
most of them.
