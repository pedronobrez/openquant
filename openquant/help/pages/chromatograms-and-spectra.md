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
| right-click | *Extract XIC from selection*, *Find formula for this peak*, *Add marker here*, *Clear markers*, *Clear theoretical overlay*, *Reset label floor* |
| drag / double-click | zoom / fit |

**m/z labels** writes the mass beside the peaks worth naming, and which
those are is decided again every time the view moves. The mass axis on
screen is cut into eight equal windows, each may claim three labels
starting with its tallest, and the tallest peak of every window asks for
room before any window asks for a second — so a crowded stretch cannot
spend the whole allowance on itself. A label that would print on top of one
already placed is still dropped rather than overlapped, which means the
number drawn is what fits and not what was offered.

Picking by height alone is what this replaced, and it read badly on a
survey scan: on the TOF MS survey of a real acquisition the twelve tallest
peaks all fell inside a stretch 118 Da wide near the bottom of a 100–2000
axis, eleven of the twelve collided with one another, and the whole
spectrum was drawn with a single label on it. By region, six are drawn and
they run the length of the axis. Because the windows follow the view,
zooming in names more: on the same scan, seven labels over m/z 150–350
against four before. *Compare spectra…* prints with the same rule — twenty
labels on that pair of spectra against twelve.

**The label floor**, and the triangle that sets it. A peak has to reach a
share of the tallest peak *in view* before it is worth a label; it starts
at 2%, which is what leaves a survey scan readable. When the peak you are
after is a small one — a standard at a per cent of the base peak — that
floor is what is hiding its mass. The small filled triangle beside the Y
axis, in the margin left of it, is where the floor sits: drag it down and
more peaks are named, drag it up and fewer are. A dotted line across the
plot shows the level while the mouse is down. Double-click the triangle, or
right-click ▸ *Reset label floor*, to put it back at 2%. **Label floor (%)**
in the View toolbar is the same number typed rather than dragged, and
either moves the other; it is remembered between sessions, and the picture
*Compare spectra…* prints is labelled at whatever the pane was showing.

It is a share of the tallest peak in view and not an intensity, so it
survives a zoom, a *Normalise* and the next spectrum: zoomed into a quiet
stretch the floor is measured against what is on screen, not against a base
peak that is off it.

What it is worth, measured. On the product-ion scan of a deuterated bile
acid infused for the purpose, averaged over the whole run, the precursor
itself — m/z 430.3197, at 1.49% of the base peak — is **not** named at 2%
and **is** named at 0.5%: seven labels against eight over the full 50–450
axis, and two against three zoomed to 350–440. On the TOF MS survey of a
real acquisition the full 100–1960 axis is drawn with the same six labels
at 2%, at 0.5% and at 0.1% — there the crowding decides and not the floor —
while across the axis in eighteen windows of 100 Da it goes 57 labels at 2%,
57 at 0.5% and 70 at 0.1%, and in nineteen windows of 20 Da over m/z
100–500, 67, 95 and 95. The gain is in the quiet stretches, which is where
a small peak is worth naming; in a crowded one the three labels a window may
claim are what runs out first, and lowering the floor changes nothing.

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

### Taking the comparison away

**File ▸ Export comparison (PNG/SVG)…** writes what the pane is showing as
one picture — enabled as soon as something is pinned. PNG comes out at
twice the drawing's own size, which is what makes the type and the sticks
sharp when it is printed or dropped into a slide; SVG is the same drawing
as vectors, for a figure that will be resized. Either way the picture is
drawn again from the data rather than grabbed off the screen, so it is the
same whatever the size of the window, and it is always drawn for paper: a
white ground and dark axes, whatever theme the application is in. A trace
colour that was lightened to carry on a dark window is darkened until it
reads on white, keeping its hue, so a trace known by its colour on screen
is the same trace on the page.

The same picture goes into the [[report]], under *Compared spectra*, with
a table of the traces and a table of the masses they have in common. What
the report prints is what the pane shows: pinning a spectrum starts the
comparison, changing the live spectrum or either switch refreshes it, and
**Unpin spectra** drops it. There is nothing to keep in step by hand and
nothing that can go stale — if the pane holds two spectra worth reporting,
so does the report; if it does not, the report leaves the section out. It
is not saved with the project, for the same reason the pins are not.

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
