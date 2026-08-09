"""End-to-end measurement accuracy on a synthetic camera view of the mat.

Renders the real printable mat, draws objects of exactly known mm size on it,
warps the sheet through a perspective homography (simulating an off-axis
camera at arbitrary height), and asserts the pipeline recovers the true
dimensions. No camera, no lens distortion — this bounds the pipeline's own
error, which must stay well under the printed-fiducial error budget.
"""

import json

import cv2
import numpy as np
import pytest

from cameraboi_cv.boards import generate_mat
from cameraboi_cv.measure import measure_image

DPI = 300
PX_PER_MM = DPI / 25.4

RECT_MM = (60.0, 40.0)
RECT_AT = (120.0, 80.0)
CIRCLE_D_MM = 30.0
CIRCLE_AT = (220.0, 120.0)


@pytest.fixture(scope="module")
def synthetic_shot(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("measure")
    png, meta = generate_mat(tmp)
    sheet = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)

    x, y = int(RECT_AT[0] * PX_PER_MM), int(RECT_AT[1] * PX_PER_MM)
    w, h = int(RECT_MM[0] * PX_PER_MM), int(RECT_MM[1] * PX_PER_MM)
    cv2.rectangle(sheet, (x, y), (x + w, y + h), 40, -1)
    cx, cy = int(CIRCLE_AT[0] * PX_PER_MM), int(CIRCLE_AT[1] * PX_PER_MM)
    cv2.circle(sheet, (cx, cy), int(CIRCLE_D_MM / 2 * PX_PER_MM), 40, -1)

    # Camera view: sheet projected onto a tilted quad in a larger frame.
    sh, sw = sheet.shape
    src = np.array([[0, 0], [sw, 0], [sw, sh], [0, sh]], np.float32)
    dst = np.array(
        [[210, 155], [2905, 240], [2820, 2110], [150, 2010]], np.float32
    )
    H = cv2.getPerspectiveTransform(src, dst)
    view = cv2.warpPerspective(
        sheet, H, (3100, 2300), borderValue=110, flags=cv2.INTER_LINEAR
    )
    shot = tmp / "shot.png"
    cv2.imwrite(str(shot), view)
    return shot, meta


def test_measures_rectangle_and_circle(synthetic_shot):
    shot, meta = synthetic_shot
    result = measure_image(shot, meta)

    assert result["markers_detected"] == [0, 1, 2, 3]
    assert result["fit_residual_mm"] < 0.2
    assert result["object_count"] == 2

    by_area = sorted(result["objects"], key=lambda o: o["area_mm2"], reverse=True)
    rect, circle = by_area
    assert rect["width_mm"] == pytest.approx(RECT_MM[0], abs=0.4)
    assert rect["height_mm"] == pytest.approx(RECT_MM[1], abs=0.4)
    assert circle["width_mm"] == pytest.approx(CIRCLE_D_MM, abs=0.4)
    assert circle["height_mm"] == pytest.approx(CIRCLE_D_MM, abs=0.4)
    assert circle["area_mm2"] == pytest.approx(
        3.14159 * (CIRCLE_D_MM / 2) ** 2, rel=0.03
    )


def test_scale_correction_applies(synthetic_shot, tmp_path):
    shot, meta = synthetic_shot
    data = json.loads(meta.read_text())
    data["scale_correction"] = 1.02
    corrected = tmp_path / "mat-corrected.json"
    corrected.write_text(json.dumps(data))

    base = measure_image(shot, meta)
    scaled = measure_image(shot, corrected)
    rect_b = max(base["objects"], key=lambda o: o["area_mm2"])
    rect_s = max(scaled["objects"], key=lambda o: o["area_mm2"])
    assert rect_s["width_mm"] == pytest.approx(rect_b["width_mm"] * 1.02, abs=0.05)


def test_refuses_without_enough_markers(synthetic_shot, tmp_path):
    shot, meta = synthetic_shot
    view = cv2.imread(str(shot), cv2.IMREAD_GRAYSCALE)
    # Cover two markers: fewer than MIN_MARKERS remain.
    view[0:900, 0:900] = 110
    view[1300:, 0:900] = 110
    blocked = tmp_path / "blocked.png"
    cv2.imwrite(str(blocked), view)
    with pytest.raises(SystemExit, match="markers detected"):
        measure_image(blocked, meta)
