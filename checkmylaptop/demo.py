"""Synthetic scan for previews and troubleshooting the presentation layer."""

from datetime import datetime, timedelta, timezone


def snapshot() -> dict:
    now = datetime.now(timezone.utc)
    event_time = (now - timedelta(hours=2)).isoformat()
    return {
        "scanned_at": now.isoformat(),
        "sections": {
            "inventory": {"state": "checked", "data": {
                "manufacturer": "Example", "model": "Demo Notebook",
                "os": "Windows 11", "build": "26100", "memory_bytes": 8 * 1024**3,
                "cpu": ["Demo Processor"], "gpu": ["Demo Graphics"], "devices": [],
                "device_classes": [{"Name": "Keyboard", "Count": 1}],
            }},
            "battery": {"state": "checked", "data": [
                {"DesignCapacity": 50000, "FullChargeCapacity": 31000, "CycleCount": 480},
            ]},
            "storage": {"state": "checked", "data": [
                {"number": 0, "model": "Demo SSD", "health": "Warning", "read_uncorrected": 4},
                {"number": 1, "model": "Demo external disk", "health": "Healthy"},
            ]},
            "events": {"state": "checked", "data": {"entries": [
                {"id": 153, "provider": "disk", "time": event_time, "disk": 0,
                 "current_boot": True},
                {"id": 153, "provider": "disk", "time": event_time, "disk": 0,
                 "current_boot": True},
                {"id": 41, "provider": "Microsoft-Windows-Kernel-Power", "time": event_time},
            ], "unavailable": []}},
            "performance": {"state": "checked", "data": {
                "system_drive": "C:", "system_size": 256 * 1024**3, "system_free": 8 * 1024**3,
                "samples": [
                    {"memory_total_mib": 8192, "memory_available_mib": 480,
                     "pages_input_sec": 75, "disk_queue": 2, "cpu_percent": 22}
                    for _ in range(5)
                ],
            }},
        },
    }
