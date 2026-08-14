"""Grounding parser/denormalizer tests — no model, no network."""

from PIL import Image

from cameraboi_vlm.grounding import annotate, denormalize, parse_boxes


def test_parses_clean_json_array():
    raw = '[{"bbox_2d": [100, 200, 300, 400], "label": "screw"}]'
    boxes = parse_boxes(raw)
    assert len(boxes) == 1
    assert boxes[0].label == "screw"
    assert (boxes[0].x1, boxes[0].y1, boxes[0].x2, boxes[0].y2) == (100, 200, 300, 400)


def test_parses_fenced_and_prosey_output():
    raw = (
        "Here are the objects I found:\n```json\n"
        '[\n {"bbox_2d": [10, 20, 30, 40], "label": "cap"},\n'
        ' {"bbox_2d": [50, 60, 70, 80], "label": "pen"}\n]\n```\nDone.'
    )
    boxes = parse_boxes(raw)
    assert [b.label for b in boxes] == ["cap", "pen"]


def test_rejects_degenerate_and_malformed_boxes():
    raw = (
        '{"bbox_2d": [300, 400, 100, 200], "label": "inverted"}'
        '{"bbox_2d": [1, 2, 3], "label": "short"}'
        '{"bbox_2d": ["a", 2, 3, 4], "label": "nonnumeric"}'
        '{"label": "no box"}'
        '{"bbox_2d": [5, 5, 6, 6], "label": "ok"}'
    )
    boxes = parse_boxes(raw)
    assert [b.label for b in boxes] == ["ok"]


def test_empty_result_for_no_matches():
    assert parse_boxes("[]") == []
    assert parse_boxes("I could not find any such object.") == []


def test_denormalize_maps_and_clamps():
    boxes = parse_boxes('{"bbox_2d": [0, 0, 500, 1000], "label": "half"}')
    (b,) = denormalize(boxes, 2000, 1000)
    assert (b.x1, b.y1, b.x2, b.y2) == (0, 0, 1000, 1000)

    boxes = parse_boxes('{"bbox_2d": [900, 900, 1000, 1000], "label": "corner"}')
    (b,) = denormalize(boxes, 3264, 2448)
    assert b.x2 == 3264 and b.y2 == 2448
    assert round(b.x1) == round(900 * 3.264)


def test_annotate_draws_without_error():
    img = Image.new("RGB", (400, 300), "white")
    boxes = denormalize(parse_boxes('{"bbox_2d": [100, 100, 500, 500], "label": "x"}'), 400, 300)
    out = annotate(img, boxes)
    assert out.size == (400, 300)
    # box outline actually landed on the canvas
    assert out.getpixel((int(boxes[0].x1), int((boxes[0].y1 + boxes[0].y2) / 2))) != (255, 255, 255)
