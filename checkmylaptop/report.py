"""Summarize scan coverage and export a local, shareable report."""

from .collect import DETAIL_SECTIONS, SECTIONS
from .deep_diagnostics import component_health, conclusions, detail_data, detail_measurements, render_details
from .diagnose import MANUAL_COVERAGE, diagnose
from .performance import GIB, summarize_performance


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
                status = ("unavailable" if len(missing) >= data.get("query_count", 8)
                          else "partial" if missing else "checked")
                details = f"14-day lookback. {len(missing)} event sources unavailable."
            if name == "performance":
                samples = data.get("samples", [])
                count = sum(all(row.get(key) is not None for key in (
                    "memory_available_mib", "pages_input_sec", "disk_queue", "cpu_percent",
                    "commit_bytes", "commit_limit_bytes"
                )) for row in samples)
                if not count and not data.get("system_size"):
                    status = "unavailable"
                elif count < len(samples) or not samples or not data.get("system_size"):
                    status = "partial"
                details = f"{count} complete performance samples out of {len(samples)}."
                if not data.get("processes_end"):
                    details += " Process memory unavailable."
                    if status == "checked":
                        status = "partial"
            if name == "network":
                count = sum(row.get("receive_errors") is not None and
                            row.get("send_errors") is not None for row in data)
                status = ("checked" if data and count == len(data)
                          else "partial" if data else "unavailable")
                details = f"Packet error counters for {count} of {len(data)} detected adapters."
            if name in DETAIL_SECTIONS:
                checks = DETAIL_SECTIONS[name]
                missing = [label for key, label in checks.items()
                           if detail_data(sections, name, key) is None]
                status = ("unavailable" if len(missing) == len(checks)
                          else "partial" if missing else "checked")
                details = f"{len(checks) - len(missing)} of {len(checks)} queries returned data."
                if missing:
                    details += " Unavailable: " + ", ".join(missing) + "."
        coverage[label] = {"state": status, "details": details}
    verification = sections.get("windows_verification")
    if verification is not None:
        coverage["Windows component-store verification"] = {
            "state": verification["state"], "details": verification.get("reason", ""),
        }
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
    perf = sections.get("performance", {}).get("data", {})
    metrics = summarize_performance(perf)
    battery = sections.get("battery", {}).get("data", [])
    storage = sections.get("storage", {}).get("data", [])
    network = sections.get("network", {}).get("data", [])
    events = sections.get("events", {}).get("data", {}).get("entries", [])
    timeline = sorted(events, key=lambda row: row["time"], reverse=True)[:12]
    findings = diagnose(snapshot, metrics)
    health, verified = component_health(sections)
    not_tested = list(MANUAL_COVERAGE)
    if not verified:
        not_tested.append("Full Windows component-store verification")
    return {
        "schema_version": 2, "demo": demo, "scanned_at": snapshot["scanned_at"],
        "administrator": snapshot.get("administrator"),
        "findings": findings, "coverage": coverage, "overview": overview,
        "conclusions": conclusions(sections, findings, metrics), "not_tested": not_tested,
        "recent_events": timeline,
        "measurements": {
            "performance": metrics, "performance_samples": perf.get("samples", []),
            "battery": battery, "storage": storage, "network": network,
            "diagnostic_details": detail_measurements(sections),
            "component_store": {"health": health, "verified": verified},
            "system_volume": {"drive": perf.get("system_drive"), "free_bytes": perf.get("system_free"),
                              "size_bytes": perf.get("system_size")},
        },
    }


