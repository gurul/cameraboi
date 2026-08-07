---
title: Troubleshooting
icon: 🔧
order: 5
---

# Troubleshooting

## Start with doctor

```bash
scripts/cameraboi doctor
```

`doctor` exists so you do not have to guess which of the three failure modes you have hit.
It checks `ffmpeg`, then the device list, then runs a live 640x480 test capture. Each stage
fails differently and needs a different fix:

| Stage that fails | Cause | Fix |
|---|---|---|
| `ffmpeg` check | Not installed or not on `PATH` | `brew install ffmpeg` |
| Device check | Camera unplugged, asleep, or renamed | See [Device not found](#device-not-found) |
| Test capture | Camera permission denied | See [Camera permission](#camera-permission-tcc) |

A green `doctor` means capture works right now, with the real permission path exercised —
not inferred. It also prints the most recent recorded capture failure from the event log.

## Debug from the event log

Every capture appends a JSONL event (command, device, exit code, duration, artifact, up to
4 KiB of ffmpeg stderr) to `~/Pictures/cameraboi/.sessions/events.jsonl`. When a capture
failed earlier — even in a previous session — the evidence is already on disk:

```bash
scripts/cameraboi logs --failures          # what failed, when, how long it took
scripts/cameraboi logs --failures --json   # includes the full captured ffmpeg stderr
```

Read the recorded stderr before rerunning anything; the answer is usually already there.
See [command reference → logs](./command-reference.md#logs).

## Camera permission (TCC)

This is the most common failure, and the most confusing, because the permission does not
belong to cameraBoi.

macOS grants camera access **per application**. The app that matters is the terminal
program running the CLI — Terminal, iTerm2, Ghostty, VS Code, or the host running your
Claude Code session. cameraBoi is a bash script; it inherits whatever its parent app was
granted.

**Fix:** System Settings → Privacy & Security → Camera → enable the terminal application
you are using.

> [!IMPORTANT]
> If you denied the prompt the first time, macOS will not ask again. You have to enable it
> by hand at the path above.

Two follow-on gotchas:

- **Quit and reopen the terminal app** after changing the setting. A running process may
  keep the old, denied state.
- **Switching terminal apps resets you to square one.** Permission granted to iTerm says
  nothing about Ghostty. If cameraBoi worked yesterday and fails today from a different
  terminal, this is why.

Symptoms of a permission denial rather than a missing device: the device *is* listed by
`cameraboi devices`, but capture fails or returns black or empty frames.

## Device not found

List what AVFoundation actually sees:

```bash
scripts/cameraboi devices
```

If the IPEVO V4K is absent, it is unplugged, on a dead hub, or on a port that lost power.
Reseat it and re-run.

**To keep working without it,** fall back to the built-in camera:

```bash
scripts/cameraboi snap -d "MacBook Pro Camera"
```

Device matching is a case-insensitive substring, so `-d macbook` is enough. Numeric indexes
work too (`-d 1`) but shift whenever hardware is plugged or unplugged — prefer names for
anything you repeat.

## Pixel format errors

If you see an `ffmpeg` error about the input pixel format, you are almost certainly invoking
`ffmpeg` directly rather than through cameraBoi.

The IPEVO V4K **rejects `yuv420p` input**. It accepts `uyvy422`, `yuyv422`, `nv12`, `0rgb`,
and `bgr0`. cameraBoi always passes `-pixel_format uyvy422`, which is why its captures work
and a hand-rolled `ffmpeg` command frequently does not. Add that flag to your own command.

## Dark, washed out, or blurry stills

Auto-exposure and auto-white-balance need frames to converge on. `snap` captures a warm-up
run of 15 frames by default and keeps the last one, precisely to avoid this. In difficult
light, give it longer:

```bash
scripts/cameraboi snap --warmup 30
```

For document and whiteboard scans, combine a longer warm-up with the high-resolution mode:

```bash
scripts/cameraboi snap --max --warmup 30
```

If `--max` produces nothing better than the standard capture, the camera's firmware does not
advertise a higher still mode — `--max` degrades gracefully rather than failing, so this is
expected on some V4K firmware revisions.

## Claude captured something but did not look at it

The capture is only half the loop. Claude has to **Read** the printed path — that is where
the image is actually rendered. If a session reports a file path and stops, ask it to read
the file.

For video, reading the MP4 directly does not work. Convert it first:

```bash
scripts/cameraboi frames <video> -n 12 --sheet
```

Then read the contact sheets.

## Scripting against the CLI

If your own script is mis-parsing output, remember the contract: **the last stdout line(s)
are the absolute artifact paths**, and failures exit non-zero with human-readable text on
**stderr**. Diagnostics never appear in the stdout artifact block.

```bash
if IMG=$(scripts/cameraboi snap | tail -1); then
  echo "captured: $IMG"
else
  echo "capture failed" >&2
fi
```

## The skill is not showing up

Check the symlink:

```bash
ls -l ~/.claude/skills/cameraboi
```

It should point at `skills/cameraboi` inside this repo. If it is missing, re-run the install
from the repo root:

```bash
ln -s "$PWD/skills/cameraboi" ~/.claude/skills/cameraboi
```

Skills are discovered when a session starts, so **start a new Claude Code session** after
installing. An already-running session will not see it.
