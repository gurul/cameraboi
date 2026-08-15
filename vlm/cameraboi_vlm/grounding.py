"""Parse and render Qwen VLM grounding output (Qwen3-VL / Qwen3.8).

Qwen VLMs emit boxes as JSON objects with a ``bbox_2d`` [x1, y1, x2, y2] and a
``label``, with coordinates in a 0-1000 space normalized to the image the model
saw. The model wraps the JSON in markdown fences or prose often enough that the
parser scans for objects rather than trusting the whole reply to be JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

NORM_SPACE = 1000.0

_JSON_BLOCK = re.compile(r"\{[^{}]*\}", re.DOTALL)


@dataclass
class Box:
    label: str
    x1: float
    y1: float
    x2: float
    y2: float

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "box": [round(self.x1, 1), round(self.y1, 1), round(self.x2, 1), round(self.y2, 1)],
            "center": [round((self.x1 + self.x2) / 2, 1), round((self.y1 + self.y2) / 2, 1)],
        }


def parse_boxes(text: str) -> list[Box]:
    """Extract every bbox_2d object from model output, in 0-1000 space."""
    boxes: list[Box] = []
    for match in _JSON_BLOCK.finditer(text):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        bbox = obj.get("bbox_2d") or obj.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue
        try:
            x1, y1, x2, y2 = (float(v) for v in bbox)
        except (TypeError, ValueError):
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append(Box(str(obj.get("label", "object")), x1, y1, x2, y2))
    return boxes


def denormalize(boxes: list[Box], width: int, height: int) -> list[Box]:
    """Map 0-1000 normalized boxes onto pixel coordinates of a width x height image."""
    sx, sy = width / NORM_SPACE, height / NORM_SPACE
    return [
        Box(
            b.label,
            max(0.0, min(b.x1 * sx, width)),
            max(0.0, min(b.y1 * sy, height)),
            max(0.0, min(b.x2 * sx, width)),
            max(0.0, min(b.y2 * sy, height)),
        )
        for b in boxes
    ]


def annotate(image: Image.Image, boxes: list[Box]) -> Image.Image:
    """Draw labelled boxes; line weight and text scale with image size."""
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    stroke = max(2, out.width // 400)
    text_size = max(14, out.width // 60)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", text_size)
    except OSError:
        font = ImageFont.load_default()
    for i, b in enumerate(boxes):
        color = _palette(i)
        draw.rectangle([b.x1, b.y1, b.x2, b.y2], outline=color, width=stroke)
        tag = f"{i + 1} {b.label}"
        tw, th = draw.textbbox((0, 0), tag, font=font)[2:]
        ty = b.y1 - th - stroke if b.y1 - th - stroke > 0 else b.y1 + stroke
        draw.rectangle([b.x1, ty, b.x1 + tw + 2 * stroke, ty + th + stroke], fill=color)
        draw.text((b.x1 + stroke, ty), tag, fill="white", font=font)
    return out


def _palette(i: int) -> str:
    colors = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#008080", "#9a6324", "#800000"]
    return colors[i % len(colors)]
