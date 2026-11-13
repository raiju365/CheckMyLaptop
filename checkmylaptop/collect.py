"""Read Windows diagnostic data without elevation or system changes."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SECTIONS = {
    "inventory": ("Hardware inventory", dict),
    "battery": ("Battery", list),
    "storage": ("Storage", list),
    "events": ("System event history", dict),
    "performance": ("Live performance and free space", dict),
}
SCRIPT = Path(__file__).with_name("windows.ps1")


def read_section(section: str) -> dict:
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
        r"System32\WindowsPowerShell\v1.0\powershell.exe"
    )
    # Use a process-scoped policy for the bundled, fixed collector. Group Policy
    # still takes precedence. No system-wide execution policy is changed.
    command = [
        str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), section,
    ]
    try:
        process = subprocess.run(
            command, capture_output=True, timeout=40, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(process.stdout.decode("utf-8-sig"))
        if not isinstance(data, SECTIONS[section][1]):
            raise ValueError("Unexpected section format")
    except subprocess.TimeoutExpired:
        return {"state": "unavailable", "reason": "The Windows query timed out."}
    except (OSError, subprocess.CalledProcessError, ValueError):
        return {
            "state": "unavailable",
            "reason": "Windows did not return readable data for this check.",
        }
    return {"state": "checked", "data": data}


def scan(progress: Callable[[str], None] | None = None) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("Live scans require Windows. Use --demo on other platforms.")
    report = {"scanned_at": datetime.now(timezone.utc).isoformat(), "sections": {}}
    with ThreadPoolExecutor(max_workers=4) as executor:
        pending = {name: executor.submit(read_section, name) for name in SECTIONS}
        for name, (label, _) in SECTIONS.items():
            if progress:
                progress(label)
            report["sections"][name] = pending[name].result()
    return report
