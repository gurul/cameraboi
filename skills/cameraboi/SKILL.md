---
name: cameraboi
description: Captures stills, video, and timelapse bursts from the connected camera (IPEVO V4K document camera, or the built-in Mac camera as fallback) and hands the files to Claude to Read, giving Claude real-world vision. Use whenever the user mentions cameraBoi, asks to take a picture/photo/snapshot, record a video or clip, scan a document/whiteboard/page/book, says "look at this", "what do you see", "watch this", "check my desk", holds something up to the camera, or whenever a task needs to see the physical world.
---

# cameraBoi — physical vision for Claude Code

The camera is Claude's eye. The CLI captures a file; **Read** renders it. Capturing
without Reading is pointless — the Read is where the seeing happens.

**CLI path (always use the absolute path — the skill is symlinked globally):**

```
~/Documents/work/cameraBoi/scripts/cameraboi
```

## The core loop — a still photo

1. Bash: `~/Documents/work/cameraBoi/scripts/cameraboi snap`
2. The **last stdout line is the path to Read**. Stills capture at the camera's native
   resolution by default, so they also get a model-sized `<name>-model.jpg` copy printed
   last — Read that one; the full-res original is the line above it.
3. **Read that path.** The Read tool renders JPEGs — that image becomes Claude's vision.
4. Describe / analyze / act on what is actually in the frame.

On success the capture also **opens in Preview automatically** so the user sees what was
taken (suppress with `--no-open` or `CAMERABOI_NO_OPEN=1`).

**Full resolution on request:** when the user explicitly asks for full resolution / full
quality / fine detail — or the task is transcribing fine text from a scan — use
`snap --full` (skips the model copy) or Read the full-res original (the line above the
model path) instead of the model copy. Capture is already native-res; this only changes
which file gets Read.

```bash
~/Documents/work/cameraBoi/scripts/cameraboi snap
# → /Users/<you>/Pictures/cameraboi/snap-20260807-151233.jpg
```

Then `Read /Users/<you>/Pictures/cameraboi/snap-20260807-151233.jpg`.

Never describe a capture from assumption. If the user asks what Claude sees, there must
be a Read of the captured artifact in the transcript first.

## Video — record, then watch it as contact sheets

Claude cannot play video. Convert it to frames, tile them, and Read the tiles.

```bash
~/Documents/work/cameraBoi/scripts/cameraboi record -t 8            # → /…/rec-<ts>.mp4
~/Documents/work/cameraBoi/scripts/cameraboi frames /…/rec-<ts>.mp4 -n 12 --sheet
# → frame paths, then the sheet path(s): /…/frames-<ts>/contact-sheet.jpg
#   (>16 frames chunks into contact-sheet-01.jpg, contact-sheet-02.jpg, …)
```

Read the sheet(s) — one or two Reads cover the whole clip. Add `--audio` to `record`
when the sound matters to the user's own playback (Claude does not transcribe audio).

## Monitoring and timelapse

```bash
~/Documents/work/cameraBoi/scripts/cameraboi burst -n 6 -i 10   # 6 stills, 10s apart
```

Each produced path is printed. Read the first and last to judge change; Read the
in-between frames only when something actually moved.

## Precision & exactness — the cameraboi-cv companion

For **measurements in mm**, **exact counts**, or **batch scan cleanup**, do not estimate
from the image — shell out to the deterministic CV CLI:

```
~/Documents/work/cameraBoi/scripts/cameraboi-cv
```

(first run bootstraps its own venv; same contract — last stdout lines are artifact paths)

- **"How big is this?"** → object on the printed measuring mat → `snap --full --no-open`
  → `cameraboi-cv measure <img>` → JSON in mm + an annotated image. **Read the annotated
  image** to confirm the segmentation grabbed the right object before reporting numbers.
  Requires the mat (one-time: `cameraboi-cv mat`, print at 100%). If the command refuses
  because markers are missing, tell the user to uncover the mat corners — never
  eyeball-estimate dimensions instead. Flat objects: ±0.2–0.5 mm. Tall objects read
  large by ~`thickness / camera height` unless `--object-height` is given (camera
  height auto-estimates from the markers once intrinsics are calibrated; else pass
  `--camera-height` too) — say so. Shadows are rejected by default (`--seg auto`);
  for a colored object prefer `--seg color` (immune to the dark contact shadow at
  the base), and for a neutral-gray object use `--seg gray`.
