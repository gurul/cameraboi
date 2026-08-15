"""MCP server exposing the local MLX VLM as tools over stdio.

The process stays resident, so the model loads once and every call after the
first is warm. Register in .mcp.json as: scripts/cameraboi-vlm serve
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import ops

mcp = FastMCP("cameraboi-vlm")


@mcp.tool()
def vlm_describe(image_path: str, detail: str = "short") -> str:
    """Caption an image with a local VLM (Qwen3.8 on MLX).

    Args:
        image_path: Absolute path to the image file.
        detail: "short" (1-2 sentences) or "long" (thorough description).
    """
    return ops.to_json(ops.describe(image_path, detail))


@mcp.tool()
def vlm_query(image_path: str, question: str) -> str:
    """Answer a free-form question about an image with a local VLM.

    Args:
        image_path: Absolute path to the image file.
        question: The question to answer about the image.
    """
    return ops.to_json(ops.ask(image_path, question))


@mcp.tool()
def vlm_read_text(image_path: str) -> str:
    """Transcribe all visible text in an image, including handwriting and
    scene text. Complements the Apple-Vision `ocr` server: use this when
    layout/handwriting confuses classical OCR, use `ocr` for per-line boxes.

    Args:
        image_path: Absolute path to the image file.
    """
    return ops.to_json(ops.read_text(image_path))


@mcp.tool()
def vlm_find(image_path: str, objects: str, annotate: bool = True) -> str:
    """Locate objects in an image by open-vocabulary description. Returns
    pixel bounding boxes + centers in original image coordinates, and writes
    an annotated copy next to the source image.

    Args:
        image_path: Absolute path to the image file.
        objects: What to find, comma-separated for multiple ("red screw, allen key").
        annotate: Also write an annotated -vlm-find.png next to the image.
    """
    return ops.to_json(ops.find(image_path, objects, annotate))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
