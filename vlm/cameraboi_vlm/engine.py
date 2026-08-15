"""Model loading and inference for cameraboi-vlm.

One resident model per process, loaded lazily on first use — the MCP server
stays warm across calls, which is the whole point versus per-call CLI loads.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from PIL import Image

DEFAULT_MODEL = os.environ.get("CAMERABOI_VLM_MODEL", "mlx-community/Qwen3.8-27B-4bit")

# Long-side cap fed to the model. Matches the -model.jpg convention of the
# capture CLI; grounding output is mapped back to original pixels afterwards.
MAX_SIDE = int(os.environ.get("CAMERABOI_VLM_MAX_SIDE", "1568"))

_state: dict = {}


def _log(msg: str) -> None:
    print(f"cameraboi-vlm: {msg}", file=sys.stderr, flush=True)


def get_model():
    if "model" not in _state:
        from mlx_vlm import load
        from mlx_vlm.utils import load_config

        t0 = time.monotonic()
        _log(f"loading {DEFAULT_MODEL} (first call downloads it to the HF cache)...")
        model, processor = load(DEFAULT_MODEL)
        _state["model"] = model
        _state["processor"] = processor
        _state["config"] = load_config(DEFAULT_MODEL)
        _log(f"model ready in {time.monotonic() - t0:.1f}s")
    return _state["model"], _state["processor"], _state["config"]


def prepare_image(image_path: str) -> tuple[Image.Image, Image.Image, float]:
    """Return (original, model-sized copy, scale original/model)."""
    path = Path(image_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"image not found: {path}")
    original = Image.open(path)
    original.load()
    if original.mode != "RGB":
        original = original.convert("RGB")
    long_side = max(original.size)
    if long_side <= MAX_SIDE:
        return original, original, 1.0
    scale = MAX_SIDE / long_side
    resized = original.resize(
        (round(original.width * scale), round(original.height * scale)), Image.LANCZOS
    )
    return original, resized, 1.0 / scale


def infer(image: Image.Image, prompt: str, max_tokens: int = 512) -> tuple[str, float]:
    """Run one generation; returns (text, seconds)."""
    import tempfile

    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template

    model, processor, config = get_model()
    formatted = apply_chat_template(processor, config, prompt, num_images=1)
    t0 = time.monotonic()
    # generate() is typed for image paths, not PIL objects — hand it a file.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
        image.save(tmp.name)
        result = generate(
            model, processor, formatted, image=[tmp.name], max_tokens=max_tokens, verbose=False
        )
    text = result.text if hasattr(result, "text") else str(result)
    return text.strip(), time.monotonic() - t0
