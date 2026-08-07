# cameraBoi — deeper usage patterns

Everything here assumes the CLI at `~/Documents/work/cameraBoi/scripts/cameraboi` and the
core rule from SKILL.md: **capture → Read the printed path**. Paths below are abbreviated
as `/…/` for readability; the CLI always prints absolute paths.

---

## 1. Multi-shot document scanning

The IPEVO V4K is a document camera on an arm — it is pointed down at a page, not at a
face. Scanning multiple pages is a loop of snap → Read → confirm → ask for the next page.

```bash
CB=~/Documents/work/cameraBoi/scripts/cameraboi

$CB snap --max -o ~/Pictures/cameraboi/scan/page-01.jpg
# → /Users/you/Pictures/cameraboi/scan/page-01.jpg
```

Read `page-01.jpg`, transcribe or extract what is needed, then tell the user to turn the
page and repeat with `page-02.jpg`. Keep the numbering zero-padded so the files sort.

Guidelines that matter in practice:

- **Use `--max` for text.** Higher resolution is the difference between readable and
  unreadable small print. If `--max` is unsupported by the attached firmware the CLI
  falls back to the standard mode — no error, just a lower-resolution file.
- **Read every page before asking for the next one.** If page 3 came out blurry, you want
  to know at page 3, not after page 12.
- **Report unreadable regions honestly.** If a column is cut off or glare washes out a
  paragraph, say so and ask for a re-snap with the page moved — do not infer the missing
  words.
- **Whiteboards** are the same flow with the built-in or a repositioned camera: `-d`
  whichever device actually faces the board, `--max`, and one snap per board region if it
  does not fit in a single frame.

## 2. Before / after comparison

Two snaps to distinct paths, both Read, then compare explicitly.

```bash
$CB snap -o /tmp/before.jpg
# … user changes the physical thing …
$CB snap -o /tmp/after.jpg
```

Read `/tmp/before.jpg`, then `/tmp/after.jpg`, then describe the delta. Two points that
save wasted turns:

- **Do not move the camera between shots.** A reframed camera makes every pixel differ
  and the comparison worthless. If the user moved it, say the comparison is unreliable.
- **Read both in the same turn** when possible, so both images are in context
  simultaneously — comparing against a remembered image from ten turns ago is guessing.

## 3. Watching a physical process with `burst`

`burst` is for slow change: a print job, a solder reflow, a plant, a build's physical
output, a queue of people. Pick the interval so the whole process fits in a reasonable
frame count.

```bash
$CB burst -n 12 -i 15 -o ~/Pictures/cameraboi/watch-print
# → 12 absolute paths, one per line
```

Then triage rather than Reading all twelve:

1. Read the **first** and **last** frame — did anything change at all?
2. If yes, Read the **middle** frame to bisect when it changed.
3. Continue bisecting only until the moment of change is located.

For a continuous few seconds rather than a slow process, prefer `record` + `frames
--sheet` — a contact sheet is one Read for a dozen frames.

## 4. Video → contact sheets, in detail

```bash
$CB record -t 10 -o /tmp/clip.mp4
$CB frames /tmp/clip.mp4 -n 16 --sheet -o /tmp/clip-frames
# → /tmp/clip-frames/frame-001.jpg … frame-016.jpg
# → /tmp/clip-frames/contact-sheet.jpg   (>16 frames: contact-sheet-01.jpg, -02.jpg, …)
```

- Read the **sheet** first. Individual frames are already on disk; Read one full-size only
  when a tile is too small to judge (fine text, a small indicator light).
- `-n` trades detail for coverage. 9–16 frames is the useful band for a short clip; more
  frames per sheet means smaller, less legible tiles.
- `--audio` records the device mic into the mp4. It is for the user's own playback —
  Claude reads frames, not sound, so audio never affects what Claude can describe.
- Long clips are a false economy. Two short targeted recordings usually beat one long one.

## 5. Resolution flags

| Flag | Effect |
|---|---|
| `-r WxH` | Requests an explicit capture mode, e.g. `-r 1280x720`. Must be a mode the device actually supports — run `devices` if unsure |
| `--max` | Asks for the V4K's highest available photo mode. Probes supported modes and degrades gracefully to the default if the mode is unavailable |
| *(neither)* | 1920x1080 @ 30fps — the right default for a scene, a face, or a person holding something up |

