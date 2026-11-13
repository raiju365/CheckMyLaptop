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
                     "pages_input_sec": 75, "disk_queue": 2, "cpu_percent": 22,
                     "commit_bytes": 15 * 1024**3, "commit_limit_bytes": 16 * 1024**3}
                    for _ in range(8)
                ],
                "processes_start": [
                    {"name": "demo-browser", "count": 6, "working_set_bytes": 2200 * 1024**2},
                ],
                "processes_end": [
                    {"name": "demo-browser", "count": 6, "working_set_bytes": 2500 * 1024**2},
                    {"name": "demo-editor", "count": 1, "working_set_bytes": 600 * 1024**2},
                ],
            }},
            "network": {"state": "checked", "data": [
                {"description": "Demo Wi-Fi adapter", "status": "Up",
                 "receive_errors": 0, "send_errors": 0},
            ]},
            "volumes": {"state": "checked", "data": {
                "volumes": {"state": "checked", "data": [
                    {"drive": "C:", "file_system": "NTFS", "dirty": True,
                     "free_bytes": 8 * 1024**3, "size_bytes": 256 * 1024**3},
                ]},
                "disk_map": {"state": "checked", "data": [{"drive": "C:", "disk": 0}]},
            }},
            "platform": {"state": "checked", "data": {
                "firmware": {"state": "checked", "data": {"version": "Demo 1.0"}},
                "memory": {"state": "checked", "data": [{"capacity_bytes": 8 * 1024**3}]},
                "power": {"state": "checked", "data": {"ac": "Online", "battery_status": "High"}},
            }},
        },
    }
