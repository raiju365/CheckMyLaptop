# Diagnostic rules

CheckMyLaptop collects five independent sections. A failed query is marked unavailable and the remaining checks still run. Reports sort findings by severity and preserve the observations that triggered each rule.

| Finding | Evidence and interpretation |
| --- | --- |
| Storage needs attention | Windows reports warning/unhealthy status, or the drive reports at least one uncorrected read/write error. The raw error count may be historical. At least two Event ID 153 retries tied to that Windows disk number during the current boot add supporting evidence when Windows exposes the device reference. Disk numbers can be reassigned, especially for removable drives. |
| Storage interruptions | Selected disk/controller events within the 14-day window. Possible causes include the drive, controller, driver or connection. |
| Reduced battery capacity | Reported full-charge capacity is below 75% of design capacity. This is a screening threshold and should be compared with actual runtime. |
| Low free space | Free space is below the lesser of 10% of the system volume or 15 GiB. |
| Memory pressure with disk activity | At least three samples have available RAM below the lesser of 1,024 MiB or 10% of visible memory, at least 50 pages input per second and a disk queue of at least one. Paging counters include reads other than the pagefile. |
| Low available memory | At least three samples meet the low-memory condition, with weaker evidence linking it to disk activity. |
| Memory test errors | Windows Memory Diagnostic Event ID 1202. The application reads past results. |
| Graphics recovery near a crash | A display recovery was logged within two minutes of a bugcheck report. A crash dump can help investigate whether the two events share a cause. |
| Graphics recovery | Display Event ID 4101. Timeout and recovery can have software or hardware causes. |
| Hardware events | Selected WHEA events, including some corrected errors. The events alone do not identify a part to replace. |
| System crash or unexpected shutdown | Selected bugcheck reports or Kernel-Power Event ID 41. Event 41 records an unclean shutdown. |
| Device problem | A present Plug and Play device has a nonzero configuration-manager code other than intentionally disabled (22). |

The event collector fetches at most 80 matching records per provider query. The five live performance samples are spaced about a second apart and reflect the conditions during the scan. The scan does not change workload or run a stress test.

## Upstream references

- [Windows PowerCfg options](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options)
- [Storage reliability counters](https://learn.microsoft.com/en-us/powershell/module/storage/get-storagereliabilitycounter)
- [Windows hardware error events](https://learn.microsoft.com/en-us/windows-hardware/drivers/whea/whea-hardware-error-events)
- [Graphics timeout detection and recovery](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/timeout-detection-and-recovery)
- [Troubleshooting Kernel-Power Event ID 41](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/event-id-41-restart)
