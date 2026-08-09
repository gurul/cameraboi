"""One-time lens intrinsics calibration from ChArUco board captures.

Feed it a directory of stills of the printed board (~15 shots, varied position
and tilt, board filling a good fraction of the frame). Output is intrinsics.json
consumed by measure.py. Intrinsics are a property of the camera+mode, not the
stand height — recalibrate only if the camera or capture resolution changes.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import cv2
import numpy as np

from .boards import charuco_board

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MIN_VIEWS = 6
MIN_CORNERS_PER_VIEW = 8
RMS_WARN_PX = 1.0


def calibrate_dir(image_dir: Path, out_path: Path) -> dict:
    image_dir = Path(image_dir)
    paths = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not paths:
        raise SystemExit(f"calibrate: no images found in {image_dir}")

    board = charuco_board()
    detector = cv2.aruco.CharucoDetector(board)

    obj_all, img_all, used = [], [], []
    image_size = None
    for p in paths:
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"calibrate: skipping unreadable {p.name}")
            continue
        if image_size is None:
            image_size = (img.shape[1], img.shape[0])
        elif (img.shape[1], img.shape[0]) != image_size:
            raise SystemExit(
                f"calibrate: {p.name} is {img.shape[1]}x{img.shape[0]}, expected "
                f"{image_size[0]}x{image_size[1]} — all views must share one capture mode"
            )
        corners, ids, _, _ = detector.detectBoard(img)
        if corners is None or ids is None or len(corners) < MIN_CORNERS_PER_VIEW:
            print(f"calibrate: {p.name}: board not found / too few corners — skipped")
            continue
        obj_pts, img_pts = board.matchImagePoints(corners, ids)
        if obj_pts is None or len(obj_pts) < MIN_CORNERS_PER_VIEW:
            print(f"calibrate: {p.name}: could not match corners — skipped")
            continue
        obj_all.append(obj_pts)
        img_all.append(img_pts)
        used.append(p.name)
        print(f"calibrate: {p.name}: {len(obj_pts)} corners")

    if len(used) < MIN_VIEWS:
        raise SystemExit(
            f"calibrate: only {len(used)} usable view(s); need >= {MIN_VIEWS}. "
            "Capture more shots with the board at varied positions and tilts."
        )

    rms, camera_matrix, dist_coeffs, _, _ = cv2.calibrateCamera(
        obj_all, img_all, image_size, None, None
    )

    result = {
        "kind": "cameraboi-intrinsics",
        "calibrated_on": date.today().isoformat(),
        "image_size": list(image_size),
        "camera_matrix": np.asarray(camera_matrix).tolist(),
        "dist_coeffs": np.asarray(dist_coeffs).ravel().tolist(),
        "rms_reprojection_px": float(rms),
        "views_used": used,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2))

    print(f"calibrate: {len(used)} views, RMS reprojection {rms:.3f}px")
    if rms > RMS_WARN_PX:
        print(
            f"calibrate: WARNING — RMS {rms:.3f}px is high (want < {RMS_WARN_PX}). "
            "Check the board is flat and shots are sharp, then recalibrate."
        )
    print(str(out_path))
    return result


def load_intrinsics(path: Path) -> tuple[np.ndarray, np.ndarray, tuple[int, int]]:
    data = json.loads(Path(path).read_text())
    if data.get("kind") != "cameraboi-intrinsics":
        raise SystemExit(f"{path} is not a cameraboi intrinsics file")
    return (
        np.asarray(data["camera_matrix"], dtype=np.float64),
        np.asarray(data["dist_coeffs"], dtype=np.float64),
        tuple(data["image_size"]),
    )
