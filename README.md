# CheckMyLaptop

**One-click Windows laptop diagnostics with evidence and next steps.**

CheckMyLaptop reads hardware inventory, battery capacity, storage reliability data, live performance counters and selected Windows events. It combines related findings and tells you what to check first. A scan runs locally and requires no symptom input.

## Run a scan

### Windows executable

1. Open [Releases](https://github.com/raiju365/CheckMyLaptop/releases) and download `CheckMyLaptop.exe` if a release asset is available. The current build target is Windows x64.
2. Open the executable as a standard user and select **Scan laptop**.
3. Read the highest-priority findings first. Scroll to **Scan coverage** in the report to see which checks returned data.
4. Select **Save report** if you want to keep a TXT or JSON copy. Review it before sharing.

### Run from source

Use Windows 11 with Python 3.11 or newer and Tcl/Tk for the desktop interface. Windows PowerShell 5.1 and the built-in Windows management tools supply the diagnostic data.

```powershell
git clone https://github.com/raiju365/CheckMyLaptop.git
cd CheckMyLaptop
py -3 -m checkmylaptop
```

You can also double-click `CheckMyLaptop.cmd` from the extracted source folder. The CLI and simulated scan are available without Tcl/Tk.

```powershell
py -3 -m checkmylaptop --cli
py -3 -m checkmylaptop --cli --json report.json
py -3 -m checkmylaptop --demo --cli
```

On Linux or macOS, use `python3 -m checkmylaptop --demo --cli` for a simulated report.

## Scan coverage

| Area | Data checked |
| --- | --- |
| Hardware and devices | Windows hardware inventory and Device Manager problem codes |
| Battery | Full-charge and design capacities reported by Windows |
| Storage | Windows disk health, supported reliability counters, recent storage events and system-drive free space |
| Memory and performance | Short series of samples for available RAM, page reads, disk queue and CPU load. Prior Windows memory-test errors are also checked. |
| Graphics, crashes and hardware errors | Selected display, bugcheck, unexpected-shutdown and WHEA events from the last 14 days |

A storage warning may include repeated I/O retries linked to the same reported disk number during the current boot. Memory pressure is reported when low available RAM coincides with paging and a disk queue in several samples. A restart record on its own leaves the cause undetermined. See [diagnostic rules](docs/diagnostics.md) for evidence and thresholds.

## Disclaimer and privacy

CheckMyLaptop is a screening tool. A scan with no findings can still miss intermittent faults or components with unavailable data. Use the manufacturer's diagnostics or a qualified technician to confirm hardware failure before replacing parts. Prioritize backing up important files when a storage finding recommends it.

This version uses passive checks. Dedicated stability tests, temperature and fan checks, and functional tests of the display, keyboard, ports and peripherals require separate tools or manual inspection. Available data varies by Windows configuration, permissions, drivers and hardware.

The app makes no network requests, performs no repairs and leaves Windows settings untouched. It runs its bundled Windows PowerShell collector with a process-scoped execution policy and removes the temporary battery report after normal collection. Exported reports include finding details such as laptop and disk models, device names and selected event timestamps. They omit raw event messages, usernames, hardware serial numbers and the machine name.

## Development

```text
python -m unittest discover -s tests -v
python -m checkmylaptop --demo --cli
```

GitHub Actions tests the Python code and runs the collectors on a Windows runner. An Actions workflow packages the Windows executable when a maintainer pushes a version tag. See [CONTRIBUTING.md](CONTRIBUTING.md) for tests, local builds and release instructions.

[Petunjuk penggunaan dalam Bahasa Indonesia](docs/panduan-id.md)

Licensed under the [MIT License](LICENSE).
