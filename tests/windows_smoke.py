"""Exercise the diagnostic collectors on an actual Windows runner."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from checkmylaptop.collect import scan
from checkmylaptop.report import build_report

snapshot = scan(allow=True)
sections = snapshot["sections"]
for name, entry in sections.items():
    print(f"{name}: {entry['state']}")
for required in ("inventory", "storage", "events", "performance", "network", "volumes",
                 "drivers", "platform", "windows_health", "protection"):
    if sections[required]["state"] != "checked":
        raise SystemExit(f"Windows collector failed: {required}")
if not sections["inventory"]["data"]["cpu"]:
    raise SystemExit("Windows inventory did not return a processor.")
if len(sections["performance"]["data"]["samples"]) != 8:
    raise SystemExit("Windows performance sample count is incorrect.")
report = build_report(snapshot)
assert report["schema_version"] == 2 and report["coverage"]
assert report["measurements"]["performance"]["processes"], "Process memory was not returned."
if "--require-native" in sys.argv:
    assert report["measurements"]["performance_source"] == "native", "Native performance collector was not used."
    native_samples = report["measurements"]["performance_samples"]
    assert all(row["memory_total_mib"] > 0 and row["commit_limit_bytes"] > 0 and
               0 <= row["cpu_percent"] <= 100 and row["disk_queue"] >= 0
               for row in native_samples), "Native performance counters were invalid."
details = report["measurements"]["diagnostic_details"]
assert details["volumes"]["volumes"], "No fixed volumes returned."
assert details["drivers"]["devices"], "No present device records returned."
assert details["platform"]["firmware"], "No firmware data returned."
assert details["windows_health"]["reboot"] is not None, "No servicing reboot data returned."
