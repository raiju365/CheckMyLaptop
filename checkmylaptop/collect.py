"""Read Windows diagnostic data without elevation or system changes."""

import ctypes
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .performance import summarize_performance

SECTIONS = {
    "inventory": ("Hardware inventory", dict),
    "battery": ("Battery", list),
    "storage": ("Storage", list),
    "events": ("System event history", dict),
    "performance": ("Live performance and free space", dict),
    "network": ("Network adapter status", list),
    "volumes": ("Local volumes and file systems", dict),
    "drivers": ("Device drivers", dict),
    "platform": ("Firmware, power and memory modules", dict),
    "windows_health": ("Windows servicing and page file", dict),
    "protection": ("Windows protection status", dict),
}
DETAIL_SECTIONS = {
    "volumes": {"volumes": "Fixed volumes", "disk_map": "Volume-to-disk mapping"},
    "drivers": {"devices": "Present devices and driver packages"},
    "platform": {"firmware": "BIOS and boot time", "memory": "Memory modules",
                 "power": "AC and battery status", "thermal": "ACPI thermal zones"},
    "windows_health": {"reboot": "Servicing reboot indicators", "page_file": "Page-file usage",
                       "component_store": "Previously recorded component-store health"},
    "protection": {"secure_boot": "Secure Boot", "tpm": "TPM", "firewall": "Windows Firewall",
                   "defender": "Microsoft Defender", "encryption": "System-volume encryption"},
}
CONSENT_NOTICE = (
    "CheckMyLaptop will read local hardware, drivers, Windows events, running process names, "
    "network status and Windows protection settings. It will use the permissions of the current "
    "Windows session. Reports stay local and are only saved when you choose to export. "
    "The scan makes no repairs or network probes. Windows may write a servicing log."
)
VERIFICATION_NOTICE = (
    "Windows component verification can take up to 15 minutes and writes a Windows servicing log."
)
SCRIPT = Path(__file__).with_name("windows.ps1")
NATIVE_NAME = "checkmylaptop-performance.exe"
BACKGROUND_CHECKS = (
    "protection", "drivers", "network", "volumes", "platform", "windows_health",
    "storage", "inventory", "events", "battery",
)


def read_section(section: str) -> dict:
    if section == "performance" and sys.platform == "win32":
        executable = SCRIPT.with_name(NATIVE_NAME) if getattr(sys, "frozen", False) else (
            SCRIPT.parent.parent / "build" / NATIVE_NAME
        )
        if executable.is_file():
            result = _read_json([str(executable), "--allow"], dict, timeout=15)
            data = result.get("data", {})
            if (isinstance(data.get("samples"), list) and len(data["samples"]) == 8
                    and data.get("processes_start") and data.get("processes_end")):
                data["source"] = "native"
                return result
    result = _read_collector(section, SECTIONS[section][1], timeout=40)
    if section == "performance" and result["state"] == "checked":
        result["data"]["source"] = "powershell"
    return result


def _read_collector(section: str, expected_type: type, *, timeout: int) -> dict:
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
        r"System32\WindowsPowerShell\v1.0\powershell.exe"
    )
    # Use a process-scoped policy for the bundled, fixed collector. Group Policy
    # still takes precedence. No system-wide execution policy is changed.
    command = [
        str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), section,
    ]
    return _read_json(command, expected_type, timeout=timeout)


def _read_json(command: list[str], expected_type: type, *, timeout: int) -> dict:
    try:
        process = subprocess.run(
            command, capture_output=True, timeout=timeout, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(process.stdout.decode("utf-8-sig"))
        if not isinstance(data, expected_type):
            raise ValueError("Unexpected section format")
    except subprocess.TimeoutExpired:
        return {"state": "unavailable", "reason": "The Windows query timed out."}
    except (OSError, subprocess.CalledProcessError, ValueError):
        return {
            "state": "unavailable",
            "reason": "Windows did not return readable data for this check.",
        }
    return {"state": "checked", "data": data}


def scan(progress: Callable[[str], None] | None = None, *, allow: bool = False,
         verify_windows: bool = False) -> dict:
    if not allow:
        raise PermissionError("Live diagnostics require explicit consent for each scan.")
    if sys.platform != "win32":
        raise RuntimeError("Live scans require Windows. Use --demo on other platforms.")
    administrator = bool(ctypes.windll.shell32.IsUserAnAdmin())
    report = {"scanned_at": datetime.now(timezone.utc).isoformat(), "sections": {},
              "administrator": administrator}
    if progress:
        progress("Sampling CPU, memory and disk while checking Windows…")
    with ThreadPoolExecutor(max_workers=7) as executor:
        performance = executor.submit(read_section, "performance")
        inventory_checks = {
            executor.submit(read_section, name): name
            for name in BACKGROUND_CHECKS
        }
        for future in as_completed(inventory_checks):
            name = inventory_checks[future]
            report["sections"][name] = future.result()
            if progress:
                progress(f"Completed {SECTIONS[name][0].lower()}")
    performance_result = performance.result()
    if performance_result["state"] == "checked":
        data = performance_result["data"]
        metrics = summarize_performance(data)
        if any(metrics[key] >= metrics["required"] for key in (
            "low_count", "commit_high_count", "cpu_high_count", "queue_high_count",
        )):
            if progress:
                progress("Rechecking performance after the other checks finished…")
            performance_result = read_section("performance")
            if performance_result["state"] == "checked":
                performance_result["data"]["collection"] = "isolated"
            else:
                performance_result["reason"] = (
                    "The parallel samples showed resource pressure. An isolated recheck could not confirm it. "
                    + performance_result.get("reason", "")
                ).strip()
        else:
            data["collection"] = "parallel"
    report["sections"]["performance"] = performance_result
    if verify_windows:
        if administrator:
            if progress:
                progress("Verifying the Windows component store. This can take several minutes…")
            result = _read_collector("verify_windows", dict, timeout=900)
        else:
            result = {"state": "unavailable", "reason": "Verification requires Administrator privileges."}
        report["sections"]["windows_verification"] = result
    return report
