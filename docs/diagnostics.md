# Diagnostic rules

CheckMyLaptop collects 11 sections after explicit consent. The optional Windows component-store verification has its own coverage entry. A failed query is marked unavailable and the remaining checks still run. Reports sort findings by severity and preserve the observations that triggered each rule. JSON report schema version 2 retains the existing fields and adds `administrator`, `conclusions` and `measurements.diagnostic_details`.

| Finding | Evidence and interpretation |
| --- | --- |
| Storage needs attention | Windows reports warning/unhealthy status, or the drive reports at least one uncorrected read/write error. The raw error count may be historical. At least two Event ID 153 retries tied to that Windows disk number during the current boot add supporting evidence when Windows exposes the device reference. Disk numbers can be reassigned, especially for removable drives. |
| Storage interruptions | Selected disk/controller events within the 14-day window. Possible causes include the drive, controller, driver or connection. |
| Reduced battery capacity | Reported full-charge capacity is below 75% of design capacity. This is a screening threshold and should be compared with actual runtime. |
| Low free space | Free space is below the lesser of 10% of the system volume or 15 GiB. |
| Memory pressure with disk activity | At least 60% of the scan samples, with a minimum of three, have available RAM below the lesser of 1,024 MiB or 10% of visible memory, at least 50 pages input per second and a disk queue of at least one. Paging counters include reads other than the pagefile. |
| Low available memory | At least 60% of the scan samples, with a minimum of three, meet the low-memory condition, with weaker evidence linking it to disk activity. |
| High memory commit | Commit reaches at least 90% of its reported limit in at least 60% of samples, with a minimum of three. A combined low-RAM finding requires both conditions to coincide in those samples. |
| Sustained CPU use or disk queue | CPU load reaches 90%, or the combined disk queue reaches two, in at least 60% of samples, with a minimum of three. Disk queue alone can reflect normal work. |
| Memory test errors | Windows Memory Diagnostic Event ID 1202. The application reads past results. |
| Graphics recovery near a crash | A display recovery was logged within two minutes of a bugcheck report. A crash dump can help investigate whether the two events share a cause. |
| Graphics recovery | Display Event ID 4101. Timeout and recovery can have software or hardware causes. |
| Hardware error reports near a crash | Selected WHEA IDs (18, 20, 46) appear within two minutes of a bugcheck report. Compare the original records in diagnostics before attributing the crash to any component. |
| Hardware events | Selected WHEA events, including some corrected errors. The events alone do not identify a part to replace. |
| System crash or unexpected shutdown | Selected bugcheck reports or Kernel-Power Event ID 41. Event 41 records an unclean shutdown. |
| Device problem | A present Plug and Play device has a nonzero configuration-manager code other than intentionally disabled (22). |
| File-system warning | A local fixed volume has its dirty flag set, or Windows logged a selected NTFS corruption event. The dirty flag can also follow an interrupted shutdown. |
| Firmware frequency limit | Kernel-Processor-Power Event ID 37 records firmware limiting CPU speed. It does not distinguish power policy, heat, or other platform limits. |
| Windows servicing | Reports component-store health, recorded installation failures and reboot indicators. The optional Administrator verification uses DISM ScanHealth; the quick query reads previously recorded health. An update failure can be historical. |
| Virtual-memory exhaustion | Windows logged Resource-Exhaustion-Detector Event ID 2004. Correlation with current performance depends on measurements from the current scan. |
| Local network addressing | An active physical adapter has only link-local IPv4 addressing and Windows reports limited connectivity on both address families. The finding does not imply a DHCP fault on networks designed for local traffic. |

## Diagnostic summary

`corroborated` means compatible observations support a specific condition. For example, a dirty volume and a storage warning must map to the same single Windows disk. Low RAM, paging and disk activity must overlap in repeated samples for a memory-pressure conclusion. Historical memory-exhaustion events add context to the live measurements.

`possible association` indicates that the observations warrant a joint investigation. A crash close to graphics or WHEA events and servicing corruption alongside update failures fall in this category. A single unclean shutdown, for example, leaves the cause undetermined. Multiple independent issues can appear in one report.

The event collector fetches at most 80 matching records per provider query from the last 14 days. The app takes eight live performance samples at intervals of at least one second, after the initial collection jobs finish and before any requested DISM verification. Process names are grouped and ranked by total resident working set, which can double-count shared pages. Changes compare name groups rather than individual processes. A name entering or leaving the tracked groups, or a change in the number of running instances, can affect the comparison.

The storage collector first queries reliability counters using the Windows disk object. If the key counters are missing, it retries through a physical disk object when a unique device identifier matches. The identifier is used locally and omitted from exported reports. Missing counters remain visible as partial coverage.

Network counters reflect adapter statistics reported by Windows. The scan sends no traffic and does not test internet reachability. The scan does not change workload or run a stress test.

ACPI thermal zones are firmware-defined and may have no direct mapping to the CPU or GPU. Windows protection statuses are local configuration observations. Defender can be passive on a device using another antivirus, and unavailable checks may require Administrator access or hardware support.

## Upstream references

- [Windows PowerCfg options](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options)
- [Storage reliability counters](https://learn.microsoft.com/en-us/powershell/module/storage/get-storagereliabilitycounter)
- [Windows hardware error events](https://learn.microsoft.com/en-us/windows-hardware/drivers/whea/whea-hardware-error-events)
- [Graphics timeout detection and recovery](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/timeout-detection-and-recovery)
- [Troubleshooting Kernel-Power Event ID 41](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/event-id-41-restart)

- [Windows memory counters](https://learn.microsoft.com/en-us/windows/win32/memory/memory-performance-information)
- [Windows network adapter statistics](https://learn.microsoft.com/en-us/powershell/module/netadapter/get-netadapterstatistics)
- [Win32_LogicalDisk and the VolumeDirty flag](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-logicaldisk)
- [Firmware processor limits and Event ID 37](https://learn.microsoft.com/en-us/troubleshoot/windows-server/setup-upgrade-and-drivers/event-id-37-windows-kernel-processor-power)
- [DISM CheckHealth and ScanHealth](https://learn.microsoft.com/en-us/powershell/module/dism/repair-windowsimage)
- [Secure Boot status and permissions](https://learn.microsoft.com/en-us/powershell/module/secureboot/confirm-securebootuefi)
