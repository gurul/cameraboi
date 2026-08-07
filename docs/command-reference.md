---
title: Command Reference
icon: 📖
order: 3
---

# Command Reference

```bash
scripts/cameraboi <command> [options]
```

A single bash script. No subcommand aliases, no config file, no environment variables —
everything is a flag.

| Command | Purpose |
|---|---|
| `devices` | List AVFoundation video and audio devices |
| `snap` | Capture a still image |
| `record` | Record an H.264 MP4 clip |
| `burst` | Capture N stills at a fixed interval |
| `frames` | Extract frames from a video, optionally as contact sheets |
| `doctor` | Check dependencies, device, and permission with a live test capture |

## Conventions that apply to every command

### Artifact paths are the last stdout lines

**The last line, or lines, that the CLI writes to stdout are the absolute paths of the
artifacts it produced.** That is the machine-parseable contract, and it is what lets Claude
chain a capture straight into a file read without interpreting human prose.

```bash
IMG=$(scripts/cameraboi snap | tail -1)
```

For commands that emit several artifacts — `burst`, `frames` — the trailing block is one
absolute path per line.

### Failure is a non-zero exit

On failure the command exits non-zero and writes a human-readable explanation to **stderr**.
Diagnostics never contaminate the stdout artifact block.

### Device selection

`-d` accepts either form:

| Form | Behaviour | Example |
|---|---|---|
| Name | Case-insensitive substring match against the device list | `-d ipevo` |
| Index | Numeric AVFoundation device index | `-d 1` |

Substring matching is deliberate: `-d ipevo` keeps working when the enumerated name varies,
and `-d "MacBook Pro Camera"` is a documented fallback when the document camera is
unplugged. The default device is **IPEVO V4K**.

> [!NOTE]
> Indexes are assigned by AVFoundation and shift when you plug or unplug hardware. Prefer
> a name substring in anything you script or repeat.

### Default output location

Captures default to `~/Pictures/cameraboi/`, created on demand. Still filenames follow
`snap-YYYYmmdd-HHMMSS.jpg`. Pass `-o` to override the file (or, for `burst` and `frames`,
the directory).

### The uyvy422 pixel format constraint

Every capture passes `-pixel_format uyvy422` to `ffmpeg`. This is not a tuning choice — the
IPEVO V4K **rejects `yuv420p` input outright**. The formats it accepts are `uyvy422`,
`yuyv422`, `nv12`, `0rgb`, and `bgr0`, and `uyvy422` is the one cameraBoi standardizes on.

If you invoke `ffmpeg` against this camera by hand and get a pixel-format error, this is
why. The constraint is on the AVFoundation *input*; the encoded output is ordinary JPEG or
H.264.

---

## devices

Lists the cameras and microphones AVFoundation can see, by parsing
`ffmpeg -f avfoundation -list_devices true -i ""`. Video and audio are printed as separate
tables, each entry with its index and name.

```bash
scripts/cameraboi devices
```

Run this whenever a capture reports a missing device, or before scripting an index.

## snap

Captures a single still image.

```bash
scripts/cameraboi snap [-o FILE] [-d DEVICE] [-r WxH] [--warmup N] [--max]
```

| Flag | Default | Description |
|---|---|---|
| `-o FILE` | `~/Pictures/cameraboi/snap-YYYYmmdd-HHMMSS.jpg` | Output file path |
| `-d DEVICE` | `IPEVO V4K` | Device name substring or index |
| `-r WxH` | `1920x1080` (at 30 fps) | Capture resolution |
| `--warmup N` | `15` frames | Frames to pull before keeping one |
| `--max` | off | Try the V4K's high-resolution photo mode |

**Warm-up is why the images are usable.** A USB camera's first frames are captured before
auto-exposure and auto-white-balance converge, so a naive single-frame grab is typically
dark or colour-cast. `snap` requests `--warmup` frames with `-frames:v N -update 1`, which
overwrites the output file on each frame — the last frame wins, and by then the sensor has
settled. Raise it in difficult light; lower it if you need the shutter to fire faster.

`--max` probes the camera's supported modes and captures at the highest still resolution it
advertises. V4K photo modes vary by firmware, so this degrades gracefully: if the probe
finds nothing better, the capture proceeds at the standard resolution rather than failing.

```bash
# default: IPEVO V4K, 1920x1080, into ~/Pictures/cameraboi/
scripts/cameraboi snap

# built-in camera, to an explicit path
scripts/cameraboi snap -d "MacBook Pro Camera" -o /tmp/desk.jpg

# document scan: highest available resolution, longer settle
scripts/cameraboi snap --max --warmup 30
```

Prints the absolute path of the image as its last stdout line.

## record

Records an H.264 MP4 clip.

