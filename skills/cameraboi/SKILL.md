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
2. The **last stdout line is the path to Read**. High-res captures (wider than 2000px,
   e.g. `--max`) also get a model-sized `<name>-model.jpg` copy printed last — Read that
   one; the full-res original is the line above it.
3. **Read that path.** The Read tool renders JPEGs — that image becomes Claude's vision.
4. Describe / analyze / act on what is actually in the frame.

On success the capture also **opens in Preview automatically** so the user sees what was
taken (suppress with `--no-open` or `CAMERABOI_NO_OPEN=1`).

**Full resolution on request:** when the user explicitly asks for full resolution / full
quality / fine detail — or the task is transcribing fine text from a `--max` scan — use
`snap --full` (skips the model copy) or Read the full-res original (the line above the
model path) instead of the model copy.

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
| `snap` | `-o FILE` `-d DEVICE` `-r WxH` `--warmup N` `--max` `--full` `--no-open` | Still capture. Defaults: IPEVO V4K, 1920x1080@30, 15 warmup frames (lets auto-exposure settle), out `~/Pictures/cameraboi/snap-YYYYmmdd-HHMMSS.jpg`. `--max` attempts the V4K high-res photo mode, degrading gracefully. Opens in Preview on success. Captures >2000px wide emit a 1568px `-model.jpg` copy as the last stdout line; `--full` (alias `--no-model`) skips it — use when the user explicitly wants full resolution |
| `record` | `-t SECONDS` (required) `-o FILE` `-d DEVICE` `-r WxH` `--audio` | H.264 mp4, faststart, 1920x1080@30 default. `--audio` mixes in the device mic |
| `burst` | `-n COUNT` (required) `-i SECONDS` `-o DIR` | N stills at an interval — timelapse / watching a slow process |
| `frames` | `VIDEO` (positional) `-n N` `-o DIR` `--sheet` | Extracts N evenly-spaced frames (default 12); `--sheet` also tiles them into contact sheet(s) |
| `logs` | `--tail N` `--failures` `--json` | Queries the capture event log (default last 20, cap 200) — every capture appends one JSONL event (cmd, device, exit code, duration, artifact, ffmpeg stderr) |
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
  artifact belongs to the work at hand (e.g. a scan destined for the repo).
- Prefer one good snap over many. Take a second only when the first is unreadable or the
  user changed the scene.
- Announce what was captured and where it landed, so the user can find the file.
- Snapping is a real-world side effect: it turns on a camera pointed at the user's space.
  Capture when asked or when the task plainly needs vision — not speculatively, and never
  on a loop without the user asking for monitoring.
- Deeper patterns (multi-page document scanning, before/after comparison, resolution
  flags, worked transcripts) live in `references/usage.md` — read it when a capture needs
  more than a single snap.
