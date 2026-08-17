---
title: MCP Vision Servers
icon: 🧠
order: 7
---

# MCP Vision Servers — OCR and local VLMs

Three MCP servers extend cameraBoi's vision beyond the deterministic CV toolkit. All run
**fully locally** — no API keys, no cloud, captures never leave the machine. They are
registered in the workspace `.mcp.json`, so any Claude Code session in the project can
call them as tools.

| Server | Tool(s) | What it adds |
|---|---|---|
| `vlm` (cameraboi-vlm) | `vlm_describe`, `vlm_query`, `vlm_read_text`, `vlm_find` | **The primary semantic-vision server.** Qwen3-VL 4-bit on MLX — captioning, VQA, text transcription, and reliable open-vocabulary bounding boxes, resident in memory so calls after the first are fast |
| `ocr` (ocrtool-mcp) | `ocr_extract_text` | Verbatim text extraction via the Apple Vision framework — per-line pixel bounding boxes, table/markdown/structured output |
| `moondream` (moondream-mcp) | `caption_image`, `query_image`, `detect_objects`, `point_objects`, `analyze_image`, `batch_analyze_images` | Legacy fallback VLM (~15–20 s/call, unreliable boxes) — superseded by `vlm` for everything except `point_objects`-style center points |

## Where each tool wins

- **Claude's own vision (Read)** — judgement: what things are, layout, meaning, quality.
- **`cameraboi-cv`** — calibrated numbers: millimeters on the mat, exact counts, page cleanup.
- **`ocr`** — characters: serial numbers, part codes, dense pages, anything transcribed verbatim.
- **`vlm`** — semantics + localization: "where is the X" as pixel bounding boxes, free-form
  visual questions, handwriting and scene text that defeats classical OCR.
- **`moondream`** — kept for continuity; prefer `vlm` for new work.

## cameraboi-vlm — Qwen3-VL on MLX

The `vlm` server runs **Qwen3-VL-4B-Instruct 4-bit** (~2.3 GB download on first call)
through [MLX-VLM](https://github.com/Blaizzy/mlx-vlm), Apple's-silicon-native inference.
The MCP process stays resident, so the model loads once per session and subsequent calls
skip the load entirely — this is the main speed win over spawning a CLI per call.

Verified on an M5 / 32 GB against real captures: `describe` 5.7 s, `find` 6.8 s
inference, with grounding boxes landing pixel-tight on a PCB and all four mat markers —
including one under a strong specular reflection.

- `vlm_describe(image_path, detail)` — captioning; `detail: "short" | "long"`.
- `vlm_query(image_path, question)` — free-form VQA.
- `vlm_read_text(image_path)` — full-text transcription; better than `ocr` on handwriting
  and odd layouts, worse when you need per-line boxes.
- `vlm_find(image_path, objects, annotate)` — open-vocabulary grounding. Returns pixel
  boxes + centers **in original image coordinates** (the model sees a ≤1568 px copy;
  boxes are mapped back), and writes an annotated `-vlm-find.png` next to the source.

The same operations are available as a CLI for scripting and testing:

```bash
scripts/cameraboi-vlm describe ~/Pictures/cameraboi/snap-….jpg
scripts/cameraboi-vlm find ~/Pictures/cameraboi/snap-….jpg "e-ink device, aruco marker"
scripts/cameraboi-vlm serve   # what .mcp.json runs — MCP over stdio
```

First run bootstraps a private venv in `vlm/.venv` via `uv` (system Python is too old for
`mlx-vlm`, which needs ≥3.10). Model override: `CAMERABOI_VLM_MODEL` env var — any
MLX-format VLM works, e.g. `mlx-community/Qwen3-VL-8B-Instruct-4bit` (~4.5 GB) for the
quality tier on 32 GB+ machines.

> [!NOTE]
> Grounding coordinates: Qwen3-VL emits boxes in a 0–1000 normalized space; the server
> denormalizes to original pixels and clamps to the frame. An empty `objects` array means
> "not located", not "absent".

## OCR — `ocr_extract_text`

```json
{ "image_path": "/Users/you/Pictures/cameraboi/snap-….jpg", "lang": "en", "format": "structured" }
```

- Accepts `image_path`, `url`, or `base64`. `lang` defaults to `zh+en` — pass the real
  languages (`en`, `de+en`, …). Supported: zh-Hans, zh-Hant, en-US, fr-FR, it-IT, de-DE,
  es-ES, pt-BR, ar-SA, ru-RU, ko-KR, ja-JP, uk-UA, th-TH, vi-VN.
- `format`: `text` (plain lines), `markdown` (table with boxes), `structured` (JSON),
  `auto`. `enhanced: true` selects the accurate (slower) Vision path.
- Bounding-box origin is **bottom-left**; Y increases upward.
- Feed it the **full-res capture** (`snap --full`), or better, `cameraboi-cv scan`
  cleaned pages.

Installed as a signed-checksum release binary at `bin/ocrtool-mcp` (v1.0.6, universal).

## Moondream — local VLM

First tool call downloads the model (`vikhyatk/moondream2`, revision 2025-01-09,
several GB) into the Hugging Face cache; subsequent calls are warm. Runs on MPS
(Apple Silicon) automatically.

- `point_objects` — open-vocabulary center-point coordinates for each instance
  (normalized 0–1). **The reliable localization tool** — verified accurate on real
  captures. Pairs well with `cameraboi-cv count` as a semantic cross-check.
- `detect_objects` — bounding boxes; **weak on the pinned model revision** (empty or
  degenerate boxes are common). Prefer `point_objects`; an empty result means
  "unlocated", not "absent".
- `caption_image` / `query_image` — captioning and free-form VQA; verified to read
  on-screen text and describe scenes accurately (~15–20 s per call on MPS).

> [!IMPORTANT]
> The PyPI package (`moondream-mcp` 1.0.2, Jul 2025) needs four workarounds, all
> injected via `uvx` flags in the `.mcp.json` entry: `requests` (undeclared dependency),
> `pyvips-binary` (bundles the native libvips it dlopens), and era-matched pins
> `torch==2.5.1` + `torchvision==0.20.1` + `transformers==4.48.*` on Python 3.12 —
> current torch/transformers break the moondream2 remote code (`all_tied_weights_keys`
> / meta-tensor errors). Do not "upgrade" these pins without retesting a real call.

## Registration

Workspace `.mcp.json` entries:

```json
{
  "vlm": {
    "command": "/Users/gurucharan/Documents/work/cameraBoi/scripts/cameraboi-vlm",
    "args": ["serve"]
  },
  "ocr": {
    "command": "/Users/gurucharan/Documents/work/cameraBoi/bin/ocrtool-mcp",
    "args": []
  },
  "moondream": {
    "command": "uvx",
    "args": [
      "--python", "3.12",
      "--with", "requests",
      "--with", "pyvips-binary",
      "--with", "torch==2.5.1",
      "--with", "torchvision==0.20.1",
      "--with", "transformers==4.48.*",
      "moondream-mcp"
    ]
  }
}
```

## Evaluated and rejected

- **YOLO-MCP-Server, opencv-mcp-server** — archived upstream (Mar 2026).
- **groundlight/mcp-vision** — Docker-only, CPU-slow, no MPS path.
- **Cloud vision MCPs (Z.AI, etc.)** — API-key-gated; the local pair covers the need
  without sending captures off-device.