```bash
scripts/cameraboi record -t SECONDS [-o FILE] [-d DEVICE] [--audio] [-r WxH]
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `-t SECONDS` | yes | — | Clip duration |
| `-o FILE` | no | timestamped file under `~/Pictures/cameraboi/` | Output file path |
| `-d DEVICE` | no | `IPEVO V4K` | Device name substring or index |
| `-r WxH` | no | `1920x1080` (at 30 fps) | Capture resolution |
| `--audio` | no | off | Also record the device's microphone |

Output is H.264 in MP4 with `+faststart`, so the moov atom sits at the head of the file and
the clip is seekable immediately rather than only after a full read.

`--audio` pairs the camera with its own microphone — for the default device that is the
AVFoundation pair `"IPEVO V4K:IPEVO V4K"`, video and audio from one piece of hardware.
Without the flag the clip is silent.

```bash
# 10 seconds, video only
scripts/cameraboi record -t 10

# 30 seconds with sound, to a named file
scripts/cameraboi record -t 30 --audio -o ~/Pictures/cameraboi/demo.mp4
```

Prints the absolute path of the MP4 as its last stdout line.

## burst

Captures a series of stills at a fixed interval — timelapse, or monitoring something that
changes slowly.

```bash
scripts/cameraboi burst -n COUNT [-i SECONDS] [-o DIR]
```

| Flag | Required | Description |
|---|---|---|
| `-n COUNT` | yes | Number of stills to capture |
| `-i SECONDS` | no | Interval between captures (default: 2) |
| `-o DIR` | no | Output directory (default: `~/Pictures/cameraboi/burst-<timestamp>/`) |

```bash
# 12 frames, one every 5 seconds
scripts/cameraboi burst -n 12 -i 5
```

Prints one absolute path per image in its trailing stdout block.

> [!TIP]
> `burst` beats a long `record` when the subject is nearly static. Twelve JPEGs are far
> cheaper for Claude to review than a two-minute video, and each one is already a readable
> image.

## frames

Extracts evenly spaced frames from an existing video, and optionally tiles them into contact
sheets.

```bash
scripts/cameraboi frames VIDEO [-n N] [-o DIR] [--sheet]
```

| Argument / flag | Required | Description |
|---|---|---|
| `VIDEO` | yes | Path to the source video |
| `-n N` | no | Number of frames to extract, spaced evenly across the clip (default: 12) |
| `-o DIR` | no | Output directory (default: `~/Pictures/cameraboi/frames-<timestamp>/`) |
| `--sheet` | no | Additionally tile the frames into contact sheet(s) — `contact-sheet.jpg`, chunked as `contact-sheet-NN.jpg` above 16 frames |

`--sheet` uses ffmpeg's `tile` filter to compose the extracted frames into grid images. This
is the mechanism that lets Claude "watch" a video: instead of reading twenty separate
frames, it reads one or two sheets and sees the whole clip's progression at once.

```bash
# 12 frames plus contact sheets
scripts/cameraboi frames ~/Pictures/cameraboi/demo.mp4 -n 12 --sheet
```

Prints the absolute paths of the extracted frames and, with `--sheet`, the sheets, in its
trailing stdout block.

## logs

Queries the capture event log. Every capture command (`snap`, `record`, `burst`, `frames`,
`doctor`) appends one JSONL event to `~/Pictures/cameraboi/.sessions/events.jsonl` on exit:
timestamp, command, resolved device, arguments, exit code, duration, artifact path, and up
to 4 KiB of ffmpeg stderr. The pattern is borrowed from
[hardware-logging](https://github.com/gurul/hardware-logging): failures are debugged from
recorded evidence rather than reruns, and queries are bounded so output stays readable.

```bash
scripts/cameraboi logs [--tail N] [--failures] [--json]
```

| Flag | Required | Description |
|---|---|---|
| `--tail N` | no | Number of most-recent events to show (default: 20, hard cap: 200) |
| `--failures` | no | Only events with a non-zero exit code |
| `--json` | no | Raw JSONL lines instead of the human-readable rendering |

```bash
# what just happened?
scripts/cameraboi logs

# why did that capture fail? (ffmpeg stderr is inside the event)
scripts/cameraboi logs --failures --json
```

Log writes never interfere with capture — a failure to write the event is swallowed, and
the log directory is created owner-only (`0700`).

## doctor

The diagnostic command. Run it first when anything misbehaves.

```bash
scripts/cameraboi doctor
```

It checks three things in order:

1. **`ffmpeg` is present** on `PATH`.
2. **The device exists** in the AVFoundation device list.
3. **Capture actually works** — it runs a live 640x480 test capture. Low resolution keeps it
   fast, and it exercises the real permission path rather than inferring it.

On failure it prints guidance for the most common cause: the camera TCC permission for your
terminal application, at **System Settings → Privacy & Security → Camera**. See
[Troubleshooting](./troubleshooting.md).

---

## Defaults summary

Device `IPEVO V4K`; resolution `1920x1080` at 30 fps (frame rate is mode-derived — the CLI
probes the device's advertised modes and never requests an unsupported rate); `snap`
warm-up of 15 frames; `burst` interval 2 s; `frames` count 12. Artifacts land in
`~/Pictures/cameraboi/` (override with the `CAMERABOI_DIR` environment variable or `-o`):
stills as `snap-<timestamp>.jpg`, clips as `rec-<timestamp>.mp4`, burst shots as
`burst-<timestamp>/shot-NNN.jpg`, extracted frames as `frames-<timestamp>/frame-NNN.jpg`
with contact sheets alongside them.
