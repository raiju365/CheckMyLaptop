"""Desktop and terminal entry points."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .collect import scan
from .demo import snapshot
from .report import build_report, render_text


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-click Windows laptop diagnostics")
    parser.add_argument("--demo", action="store_true", help="Use simulated data")
    parser.add_argument("--cli", action="store_true", help="Run a scan in the terminal")
    parser.add_argument("--json", type=Path, metavar="PATH", help="Export a report as JSON")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if not args.demo and sys.platform != "win32":
        parser.error("Live scans require Windows. Try --demo --cli.")
    if args.cli or args.json:
        report = build_report(snapshot() if args.demo else scan(), demo=args.demo)
        if args.json:
            try:
                args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            except OSError as exc:
                parser.exit(1, f"Could not write report: {exc}\n")
        if sys.stdout is not None:
            output = render_text(report)
            encoding = sys.stdout.encoding or "utf-8"
            print(output.encode(encoding, errors="replace").decode(encoding), end="")
        return 0
    try:
        from .gui import run
        run(demo=args.demo)
    except ImportError:
        parser.exit(1, "The Python installation needs Tcl/Tk for the GUI. Try --cli.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
