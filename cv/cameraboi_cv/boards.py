"""Printable calibration artifacts: ChArUco board (lens intrinsics, one-time)
and the ArUco measuring mat (per-shot scale/pose recovery).

Both are emitted as PNGs with real DPI metadata so "print at 100% scale" is
meaningful, plus a JSON sidecar describing the geometry so the detectors never
guess. The mat sidecar's `scale_correction` starts at 1.0; after printing,
measure the distance between the outer corners of two markers with a ruler and
set scale_correction = measured_mm / nominal_mm to cancel printer scale error.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ARUCO_DICT_NAME = "DICT_4X4_50"
MAT_MARKER_IDS = (0, 1, 2, 3)  # TL, TR, BR, BL on the sheet

# A4 landscape defaults, all mm
MAT_SHEET = (297.0, 210.0)
MAT_MARKER_SIZE = 30.0
MAT_MARGIN = 10.0  # sheet edge -> marker outer edge

# ChArUco board defaults (A4 portrait)
BOARD_SQUARES = (7, 10)
BOARD_SQUARE_MM = 25.0
BOARD_MARKER_MM = 18.0
BOARD_DICT_NAME = "DICT_5X5_100"

DPI = 300
MM_PER_INCH = 25.4


def _px(mm: float, dpi: int = DPI) -> int:
    return int(round(mm * dpi / MM_PER_INCH))


def aruco_dictionary(name: str):
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


def mat_marker_positions(
    sheet=MAT_SHEET, marker=MAT_MARKER_SIZE, margin=MAT_MARGIN
) -> dict[int, list[list[float]]]:
    """Marker id -> its 4 printed corners in mm (TL, TR, BR, BL order, matching
    the corner order cv2.aruco detection returns). Origin: sheet top-left, y down."""
    w, h = sheet
    anchors = {
        MAT_MARKER_IDS[0]: (margin, margin),
        MAT_MARKER_IDS[1]: (w - margin - marker, margin),
        MAT_MARKER_IDS[2]: (w - margin - marker, h - margin - marker),
        MAT_MARKER_IDS[3]: (margin, h - margin - marker),
    }
    return {
        mid: [
            [x, y],
            [x + marker, y],
            [x + marker, y + marker],
            [x, y + marker],
        ]
        for mid, (x, y) in anchors.items()
    }


def generate_mat(out_dir: Path, sheet=MAT_SHEET, marker=MAT_MARKER_SIZE,
                 margin=MAT_MARGIN, dpi: int = DPI) -> tuple[Path, Path]:
    """Write the printable measuring mat PNG + geometry JSON. Returns (png, json)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    w_px, h_px = _px(sheet[0], dpi), _px(sheet[1], dpi)
    canvas = np.full((h_px, w_px), 255, np.uint8)

    dictionary = aruco_dictionary(ARUCO_DICT_NAME)
    positions = mat_marker_positions(sheet, marker, margin)
    side_px = _px(marker, dpi)
    for mid, corners in positions.items():
        img = cv2.aruco.generateImageMarker(dictionary, mid, side_px)
        x, y = _px(corners[0][0], dpi), _px(corners[0][1], dpi)
        canvas[y:y + side_px, x:x + side_px] = img

    # Print-scale verification aids: label + a nominal ruler line.
    cv2.putText(
        canvas,
        f"cameraBoi measuring mat  -  print at 100% scale on "
        f"{sheet[0]:.0f}x{sheet[1]:.0f}mm  -  markers {ARUCO_DICT_NAME} "
        f"ids {list(positions)} @ {marker:.0f}mm",
        (_px(margin + marker + 5, dpi), _px(margin + 4, dpi)),
        cv2.FONT_HERSHEY_SIMPLEX, dpi / 300.0 * 0.7, 0, 2, cv2.LINE_AA,
    )
    y_line = _px(sheet[1] - margin / 2, dpi)
    x0, x1 = _px(margin + marker, dpi), _px(margin + marker + 100.0, dpi)
    cv2.line(canvas, (x0, y_line), (x1, y_line), 0, 3)
    cv2.putText(canvas, "this line is 100.0 mm when printed at 100%",
                (x0, y_line - _px(2, dpi)),
                cv2.FONT_HERSHEY_SIMPLEX, dpi / 300.0 * 0.6, 0, 2, cv2.LINE_AA)

    png_path = out_dir / "measure-mat.png"
    Image.fromarray(canvas).save(png_path, dpi=(dpi, dpi))

    meta = {
        "kind": "cameraboi-measure-mat",
        "dictionary": ARUCO_DICT_NAME,
        "sheet_mm": list(sheet),
        "marker_size_mm": marker,
        "margin_mm": margin,
        "markers_mm": {str(mid): pts for mid, pts in positions.items()},
        "scale_correction": 1.0,
        "note": "After printing, measure the 100mm line (or an outer marker-to-marker "
                "span) and set scale_correction = measured / nominal.",
    }
    json_path = out_dir / "measure-mat.json"
    json_path.write_text(json.dumps(meta, indent=2))
    return png_path, json_path


def charuco_board(squares=BOARD_SQUARES, square_mm=BOARD_SQUARE_MM,
                  marker_mm=BOARD_MARKER_MM, dict_name=BOARD_DICT_NAME):
    dictionary = aruco_dictionary(dict_name)
    return cv2.aruco.CharucoBoard(
        squares, square_mm / 1000.0, marker_mm / 1000.0, dictionary
    )


def generate_charuco(out_dir: Path, dpi: int = DPI) -> tuple[Path, Path]:
    """Write the printable ChArUco calibration board PNG + JSON sidecar."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    board = charuco_board()
    w_px = _px(BOARD_SQUARES[0] * BOARD_SQUARE_MM, dpi)
    h_px = _px(BOARD_SQUARES[1] * BOARD_SQUARE_MM, dpi)
    img = board.generateImage((w_px, h_px), marginSize=_px(10, dpi))

    png_path = out_dir / "charuco-board.png"
    Image.fromarray(img).save(png_path, dpi=(dpi, dpi))

    meta = {
        "kind": "cameraboi-charuco-board",
        "dictionary": BOARD_DICT_NAME,
        "squares": list(BOARD_SQUARES),
        "square_mm": BOARD_SQUARE_MM,
        "marker_mm": BOARD_MARKER_MM,
        "note": "Print at 100% scale; flatness matters more than exact scale for "
                "intrinsics. Tape to something rigid.",
    }
    json_path = out_dir / "charuco-board.json"
    json_path.write_text(json.dumps(meta, indent=2))
    return png_path, json_path
