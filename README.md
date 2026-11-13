# CheckMyLaptop

**In-depth Windows laptop diagnostics with evidence and next steps.**

CheckMyLaptop reads hardware, drivers, storage, power, performance, network status, Windows servicing and protection settings. The diagnostic summary combines findings that share a device, measurement interval or incident and explains what to check first. A scan runs locally and requires no symptom input.

## Run a scan

### Windows executable

1. Open [Releases](https://github.com/raiju365/CheckMyLaptop/releases), download `CheckMyLaptop-Windows-x64.zip` if available, and extract the whole folder. Keep the executable and its `_internal` directory together.
2. Open the executable, select **Scan laptop**, and approve the scan in the confirmation dialog.
3. Read **Diagnostic summary**, then check **Scan coverage** to see which data Windows supplied.
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
py -3 -m checkmylaptop --cli --allow --json report.json
py -3 -m checkmylaptop --demo --cli
```

On Linux or macOS, use `python3 -m checkmylaptop --demo --cli` for a simulated report.

The Windows ZIP includes the Go performance collector. For a source checkout, see the [build instructions](CONTRIBUTING.md#windows-packaging) to compile it. Source scans without the helper use Windows PowerShell.

In an interactive terminal, type `ALLOW` to start a live scan. Use `--allow` to explicitly authorize a scripted run. Demo mode uses simulated data.

The normal scan uses your current Windows privileges. For a full component-store verification, use a trusted copy of the app in a directory other users cannot modify, open it with **Run as administrator**, and select **Verify Windows components**. From source, run the following in an elevated terminal. Windows records a servicing log and the check can take up to 15 minutes. Windows may also log the quick health query during an elevated normal scan.

```powershell
py -3 -m checkmylaptop --cli --allow --verify-windows --json report.json
```

## Scan coverage

| Area | Data checked |
| --- | --- |
| Hardware and drivers | Device Manager problem codes, present-device driver versions and signing status, BIOS, uptime and RAM modules |
| Battery and power | Design and full-charge capacities, cycle counts, AC status, firmware CPU-limit events and exposed ACPI thermal zones |
| Storage and file systems | Disk health and reliability counters, fixed volume free space and dirty flags, volume-to-disk mapping and selected NTFS events |
| Memory and performance | Eight samples of available RAM, commit usage, page reads, disk queue and CPU load, plus process-group memory, page-file usage and previous memory diagnostic or exhaustion events. The Go collector also reads aggregate disk throughput and read/write latency. |
| Network | Physical adapter state, local packet counters and Windows IPv4/IPv6 connectivity classification |
| Windows reliability | Selected graphics recovery, bugcheck, application failures, WHEA and Windows Update events, plus servicing reboot indicators and component-store status |
| Windows protection | Secure Boot, TPM, Windows Firewall profiles, Defender mode and system-volume BitLocker status, where supported and accessible |

A storage warning may include repeated I/O retries linked to the same reported disk number during the current boot. The report distinguishes low available RAM, repeated overlap with paging and disk activity, and commit usage near the Windows limit. The ranked process list provides leads for investigation. A restart record on its own leaves the cause undetermined. See [diagnostic rules](docs/diagnostics.md) for evidence and thresholds.

## Disclaimer and privacy

CheckMyLaptop is a screening tool. A scan with no findings can still miss intermittent faults or components with unavailable data. Use the manufacturer's diagnostics or a qualified technician to confirm hardware failure before replacing parts. Prioritize backing up important files when a storage finding recommends it.

Dedicated stability tests, direct CPU/GPU and fan measurements, functional tests of the display and ports, malware detection and crash-dump analysis require separate tools. Available data varies by Windows configuration, permissions, drivers and hardware.

The app sends no network probes and performs no repairs. It removes the temporary battery report after collection. Reports can include hardware models, device and process names, driver and firmware versions, selected event timestamps and protection settings. The collector omits raw event messages, IP and MAC addresses, serial numbers and BitLocker keys. Review reports before sharing them.

## Development

```text
python -m unittest discover -s tests -v
python -m checkmylaptop --demo --cli
```

GitHub Actions tests the Python code and runs the collectors on a Windows runner. An Actions workflow packages the Windows executable when a maintainer pushes a version tag. See [CONTRIBUTING.md](CONTRIBUTING.md) for tests, local builds and release instructions.

[Petunjuk penggunaan dalam Bahasa Indonesia](docs/panduan-id.md)

Licensed under the [MIT License](LICENSE).
