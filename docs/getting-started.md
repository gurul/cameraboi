---
title: Getting Started
icon: 🚀
order: 2
---

# Getting Started

## Prerequisites

**macOS.** cameraBoi captures through AVFoundation, which is macOS-only. It was built and
verified on a macOS 26.x host.

**ffmpeg.** The only external dependency:

```bash
brew install ffmpeg
```

**A camera.** The default device is an IPEVO V4K document camera. Any AVFoundation camera
works — the built-in MacBook camera, a USB webcam, a capture device.

**Camera permission.** macOS gates camera access per application. The permission belongs to
the *terminal app* that runs the CLI (Terminal, iTerm, Ghostty, VS Code, …), not to
cameraBoi itself. Grant it under **System Settings → Privacy & Security → Camera**. The
first capture attempt normally triggers the prompt; if it was denied once, you have to
re-enable it by hand.

## Verify the setup

```bash
scripts/cameraboi doctor
```

`doctor` checks that `ffmpeg` is present, that the target device exists, and then runs a
live 640x480 test capture. If the capture fails it prints the permission guidance above.
Fix whatever it reports before going further — every other command depends on the same
three things.

List what the machine can actually see:

```bash
scripts/cameraboi devices
```

This prints the AVFoundation video and audio device tables. On the reference machine the
video devices are `[0] IPEVO V4K`, `[1] MacBook Pro Camera`,
`[2] MacBook Pro Desk View Camera`, and two capture-screen entries at `[3]` and `[4]`; the
audio devices are `[0] IPEVO V4K` and `[1] MacBook Pro Microphone`.

Note that the IPEVO V4K appears in both tables — it exposes video and audio, which is what
makes `record --audio` work against a single device name.

## First capture

```bash
scripts/cameraboi snap
```

The last line of stdout is the absolute path of the JPEG, under
`~/Pictures/cameraboi/`. Open it, or hand the path to Claude.

## Install the skill

The skill is installed globally by symlinking it into your Claude skills directory. One
line, from the repo root:

```bash
ln -s "$PWD/skills/cameraboi" ~/.claude/skills/cameraboi
```

A symlink rather than a copy means the repo stays the single source of truth — pull an
update to cameraBoi and every Claude session picks it up with no reinstall.

Verify it took:

```bash
ls -l ~/.claude/skills/cameraboi
```

New Claude Code sessions will now list `cameraboi` among the available skills.

## Use it from Claude

Start a new Claude Code session and ask:

> use cameraBoi to take a picture and tell me what you see

Claude runs `snap`, reads the printed path, and describes the frame. See
[Using the Skill](./skill-usage.md) for the other phrasings that trigger it and the video
workflow.

## Next steps

- [Command Reference](./command-reference.md) — all six commands in detail
- [Troubleshooting](./troubleshooting.md) — when `doctor` is unhappy
