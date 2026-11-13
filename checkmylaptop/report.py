"""Summarize scan coverage and export a local, shareable report."""

from .collect import SECTIONS
from .diagnose import MANUAL_COVERAGE, diagnose


def build_report(snapshot: dict, *, demo: bool = False) -> dict:
    sections = snapshot["sections"]
    coverage = {}
    for name, (label, _) in SECTIONS.items():
        result = sections.get(name, {"state": "unavailable"})
        status = result["state"]
        details = result.get("reason", "")
        data = result.get("data")
        if status == "checked":
            if name == "battery":
                count = sum(bool(row.get("DesignCapacity") and row.get("FullChargeCapacity"))
                            for row in data)
                status = ("checked" if data and count == len(data)
                          else "partial" if count else "unavailable")
                details = f"Capacity data for {count} of {len(data)} reported batteries."
            if name == "storage":
                count = sum(any(disk.get(key) is not None for key in
                                ("wear", "read_uncorrected", "write_uncorrected"))
                            for disk in data)
                status = ("checked" if data and count == len(data)
                          else "partial" if data else "unavailable")
                details = f"Reliability counters for {count} of {len(data)} detected disks."
            if name == "events":
                missing = data.get("unavailable", [])
                status = ("unavailable" if len(missing) >= 8
                          else "partial" if missing else "checked")
                details = f"14-day lookback. {len(missing)} event sources unavailable."
            if name == "performance":
                samples = data.get("samples", [])
                count = sum(all(row.get(key) is not None for key in (
                    "memory_available_mib", "pages_input_sec", "disk_queue", "cpu_percent"
                )) for row in samples)
                if not count and not data.get("system_size"):
                    status = "unavailable"
                elif count < len(samples) or not samples or not data.get("system_size"):
                    status = "partial"
                details = f"{count} complete performance samples out of {len(samples)}."
        coverage[label] = {"state": status, "details": details}
    inventory = sections.get("inventory", {}).get("data", {})
    overview = {}
    laptop = " ".join(inventory.get(key) or "" for key in ("manufacturer", "model")).strip()
    if laptop:
        overview["Model"] = laptop
    if inventory.get("os"):
        overview["Operating system"] = f"{inventory['os']} (build {inventory.get('build') or 'unknown'})"
    for key, label in (("cpu", "Processor"), ("gpu", "Graphics")):
        if inventory.get(key):
            overview[label] = ", ".join(inventory[key])
    if inventory.get("memory_bytes"):
        overview["Installed RAM"] = f"{inventory['memory_bytes'] / 1024**3:.1f} GiB"
    findings = diagnose(snapshot)
    return {
        "schema_version": 1, "demo": demo, "scanned_at": snapshot["scanned_at"],
        "findings": findings, "coverage": coverage, "overview": overview,
        "not_tested": MANUAL_COVERAGE,
    }


def render_text(report: dict) -> str:
    lines = ["CheckMyLaptop · Diagnostic report",
             f"Scan time: {report['scanned_at']}"]
    if report["demo"]:
        lines.append("DEMO · Simulated data")
    lines.append("")
    if not report["findings"]:
        if any(item["state"] in {"checked", "partial"} for item in report["coverage"].values()):
            lines.append("No issues flagged by the available checks. Review coverage below.")
        else:
            lines.append("No diagnostic data available. The scan could not assess this device.")
    for item in report["findings"]:
        lines.append(f"[{item['severity'].upper()}] {item['title']}")
        lines.extend(f"  • {detail}" for detail in item["evidence"])
        lines.extend([f"  Next step: {item['action']}", ""])
    lines.extend(["", "Scan coverage"])
    for label, item in report["coverage"].items():
        detail = f" · {item['details']}" if item["details"] else ""
        lines.append(f"  {label}: {item['state'].replace('_', ' ').title()}{detail}")
    if report["overview"]:
        lines.extend(["", "Device overview"])
        lines.extend(f"  {label}: {value}" for label, value in report["overview"].items())
    lines.extend(["", "Outside this release's scan coverage"])
    lines.extend(f"  • {item}" for item in report["not_tested"])
    lines.extend(["", "This report is screening guidance. Review the evidence before making repairs."])
    return "\n".join(lines) + "\n"
