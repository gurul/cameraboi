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
from cameraboi_cv.measure import estimate_camera_height, measure_image

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


def test_object_height_correction_scales_down(synthetic_shot):
    shot, meta = synthetic_shot
    base = measure_image(shot, meta)
    corrected = measure_image(shot, meta, object_height_mm=15.0,
                              camera_height_mm=300.0)
    rect_b = max(base["objects"], key=lambda o: o["area_mm2"])
    rect_c = max(corrected["objects"], key=lambda o: o["area_mm2"])
    factor = (300.0 - 15.0) / 300.0
    assert rect_c["width_mm"] == pytest.approx(rect_b["width_mm"] * factor, abs=0.05)
    assert corrected["camera_height_mm"] == 300.0
    assert corrected["camera_height_source"] == "given"


def test_auto_seg_rejects_shadow_and_keeps_lit_fringe(tmp_path):
    """A colored object with a bright low-saturation shadow beside it and a
    pale (but saturated) lit fringe around it: gray segmentation swallows the
    shadow and drops the fringe; auto does the opposite, matching the truth."""
    png, meta = generate_mat(tmp_path)
    sheet = cv2.cvtColor(cv2.imread(str(png), cv2.IMREAD_GRAYSCALE),
                         cv2.COLOR_GRAY2BGR)

    fringe_mm = 2.0
    x, y = int(RECT_AT[0] * PX_PER_MM), int(RECT_AT[1] * PX_PER_MM)
    w, h = int(RECT_MM[0] * PX_PER_MM), int(RECT_MM[1] * PX_PER_MM)
    f = int(fringe_mm * PX_PER_MM)
    shadow_w = int(5.0 * PX_PER_MM)
    # lit fringe (chamfer catching light): pale but clearly saturated blue
    cv2.rectangle(sheet, (x - f, y - f), (x + w + f, y + h + f),
                  (255, 210, 170), -1)
    # cast shadow touching the object's right edge: unsaturated, darker than
    # paper, brighter than a dark object
    cv2.rectangle(sheet, (x + w, y), (x + w + shadow_w, y + h),
                  (150, 150, 150), -1)
    # object body: saturated mid-blue
    cv2.rectangle(sheet, (x, y), (x + w, y + h), (200, 130, 50), -1)

    shot = tmp_path / "color-shot.png"
    cv2.imwrite(str(shot), sheet)

    true_w = RECT_MM[0] + 2 * fringe_mm
    true_h = RECT_MM[1] + 2 * fringe_mm

    auto = max(measure_image(shot, meta, thresh=180)["objects"],
               key=lambda o: o["area_mm2"])
    assert auto["width_mm"] == pytest.approx(true_w, abs=0.4)
    assert auto["height_mm"] == pytest.approx(true_h, abs=0.4)

    gray = max(measure_image(shot, meta, thresh=180, seg="gray")["objects"],
               key=lambda o: o["area_mm2"])
    assert gray["width_mm"] > RECT_MM[0] + 3.0   # shadow swallowed
    assert gray["height_mm"] < true_h - 1.0      # fringe dropped


def test_camera_height_estimation_from_markers():
    """Synthetic pinhole camera 372mm above the mat: PnP on the projected
    marker corners must recover the height."""
    from cameraboi_cv.boards import mat_marker_positions

    height = 372.0
    positions = mat_marker_positions()
    mm_pts = np.concatenate([np.asarray(positions[i], np.float64)
                             for i in sorted(positions)])
    obj = np.hstack([mm_pts, np.zeros((len(mm_pts), 1))])

    k = np.array([[3000.0, 0, 1632], [0, 3000.0, 1224], [0, 0, 1]])
    dist = np.zeros(5)
    # camera straight above the sheet center, looking down
    rot = np.diag([1.0, -1.0, -1.0])
    center = np.array([148.5, 105.0, 0.0])
    tvec = -rot @ center + np.array([0, 0, height])
    rvec, _ = cv2.Rodrigues(rot)
    img_pts, _ = cv2.projectPoints(obj, rvec, tvec, k, dist)

    est = estimate_camera_height(img_pts.reshape(-1, 2), mm_pts, k, dist)
    assert est == pytest.approx(height, abs=1.0)


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