- **"How many are there?"** → `cameraboi-cv count <img>` → exact count + numbered
  annotated image. Read the annotation and sanity-check it against the scene; tune
  `--min-area` / `--min-sep` if the segmentation visibly missed or merged objects.
  For piles too jumbled to segment, say counting needs the objects spread out.
- **"Scan these pages"** → snap each page, then `cameraboi-cv scan <dir> --mode bw`
  (or `gray`) → deskewed, perspective-corrected, shadow-free pages. Read the cleaned
  outputs for transcription — they OCR better than raw photos.
- One-time lens calibration sharpens measurement at the frame edges:
  `cameraboi-cv board` → print → ~15 varied snaps → `cameraboi-cv calibrate <dir>`.

Claude's vision judges *what* things are; `cameraboi-cv` supplies the numbers. Combine
them: measure/count with the CLI, verify with a Read, describe with vision.

## Exact text — the OCR MCP

For **verbatim transcription** (serial numbers, part codes, receipts, dense pages), do
not transcribe by eye from the Read — call the `ocr` MCP server's `ocr_extract_text`
tool on the captured file (Apple Vision framework, local, per-line bounding boxes):

- Pass the **full-res original** path (`snap --full` output), never the model copy —
  OCR accuracy comes from pixels Claude's own vision doesn't need.
- `format: "structured"` returns JSON with pixel bounding boxes (origin bottom-left);
  `lang` defaults to `zh+en` — pass `"en"` (or the right codes) explicitly.
- Best on `scan`-cleaned pages: snap → `cameraboi-cv scan` → OCR the cleaned output.
- Eyes still matter: Read the image too, and use OCR for the characters, vision for
  the layout and meaning. If OCR and vision disagree on a critical string, say so.

If the `ocr` tools are absent (server not loaded), fall back to Reading the full-res
capture and say the transcription is by eye, not OCR.

## Localization & semantics — the vlm MCP

For **"where exactly is the X"** — pixel bounding boxes of a named object — and for
machine-readable captions/VQA, use the `vlm` MCP server (Qwen3-VL 4-bit on MLX,
resident in memory; the first call of a session loads the model, allow ~30 s cold,
then ~6 s per call):

- `vlm_find {image_path, objects}` → open-vocabulary bounding boxes + centers **in
  original image pixels**, plus an annotated `-vlm-find.png` written next to the
  source. The reliable localization tool; also a semantic cross-check on
  `cameraboi-cv count`. Pass the full-res original — coordinates are mapped back.
- `vlm_query {image_path, question}` / `vlm_describe {image_path}` → VQA and
  captioning; prefer Claude's own Read for judgement, `vlm` when a machine-readable
  or coordinate-grounded answer is needed.
- `vlm_read_text {image_path}` → transcription that handles handwriting and odd
  layouts; use `ocr` instead when you need per-line boxes.
- An empty `objects` result means "unlocated", not "absent" — say so.

A `moondream` server may also be registered (legacy fallback, ~15–20 s/call, weak
boxes); prefer `vlm` whenever both are present.

Division of labor: Claude's vision for meaning, `vlm` for coordinates,
`cameraboi-cv` for calibrated numbers, `ocr` for characters. VLM output estimates —
never report its counts or sizes as exact; route those to `cameraboi-cv`.

## Device selection

Default is the **IPEVO V4K** document camera. `-d` takes a case-insensitive substring or
a numeric index:

```bash
… snap -d "macbook"    # built-in FaceTime camera — fallback when the V4K is unplugged
… snap -d 1            # by index, as listed by `devices`
… devices              # list what is actually attached right now
```

## Command reference

