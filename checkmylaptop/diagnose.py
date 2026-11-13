"""Turn collected evidence into conservative, explainable findings."""

from datetime import datetime, timedelta

from .performance import GIB, summarize_performance
from .deep_diagnostics import component_health, detail_data

EVENT_GROUPS = {
    "restart": {("microsoft-windows-kernel-power", 41)},
    "display": {("display", 4101)},
    "storage": {
        ("disk", 7), ("disk", 51), ("disk", 153), ("disk", 157),
        ("storahci", 129), ("stornvme", 129),
    },
    "hardware": {
        ("microsoft-windows-whea-logger", number)
        for number in (17, 18, 19, 20, 46, 47)
    },
    "memory": {("microsoft-windows-memorydiagnostics-results", 1202)},
    "crash": {("microsoft-windows-wer-systemerrorreporting", 1001)},
    "firmware_limit": {("microsoft-windows-kernel-processor-power", 37)},
    "file_system": {("microsoft-windows-ntfs", 55)},
    "update_failure": {("microsoft-windows-windowsupdateclient", 20)},
    "memory_exhaustion": {("microsoft-windows-resource-exhaustion-detector", 2004)},
    "app_failures": {("application error", 1000), ("application hang", 1002)},
}
PRIORITIES = {"high": 0, "attention": 1, "info": 2}
MANUAL_COVERAGE = [
    "Direct CPU/GPU sensor temperatures, fan RPM and charger or battery load tests",
    "Dedicated RAM, CPU and GPU stability tests",
    "Display pixels, keyboard and touchpad operation",
    "Speaker, microphone, camera and end-to-end network connectivity",
    "Individual USB, charging and video ports",
    "Malware, Windows system-file verification and crash-dump analysis",
    "Physical inspection and motherboard faults",
]


