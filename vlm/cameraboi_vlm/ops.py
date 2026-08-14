"""The four vision operations shared by the MCP server and the CLI."""

from __future__ import annotations

import json
from pathlib import Path

from . import engine, grounding

FIND_PROMPT = (
    'Locate every instance of: {targets}. Report each one as a JSON object '
    '{{"bbox_2d": [x1, y1, x2, y2], "label": "<name>"}} in a JSON array. '
    "If none are present, reply with an empty JSON array []."
)

READ_PROMPT = (
    "Transcribe all text visible in this image exactly as written, preserving "
    "line breaks and reading order. Reply with only the transcription, or "
    "NO TEXT if there is none."
)


def describe(image_path: str, detail: str = "short") -> dict:
    _, model_img, _ = engine.prepare_image(image_path)
    prompt = (
        "Describe this image in one or two sentences."
        if detail == "short"
        else "Describe this image thoroughly: subjects, layout, text, colors, and anything notable."
    )
    text, secs = engine.infer(model_img, prompt, max_tokens=100 if detail == "short" else 512)
    return {"caption": text, "seconds": round(secs, 1)}


def ask(image_path: str, question: str) -> dict:
    _, model_img, _ = engine.prepare_image(image_path)
    text, secs = engine.infer(model_img, question, max_tokens=512)
    return {"answer": text, "seconds": round(secs, 1)}


def read_text(image_path: str) -> dict:
    _, model_img, _ = engine.prepare_image(image_path)
    text, secs = engine.infer(model_img, READ_PROMPT, max_tokens=1024)
    return {"text": "" if text.strip() == "NO TEXT" else text, "seconds": round(secs, 1)}


def find(image_path: str, targets: str, annotate: bool = True) -> dict:
    original, model_img, _ = engine.prepare_image(image_path)
    raw, secs = engine.infer(model_img, FIND_PROMPT.format(targets=targets), max_tokens=1024)
    boxes = grounding.denormalize(grounding.parse_boxes(raw), original.width, original.height)
    result = {
        "query": targets,
        "count": len(boxes),
        "image_size": [original.width, original.height],
        "objects": [b.as_dict() for b in boxes],
        "seconds": round(secs, 1),
    }
    if annotate and boxes:
        src = Path(image_path).expanduser()
        out = src.with_name(src.stem + "-vlm-find.png")
        grounding.annotate(original, boxes).save(out)
        result["annotated_image"] = str(out)
    return result


def to_json(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)
