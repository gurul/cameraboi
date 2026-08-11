---
title: CV Tools
icon: 📐
order: 6
---

# CV Tools — measure, count, scan

`scripts/cameraboi-cv` is the deterministic computer-vision companion to the capture CLI.
It exists for the two things vision models cannot do by looking at an image: **calibrated
pixel math** (millimeter measurement) and **exactness at scale** (counting hundreds of
objects, batch-cleaning scanned pages). Capture stays in `scripts/cameraboi`; these
commands consume the image files it produces.

```bash
scripts/cameraboi-cv <command> [options]
```

First run creates a private venv in `cv/.venv` and installs the pinned requirements —
nothing global. Same output contract as the capture CLI: JSON results on stdout, the
**last stdout line(s) are artifact paths**, diagnostics on stderr.

| Command | Purpose |
|---|---|
| `mat` | Generate the printable ArUco measuring mat (PNG + geometry JSON) |
| `board` | Generate the printable ChArUco lens-calibration board |
| `calibrate` | Fit lens intrinsics from ~15 stills of the board (one-time) |
| `measure` | Millimeter dimensions of objects placed on the mat |
| `count` | Exact object count with watershed splitting of touching objects |
| `scan` | Batch page detection, perspective correction, and enhancement |

## Measurement — one-time setup

1. **Print the mat**: `cameraboi-cv mat` → print `measure-mat.png` at **100% scale**
   (no "fit to page"), tape it flat on the desk. Verify the printed 100 mm reference
   line with a ruler; if it measures off, set `scale_correction` in `measure-mat.json`
   to `measured / 100`.
2. **Calibrate the lens** (optional but worth ~1–3 mm at the frame edges): print
   `cameraboi-cv board`, tape it to something rigid, capture ~15 snaps at varied
   positions and tilts, then `cameraboi-cv calibrate <dir-of-shots>`. Intrinsics are a
   property of the camera and capture mode — stand height changes never invalidate them.

## Measurement — every shot

```bash
scripts/cameraboi snap --full --no-open -o /tmp/part.jpg
scripts/cameraboi-cv measure /tmp/part.jpg
```

Scale and tilt are re-derived from the mat's four ArUco markers **per shot**, so moving
or re-heighting the camera between shots costs nothing. At least 3 of the 4 markers must
be visible — the command refuses loudly rather than guessing. Output is JSON (width,
height, area, perimeter, center, angle per object, plus the homography fit residual in
mm as an honesty check) and an annotated image with the dimensions drawn on.

Segmentation is **color-aware by default** (`--seg auto`): cast shadows on the white
mat (unsaturated but still bright) are rejected, and saturated colored pixels are kept
even where a gray threshold would drop them — e.g. a brightly-lit chamfered edge.
`--seg gray` restores the plain darker-than-paper threshold (use it for neutral-gray
objects, which the shadow test cannot distinguish from shadow); `--seg color` keeps
only saturated pixels and is the precision choice for a colored object, since the dark
contact shadow hugging an object's base is ambiguous in gray but invisible in color.
Color cues assume neutral light on white paper: under tinted light (direct sun, warm
lamps) the paper itself reads saturated, so `auto` detects that and falls back to the
gray path with a warning, and `--seg color` should not be used. Diffuse neutral light
is what gets the last few tenths of a millimeter.

After segmentation, each min-area-rect side is refined to the outermost
sufficiently-strong intensity gradient along its normal with subpixel parabolic
interpolation (`--no-refine` disables). This sheds soft shadow penumbras (their
gradients never qualify) and beats the contour's pixel quantization; shot-to-shot
repeatability is ±0.03–0.04 mm.

Accuracy: **±0.2–0.5 mm for flat objects** with the mat verified and intrinsics
calibrated. Tall objects read large by roughly `height / camera distance`; pass
`--object-height` with the part thickness to correct. The camera height is estimated
automatically from the markers when intrinsics exist (reported as
`camera_height_mm` / `camera_height_source` in the JSON) — without intrinsics, pass
`--camera-height` too, and beware: an error in camera height converts directly into
a proportional dimension error (`14 mm` of object height at `450 mm` misjudged by
`50 mm` shifts a 90 mm reading by ~0.35 mm). Back-solving the height from a
known-size reference object is legitimate calibration, but verify both axes imply
the same height — if they disagree, the silhouette is lighting-biased, not the
height wrong. A worked validation: a 15 mm-tall 3D-printed shell measured across
two very different lighting conditions repeated to ±0.04 mm and landed within
±0.35 mm of CAD with an independently-derived camera height; the remaining
systematic error is exactly what ChArUco lens calibration removes.

## Counting

```bash
scripts/cameraboi-cv count /tmp/screws.jpg
```

Threshold (Otsu, polarity auto-detected as the minority phase) → morphology →
distance-transform watershed with **per-component** peak thresholds, so touching
objects split and mixed sizes don't starve small objects of seeds. Options:
`--fg dark|light`, `--min-area`, `--min-sep` (raise to split harder), `--thresh`.
Output: JSON count + numbered annotated image — eyeball the annotation to confirm the
segmentation matched reality.

## Scanning

```bash
scripts/cameraboi-cv scan ~/Pictures/cameraboi/scan/ -o /tmp/clean --mode bw
```

Per image: largest convex quad ≥15% of frame → perspective-correct → enhance
(`color` CLAHE, `gray` CLAHE, `bw` adaptive threshold — shadows survive). No quad
found → enhance-only passthrough, flagged in the JSON. Directories are processed in
sorted order and prior `-scan.png` outputs are skipped, so re-running is idempotent.
Note: rectified size comes from projected edge lengths, so a strongly tilted shot
recovers approximate (not exact) page aspect — irrelevant for OCR, worth knowing.

## Testing

```bash
cd cv && .venv/bin/python -m pytest tests/
```

The suite renders synthetic camera views of the real generated mat with objects of
exactly known size, and asserts the pipeline recovers dimensions within 0.4 mm,
splits touching objects exactly, and detects/rectifies pages. No camera needed.
