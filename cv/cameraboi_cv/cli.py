"""cameraboi-cv command line. Same output contract as scripts/cameraboi:
JSON results go to stdout, the last stdout line(s) are artifact paths,
diagnostics go to stderr via print() redirection where needed.
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from pathlib import Path

DEFAULT_HOME = Path.home() / "Pictures" / "cameraboi" / "cv"
DEFAULT_INTRINSICS = DEFAULT_HOME / "intrinsics.json"
DEFAULT_MAT_JSON = DEFAULT_HOME / "measure-mat.json"

# Diagnostics from library modules use print(); route them to stderr so the
# stdout artifact contract holds.
print = functools.partial(print, file=sys.stderr)  # noqa: A001


def _emit(obj: dict, artifact_keys: tuple[str, ...]) -> None:
    """JSON to stdout, then artifact path(s) as the final stdout lines."""
    sys.stdout.write(json.dumps(obj, indent=2) + "\n")
    for key in artifact_keys:
        if obj.get(key):
            sys.stdout.write(str(obj[key]) + "\n")


def cmd_mat(args) -> None:
    from .boards import generate_mat
    png, meta = generate_mat(Path(args.out_dir))
    print("mat: print at 100% scale (no 'fit to page'), verify the 100mm line, "
          "then set scale_correction in the JSON if it measures off.")
    sys.stdout.write(f"{meta}\n{png}\n")


def cmd_board(args) -> None:
    from .boards import generate_charuco
    png, meta = generate_charuco(Path(args.out_dir))
    print("board: print at 100%, tape to something rigid and flat.")
    sys.stdout.write(f"{meta}\n{png}\n")


def cmd_calibrate(args) -> None:
    from .calibrate import calibrate_dir
    calibrate_dir(Path(args.images), Path(args.out))


def cmd_measure(args) -> None:
    from .measure import measure_image
    intr = Path(args.intrinsics)
    result = measure_image(
        Path(args.image), Path(args.mat),
        intrinsics_path=intr if intr.exists() else None,
        min_area_mm2=args.min_area,
        object_height_mm=args.object_height,
        camera_height_mm=args.camera_height,
        thresh=args.thresh,
    )
    _emit(result, ("annotated",))


def cmd_count(args) -> None:
    from .count import count_image
    result = count_image(
        Path(args.image), fg=args.fg, min_area_px=args.min_area,
        peak_frac=args.min_sep, thresh=args.thresh,
    )
    _emit(result, ("annotated",))


def cmd_scan(args) -> None:
    from .scan import scan_batch
    results = scan_batch(
        [Path(p) for p in args.inputs],
        Path(args.out_dir) if args.out_dir else None,
        mode=args.mode,
    )
    sys.stdout.write(json.dumps(results, indent=2) + "\n")
    for r in results:
        sys.stdout.write(r["output"] + "\n")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="cameraboi-cv",
        description="Deterministic CV for cameraBoi: mm measurement, exact "
                    "counting, scan preprocessing.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("mat", help="generate the printable measuring mat")
    s.add_argument("-o", "--out-dir", default=str(DEFAULT_HOME))
    s.set_defaults(fn=cmd_mat)

    s = sub.add_parser("board", help="generate the printable ChArUco calibration board")
    s.add_argument("-o", "--out-dir", default=str(DEFAULT_HOME))
    s.set_defaults(fn=cmd_board)

    s = sub.add_parser("calibrate", help="fit lens intrinsics from board captures")
    s.add_argument("images", help="directory of stills of the ChArUco board")
    s.add_argument("-o", "--out", default=str(DEFAULT_INTRINSICS))
    s.set_defaults(fn=cmd_calibrate)

    s = sub.add_parser("measure", help="measure objects on the mat, in mm")
    s.add_argument("image")
    s.add_argument("--mat", default=str(DEFAULT_MAT_JSON), help="mat geometry JSON")
    s.add_argument("--intrinsics", default=str(DEFAULT_INTRINSICS))
    s.add_argument("--min-area", type=float, default=25.0, help="ignore blobs under this mm^2")
    s.add_argument("--object-height", type=float, default=0.0,
                   help="object thickness in mm (corrects top-surface parallax)")
    s.add_argument("--camera-height", type=float, default=0.0,
                   help="lens-to-mat distance in mm (needed with --object-height)")
    s.add_argument("--thresh", type=int, default=None,
                   help="manual 0-255 threshold instead of Otsu")
    s.set_defaults(fn=cmd_measure)

    s = sub.add_parser("count", help="count distinct objects in an image")
    s.add_argument("image")
    s.add_argument("--fg", choices=("auto", "dark", "light"), default="auto",
                   help="which phase is the objects (default: minority phase)")
    s.add_argument("--min-area", type=int, default=80, help="ignore blobs under this px area")
    s.add_argument("--min-sep", type=float, default=0.5,
                   help="watershed peak fraction 0-1; raise to split touching objects harder")
    s.add_argument("--thresh", type=int, default=None,
                   help="manual 0-255 threshold instead of Otsu")
    s.set_defaults(fn=cmd_count)

    s = sub.add_parser("scan", help="deskew/crop/enhance document photos (batch)")
    s.add_argument("inputs", nargs="+", help="image file(s) and/or directories")
    s.add_argument("-o", "--out-dir", default=None)
    s.add_argument("--mode", choices=("color", "gray", "bw"), default="gray")
    s.set_defaults(fn=cmd_scan)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
