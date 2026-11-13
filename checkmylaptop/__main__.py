"""Desktop and terminal entry points."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .collect import CONSENT_NOTICE, VERIFICATION_NOTICE, scan
from .demo import snapshot
from .report import build_report, render_text


def main(argv=None):
    parser = argparse.ArgumentParser(description="In-depth Windows laptop diagnostics")
    parser.add_argument("--demo", action="store_true", help="Use simulated data")
    parser.add_argument("--cli", action="store_true", help="Run a scan in the terminal")
    parser.add_argument("--allow", action="store_true",
                        help="Allow this live scan to read local Windows diagnostic data")
    parser.add_argument("--verify-windows", action="store_true",
                        help="Also verify the Windows component store (Administrator, up to 15 minutes)")
    parser.add_argument("--json", type=Path, metavar="PATH", help="Export a report as JSON")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if not args.demo and sys.platform != "win32":
        parser.error("Live scans require Windows. Try --demo --cli.")
    if args.cli or args.json:
        allowed = args.allow
        if not args.demo and not allowed:
            if sys.stdin is None or not sys.stdin.isatty() or sys.stdout is None:
                parser.error("Live diagnostics require --allow. " + CONSENT_NOTICE)
            try:
                notice = CONSENT_NOTICE
                if args.verify_windows:
                    notice += " " + VERIFICATION_NOTICE
                allowed = input(f"{notice}\nType ALLOW to start: ").strip().upper() == "ALLOW"
            except (EOFError, KeyboardInterrupt):
                allowed = False
            if not allowed:
                parser.exit(1, "Scan canceled.\n")
        data = snapshot() if args.demo else scan(allow=allowed, verify_windows=args.verify_windows)
        report = build_report(data, demo=args.demo)
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
        run(demo=args.demo, verify_windows=args.verify_windows)
    except ImportError:
        parser.exit(1, "The Python installation needs Tcl/Tk for the GUI. Try --cli.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
