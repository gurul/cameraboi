"""Exact object counting: threshold -> morphology -> distance-transform
watershed to split touching objects -> count. Deterministic, with an annotated
image so the count can be eyeballed against reality.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

DEFAULT_MIN_AREA_PX = 80
DEFAULT_PEAK_FRAC = 0.6


def _foreground_mask(gray: np.ndarray, fg: str, thresh: int | None) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    if thresh is not None:
        _, dark = cv2.threshold(blur, thresh, 255, cv2.THRESH_BINARY_INV)
        _, light = cv2.threshold(blur, thresh, 255, cv2.THRESH_BINARY)
    else:
        _, dark = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        light = cv2.bitwise_not(dark)
    if fg == "dark":
        return dark
    if fg == "light":
        return light
    # auto: objects are the minority phase
    return dark if cv2.countNonZero(dark) <= cv2.countNonZero(light) else light


def count_image(
    image_path: Path,
    fg: str = "auto",
    min_area_px: int = DEFAULT_MIN_AREA_PX,
    peak_frac: float = DEFAULT_PEAK_FRAC,
    thresh: int | None = None,
) -> dict:
    image_path = Path(image_path)
    img = cv2.imread(str(image_path))
    if img is None:
        raise SystemExit(f"count: cannot read image {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    binary = _foreground_mask(gray, fg, thresh)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)

    # Watershed seeded from distance-transform peaks splits touching objects.
    # The peak threshold is per connected component, not global — a global
    # dist.max() cutoff both merges overlapping pairs (their neck clears it)
    # and starves small objects of seeds when sizes are mixed.
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    n_comp, comp_labels = cv2.connectedComponents(binary)
    comp_max = np.zeros(n_comp, dist.dtype)
    np.maximum.at(comp_max, comp_labels.ravel(), dist.ravel())
    sure_fg = ((dist > peak_frac * comp_max[comp_labels]) & (binary > 0)).astype(
        np.uint8
    ) * 255
    sure_bg = cv2.dilate(binary, kernel, iterations=3)
    unknown = cv2.subtract(sure_bg, sure_fg)

    n_seeds, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0
    markers = cv2.watershed(img, markers)

    annotated = img.copy()
    objects = []
    for label in range(2, n_seeds + 1):
        seg = (markers == label).astype(np.uint8)
        area = int(seg.sum())
        if area < min_area_px:
            continue
        m = cv2.moments(seg, binaryImage=True)
        if m["m00"] == 0:
            continue
        cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
        objects.append({
            "id": len(objects) + 1,
            "center_px": [round(cx, 1), round(cy, 1)],
            "area_px": area,
        })
        contours, _ = cv2.findContours(seg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(annotated, contours, -1, (0, 200, 0), 2)
        cv2.putText(annotated, str(len(objects)), (int(cx) - 8, int(cy) + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 80, 255), 2, cv2.LINE_AA)

    annotated_path = image_path.with_name(image_path.stem + "-count.png")
    cv2.putText(annotated, f"count: {len(objects)}", (12, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 80, 255), 3, cv2.LINE_AA)
    cv2.imwrite(str(annotated_path), annotated)

    areas = [o["area_px"] for o in objects]
    return {
        "image": str(image_path),
        "annotated": str(annotated_path),
        "count": len(objects),
        "median_area_px": int(np.median(areas)) if areas else 0,
        "objects": objects,
    }
