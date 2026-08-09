"""Page detection, perspective correction, and batch behaviour of scan."""

import cv2
import numpy as np

from cameraboi_cv.scan import scan_batch, scan_image


def _page_photo(w=2400, h=1800):
    """A white page with text lines, perspective-tilted on a dark desk."""
    page = np.full((1400, 1000), 250, np.uint8)
    for i, y in enumerate(range(120, 1300, 60)):
        cv2.line(page, (100, y), (900 - (i % 3) * 120, y), 30, 6)
    img = np.full((h, w), 70, np.uint8)
    src = np.array([[0, 0], [1000, 0], [1000, 1400], [0, 1400]], np.float32)
    dst = np.array([[620, 190], [1815, 260], [1740, 1660], [530, 1560]], np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(page, M, (w, h), borderValue=70)
    return cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR)


def test_detects_and_rectifies_page(tmp_path):
    path = tmp_path / "photo.png"
    cv2.imwrite(str(path), _page_photo())

    result = scan_image(path)
    assert result["page_detected"] is True
    w, h = result["output_size"]
    # Rectified size comes from projected edge lengths, so a strongly tilted
    # view recovers the page taller-than-wide but not at exact 1000:1400.
    assert 1.0 < h / w < 1.6

    out = cv2.imread(result["output"], cv2.IMREAD_GRAYSCALE)
    # rectified page should be mostly bright paper, not desk
    assert float(np.mean(out)) > 150


def test_no_page_passes_through(tmp_path):
    img = np.full((900, 1200, 3), 120, np.uint8)  # featureless: no quad
    path = tmp_path / "flat.png"
    cv2.imwrite(str(path), img)

    result = scan_image(path)
    assert result["page_detected"] is False
    assert result["output_size"] == [1200, 900]


def test_batch_over_directory_skips_own_output(tmp_path):
    for i in range(3):
        cv2.imwrite(str(tmp_path / f"page-{i:02d}.png"), _page_photo())

    first = scan_batch([tmp_path])
    assert len(first) == 3
    # rerun: the -scan.png outputs from run one must not be re-scanned
    second = scan_batch([tmp_path])
    assert len(second) == 3


def test_bw_mode_binarizes(tmp_path):
    path = tmp_path / "photo.png"
    cv2.imwrite(str(path), _page_photo())
    result = scan_image(path, mode="bw")
    out = cv2.imread(result["output"], cv2.IMREAD_GRAYSCALE)
    assert set(np.unique(out)).issubset({0, 255})
