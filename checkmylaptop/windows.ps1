param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('inventory', 'battery', 'storage', 'events', 'performance', 'network',
                 'volumes', 'drivers', 'platform', 'windows_health', 'protection', 'verify_windows')]
    [string]$Section
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$WarningPreference = 'SilentlyContinue'
$env:PSModulePath = Join-Path $PSHOME 'Modules'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

function Get-BatteryData {
    $path = [IO.Path]::Combine([IO.Path]::GetTempPath(), [guid]::NewGuid().ToString() + '.xml')
    try {
        & (Join-Path $env:SystemRoot 'System32\powercfg.exe') /batteryreport /xml /output $path | Out-Null
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $path)) {
            throw 'Battery report unavailable'
        }
        [xml]$report = Get-Content -LiteralPath $path -Raw
        foreach ($battery in $report.SelectNodes("//*[local-name()='Batteries']/*[local-name()='Battery']")) {
            $row = [ordered]@{}
            foreach ($name in @('DesignCapacity', 'FullChargeCapacity', 'CycleCount')) {
                $node = $battery.SelectSingleNode("*[local-name()='$name']")
                $value = 0L
                if ($null -ne $node -and [long]::TryParse($node.InnerText, [ref]$value) -and $value -ge 0) {
                    $row[$name] = $value
                }
            }
            $row
        }
    }
    finally {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}

function Get-StorageData {
    $physical = @()
    try { $physical = @(Get-PhysicalDisk) } catch {}
    foreach ($disk in Get-Disk) {
        $counter = $null
        try { $counter = Get-StorageReliabilityCounter -Disk $disk } catch {}
        $source = 'Get-Disk'
        if ($null -eq $counter -or ($null -eq $counter.Wear -and
            $null -eq $counter.ReadErrorsUncorrected -and $null -eq $counter.WriteErrorsUncorrected)) {
            if ($disk.UniqueId) {
                $id = $disk.UniqueId.Trim()
                $matches = @($physical | Where-Object { $_.UniqueId -and $_.UniqueId.Trim() -eq $id })
                if ($matches.Count -eq 1) {
                    try {
                        $alternate = Get-StorageReliabilityCounter -PhysicalDisk $matches[0]
                        if ($null -ne $alternate) { $counter = $alternate; $source = 'Get-PhysicalDisk' }
                    } catch {}
                }
            }
        }
        [ordered]@{
            number = $disk.Number
            model = $disk.FriendlyName
            health = [string]$disk.HealthStatus
            size = $disk.Size
            bus = [string]$disk.BusType
            operational = @($disk.OperationalStatus | ForEach-Object { [string]$_ })
            counter_source = $(if ($null -ne $counter) { $source })
            temperature = $counter.Temperature
            wear = $counter.Wear
            read_uncorrected = $counter.ReadErrorsUncorrected
            write_uncorrected = $counter.WriteErrorsUncorrected
        }
    }
}

