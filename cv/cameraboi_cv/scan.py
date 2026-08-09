"""Batch document scan preprocessing: find the page quad, perspective-correct,
enhance. Deterministic cleanup so downstream OCR / vision reads clean pages
instead of skewed, shadowed photos.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MIN_QUAD_AREA_FRAC = 0.15
DETECT_WIDTH = 900


def _order_quad(pts: np.ndarray) -> np.ndarray:
    """Order 4 points TL, TR, BR, BL."""
    pts = pts.reshape(4, 2).astype(np.float64)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([
        pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]
    ])


def _find_page_quad(img: np.ndarray) -> np.ndarray | None:
    h, w = img.shape[:2]
    scale = DETECT_WIDTH / w
    small = cv2.resize(img, (DETECT_WIDTH, int(h * scale)))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    med = float(np.median(gray))
    edges = cv2.Canny(gray, max(0, 0.66 * med), 1.33 * med + 1)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8))

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = MIN_QUAD_AREA_FRAC * small.shape[0] * small.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        if cv2.contourArea(c) < min_area:
            break
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return _order_quad(approx) / scale
    return None


def _enhance(img: np.ndarray, mode: str) -> np.ndarray:
    if mode == "color":
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        lab[..., 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[..., 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if mode == "gray":
        return cv2.createCLAHE(2.0, (8, 8)).apply(gray)
    # bw: adaptive threshold survives uneven lighting/shadows
    return cv2.adaptiveThreshold(
        cv2.GaussianBlur(gray, (3, 3), 0), 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15,
    )


def scan_image(image_path: Path, out_dir: Path | None = None,
               mode: str = "gray") -> dict:
    image_path = Path(image_path)
    img = cv2.imread(str(image_path))
    if img is None:
        raise SystemExit(f"scan: cannot read image {image_path}")

    quad = _find_page_quad(img)
    if quad is not None:
        (tl, tr, br, bl) = quad
        w = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
        h = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
        dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float64)
        M = cv2.getPerspectiveTransform(quad.astype(np.float32), dst.astype(np.float32))
        page = cv2.warpPerspective(img, M, (w, h))
        cropped = True
    else:
        page = img
        cropped = False

    result = _enhance(page, mode)

    out_dir = Path(out_dir) if out_dir else image_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{image_path.stem}-scan.png"
    cv2.imwrite(str(out_path), result)
    return {
        "image": str(image_path),
        "output": str(out_path),
        "page_detected": cropped,
        "output_size": [result.shape[1], result.shape[0]],
        "mode": mode,
    }


def scan_batch(inputs: list[Path], out_dir: Path | None = None,
               mode: str = "gray") -> list[dict]:
    paths: list[Path] = []
    for p in inputs:
        p = Path(p)
        if p.is_dir():
            paths.extend(sorted(
                f for f in p.iterdir()
                if f.suffix.lower() in IMAGE_EXTS and not f.stem.endswith("-scan")
            ))
        else:
            paths.append(p)
    if not paths:
        raise SystemExit("scan: no input images")
    return [scan_image(p, out_dir, mode) for p in paths]
