"""Summarize detailed Windows observations and combine related evidence."""

from .collect import DETAIL_SECTIONS
from .performance import GIB


def detail_data(sections, section, check):
    result = sections.get(section, {}).get("data", {}).get(check, {})
    return result.get("data") if result.get("state") == "checked" else None


def component_health(sections):
    verified = sections.get("windows_verification", {})
    if verified.get("state") == "checked":
        return verified["data"].get("health"), True
    recorded = detail_data(sections, "windows_health", "component_store") or {}
    return recorded.get("health"), False


def detail_measurements(sections):
    return {
        name: {check: detail_data(sections, name, check) for check in checks}
        for name, checks in DETAIL_SECTIONS.items()
    }


def conclusions(sections, findings, metrics):
    by_code = {}
    for item in findings:
        by_code.setdefault(item["code"], []).append(item)
    results = []

    covered = set()

    def add(title, confidence, evidence, action, *, priority=1):
        results.append((priority, dict(title=title, confidence=confidence, evidence=evidence, action=action)))

    volumes = detail_data(sections, "volumes", "volumes") or []
    mapping = detail_data(sections, "volumes", "disk_map") or []
    for volume in volumes:
        disks = {row["disk"] for row in mapping if row["drive"] == volume["drive"]}
        if volume.get("dirty") is not True or len(disks) != 1:
            continue
        disk_number = next(iter(disks))
        disk = next((row for row in sections.get("storage", {}).get("data", [])
                     if row["number"] == disk_number), None)
        if disk and (disk.get("health") in {"Warning", "Unhealthy"} or
                     any((disk.get(key) or 0) > 0 for key in ("read_uncorrected", "write_uncorrected"))):
            add("File-system and storage warnings on the same mapped disk", "corroborated",
                [f"{volume['drive']} is marked dirty and maps to Windows disk {disk_number}.",
                 "The mapped disk reports a health warning or uncorrected I/O errors."],
                "Back up the volume first. Run the manufacturer's storage diagnostic, then inspect the file system.",
                priority=0)
            covered.add(disk_number)

    for item in by_code.get("storage_health", []):
        if item.get("disk") not in covered:
            add(item["title"], "cause undetermined", item["evidence"], item["action"], priority=0)
    for item in by_code.get("memory", []):
        add(item["title"], "cause undetermined", item["evidence"], item["action"], priority=0)

    if "memory_paging" in by_code and (metrics["commit_and_low_count"] >= metrics["required"] or
                                       "memory_exhaustion" in by_code):
        evidence = by_code["memory_paging"][0]["evidence"][:2]
        if metrics["commit_and_low_count"] >= metrics["required"]:
            evidence.append(f"Commit was at least 90% while RAM was low in {metrics['commit_and_low_count']} samples.")
        if "memory_exhaustion" in by_code:
            evidence.append("Windows also recorded virtual-memory exhaustion during the event lookback.")
        add("Sustained memory pressure with paging and disk activity", "corroborated", evidence,
            "Review process commit size and repeat the scan during the same workload after closing an unused app.")

    for code in ("hardware_crash_timing", "graphics_crash_timing"):
        if code in by_code:
            item = by_code[code][0]
            add(item["title"], "possible association", item["evidence"], item["action"],
                priority=0 if item["severity"] == "high" else 1)

    if "component_store" in by_code and "update_failure" in by_code:
        add("Component-store health is relevant to the update investigation", "possible association",
            by_code["component_store"][0]["evidence"] + by_code["update_failure"][0]["evidence"],
            "Compare the failing update's error code with servicing logs before choosing a repair.")

    if not results and findings:
        item = findings[0]
        add(f"Start with {item['title'][0].lower() + item['title'][1:]}", "cause undetermined",
            item["evidence"], item["action"])
    return [item for _, item in sorted(results, key=lambda result: result[0])]


def render_details(measurements):
    details = measurements.get("diagnostic_details", {})
    lines = []

    def show(label, value):
        if value is not None:
            lines.append(f"  {label}: {value}")

    for volume in details.get("volumes", {}).get("volumes") or []:
        drive = volume["drive"]
        if volume.get("size_bytes") and volume.get("free_bytes") is not None:
            show(drive, f"{volume.get('file_system') or 'Unknown file system'} · "
                 f"{volume['free_bytes'] / GIB:.1f} GiB free of {volume['size_bytes'] / GIB:.1f} GiB")
        if volume.get("dirty") is not None:
            show(f"{drive} file-system dirty flag", volume["dirty"])

    platform = details.get("platform", {})
    firmware = platform.get("firmware") or {}
    show("BIOS version", firmware.get("version"))
    show("Last boot (UTC)", firmware.get("last_boot"))
    modules = platform.get("memory")
    if modules:
        capacities = [f"{row['capacity_bytes'] / GIB:.1f} GiB" for row in modules if row.get("capacity_bytes")]
        show("Detected memory modules", ", ".join(capacities) or len(modules))
    power = platform.get("power") or {}
    show("AC line", power.get("ac"))
    show("Battery charge status", power.get("battery_status"))
    zones = platform.get("thermal") or []
    if zones:
        show("ACPI thermal zones", ", ".join(f"{row['celsius']:.1f} °C" for row in zones))

    drivers = details.get("drivers", {}).get("devices")
    if drivers is not None:
        show("Present devices with driver version", f"{sum(bool(row.get('version')) for row in drivers)} of {len(drivers)}")
        for row in drivers:
            if row.get("error_code") not in {None, 0, 22} and row.get("version"):
                show(row.get("name") or "Device", f"driver {row['version']} · code {row['error_code']}")

    page_file = details.get("windows_health", {}).get("page_file") or {}
    show("Automatic page-file management", page_file.get("managed"))
    for row in page_file.get("files", []):
        show("Page file", f"{row['used_mib']} of {row['allocated_mib']} MiB in use")
    component = measurements.get("component_store", {})
    label = "Verified component store" if component.get("verified") else "Previously recorded component-store health"
    show(label, component.get("health"))

    protection = details.get("protection", {})
    show("Secure Boot enabled", (protection.get("secure_boot") or {}).get("enabled"))
    show("TPM ready", (protection.get("tpm") or {}).get("ready"))
    for row in protection.get("firewall") or []:
        show(f"Windows Firewall · {row['profile']}", row.get("enabled"))
    defender = protection.get("defender") or {}
    show("Microsoft Defender mode", defender.get("mode"))
    show("Microsoft Defender real-time protection", defender.get("realtime"))
    show("System-volume encryption protection", (protection.get("encryption") or {}).get("protection"))
    return lines