| Command | Flags | Notes |
|---|---|---|
| `devices` | — | Lists attached video + audio devices with their indices |
| `snap` | `-o FILE` `-d DEVICE` `-r WxH` `--warmup N` `--full` `--no-open` | Still capture. Defaults: IPEVO V4K, **native (highest advertised) resolution** probed at runtime (3264x2448 on the V4K; falls back to 1920x1080 if probing fails), 15 warmup frames (lets auto-exposure settle), out `~/Pictures/cameraboi/snap-YYYYmmdd-HHMMSS.jpg`. `-r WxH` forces a specific size; `--max` is a legacy no-op alias. Opens in Preview on success. Captures >2000px wide emit a 1568px `-model.jpg` copy as the last stdout line; `--full` (alias `--no-model`) skips it — use when the user explicitly wants full resolution |
| `record` | `-t SECONDS` (required) `-o FILE` `-d DEVICE` `-r WxH` `--audio` | H.264 mp4, faststart, 1920x1080@30 default. `--audio` mixes in the device mic |
| `burst` | `-n COUNT` (required) `-i SECONDS` `-o DIR` | N stills at an interval — timelapse / watching a slow process |
| `frames` | `VIDEO` (positional) `-n N` `-o DIR` `--sheet` | Extracts N evenly-spaced frames (default 12); `--sheet` also tiles them into contact sheet(s) |
| `logs` | `--tail N` `--failures` `--json` | Queries the capture event log (default last 20, cap 200) — every capture appends one JSONL event (cmd, device, exit code, duration, artifact, ffmpeg stderr) |
| `clean` | `--older-than AGE` `--logs` `--yes` | Deletes captured artifacts (`snap-*`, `rec-*`, `burst-*/`, `frames-*/`) from the capture dir; other files are never touched. **Dry run by default** — lists what would go; only `--yes` deletes. `--older-than 7d/24h/30m` age-filters; `--logs` also clears the event log. Deleting the user's captures is destructive: run without `--yes` first and confirm with the user unless they already asked for the deletion |
| `doctor` | — | Verifies ffmpeg, device presence, runs a live 640x480 test capture, and surfaces the last recorded capture failure |

Output contract for every command: **the last stdout line(s) are the absolute paths of
the produced artifacts**. Failures exit non-zero with a human-readable message on stderr.

## Troubleshooting

**Any capture failure → run `doctor` first.** It isolates whether the problem is ffmpeg,
the device, or permissions, and prints the fix. For failures that already happened
(including in earlier sessions), `logs --failures` replays the recorded evidence —
exit code, ffmpeg stderr, timing — so debug from the log, not from blind reruns.

- **Camera permission (TCC) denied** — the terminal app running Claude Code needs camera
  access. Fix: **System Settings → Privacy & Security → Camera** → enable the terminal
  app (Terminal / iTerm / Ghostty / VS Code — whichever hosts this session), then
  **fully quit and relaunch that app**; the grant does not apply to a running process.
- **Device not found / unplugged** — run `devices`. If the IPEVO V4K is absent, either
  reseat the USB cable or fall back to the built-in camera with `-d "macbook"`. Tell the
  user which camera was actually used when it is not the V4K.
- **Frame is black or badly exposed** — the sensor needed longer to settle. Retry with a
  larger warmup: `snap --warmup 40`.
- **Frame is blurry** — snap/record/burst auto-enable continuous autofocus on cameras
  that support it (the V4K does); check stderr for the `af:` lines. If AF ran and the
  frame is still soft, the subject may be too close for the lens — ask the user to
  raise the V4K arm or improve lighting, then snap again. `--no-af` /
  `CAMERABOI_NO_AF=1` disables the AF pass; `CAMERABOI_AF_SETTLE=2` gives the lens
  longer to settle.
- **Frame is cropped wrong** — this is physical. Ask the user to adjust the V4K arm,
  then snap again. Do not try to fix framing in software.

## Conventions

- Captures land in `~/Pictures/cameraboi/` unless `-o` is given. Pass `-o` when the
  artifact belongs to the work at hand (e.g. a scan destined for the repo). Captures
  persist until deleted — when the user wants them gone, use `clean` (dry-run first).
- Prefer one good snap over many. Take a second only when the first is unreadable or the
  user changed the scene.
- Announce what was captured and where it landed, so the user can find the file.
- Snapping is a real-world side effect: it turns on a camera pointed at the user's space.
  Capture when asked or when the task plainly needs vision — not speculatively, and never
  on a loop without the user asking for monitoring.
- Deeper patterns (multi-page document scanning, before/after comparison, resolution
  flags, worked transcripts) live in `references/usage.md` — read it when a capture needs
  more than a single snap.
