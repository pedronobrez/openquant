---
title: Contour view
---
**View ▸ Contour** at the top of the [[explorer]] draws the active channel as
a surface: retention time across, m/z up, intensity as colour. A
chromatogram sums the mass axis away and a spectrum sums the time axis
away; the contour is the same data with neither summed, so an interference
sitting beside a target, or a ridge running down the whole run at one mass,
is visible rather than inferred.

## What is drawn

Each scan of the channel is a row and each m/z bin a column. The mass axis
is divided into about 1,400 bins — roughly one per screen pixel across a
wide range; finer than that the picture is the same, only slower. A long
run has more scans than a screen has rows, and the scans over the limit of
about 900 rows are **averaged into their row, not skipped**: sampling every
k-th scan is faster and loses a one-scan peak entirely, which is the
opposite of what a picture of the data is for. The average rather than the
sum, because the last group is usually short and a row that is dimmer only
for that would be a lie about the data.

Spectra are taken without their restored zeros: a histogram of intensities
cannot be changed by adding points of intensity zero, and restoring them
was measured to triple the time for the same grid.

## Controls

| Control | Effect |
|---|---|
| **Intensity** | how intensities become colour: *sqrt* (default), *log* or *linear*. A linear ramp over four decades shows the base peak and nothing else; square root lifts the minor ions into view without the flattening that makes a log plot look uniformly grey |
| **Colours** | the palette: inferno, viridis, magma, turbo, CET-L9 |
| **Extract this view** | the chromatogram and the spectrum of the rectangle on screen — both taken from the reader, not from the grid |
| **Rebuild** | rebuild the grid over the range currently on screen, at full resolution for that range |
| click | the spectrum of the scan under the cursor, in the spectrum pane |
| readout | the retention time, m/z and intensity under the cursor |

The top of the colour scale is the 99.7th percentile of the intensities,
not the maximum: a single saturated or spiking scan would otherwise set the
scale for everything else and leave the rest of the surface black.

## Nothing is quantified from the contour

Its m/z bins are wider than the instrument's steps and its rows may be
several scans averaged, so it is a picture, deliberately. *Extract this
view* goes back to the reader for both the XIC and the spectrum, and those
are what the [[manual-xic]] and the Results tab work with.

The readout under the cursor searches the bin edges to the right, because
that is where a value sitting exactly on an edge is put by the histogram;
searching left reads the cell next door and the readout disagrees with the
picture — caught by a test, not by eye.
