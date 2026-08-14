"""CLI for one-off use and testing. Same output contract as cameraboi-cv:
JSON on stdout, artifact paths as the last stdout line(s), diagnostics on stderr.

For interactive Claude sessions prefer the MCP server (`cameraboi-vlm serve`),
which keeps the model warm between calls.
"""

from __future__ import annotations

import argparse
import sys

from . import ops


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cameraboi-vlm", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("describe", help="caption an image")
    p.add_argument("image")
    p.add_argument("--long", action="store_true", help="thorough description")

    p = sub.add_parser("ask", help="answer a question about an image")
    p.add_argument("image")
    p.add_argument("question")

    p = sub.add_parser("read", help="transcribe visible text")
    p.add_argument("image")

    p = sub.add_parser("find", help="locate objects; boxes in original pixels")
    p.add_argument("image")
    p.add_argument("objects", help='what to find, e.g. "red screw, allen key"')
    p.add_argument("--no-annotate", action="store_true")

    p = sub.add_parser("serve", help="run the MCP server on stdio")

    args = parser.parse_args(argv)

    if args.command == "serve":
        from .server import main as serve_main

        serve_main()
        return 0

    if args.command == "describe":
        result = ops.describe(args.image, "long" if args.long else "short")
    elif args.command == "ask":
        result = ops.ask(args.image, args.question)
    elif args.command == "read":
        result = ops.read_text(args.image)
    else:
        result = ops.find(args.image, args.objects, annotate=not args.no_annotate)

    print(ops.to_json(result))
    if "annotated_image" in result:
        print(result["annotated_image"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