Rules of thumb: `--max` for anything with text on it (documents, whiteboards, screens,
labels, serial numbers). Default 1080p for scenes and objects. Lower `-r` only when the
file size actually matters, such as a long burst.

## 6. Pixel format constraint (already handled — context only)

The IPEVO V4K rejects `yuv420p` input. Supported input formats are `uyvy422, yuyv422,
nv12, 0rgb, bgr0`. **The CLI always passes `-pixel_format uyvy422` internally**, so no
caller ever needs to think about it.

It is documented here for one reason: if you ever see an ffmpeg error mentioning a pixel
format or "Selected pixel format is not supported", the fix belongs in the CLI, not in a
hand-rolled ffmpeg command at the call site. Do not bypass the CLI with raw ffmpeg —
that is how this constraint reappears.

## 7. End-to-end transcripts

### "What's on my desk?"

```
$ ~/Documents/work/cameraBoi/scripts/cameraboi snap
/Users/you/Pictures/cameraboi/snap-20260807-151233.jpg
```

→ Read that path → describe the frame → tell the user where the file landed.

### "Scan this page for me"

```
$ ~/Documents/work/cameraBoi/scripts/cameraboi snap --max -o ~/Pictures/cameraboi/scan/page-01.jpg
/Users/you/Pictures/cameraboi/scan/page-01.jpg
```

→ Read it → transcribe → "Ready for page 2 whenever you turn it."

### "Watch me do this for 10 seconds"

```
$ ~/Documents/work/cameraBoi/scripts/cameraboi record -t 10
/Users/you/Pictures/cameraboi/rec-20260807-151455.mp4

$ ~/Documents/work/cameraBoi/scripts/cameraboi frames /Users/you/Pictures/cameraboi/rec-20260807-151455.mp4 -n 12 --sheet
/Users/you/Pictures/cameraboi/frames-20260807-151502/frame-001.jpg
… (12 frames) …
/Users/you/Pictures/cameraboi/frames-20260807-151502/contact-sheet.jpg
```

→ Read `contact-sheet.jpg` → narrate the sequence → Read an individual frame only if a
moment needs a closer look.

### Capture failed

```
$ ~/Documents/work/cameraBoi/scripts/cameraboi snap
cameraboi: capture failed — no frames from "IPEVO V4K"
$ echo $?
1
```

→ Run `doctor` → follow its guidance (TCC grant, or `devices` then `-d "macbook"`) →
retry once → if it still fails, report the exact stderr to the user rather than retrying
in a loop.

## 8. Debugging from the event log

Every capture command appends one JSONL event to
`~/Pictures/cameraboi/.sessions/events.jsonl` — timestamp, command, resolved device,
args, exit code, duration, artifact path, and up to 4 KiB of ffmpeg stderr. This is
the hwlog pattern (structured, bounded, crash-aware logging) applied to the camera:
**debug from recorded evidence, not blind reruns.**

```bash
$CB logs                     # last 20 events, one line each
$CB logs --failures          # only failed captures (the ffmpeg stderr is in the event)
$CB logs --tail 50 --json    # raw JSONL for programmatic inspection (cap 200)
```

`doctor` also prints the most recent recorded failure, so a single doctor run shows
both the live state and the last thing that went wrong — including failures from
previous sessions that scrolled away.

## 9. Anti-patterns

1. **Capturing without Reading.** The file on disk is not vision. Read it.
2. **Describing the scene from context instead of the image.** If there is no Read, there
   is no observation — only a guess.
3. **Hand-rolling ffmpeg.** Reintroduces the pixel-format bug, the warmup problem, and
   the path contract. Use the CLI.
4. **Retry loops on failure.** Run `doctor` once, apply the fix, retry once, then report.
5. **Reading every burst/`frames` output.** Bisect, or Read the contact sheet.
6. **Snapping speculatively or repeatedly without being asked.** A capture points a live
   camera at the user's physical space — take one when it is asked for or plainly needed,
   and say what was taken.
