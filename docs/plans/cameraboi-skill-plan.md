# cameraBoi — Camera-as-a-Skill for Claude Code

## Goal

Give Claude Code a physical vision capability: a skill (like `claude-in-chrome` or
`playwright-cli`) that lets any session take pictures, record video, and "see" the real
world through the connected camera whenever the user says "use cameraBoi", asks for a
photo/video, or the task needs physical vision.

## Verified facts (recon done 2026-08-07)

- Host: macOS 26.5.2 (Darwin 25.5.0), Apple Silicon.
- `ffmpeg` present at `/opt/homebrew/bin/ffmpeg`; `imagesnap` NOT installed; `swiftc` present.
- AVFoundation video devices: `[0] IPEVO V4K`, `[1] MacBook Pro Camera`,
  `[2] MacBook Pro Desk View Camera`, `[3][4] Capture screens`.
- AVFoundation audio devices: `[0] IPEVO V4K`, `[1] MacBook Pro Microphone`.
- Camera TCC permission for this terminal is ALREADY GRANTED — a 1920x1080 test frame was
  captured successfully from "IPEVO V4K" and read back by Claude (vision loop proven).
- Device rejects `yuv420p` input pixel format; supported: `uyvy422, yuyv422, nv12, 0rgb, bgr0`
  → always pass `-pixel_format uyvy422`.

## Architecture

```
cameraBoi/                          (this repo — source of truth)
├── scripts/
│   └── cameraboi                   # single bash CLI, all capture logic
├── skills/cameraboi/
│   ├── SKILL.md                    # the skill definition Claude loads
│   └── references/usage.md         # deeper patterns kept out of SKILL.md body
├── docs/                           # project docs (Notion-sync structure)
├── captures -> ~/Pictures/cameraboi (default output dir, created on demand)
└── README.md

~/.claude/skills/cameraboi  →  symlink to skills/cameraboi   (global availability)
```

Design choice: **ffmpeg-only** (no new dependencies — already installed, does stills,
video, audio, frame extraction, contact sheets). No Swift build, no imagesnap.

## CLI contract (fixed — all agents build against this)

`scripts/cameraboi <command> [options]`, bash, shellcheck-clean, `set -euo pipefail`.

| Command | Behaviour |
|---|---|
| `devices` | Parse `ffmpeg -f avfoundation -list_devices true -i ""`; print video + audio device tables |
| `snap [-o FILE] [-d DEVICE] [-r WxH] [--warmup N] [--max]` | Still capture. Defaults: device `IPEVO V4K`, 1920x1080@30, warmup 15 frames (`-frames:v N -update 1` — last frame wins, lets auto-exposure settle), out `~/Pictures/cameraboi/snap-YYYYmmdd-HHMMSS.jpg`. `--max` tries the V4K's high-res photo mode (probe supported modes; fall back gracefully) |
| `record -t SECONDS [-o FILE] [-d DEVICE] [--audio] [-r WxH]` | H.264 mp4, `+faststart`, default 1920x1080@30; `--audio` adds the device mic (`"IPEVO V4K:IPEVO V4K"`) |
| `burst -n COUNT [-i SECONDS] [-o DIR]` | N stills at interval (timelapse/monitoring) |
| `frames VIDEO [-n N] [-o DIR] [--sheet]` | Extract N evenly-spaced frames; `--sheet` additionally tiles them into contact sheet(s) (ffmpeg `tile` filter) so Claude can "watch" a video in few Reads |
| `doctor` | Verify ffmpeg, device presence, run a live 640x480 test capture; on failure print TCC guidance (System Settings → Privacy & Security → Camera) |

Machine-parseable contract: **the last stdout line(s) are the absolute path(s) of produced
artifacts**. Non-zero exit + human-readable stderr on failure. Device-name matching is
case-insensitive substring (`-d ipevo` works); numeric `-d 1` selects by index.

## Skill design

- `skills/cameraboi/SKILL.md` frontmatter: name `cameraboi`; description triggering on:
  "cameraBoi", take a picture/photo/snapshot, record a video/clip, "look at this",
  "what do you see", "watch", document/whiteboard scan, any need for real-world vision.
- Body teaches the loop: run `scripts/cameraboi snap` → **Read the printed path** (Read
  renders images natively); for video: `record` → `frames --sheet` → Read the sheet(s);
  burst for monitoring. Includes troubleshooting (TCC, device unplugged → fallback to
  MacBook Pro Camera) and the capture-dir convention.
- Installed globally by symlinking `skills/cameraboi` → `~/.claude/skills/cameraboi`
  (single source of truth; repo updates propagate).

## Execution — Opus agent swarm (parallel, file-ownership disjoint)

| Agent | Model | Owns | Task |
|---|---|---|---|
| capture-engineer | opus | `scripts/` | Implement the CLI per contract; `bash -n` + shellcheck (if present); live-test `devices`, `doctor`, `snap` |
| skill-author | opus | `skills/` + `~/.claude/skills` symlink | SKILL.md + references/usage.md; install symlink |
| docs-author | opus | `README.md`, `docs/` (not this plan) | README + docs via docs-generator skill structure |

Orchestrator (me) then: end-to-end verification (doctor → snap → Read image → record 3s →
frames --sheet → Read sheet), fix anything broken, git init on a feature branch, commit.

## Debug logging — hwlog variant (added per /goal, 2026-08-07)

Adapted from gurul/hardware-logging (structured, crash-aware serial logging for agent
debugging): cameraBoi gets a camera-flavored variant so capture failures are debuggable
from recorded evidence, not reruns.

- Every CLI invocation appends one JSONL event to `~/Pictures/cameraboi/.sessions/events.jsonl`:
  `{ts, cmd, device, args, exit_code, duration_ms, artifact, ffmpeg_stderr}` —
  ffmpeg stderr is captured verbatim (truncated to 4 KiB per event, hwlog-style bounding).
- New subcommand `logs [--tail N] [--failures]` — bounded query (default last 20 events,
  hard cap 200); `--failures` filters exit_code != 0. Human-readable one-line-per-event
  output; `--json` for raw events.
- `doctor` reads the recent event log and surfaces the last failure inline.
- Atomic appends (single `>>` write per event); log dir owner-only (0700), matching
  hwlog's session-hygiene posture.

## Verification gates

1. `bash -n` clean; shellcheck clean if installed (no TS/linter in this repo — bash project;
   stated per Forced Verification directive).
2. `cameraboi doctor` passes live.
3. `snap` produces a JPEG that Claude Reads successfully (vision loop).
4. `record -t 3` + `frames --sheet` produce a readable contact sheet.
5. New Claude session sees the skill (symlink exists, SKILL.md valid frontmatter).

## Out of scope (v1)

Audio transcription, motion detection, streaming/live preview, Windows/Linux support,
iOS Continuity Camera pinning.

## Risks

- **TCC revocation / different terminal app**: doctor gives explicit fix instructions.
- **Device unplugged**: substring matching + documented fallback to built-in camera.
- **High-res mode probing**: V4K photo modes vary by fw; `--max` must degrade gracefully.
- **ffmpeg via brew upgrade**: pinning not needed; CLI probes at runtime.
