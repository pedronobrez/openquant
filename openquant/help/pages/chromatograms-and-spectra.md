---
title: Chromatograms and spectra
---
## The chromatogram pane

Every checked channel is a trace. The *Sample TIC* node draws the run's
total ion chromatogram, which is summed **by cycle, not by time**: the
experiments of one cycle are measured one after another, so the union of
their times is one point per spectrum — 23,722 where the instrument reports
577 — and the program reports the instrument's 577. A channel drawn as
**TIC** is the sum of each of its scans; as **BPC**, the tallest peak of
each scan.

| Gesture | Effect |
|---|---|
| single click | spectrum of the scan under the cursor |
| drag | rubber-band zoom |
| double-click | fit the trace |
| Shift + drag, or drag with *Select range* on | select a range: the spectrum pane shows the average over it, live, while the selection is dragged or resized, and the status bar reports the range's integration — area, height, apex and S/N |
| ← → | previous and next scan |
| right-click | the plot menu: export as image, axes, grid |

**Stack** gives each trace a pane of its own, the time axes locked so a
zoom in one is a zoom in all. **Overview** adds a navigator along the
bottom: the full range, with the current zoom drawn as a window that can be
dragged. **Mirror** draws every other trace downwards, which is how a
sample is compared against its blank. **Cascade** offsets overlaid traces
in x (minutes) and y (per cent of height) so that eight nearly identical
runs can be told apart.

**RT labels** puts the apex time on every peak. With a marker present,
**Relative labels** re-labels peaks by their distance to it.

## The spectrum pane

The spectrum of one scan of the active channel, or the average over a
selected range. Product-ion channels show what survived fragmentation of
their precursor; the survey channel (TOF MS) shows everything eluting at
that moment. Where there is nothing eluting at all — an infusion sprayed
for a minute, every scan the same — the whole run averages into one
spectrum instead, and that is what the pane opens on: see
[[direct-infusion]].

| Gesture | Effect |
|---|---|
| Shift + drag | select an m/z range |
| right-click | *Extract XIC from selection*, *Find formula for this peak*, *Add marker here*, *Clear markers*, *Clear theoretical overlay* |
| drag / double-click | zoom / fit |

**Markers.** Drop a marker on a peak and the other peaks are labelled with
their distance to it in daltons, which is how neutral losses (18.011 for
water, 44.026 for CO₂, 87.032 for a serine) and isotope spacings are read
off a spectrum. Several markers can be placed; *Clear markers* removes them.

**Spectrum peaks** tab. The peaks of the spectrum on screen — m/z,
intensity and per cent of the base peak — picked by local maximum,
centroided in profile data, and merged when closer than 0.03 Da so a
profile's rippled top does not appear as five masses. Double-click a row to
extract that mass as an XIC.

## Comparing spectra across samples

The chromatogram pane overlays as many traces as are checked; the spectrum
pane shows one spectrum at a time, because a spectrum belongs to one scan
of one channel of one sample. **Pin spectrum** (the Processing toolbar, or
the spectrum's right-click menu) keeps the spectrum on screen so the next
one draws over it: switch to another sample in the tree, another scan, or
another channel, and the new spectrum is drawn in blue over the pinned
ones, each in its own colour and named in the legend by the sample,
channel and scan it came from. Several can be pinned; **Unpin spectra**
clears them.

Two switches make the comparison readable. **Normalise** puts every
spectrum on its own base peak, which is what two samples at different
concentrations need. **Mirror** draws every other spectrum downwards, so
one pinned spectrum and the live one become a head-to-tail plot — the way
a library match is usually shown, and the quickest way to see a peak
present in one and absent from the other. With more than one pinned,
colours do the separating and Mirror alternates.

Everything else reads the live spectrum: the peak table, the
[[formula-finder]], the [[lipid-maps]] Explain, the [[spectral-library]].
The pinned copies are pictures, and are lost when the files are closed.

## Profile spectra and their zeros

A profile spectrum from a `.wiff` and the same spectrum from mzML do not
have the same number of points. SCIEX strips the zero-intensity points when
storing and puts them back when drawing; an mzML carries what was stored.
Drawn as they come, a line runs straight from the last point of one peak to
the first point of the next and the empty stretch between them looks like a
sloping baseline — signal where there is none. Worse, a peak label taken
across the gap was wrong: one read 184.8466 for a peak at 185.0077.

So the program restores the zeros for any format that lacks them, measuring
the sampling interval from the file itself: the smallest quarter of the
gaps between points are the ones inside peaks, and interpolating those
across the mass axis gives the interval at any mass — no instrument physics
is assumed, which covers a time-of-flight and an Orbitrap alike. Every
point added is a zero, at a mass where the instrument reported nothing;
no intensity changes. A spectrum that already carries its zeros has no gap
wide enough to trigger it and comes back untouched.

## Centroid

*Centroid* on the Processing toolbar converts a profile spectrum into
sticks: one per peak, at the intensity-weighted centre of mass, as tall as
the profile apex. A centroided spectrum has fewer points than its profile,
which is why the theoretical isotope overlay and the formula finder work on
whichever is shown.

## Smoothing and baseline

**Smooth (σ, scans)** applies a Gaussian filter of that width to every
chromatogram; 0 turns it off. A Gaussian is the right filter for
chromatography because, unlike a moving average, it preserves peak position
and area. **Baseline (min)** estimates a lower envelope over a window of that
width — block minima, interpolated and smoothed — and subtracts it; the
window must be wider than the broadest peak worth keeping, or the peak is
taken as baseline. Both apply to the drawing, the integration and the
export, so a number in the Results tab is the number on screen.

## Background subtraction

Select a stretch of chromatogram that holds no peak and use **Set
background**: the average spectrum over that range is subtracted from every
spectrum shown until **Clear background**. The range in use is named beside
the scan controls.
