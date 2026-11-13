"""Turn collected evidence into conservative, explainable findings."""

from datetime import datetime, timedelta

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
}
PRIORITIES = {"high": 0, "attention": 1, "info": 2}
MANUAL_COVERAGE = [
    "CPU/GPU temperatures and fan operation",
    "Dedicated RAM, CPU and GPU stability tests",
    "Display pixels, keyboard and touchpad operation",
    "Speaker, microphone, camera and Wi-Fi functionality",
    "Individual USB, charging and video ports",
    "Physical inspection and motherboard faults",
]


def nearby_events(first: list[dict], second: list[dict]) -> int:
    first_times = [datetime.fromisoformat(entry["time"]) for entry in first]
    second_times = [datetime.fromisoformat(entry["time"]) for entry in second]
    window = timedelta(minutes=2)
    return sum(any(abs(event - other) <= window for other in second_times)
               for event in first_times)


def diagnose(report: dict) -> list[dict]:
    def data(section, default):
        return report["sections"].get(section, {}).get("data", default)

    findings = []

    def add(code, severity, title, evidence, action):
        findings.append(dict(code=code, severity=severity, title=title,
                             evidence=evidence, action=action))

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
                "Back up important files, then run the manufacturer's storage diagnostic.")
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
    if size and free is not None and free < min(size * 0.10, 15 * 1024**3):
        add("free_space", "attention", "Low space on the Windows drive",
            [f"{perf.get('system_drive', 'System drive')} has {free / 1024**3:.1f} GiB free."],
            "Review Windows Settings → System → Storage and free space before large updates.")
    samples = perf.get("samples", [])
    low = [
        sample for sample in samples
        if sample.get("memory_available_mib") is not None and
        sample["memory_available_mib"] < min(1024, sample["memory_total_mib"] * 0.10)
    ]
    paging = [sample for sample in low
              if (sample.get("pages_input_sec") or 0) >= 50 and
              (sample.get("disk_queue") or 0) >= 1]
    if len(paging) >= 3:
        add("memory_paging", "attention", "Memory pressure and disk activity coincided",
            [f"{len(paging)} of {len(samples)} samples had low available RAM, page reads, and a disk queue."],
            "Check Task Manager for memory-heavy apps, close one you do not need, then scan again.")
    elif len(low) >= 3:
        add("memory_low", "attention", "Low available memory during the scan",
            [f"Available RAM was low in {len(low)} of {len(samples)} samples."],
            "Review memory use in Task Manager and scan again after closing unused apps.")
    display_near_crashes = nearby_events(events["display"], events["crash"])
    if display_near_crashes:
        add("graphics_crash_timing", "attention", "Graphics recovery occurred near a system crash",
            [f"{display_near_crashes} graphics recovery events within two minutes of a bugcheck log.",
             "Event timing can suggest a shared incident. A crash dump is needed to investigate the cause."],
            "Check the manufacturer's graphics driver and have a technician review the crash dump.")
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

    return sorted(findings, key=lambda item: PRIORITIES[item["severity"]])