function Get-EventData {
    $start = (Get-Date).AddDays(-14)
    $boot = (Get-CimInstance Win32_OperatingSystem -Property LastBootUpTime).LastBootUpTime
    $queries = @(
        @{ ProviderName = 'Microsoft-Windows-Kernel-Power'; Id = 41 },
        @{ ProviderName = 'Microsoft-Windows-WHEA-Logger'; Id = @(17, 18, 19, 20, 46, 47) },
        @{ ProviderName = 'Display'; Id = 4101 },
        @{ ProviderName = 'disk'; Id = @(7, 51, 153, 157) },
        @{ ProviderName = 'storahci'; Id = 129 },
        @{ ProviderName = 'stornvme'; Id = 129 },
        @{ ProviderName = 'Microsoft-Windows-WER-SystemErrorReporting'; Id = 1001 },
        @{ ProviderName = 'Microsoft-Windows-MemoryDiagnostics-Results'; Id = @(1101, 1201, 1202) },
        @{ ProviderName = 'Microsoft-Windows-Kernel-Processor-Power'; Id = 37 },
        @{ ProviderName = 'Microsoft-Windows-Ntfs'; Id = 55 },
        @{ ProviderName = 'Microsoft-Windows-WindowsUpdateClient'; Id = 20 },
        @{ ProviderName = 'Microsoft-Windows-Resource-Exhaustion-Detector'; Id = 2004 },
        @{ ProviderName = 'Application Error'; Id = 1000; LogName = 'Application' },
        @{ ProviderName = 'Application Hang'; Id = 1002; LogName = 'Application' }
    )
    $unavailable = @()
    $events = @(
        foreach ($filter in $queries) {
            if (-not $filter.ContainsKey('LogName')) { $filter.LogName = 'System' }
            $filter.StartTime = $start
            try {
                $entries = Get-WinEvent -FilterHashtable $filter -MaxEvents 80
            } catch {
                if ($_.FullyQualifiedErrorId -notlike 'NoMatchingEventsFound,*') {
                    $unavailable += $filter.ProviderName
                }
                continue
            }
            foreach ($entry in $entries) {
                $diskNumber = $null
                if ($entry.ProviderName -eq 'disk') {
                    if ($entry.Id -eq 153) {
                        [xml]$xml = $entry.ToXml()
                        $numberNode = $xml.SelectSingleNode("//*[local-name()='Data' and (@Name='DiskNumber' or @Name='DeviceNumber')]")
                        $parsedNumber = 0
                        if ($null -ne $numberNode -and [int]::TryParse($numberNode.InnerText, [ref]$parsedNumber)) {
                            $diskNumber = $parsedNumber
                        }
                    }
                    foreach ($prop in $entry.Properties) {
                        $match = [regex]::Match([string]$prop.Value, '(?i)^\\Device\\Harddisk(\d+)(?:\\DR\d+)?$')
                        if ($match.Success) { $diskNumber = [int]$match.Groups[1].Value; break }
                    }
                }
                [ordered]@{
                    id = $entry.Id
                    provider = $entry.ProviderName
                    time = $entry.TimeCreated.ToUniversalTime().ToString('o')
                    disk = $diskNumber
                    current_boot = ($entry.TimeCreated -ge $boot)
                }
            }
        }
    )
    [ordered]@{ entries = $events; unavailable = $unavailable; query_count = $queries.Count }
}

function Get-InventoryData {
    $computer = Get-CimInstance Win32_ComputerSystem -Property Manufacturer,Model,TotalPhysicalMemory
    $os = Get-CimInstance Win32_OperatingSystem -Property Caption,BuildNumber
    $cpu = @(Get-CimInstance Win32_Processor -Property Name | ForEach-Object { $_.Name.Trim() })
    $gpu = @(Get-CimInstance Win32_VideoController -Property Name | Select-Object -ExpandProperty Name)
    $devices = @(Get-CimInstance Win32_PnPEntity -Filter 'Present = TRUE' -Property Name,PNPClass,ConfigManagerErrorCode)
    $deviceIssues = @($devices | Where-Object { $_.ConfigManagerErrorCode -notin @(0, 22, $null) } |
        Select-Object -First 25 Name, PNPClass, ConfigManagerErrorCode)
    $deviceClasses = @($devices | Group-Object PNPClass | Where-Object { $_.Name } |
        Sort-Object Name | Select-Object Name, Count)
    [ordered]@{
        manufacturer = $computer.Manufacturer
        model = $computer.Model
        os = $os.Caption
        build = $os.BuildNumber
        memory_bytes = $computer.TotalPhysicalMemory
        cpu = $cpu
        gpu = $gpu
        devices = $deviceIssues
        device_classes = $deviceClasses
    }
}

function Get-ProcessData {
    Get-Process | Where-Object { $_.Id -notin @(0, 4, $PID) } |
        Group-Object ProcessName | ForEach-Object {
            [ordered]@{
                name = $_.Name
                count = $_.Count
                working_set_bytes = ($_.Group | Measure-Object WorkingSet64 -Sum).Sum
                private_bytes = ($_.Group | Measure-Object PrivateMemorySize64 -Sum).Sum
            }
        } | Sort-Object { $_.working_set_bytes } -Descending | Select-Object -First 12
}

