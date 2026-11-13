param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('inventory', 'battery', 'storage', 'events', 'performance')]
    [string]$Section
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
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
    foreach ($disk in Get-Disk) {
        $counter = $null
        try { $counter = Get-StorageReliabilityCounter -Disk $disk } catch {}
        [ordered]@{
            number = $disk.Number
            model = $disk.FriendlyName
            health = [string]$disk.HealthStatus
            size = $disk.Size
            temperature = $counter.Temperature
            wear = $counter.Wear
            read_uncorrected = $counter.ReadErrorsUncorrected
            write_uncorrected = $counter.WriteErrorsUncorrected
        }
    }
}

function Get-EventData {
    $start = (Get-Date).AddDays(-14)
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    $queries = @(
        @{ ProviderName = 'Microsoft-Windows-Kernel-Power'; Id = 41 },
        @{ ProviderName = 'Microsoft-Windows-WHEA-Logger'; Id = @(17, 18, 19, 20, 46, 47) },
        @{ ProviderName = 'Display'; Id = 4101 },
        @{ ProviderName = 'disk'; Id = @(7, 51, 153, 157) },
        @{ ProviderName = 'storahci'; Id = 129 },
        @{ ProviderName = 'stornvme'; Id = 129 },
        @{ ProviderName = 'Microsoft-Windows-WER-SystemErrorReporting'; Id = 1001 },
        @{ ProviderName = 'Microsoft-Windows-MemoryDiagnostics-Results'; Id = @(1101, 1201, 1202) }
    )
    $unavailable = @()
    $events = @(
        foreach ($filter in $queries) {
            $filter.LogName = 'System'
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
    [ordered]@{ entries = $events; unavailable = $unavailable }
}

function Get-InventoryData {
    $computer = Get-CimInstance Win32_ComputerSystem
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = @(Get-CimInstance Win32_Processor | ForEach-Object { $_.Name.Trim() })
    $gpu = @(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)
    $devices = @(Get-CimInstance Win32_PnPEntity -Filter 'Present = TRUE')
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

function Get-PerformanceData {
    $os = Get-CimInstance Win32_OperatingSystem
    $samples = @(
        for ($i = 0; $i -lt 5; $i++) {
            $memory = $null
            $disk = $null
            $cpu = $null
            try { $memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory } catch {}
            try { $disk = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -Filter "Name = '_Total'" } catch {}
            try { $cpu = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name = '_Total'" } catch {}
            [ordered]@{
                memory_total_mib = [double]$os.TotalVisibleMemorySize / 1024
                memory_available_mib = $memory.AvailableMBytes
                pages_input_sec = $memory.PagesInputPersec
                disk_queue = $disk.AvgDiskQueueLength
                cpu_percent = $cpu.PercentProcessorTime
            }
            if ($i -lt 4) { Start-Sleep -Seconds 1 }
        }
    )
    $volume = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID = '$($env:SystemDrive)'"
    [ordered]@{
        samples = $samples
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
}
ConvertTo-Json -InputObject $result -Depth 8 -Compress