def nearby_events(first: list[dict], second: list[dict]) -> int:
    def timestamps(entries):
        for entry in entries:
            try:
                value = datetime.fromisoformat(entry.get("time", "").replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                continue
            if value.tzinfo is not None:
                yield value

    first_times = list(timestamps(first))
    second_times = list(timestamps(second))
    window = timedelta(minutes=2)
    return sum(any(abs(event - other) <= window for other in second_times)
               for event in first_times)


def diagnose(report: dict, performance: dict | None = None) -> list[dict]:
    def data(section, default):
        return report["sections"].get(section, {}).get("data", default)

    findings = []

    def add(code, severity, title, evidence, action, **details):
        findings.append(dict(code=code, severity=severity, title=title,
                             evidence=evidence, action=action, **details))

    entries = data("events", {}).get("entries", [])
    events = {
        group: [entry for entry in entries if
                (entry["provider"].casefold(), entry["id"]) in keys]
        for group, keys in EVENT_GROUPS.items()
    }
    for disk in data("storage", []):
        label = f"Disk {disk['number']} ({disk.get('model') or 'unknown model'})"
        health = disk.get("health") or "Unknown"
        errors = sum(disk.get(key) or 0 for key in ("read_uncorrected", "write_uncorrected"))
        retries = sum(
            entry["id"] == 153 and entry.get("current_boot") and
            entry.get("disk") is not None and entry["disk"] == disk["number"]
            for entry in events["storage"]
        )
        if health in {"Warning", "Unhealthy"} or errors > 0:
            evidence = [f"{label}. Windows health: {health}."]
            if errors:
                evidence.append(f"Device reports {errors} uncorrected read/write errors in total.")
            if retries >= 2:
                evidence.append(f"{retries} I/O retries in this boot reference the same Windows disk number.")
            add("storage_health", "high", "Storage needs attention", evidence,
                "Back up important files, then run the manufacturer's storage diagnostic.", disk=disk["number"])
    if events["storage"]:
        add("storage_events", "attention", "Windows recorded storage interruptions",
            [f"{len(events['storage'])} selected storage events in the last 14 days."],
            "Run the manufacturer's storage diagnostic. Review the storage driver if drive tests pass.")
    for index, battery in enumerate(data("battery", []), 1):
        design = battery.get("DesignCapacity") or 0
        capacity = battery.get("FullChargeCapacity") or 0
        if design > 0 and 0 < capacity / design < 0.75:
            add("battery_capacity", "attention", "Battery reports reduced capacity",
                [f"Battery {index}: {capacity / design:.0%} of design capacity ({capacity:,} / {design:,} mWh)."],
                "Compare expected runtime with actual runtime and use the maker's battery test if needed.")
    perf = data("performance", {})
    size, free = perf.get("system_size"), perf.get("system_free")
    if size and free is not None and free < min(size * 0.10, 15 * GIB):
        add("free_space", "attention", "Low space on the Windows drive",
            [f"{perf.get('system_drive', 'System drive')} has {free / GIB:.1f} GiB free."],
            "Review Windows Settings → System → Storage and free space before large updates.")

    metrics = performance if performance is not None else summarize_performance(perf)
    needed = metrics["required"]
    sample_count = metrics["samples"]
    low = metrics["low_count"]
    paging = metrics["paging_count"]
    high_commit = metrics["commit_high_count"]
    commit_and_low = metrics["commit_and_low_count"]
    if low >= needed:
        evidence = [
            f"Available RAM: {metrics['available_min_mib']:.0f}–{metrics['available_max_mib']:.0f} MiB "
            f"(median {metrics['available_median_mib']:.0f} MiB). "
            f"{low}/{sample_count} samples were below the scan threshold.",
        ]
        if paging >= needed:
            evidence.append(f"Low RAM, page reads and a disk queue coincided in {paging}/{sample_count} samples.")
        if commit_and_low >= needed:
            evidence.append(f"Low RAM and commit usage of at least 90% coincided in {commit_and_low}/{sample_count} samples.")
        apps = metrics["processes"]
        if apps:
            largest = apps[0]
            evidence.append(
                f"Largest process group at the end: {largest['name']} "
                f"({largest['count']} instances, {largest['working_set_mib']:.0f} MiB resident in total)."
            )
        if paging >= needed:
            code, title = "memory_paging", "Memory pressure and disk activity coincided"
        elif commit_and_low >= needed:
            code, title = "memory_commit", "Low available RAM and high committed memory"
        else:
            code, title = "memory_low", "Low available memory during the scan"
        add(code, "attention", title, evidence,
            "Review the process list below, close an unused application if appropriate, then repeat the scan.")
    if high_commit >= needed and commit_and_low < needed:
        add("commit_limit", "attention", "Committed memory approached its limit",
            [f"{high_commit}/{sample_count} samples reached at least 90% of the reported commit limit.",
             "Committed memory and physical RAM usage measure different things."],
            "Check the largest processes by commit size in Task Manager and repeat the scan.")
    if metrics["cpu_high_count"] >= needed:
        add("cpu_load", "attention", "Sustained high CPU use during the scan",
            [f"CPU usage was at least 90% in {metrics['cpu_high_count']}/{sample_count} samples."],
            "Sort Task Manager by CPU to identify active workloads, then compare with a scan after they finish.")
    if metrics["queue_high_count"] >= needed and paging < needed:
        evidence = [f"The combined disk queue reached two in {metrics['queue_high_count']}/{sample_count} samples."]
        if events["storage"]:
            evidence.append("Recent storage events were also found. Their relation to this scan is unverified.")
        add("disk_activity", "attention", "Sustained disk queue during the scan", evidence,
            "Sort Task Manager by Disk and check for a background workload. Review any separate storage findings.")

    display_near_crashes = nearby_events(events["display"], events["crash"])
    if display_near_crashes:
        add("graphics_crash_timing", "attention", "Graphics recovery occurred near a system crash",
            [f"{display_near_crashes} graphics recovery events within two minutes of a bugcheck log.",
             "Event timing can suggest a shared incident. A crash dump is needed to investigate the cause."],
            "Check the manufacturer's graphics driver and have a technician review the crash dump.")
    serious_hardware = [entry for entry in events["hardware"] if entry["id"] in {18, 20, 46}]
    hardware_near_crashes = nearby_events(serious_hardware, events["crash"])
    if hardware_near_crashes:
        add("hardware_crash_timing", "high", "Hardware error reports occurred near a system crash",
            [f"{hardware_near_crashes} selected WHEA events within two minutes of a bugcheck log.",
             "The timing supports further investigation. These events do not isolate a specific component."],
            "Run the manufacturer's extended diagnostics and have a technician review the WHEA and crash records.")
    for group, severity, title, evidence, action in (
        ("memory", "high", "Windows memory test reported errors",
         "Windows logged a memory diagnostic failure.",
         "Run the manufacturer's extended memory diagnostic."),
        ("hardware", "attention", "Windows logged hardware error reports",
         "Windows Hardware Error Architecture recorded one or more selected events.",
         "Run the laptop manufacturer's diagnostics and share the event details with a technician if they recur."),
        ("display", "attention", "Graphics driver recovered after a timeout",
         "Windows logged a display driver timeout and recovery.",
         "Check for a manufacturer-recommended graphics driver and monitor whether the event recurs."),
        ("crash", "attention", "Windows logged a system crash",
         "Windows logged a bugcheck report.",
         "Use the manufacturer's diagnostics and have a technician review the Windows crash report if it repeats."),
        ("restart", "info", "Unexpected shutdown recorded",
         "Windows reported an unclean shutdown. Cause undetermined.",
         "Review related findings and run the manufacturer's diagnostics if shutdowns recur."),
    ):
        if events[group]:
            latest = max(entry["time"] for entry in events[group])
            add(group, severity, title,
                [evidence, f"{len(events[group])} matching events in the last 14 days. Latest: {latest}."],
                action)
    for device in data("inventory", {}).get("devices", []):
        add("device_status", "attention", "Windows reports a device problem",
            [f"{device['Name']} · Device Manager code {device['ConfigManagerErrorCode']}."],
            "Open Device Manager to see the device status and check the manufacturer's support page.")

    sections = report["sections"]
    for row in detail_data(sections, "volumes", "volumes") or []:
        if row.get("dirty") is True:
            add("volume_dirty", "attention", "Windows marked a file system dirty",
                [f"Volume {row['drive']} has its dirty flag set."],
                "Back up important files and check the volume with Windows Error checking.")
    health, verified = component_health(sections)
    if health in {"Repairable", "NonRepairable"}:
        source = "Component-store verification" if verified else "Windows servicing health record"
        add("component_store", "attention", "Windows component-store corruption reported",
            [f"{source}: {health}."],
            "Review Windows servicing errors and use the documented repair procedure if appropriate.")
    reboot = detail_data(sections, "windows_health", "reboot") or {}
    if any(value is True for value in reboot.values()):
        add("servicing_reboot", "info", "Windows servicing reports a pending restart",
            ["A servicing or Windows Update restart indicator is present."],
            "Save your work and check Windows Update for a restart request.")
    for group, title, action in (
        ("file_system", "Windows logged NTFS corruption", "Review the original events to identify the volume and back up important files."),
        ("firmware_limit", "Firmware limited processor speed", "Compare AC and battery operation and review the manufacturer's power settings."),
        ("memory_exhaustion", "Windows logged virtual-memory exhaustion", "Review commit usage and page-file configuration, then repeat the scan during the slowdown."),
        ("update_failure", "Windows logged update installation failures", "Open Windows Update history to see the affected updates and whether they later installed."),
        ("app_failures", "Windows logged application crashes or hangs", "Use Reliability Monitor to check which applications repeatedly failed."),
    ):
        if events[group]:
            add(group, "attention" if group in {"file_system", "memory_exhaustion"} else "info",
                title, [f"{len(events[group])} matching events in the last 14 days."], action)
    for adapter in data("network", []):
        if (adapter.get("ipv4_link_local_only") is True and
                adapter.get("ipv4_connectivity") in {"LocalNetwork", "Subnet", "NoTraffic"} and
                adapter.get("ipv6_connectivity") in {"LocalNetwork", "Subnet", "NoTraffic"}):
            add("network_addressing", "info", "Connected adapter has limited IP configuration",
                [f"{adapter['description']}: only a link-local IPv4 address; Windows reports limited connectivity."],
                "If the network should provide internet access, check its DHCP settings and compare another device.")

    return sorted(findings, key=lambda item: PRIORITIES[item["severity"]])
