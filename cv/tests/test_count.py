"""Exact-count guarantees on synthetic scenes, including touching objects."""

import cv2
import numpy as np

from cameraboi_cv.count import count_image

RNG_SEED = 7


def _canvas(w=1600, h=1200, bg=235):
    return np.full((h, w, 3), bg, np.uint8)


def test_counts_separated_objects_exactly(tmp_path):
    img = _canvas()
    rng = np.random.default_rng(RNG_SEED)
    placed = []
    while len(placed) < 27:
        x, y = int(rng.integers(80, 1520)), int(rng.integers(80, 1120))
        r = int(rng.integers(18, 34))
        if all((x - px) ** 2 + (y - py) ** 2 > (r + pr + 12) ** 2
               for px, py, pr in placed):
            placed.append((x, y, r))
            cv2.circle(img, (x, y), r, (60, 50, 45), -1)
    path = tmp_path / "screws.png"
    cv2.imwrite(str(path), img)

    result = count_image(path)
    assert result["count"] == 27


def test_splits_touching_pairs(tmp_path):
    img = _canvas()
    n = 0
    for row in range(2):
        for col in range(4):
            cx, cy = 220 + col * 380, 350 + row * 500
            r = 45
            # two circles overlapping by ~25% of a radius — one blob to Otsu
            cv2.circle(img, (cx - int(r * 0.85), cy), r, (50, 50, 50), -1)
            cv2.circle(img, (cx + int(r * 0.85), cy), r, (50, 50, 50), -1)
            n += 2
    path = tmp_path / "touching.png"
    cv2.imwrite(str(path), img)

    result = count_image(path)
    assert result["count"] == n


def test_light_objects_on_dark_auto(tmp_path):
    img = _canvas(bg=40)
    for i in range(5):
        cv2.circle(img, (200 + i * 280, 600), 50, (220, 225, 230), -1)
    path = tmp_path / "light.png"
    cv2.imwrite(str(path), img)

    result = count_image(path)
    assert result["count"] == 5


def test_min_area_filters_noise(tmp_path):
    img = _canvas()
    cv2.circle(img, (400, 400), 60, (50, 50, 50), -1)
    for i in range(30):  # confetti below the area floor
        cv2.circle(img, (100 + i * 45, 900), 3, (50, 50, 50), -1)
    path = tmp_path / "noisy.png"
    cv2.imwrite(str(path), img)

    result = count_image(path, min_area_px=500)
    assert result["count"] == 1