function Get-NetworkData {
    $profiles = $null
    try { $profiles = @(Get-NetConnectionProfile) } catch {}
    foreach ($adapter in Get-NetAdapter -Physical) {
        $stats = $null
        $profile = $null
        $linkLocalOnly = $null
        if ($null -ne $profiles) {
            $profile = $profiles | Where-Object InterfaceIndex -eq $adapter.ifIndex | Select-Object -First 1
        }
        try { $stats = $adapter | Get-NetAdapterStatistics } catch {}
        if ($adapter.Status -eq 'Up') {
            try {
                $addresses = @(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4)
                if ($addresses.Count) {
                    $linkLocalOnly = (@($addresses | Where-Object { $_.IPAddress -notlike '169.254.*' }).Count -eq 0)
                }
            } catch {}
        }
        [ordered]@{
            description = $adapter.InterfaceDescription
            status = [string]$adapter.Status
            receive_errors = $stats.ReceivedPacketErrors
            send_errors = $stats.OutboundPacketErrors
            receive_discarded = $stats.ReceivedDiscardedPackets
            send_discarded = $stats.OutboundDiscardedPackets
            ipv4_link_local_only = $linkLocalOnly
            ipv4_connectivity = $(if ($profile) { [string]$profile.IPv4Connectivity })
            ipv6_connectivity = $(if ($profile) { [string]$profile.IPv6Connectivity })
        }
    }
}

function Read-DiagnosticQuery([scriptblock]$Query) {
    try {
        $value = & $Query
        if ($null -eq $value) { return @{ state = 'unavailable' } }
        return @{ state = 'checked'; data = $value }
    } catch {
        return @{ state = 'unavailable' }
    }
}

function Get-VolumeData {
    [ordered]@{
        volumes = Read-DiagnosticQuery {
            ,@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType = 3' | ForEach-Object {
                [ordered]@{
                    drive = $_.DeviceID
                    file_system = $_.FileSystem
                    dirty = $_.VolumeDirty
                    free_bytes = $_.FreeSpace
                    size_bytes = $_.Size
                }
            })
        }
        disk_map = Read-DiagnosticQuery {
            ,@(Get-Partition | Where-Object { $_.DriveLetter -match '^[A-Z]$' } | ForEach-Object {
                @{ drive = "$($_.DriveLetter):"; disk = $_.DiskNumber }
            })
        }
    }
}

function Get-DriverData {
    [ordered]@{
        devices = Read-DiagnosticQuery {
            $devices = @(Get-CimInstance Win32_PnPEntity -Filter 'Present = TRUE' -Property DeviceID,Name,PNPClass,ConfigManagerErrorCode)
            $packages = @{}
            Get-CimInstance Win32_PnPSignedDriver -Property DeviceID,DriverVersion,IsSigned | ForEach-Object {
                if ($_.DeviceID) { $packages[$_.DeviceID] = $_ }
            }
            ,@($devices | ForEach-Object {
                $package = $packages[$_.DeviceID]
                [ordered]@{
                    name = $_.Name
                    class = $_.PNPClass
                    error_code = $_.ConfigManagerErrorCode
                    version = $package.DriverVersion
                    signed = $package.IsSigned
                }
            })
        }
    }
}

function Get-PlatformData {
    [ordered]@{
        firmware = Read-DiagnosticQuery {
            $bios = Get-CimInstance Win32_BIOS
            $os = Get-CimInstance Win32_OperatingSystem
            @{
                version = $bios.SMBIOSBIOSVersion
                last_boot = $os.LastBootUpTime.ToUniversalTime().ToString('o')
            }
        }
        memory = Read-DiagnosticQuery {
            ,@(Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
                @{ capacity_bytes = $_.Capacity; configured_mts = $_.ConfiguredClockSpeed }
            })
        }
        power = Read-DiagnosticQuery {
            Add-Type -AssemblyName System.Windows.Forms
            $power = [System.Windows.Forms.SystemInformation]::PowerStatus
            @{
                ac = [string]$power.PowerLineStatus
                battery_status = [string]$power.BatteryChargeStatus
            }
        }
        thermal = Read-DiagnosticQuery {
            $zones = @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature |
                Where-Object { $_.CurrentTemperature -gt 0 } | ForEach-Object {
                    @{ celsius = [math]::Round($_.CurrentTemperature / 10.0 - 273.15, 1) }
                } | Where-Object { $_.celsius -ge -20 -and $_.celsius -le 150 })
            if ($zones.Count) { ,$zones }
        }
    }
}

function Get-WindowsHealthData {
    [ordered]@{
        reboot = Read-DiagnosticQuery {
            @{
                component_servicing = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
                windows_update = Test-Path -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
            }
        }
        page_file = Read-DiagnosticQuery {
            $computer = Get-CimInstance Win32_ComputerSystem
            @{
                managed = $computer.AutomaticManagedPagefile
                files = @(Get-CimInstance Win32_PageFileUsage | ForEach-Object {
                    @{ allocated_mib = $_.AllocatedBaseSize; used_mib = $_.CurrentUsage; peak_mib = $_.PeakUsage }
                })
            }
        }
        component_store = Read-DiagnosticQuery {
            $image = Repair-WindowsImage -Online -CheckHealth -LimitAccess -NoRestart
            if ($null -ne $image.ImageHealthState) { @{ health = [string]$image.ImageHealthState } }
        }
    }
}

