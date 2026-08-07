---
title: Using the Skill
icon: 👁️
order: 4
---

# Using the Skill

The CLI is usable on its own, but the point of cameraBoi is that Claude reaches for it
unprompted when a task needs eyes. That is what `skills/cameraboi/` provides.

## Installing

Symlink the skill directory into your global Claude skills folder, from the repo root:

```bash
ln -s "$PWD/skills/cameraboi" ~/.claude/skills/cameraboi
```

A symlink, not a copy — the repo remains the single source of truth, and updates propagate
to every session without a reinstall. New Claude Code sessions pick the skill up
automatically.

## What triggers it

The skill's description is written to fire on the ways people actually ask for a camera, not
just on the tool's name. Claude loads it when you:

- name **cameraBoi** directly
- ask it to **take a picture, photo, or snapshot**
- ask it to **record a video or clip**
- ask it to **scan** a document, whiteboard, page, or book
- say **"look at this"**, **"what do you see"**, **"watch this"**, **"check my desk"**
- **hold something up to the camera**
- or give it any task that simply cannot be done without seeing the physical world

Some examples that work:

> use cameraBoi to take a picture and tell me what you see

> what's written on this whiteboard?

> record 10 seconds and tell me if the print head is wobbling

> I'm holding up a component — what is it?

## The loop Claude runs

The camera is the eye; **Read** is the seeing. Capturing a file without reading it
accomplishes nothing, so every workflow ends in a Read.

### Stills

1. Run `cameraboi snap`.
2. Take the **last stdout line** — the absolute path of the JPEG.
3. Read that path. Claude Code's Read tool renders images natively.
4. Describe, extract, compare — whatever the task asked for.

### Video

Reading a video file directly is not useful. The skill converts a clip into images first:

1. `cameraboi record -t SECONDS` → an MP4 path.
2. `cameraboi frames <video> -n N --sheet` → extracted frames plus tiled contact sheets.
3. Read the **sheets**, not the individual frames. One or two images carry the whole clip's
   progression, which is a fraction of the reads and a fraction of the context.

### Monitoring over time

For a slow-changing subject, `cameraboi burst -n COUNT -i SECONDS` produces a series of
stills. Claude reads them in sequence and reports what changed between them. Cheaper and
sharper than recording video of something that barely moves.

## Why the last-line convention matters here

The skill relies on the CLI's promise that **the last stdout line(s) are the absolute paths
of the produced artifacts**. That is what makes the hand-off from Bash to Read mechanical:
Claude does not have to parse status chatter or guess at a filename built from a timestamp
it cannot see. Any change to that convention breaks the loop, which is why it is part of the
frozen contract rather than an implementation detail.

## Reference material

`skills/cameraboi/references/usage.md` holds the deeper patterns — the ones that would bloat
the skill body if inlined. Claude reads it on demand when a task needs more than the core
loop.

## Practical notes for sessions

- **Absolute paths only.** The skill invokes the CLI by absolute path, because a Claude
  session's working directory is rarely the cameraBoi repo.
- **Device fallback.** If the IPEVO V4K is unplugged, `-d "MacBook Pro Camera"` switches to
  the built-in camera. Claude is told to do this rather than give up.
- **When in doubt, `doctor`.** The skill runs it before concluding that the camera is
  broken — it distinguishes a missing `ffmpeg`, a missing device, and a permission denial,
  which need three different fixes. See [Troubleshooting](./troubleshooting.md).
