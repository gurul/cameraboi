"""Millimeter measurement from a single shot of objects on the printed mat.

Per-shot pipeline: undistort (if intrinsics exist) -> detect the mat's ArUco
markers with subpixel refinement -> fit a homography image->mat-mm -> rectify
-> segment objects in the work area -> report min-area-rect dimensions in mm.

Scale is re-derived from the mat every shot, so camera height and tilt are free
to change between shots. Requires >= MIN_MARKERS of the 4 markers visible;
refuses loudly otherwise rather than guessing.

Accuracy contract: flat objects on the mat. Tall objects measured at their top
surface read large by ~(height / camera distance); pass --object-height to
correct when the thickness is known.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from .boards import aruco_dictionary, mat_marker_positions
from .calibrate import load_intrinsics

MIN_MARKERS = 3
DEFAULT_PX_PER_MM = 10.0
DEFAULT_MIN_AREA_MM2 = 25.0
WORK_AREA_PAD_MM = 6.0  # exclusion band around markers and the sheet border


def _detector(dict_name: str) -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(aruco_dictionary(dict_name), params)


def load_mat(mat_json: Path) -> dict:
    data = json.loads(Path(mat_json).read_text())
    if data.get("kind") != "cameraboi-measure-mat":
        raise SystemExit(f"{mat_json} is not a cameraboi measuring-mat file")
    return data


def measure_image(
    image_path: Path,
    mat_json: Path,
    intrinsics_path: Path | None = None,
    px_per_mm: float = DEFAULT_PX_PER_MM,
    min_area_mm2: float = DEFAULT_MIN_AREA_MM2,
    object_height_mm: float = 0.0,
    camera_height_mm: float = 0.0,
    thresh: int | None = None,
) -> dict:
    image_path = Path(image_path)
    img = cv2.imread(str(image_path))
    if img is None:
        raise SystemExit(f"measure: cannot read image {image_path}")

    mat = load_mat(mat_json)
    scale_correction = float(mat.get("scale_correction", 1.0))

    undistorted = False
    if intrinsics_path and Path(intrinsics_path).exists():
        camera_matrix, dist_coeffs, size = load_intrinsics(intrinsics_path)
        if (img.shape[1], img.shape[0]) != size:
            print(
                f"measure: note — image is {img.shape[1]}x{img.shape[0]} but intrinsics "
                f"were calibrated at {size[0]}x{size[1]}; skipping undistortion"
            )
        else:
            img = cv2.undistort(img, camera_matrix, dist_coeffs)
            undistorted = True
    else:
        print("measure: note — no intrinsics file; measuring without lens "
              "undistortion (edges of frame less accurate)")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _detector(mat["dictionary"]).detectMarkers(gray)
    known = {int(k): np.asarray(v, np.float64) for k, v in mat["markers_mm"].items()}
    found = {} if ids is None else {
        int(i): c.reshape(4, 2)
        for i, c in zip(ids.ravel(), corners) if int(i) in known
    }
    if len(found) < MIN_MARKERS:
        raise SystemExit(
            f"measure: only {len(found)} of {len(known)} mat markers detected "
            f"(need >= {MIN_MARKERS}). Is the mat fully in frame and unobstructed?"
        )

    img_pts = np.concatenate([found[i] for i in sorted(found)]).astype(np.float64)
    mm_pts = np.concatenate([known[i] for i in sorted(found)]).astype(np.float64)
    dst_pts = mm_pts * px_per_mm
    H, _ = cv2.findHomography(img_pts, dst_pts, cv2.RANSAC, 3.0)
    if H is None:
        raise SystemExit("measure: homography fit failed")

    # Residual of the fit, reported honestly in mm.
    proj = cv2.perspectiveTransform(img_pts.reshape(-1, 1, 2), H).reshape(-1, 2)
    residual_mm = float(np.sqrt(np.mean(np.sum((proj - dst_pts) ** 2, axis=1)))) / px_per_mm

    sheet_w, sheet_h = mat["sheet_mm"]
    rect_size = (int(round(sheet_w * px_per_mm)), int(round(sheet_h * px_per_mm)))
    rectified = cv2.warpPerspective(gray, H, rect_size)

    # Work-area mask: sheet minus border band minus marker tiles (padded).
    mask = np.zeros(rectified.shape, np.uint8)
    pad = WORK_AREA_PAD_MM
    x0, y0 = int(pad * px_per_mm), int(pad * px_per_mm)
    x1, y1 = int((sheet_w - pad) * px_per_mm), int((sheet_h - pad) * px_per_mm)
    mask[y0:y1, x0:x1] = 255
    marker = mat["marker_size_mm"]
    margin = mat["margin_mm"]
    for pts in mat_marker_positions((sheet_w, sheet_h), marker, margin).values():
        mx0 = int((pts[0][0] - pad) * px_per_mm)
        my0 = int((pts[0][1] - pad) * px_per_mm)
        mx1 = int((pts[2][0] + pad) * px_per_mm)
        my1 = int((pts[2][1] + pad) * px_per_mm)
        mask[max(my0, 0):my1, max(mx0, 0):mx1] = 0

    # Objects are darker than the white mat. Otsu unless a manual threshold given.
    blur = cv2.GaussianBlur(rectified, (5, 5), 0)
    if thresh is None:
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, binary = cv2.threshold(blur, thresh, 255, cv2.THRESH_BINARY_INV)
    binary = cv2.bitwise_and(binary, mask)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # Perspective correction for known object thickness: top surface is closer
    # to the lens by object_height, scaling up by ~camera/(camera-object).
    height_scale = 1.0
    if object_height_mm > 0 and camera_height_mm > 0:
        height_scale = (camera_height_mm - object_height_mm) / camera_height_mm

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    annotated = cv2.cvtColor(rectified, cv2.COLOR_GRAY2BGR)
    to_mm = scale_correction * height_scale / px_per_mm
    objects = []
    for c in sorted(contours, key=cv2.contourArea, reverse=True):
        area_mm2 = cv2.contourArea(c) * to_mm * to_mm
        if area_mm2 < min_area_mm2:
            continue
        (cx, cy), (w, h), angle = cv2.minAreaRect(c)
        w_mm, h_mm = sorted((w * to_mm, h * to_mm), reverse=True)
        objects.append({
            "id": len(objects) + 1,
            "width_mm": round(w_mm, 2),
            "height_mm": round(h_mm, 2),
            "area_mm2": round(area_mm2, 1),
            "perimeter_mm": round(cv2.arcLength(c, True) * to_mm, 1),
            "center_mm": [round(cx / px_per_mm, 1), round(cy / px_per_mm, 1)],
            "angle_deg": round(angle, 1),
        })
        box = cv2.boxPoints(((cx, cy), (w, h), angle)).astype(np.int32)
        cv2.drawContours(annotated, [box], 0, (0, 180, 0), 2)
        cv2.putText(annotated, f"#{len(objects)} {w_mm:.1f} x {h_mm:.1f} mm",
                    (int(cx - w / 2), max(int(cy - h / 2) - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 120, 255), 2, cv2.LINE_AA)

    annotated_path = image_path.with_name(image_path.stem + "-measure.png")
    cv2.imwrite(str(annotated_path), annotated)

    return {
        "image": str(image_path),
        "annotated": str(annotated_path),
        "markers_detected": sorted(found),
        "undistorted": undistorted,
        "fit_residual_mm": round(residual_mm, 3),
        "scale_correction": scale_correction,
        "object_count": len(objects),
        "objects": objects,
    }
