"""Exercise the bundled PowerShell on an actual Windows runner."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from checkmylaptop.collect import scan
from checkmylaptop.report import build_report

snapshot = scan()
sections = snapshot["sections"]
for name, entry in sections.items():
    print(f"{name}: {entry['state']}")
for required in ("inventory", "storage", "events", "performance"):
    if sections[required]["state"] != "checked":
        raise SystemExit(f"Windows collector failed: {required}")
if not sections["inventory"]["data"]["cpu"]:
    raise SystemExit("Windows inventory did not return a processor.")
if len(sections["performance"]["data"]["samples"]) != 5:
    raise SystemExit("Windows performance sample count is incorrect.")
report = build_report(snapshot)
assert report["schema_version"] == 1 and report["coverage"]
