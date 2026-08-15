# cameraBoi

**Physical vision for Claude Code.** A Claude Code skill plus a single bash CLI that lets a
Claude session take a photo, record a clip, or watch a scene through the camera attached to
your Mac — and then actually look at what it captured.

Built around an [IPEVO V4K](https://www.ipevo.com/) document camera by default, but any
AVFoundation device works, including the built-in MacBook camera.

- **macOS only** — captures go through AVFoundation
- **`ffmpeg` is the only dependency** — no build step, no package manager, no runtime beyond bash
- **Machine-parseable output** — the last stdout line is the artifact path, so capture chains
  straight into a file read

## Quick start

**Prerequisites**

```bash
brew install ffmpeg
```

Then grant camera access to whichever terminal app you run the CLI from — Terminal, iTerm,
Ghostty, VS Code — under **System Settings → Privacy & Security → Camera**. The permission
belongs to the terminal app, not to cameraBoi.

**Verify**

```bash
scripts/cameraboi doctor
```

`doctor` checks `ffmpeg`, checks the device, and runs a live test capture. Fix whatever it
reports before going further.

**Install the skill**

```bash
ln -s "$PWD/skills/cameraboi" ~/.claude/skills/cameraboi
```

A symlink, not a copy — the repo stays the single source of truth and updates propagate to
every session.

**Use it**

Start a new Claude Code session and ask:

> use cameraBoi to take a picture and tell me what you see

## Commands

```bash
scripts/cameraboi <command> [options]
```

| Command | Options | What it does |
|---|---|---|
| `devices` | — | List AVFoundation video and audio devices |
| `snap` | `[-o FILE] [-d DEVICE] [-r WxH] [--warmup N] [--full] [--no-open] [--no-af]` | Still capture. Defaults: `IPEVO V4K`, **native (highest advertised) resolution** — 3264x2448 on the V4K, 1920x1080 fallback if probing fails — 15-frame warm-up, output `~/Pictures/cameraboi/snap-YYYYmmdd-HHMMSS.jpg`. `-r WxH` forces a specific mode; `--max` is a legacy no-op. Continuous autofocus is enabled automatically on cameras that support it (`--no-af` / `CAMERABOI_NO_AF=1` to skip). Opens in Preview on success (`--no-open` to skip); captures wider than 2000px also emit a 1568px `-model.jpg` copy for vision models, skipped by `--full` |
| `record` | `-t SECONDS [-o FILE] [-d DEVICE] [--audio] [-r WxH]` | H.264 MP4 with `+faststart`, 1920x1080@30. `--audio` adds the device's own microphone |
| `burst` | `-n COUNT [-i SECONDS] [-o DIR]` | N stills at a fixed interval — timelapse or monitoring |
| `frames` | `VIDEO [-n N] [-o DIR] [--sheet]` | Extract evenly spaced frames (default 12); `--sheet` tiles them into contact sheets |
| `logs` | `[--tail N] [--failures] [--json]` | Query the capture event log — every capture records a JSONL event (exit code, duration, ffmpeg stderr) for debugging from evidence |
| `clean` | `[--older-than AGE] [--logs] [--yes]` | Delete captured artifacts (`snap-*`, `rec-*`, `burst-*/`, `frames-*/`) from the capture dir; other files are untouched. **Dry run by default** — `--yes` deletes, `--older-than 7d/24h/30m` age-filters, `--logs` also clears the event log |
| `doctor` | — | Verify ffmpeg, device, and a live 640x480 test capture; print permission guidance on failure and the last recorded capture failure |

`-d` takes a case-insensitive substring (`-d ipevo`) or a numeric index (`-d 1`). Captures
land in `~/Pictures/cameraboi/` unless `-o` says otherwise.

### CV tools — `scripts/cameraboi-cv`

Deterministic computer vision on top of the captures, for what vision models can't do by
looking: **calibrated millimeter measurement** and **exact counting / batch scan
cleanup**. Self-bootstraps a venv in `cv/.venv` on first run; same last-stdout-lines
artifact contract.

| Command | What it does |
|---|---|
| `mat` / `board` | Generate the printable ArUco measuring mat and ChArUco calibration board |
| `calibrate DIR` | One-time lens intrinsics from ~15 stills of the board |
| `measure IMG` | mm dimensions of objects on the mat (±0.2–0.5 mm flat-object accuracy; shadow-rejecting color-aware segmentation by default, `--seg gray\|color` to override; tall objects corrected via `--object-height`, with camera height auto-estimated from the markers when intrinsics exist) |
| `count IMG` | Exact object count — watershed splits touching objects; annotated image to verify |
| `scan INPUTS…` | Batch page detection, perspective correction, enhancement (`--mode color/gray/bw`) |

See [docs/cv-tools.md](docs/cv-tools.md) for setup and the accuracy contract.

### MCP vision servers — OCR and local VLMs

Three local MCP servers (registered in the workspace `.mcp.json`) round out the vision
stack — no API keys, captures never leave the machine:

- **`vlm`** (`scripts/cameraboi-vlm serve`) — the primary semantic-vision server:
  Qwen3.8-27B 4-bit on [MLX-VLM](https://github.com/Blaizzy/mlx-vlm), resident in memory.
  Captioning, VQA, text transcription, and reliable open-vocabulary bounding boxes on
  Apple Silicon (set `CAMERABOI_VLM_MODEL` to a smaller MLX VLM for the speed tier).
- **`ocr`** ([ocrtool-mcp](https://github.com/ihugang/ocrtool-mcp), `bin/ocrtool-mcp`) —
  verbatim text extraction via the Apple Vision framework, with per-line bounding boxes.
- **`moondream`** ([moondream-mcp](https://github.com/ColeMurray/moondream-mcp), via
  `uvx`) — legacy fallback VLM (~15–20 s/call); superseded by `vlm` for new work.

See [docs/mcp-vision.md](docs/mcp-vision.md) for tools, arguments, and when to use which.

```bash
scripts/cameraboi snap
scripts/cameraboi snap -d "MacBook Pro Camera" -o /tmp/desk.jpg
scripts/cameraboi record -t 10 --audio
scripts/cameraboi burst -n 12 -i 5
scripts/cameraboi frames ~/Pictures/cameraboi/demo.mp4 -n 12 --sheet
```

## How the vision loop works

Claude cannot see a camera. It can see an image file. So every workflow is: run a command,
read the path it printed.

**Stills** — `snap` writes a JPEG and prints its absolute path as the last stdout line.
Claude reads that path; Claude Code's Read tool renders images natively.

**Video** — reading an MP4 directly is useless. `record` captures the clip, then
`frames --sheet` tiles evenly spaced frames into contact sheets. Claude reads the sheets and
sees the whole clip's progression in one or two images instead of twenty.

**Monitoring** — `burst` produces a series of stills for slow-changing subjects. Cheaper and
sharper than video of something that barely moves.

The CLI's contract makes this mechanical: **the last stdout line(s) are the absolute paths
of the artifacts produced.** Failures exit non-zero with human-readable text on stderr, so
diagnostics never contaminate the artifact block.

```bash
IMG=$(scripts/cameraboi snap | tail -1)
```

## Troubleshooting

Run `scripts/cameraboi doctor` first — it separates the three failure modes, which need
three different fixes.

- **Capture fails but the device is listed** → camera permission. System Settings → Privacy &
  Security → Camera, enable your terminal app, then quit and reopen it. macOS will not
  re-prompt after a denial, and permission granted to one terminal app says nothing about
  another.
- **Device not found** → run `scripts/cameraboi devices`. If the V4K is unplugged, fall back
  to the built-in camera with `-d "MacBook Pro Camera"`.
- **Pixel format errors** → only when calling `ffmpeg` by hand. The V4K rejects `yuv420p`;
  cameraBoi always passes `-pixel_format uyvy422`.

Full guide: [docs/troubleshooting.md](./docs/troubleshooting.md).

## Documentation

- [Overview](./docs/index.md)
- [Getting Started](./docs/getting-started.md)
- [Command Reference](./docs/command-reference.md)
- [Using the Skill](./docs/skill-usage.md)
- [Troubleshooting](./docs/troubleshooting.md)
- [CV Tools](./docs/cv-tools.md)
- [MCP Vision Servers](./docs/mcp-vision.md)

## Layout

```
scripts/cameraboi        # the CLI — all capture logic
skills/cameraboi/        # the Claude Code skill (SKILL.md + references/)
bin/ocrtool-mcp          # Apple Vision OCR MCP server (release binary, v1.0.6)
docs/                    # project documentation
```

Captures are written to `~/Pictures/cameraboi/`, created on demand.