def render_text(report: dict) -> str:
    lines = ["CheckMyLaptop · Diagnostic report",
             f"Scan time: {report['scanned_at']}"]
    if report["demo"]:
        lines.append("DEMO · Simulated data")
    elif report.get("administrator") is not None:
        lines.append("Windows access: " + ("Administrator" if report["administrator"] else "Standard user"))
    lines.append("")
    if report.get("conclusions"):
        lines.append("Diagnostic summary")
        for item in report["conclusions"]:
            lines.append(f"  {item['title']} · {item['confidence']}")
            lines.extend(f"    • {detail}" for detail in item["evidence"])
            lines.extend([f"    Next step: {item['action']}", ""])
        lines.append("Detailed findings")
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
    measurements = report.get("measurements", {})
    metrics = measurements.get("performance", {})
    if metrics.get("samples"):
        lines.extend(["", "Measured performance"])
        for key, label, unit in (
            ("available_median_mib", "Available RAM, median", "MiB"),
            ("available_min_mib", "Available RAM, minimum", "MiB"),
            ("threshold_mib", "Low RAM threshold", "MiB"),
            ("cpu_median_percent", "CPU load, median", "%"),
            ("disk_queue_median", "Combined disk queue, median", ""),
            ("pages_input_median", "Pages read into memory, median", "pages/s"),
        ):
            value = metrics[key]
            if value is not None:
                lines.append(f"  {label}: {value:.1f} {unit}".rstrip())
        if metrics["commit_peak_ratio"] is not None:
            lines.append(f"  Peak commit usage: {metrics['commit_peak_ratio']:.1%} of limit")
        if metrics["processes"]:
            lines.append("  Top process groups by resident memory at the end of the scan")
            for row in metrics["processes"]:
                change = row["working_set_change_mib"]
                delta = f" · {change:+.0f} MiB since first snapshot" if change is not None else ""
                lines.append(f"    {row['name']} ({row['count']}) · {row['working_set_mib']:.0f} MiB{delta}")
            lines.append("  Process groups may include shared pages. Totals can exceed physical usage.")
    volume = measurements.get("system_volume", {})
    if volume.get("size_bytes") and volume.get("free_bytes") is not None:
        lines.append(f"  {volume['drive']} · {volume['free_bytes'] / GIB:.1f} GiB free "
                     f"of {volume['size_bytes'] / GIB:.1f} GiB")
    if measurements.get("battery"):
        lines.extend(["", "Battery measurements"])
        for index, row in enumerate(measurements["battery"], 1):
            design, full = row.get("DesignCapacity"), row.get("FullChargeCapacity")
            if design and full:
                lines.append(f"  Battery {index}: {full:,} / {design:,} mWh ({full / design:.0%} of design)")
            if row.get("CycleCount") is not None:
                lines.append(f"  Battery {index} cycle count: {row['CycleCount']}")
    if measurements.get("storage"):
        lines.extend(["", "Storage measurements"])
        for row in measurements["storage"]:
            lines.append(f"  Disk {row['number']} · {row.get('model') or 'Unknown model'} "
                         f"· Windows status: {row.get('health') or 'Unknown'}")
            if row.get("counter_source"):
                lines.append(f"    Counter source: {row['counter_source']}")
            if not any(row.get(key) is not None for key in
                       ("read_uncorrected", "write_uncorrected", "wear", "temperature")):
                lines.append("    Device reliability counters unavailable.")
            for key, label in (("read_uncorrected", "Uncorrected read errors"),
                               ("write_uncorrected", "Uncorrected write errors"),
                               ("wear", "Reported wear"), ("temperature", "Drive temperature")):
                if row.get(key) is not None:
                    unit = {"wear": "%", "temperature": " °C"}.get(key, "")
                    lines.append(f"    {label}: {row[key]}{unit}")
    if measurements.get("network"):
        lines.extend(["", "Network adapter measurements"])
        for row in measurements["network"]:
            lines.append(f"  {row['description']} · Windows status: {row.get('status') or 'Unknown'}")
            for key, label in (("receive_errors", "receive errors"), ("send_errors", "send errors")):
                if row.get(key) is not None:
                    lines.append(f"    Recorded {label}: {row[key]}")
            for key, label in (("ipv4_connectivity", "IPv4"), ("ipv6_connectivity", "IPv6")):
                if row.get(key) is not None:
                    lines.append(f"    Windows {label} connectivity: {row[key]}")
    details = render_details(measurements)
    if details:
        lines.extend(["", "Detailed Windows measurements", *details])
    if report.get("recent_events"):
        lines.extend(["", "Recent selected system events (UTC)"])
        for row in report["recent_events"]:
            disk = f" · disk {row['disk']}" if row.get("disk") is not None else ""
            lines.append(f"  {row['time']} · {row['provider']} #{row['id']}{disk}")
    lines.extend(["", "Outside this release's scan coverage"])
    lines.extend(f"  • {item}" for item in report["not_tested"])
    lines.extend(["", "This report is screening guidance. Review the evidence before making repairs."])
    return "\n".join(lines) + "\n"