function Get-VerifiedComponentStore {
    $image = Repair-WindowsImage -Online -ScanHealth -LimitAccess -NoRestart
    if ($null -eq $image.ImageHealthState) { throw 'Component-store health unavailable' }
    @{ health = [string]$image.ImageHealthState }
}

function Get-ProtectionData {
    [ordered]@{
        secure_boot = Read-DiagnosticQuery { @{ enabled = Confirm-SecureBootUEFI } }
        tpm = Read-DiagnosticQuery {
            $tpm = Get-Tpm
            if ($tpm) { @{ present = $tpm.TpmPresent; ready = $tpm.TpmReady } }
        }
        firewall = Read-DiagnosticQuery {
            ,@(Get-NetFirewallProfile -PolicyStore ActiveStore | ForEach-Object {
                @{ profile = $_.Name; enabled = [string]$_.Enabled }
            })
        }
        defender = Read-DiagnosticQuery {
            $defender = Get-MpComputerStatus
            if ($defender) {
                @{ mode = $defender.AMRunningMode; realtime = $defender.RealTimeProtectionEnabled }
            }
        }
        encryption = Read-DiagnosticQuery {
            $volume = Get-BitLockerVolume -MountPoint $env:SystemDrive
            if ($volume) {
                @{ protection = [string]$volume.ProtectionStatus; status = [string]$volume.VolumeStatus }
            }
        }
    }
}

function Get-PerformanceData {
    $os = Get-CimInstance Win32_OperatingSystem -Property TotalVisibleMemorySize
    $startProcesses = @()
    $endProcesses = @()
    try { $startProcesses = @(Get-ProcessData) } catch {}
    $samples = @(
        for ($i = 0; $i -lt 8; $i++) {
            $interval = [Diagnostics.Stopwatch]::StartNew()
            $sampleTime = [DateTime]::UtcNow.ToString('o')
            $memory = $null
            $disk = $null
            $cpu = $null
            try { $memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -Property CommittedBytes,CommitLimit,AvailableMBytes,PagesInputPersec } catch {}
            try { $disk = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name = '_Total'" -Property AvgDiskQueueLength } catch {}
            try { $cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name = '_Total'" -Property PercentProcessorTime } catch {}
            [ordered]@{
                time = $sampleTime
                commit_bytes = $memory.CommittedBytes
                commit_limit_bytes = $memory.CommitLimit
                memory_total_mib = [double]$os.TotalVisibleMemorySize / 1024
                memory_available_mib = $memory.AvailableMBytes
                pages_input_sec = $memory.PagesInputPersec
                disk_queue = $disk.AvgDiskQueueLength
                cpu_percent = $cpu.PercentProcessorTime
            }
            $remaining = 1000 - $interval.ElapsedMilliseconds
            if ($i -lt 7 -and $remaining -gt 0) { Start-Sleep -Milliseconds $remaining }
        }
    )
    try { $endProcesses = @(Get-ProcessData) } catch {}
    $volume = $null
    try { $volume = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID = '$($env:SystemDrive)'" } catch {}
    [ordered]@{
        samples = $samples
        processes_start = $startProcesses
        processes_end = $endProcesses
        system_drive = $env:SystemDrive
        system_size = $volume.Size
        system_free = $volume.FreeSpace
    }
}

switch ($Section) {
    inventory { $result = Get-InventoryData }
    battery { $result = @(Get-BatteryData) }
    storage { $result = @(Get-StorageData) }
    events { $result = Get-EventData }
    performance { $result = Get-PerformanceData }
    network { $result = @(Get-NetworkData) }
    volumes { $result = Get-VolumeData }
    drivers { $result = Get-DriverData }
    platform { $result = Get-PlatformData }
    windows_health { $result = Get-WindowsHealthData }
    protection { $result = Get-ProtectionData }
    verify_windows { $result = Get-VerifiedComponentStore }
}
ConvertTo-Json -InputObject $result -Depth 8 -Compress
