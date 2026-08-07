---
title: cameraBoi
icon: 📷
order: 1
---

# cameraBoi

cameraBoi gives Claude Code physical vision. It is a Claude Code skill plus a single bash
CLI that drives the camera attached to your Mac, so a Claude session can take a photo,
record a clip, or watch a scene over time and then actually look at what it captured.

The capture side is `scripts/cameraboi`, a bash wrapper around `ffmpeg`. The skill side is
`skills/cameraboi/`, which teaches Claude when to reach for the camera and what to do with
the resulting files.

## Quick links

- [Getting Started](./getting-started.md) — prerequisites, install, first capture
- [Command Reference](./command-reference.md) — every command, flag, and default
- [Using the Skill](./skill-usage.md) — how Claude drives the camera in a session
- [Troubleshooting](./troubleshooting.md) — permissions, missing devices, `doctor`

## What it does

- **Stills** — `snap` captures a JPEG, with a warm-up burst so auto-exposure settles before
  the frame that gets kept.
- **Video** — `record` captures H.264 MP4, optionally with the camera's microphone.
- **Time series** — `burst` takes N stills at a fixed interval for timelapse or monitoring.
- **Video as images** — `frames` pulls evenly spaced frames out of a video and can tile them
  into contact sheets, so Claude can review a clip in a handful of reads.
- **Self-diagnosis** — `doctor` checks `ffmpeg`, checks the device, runs a live test capture,
  and prints permission guidance when the capture fails.

## How the vision loop works

Claude cannot see a camera. It can see an image file. Every cameraBoi workflow is the same
two steps: run a command, then read the path the command printed.

```
snap  ──► /Users/you/Pictures/cameraboi/snap-20260807-151022.jpg ──► Claude reads the image
record ──► clip.mp4 ──► frames --sheet ──► sheet-001.jpg ──► Claude reads the sheet
```

The CLI makes that mechanical: **the last line(s) of stdout are the absolute paths of the
artifacts it produced.** Nothing has to be parsed out of prose.

## Requirements

- macOS (the host this was built and verified on runs macOS 26.x)
- `ffmpeg` — the only external dependency
- A camera visible to AVFoundation. The default is an **IPEVO V4K** document camera; any
  AVFoundation device works, including the built-in MacBook camera.
- Camera permission granted to whichever terminal app runs the CLI

There is no build step, no package manager, and no runtime beyond bash and `ffmpeg`.

## Where captures go

Everything lands in `~/Pictures/cameraboi/` unless you pass an explicit output path. The
directory is created on demand — nothing to set up in advance.
