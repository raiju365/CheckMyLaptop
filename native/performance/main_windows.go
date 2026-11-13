package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"syscall"
	"time"
	"unsafe"
)

const sampleCount = 8

var (
	kernel             = syscall.NewLazyDLL("kernel32.dll")
	getSystemDirectory = kernel.NewProc("GetSystemDirectoryW")
	getPerformanceInfo = kernel.NewProc("K32GetPerformanceInfo")
	getDiskFreeSpace   = kernel.NewProc("GetDiskFreeSpaceExW")
)

type counter struct {
	key, path string
	required  bool
	handle    uintptr
}

type performanceInfo struct {
	size                                               uint32
	commitTotal, commitLimit, commitPeak               uintptr
	physicalTotal, physicalAvailable, systemCache      uintptr
	kernelTotal, kernelPaged, kernelNonpaged, pageSize uintptr
	handleCount, processCount, threadCount             uint32
}

type formattedCounter struct {
	status uint32
	_      uint32 // Windows aligns the double in PDH_FMT_COUNTERVALUE to eight bytes.
	value  float64
}

type measurement struct {
	Samples        []map[string]any `json:"samples"`
	ProcessesStart []processGroup   `json:"processes_start"`
	ProcessesEnd   []processGroup   `json:"processes_end"`
	SystemDrive    string           `json:"system_drive"`
	SystemSize     uint64           `json:"system_size"`
	SystemFree     uint64           `json:"system_free"`
}

func collect() (measurement, error) {
	var report measurement
	systemDirectory := make([]uint16, 32768)
	length, _, err := getSystemDirectory.Call(uintptr(unsafe.Pointer(&systemDirectory[0])), uintptr(len(systemDirectory)))
	if length == 0 || length >= uintptr(len(systemDirectory)) {
		return report, fmt.Errorf("read Windows system directory: %v", err)
	}
	systemPath := syscall.UTF16ToString(systemDirectory[:length])
	pdh, err := syscall.LoadDLL(filepath.Join(systemPath, "pdh.dll"))
	if err != nil {
		return report, err
	}
	defer pdh.Release()
	openQuery := pdh.MustFindProc("PdhOpenQueryW")
	addCounter := pdh.MustFindProc("PdhAddEnglishCounterW")
	collectData := pdh.MustFindProc("PdhCollectQueryData")
	readCounter := pdh.MustFindProc("PdhGetFormattedCounterValue")
	closeQuery := pdh.MustFindProc("PdhCloseQuery")

	var query uintptr
	status, _, _ := openQuery.Call(0, 0, uintptr(unsafe.Pointer(&query)))
	if status != 0 {
		return report, fmt.Errorf("open performance query: 0x%x", status)
	}
	defer closeQuery.Call(query)
	counters := []counter{
		{key: "cpu_percent", path: `\Processor(_Total)\% Processor Time`, required: true},
		{key: "pages_input_sec", path: `\Memory\Pages Input/sec`, required: true},
		{key: "disk_queue", path: `\PhysicalDisk(_Total)\Avg. Disk Queue Length`, required: true},
		{key: "disk_read_bytes_sec", path: `\PhysicalDisk(_Total)\Disk Read Bytes/sec`},
		{key: "disk_write_bytes_sec", path: `\PhysicalDisk(_Total)\Disk Write Bytes/sec`},
		{key: "disk_read_latency_ms", path: `\PhysicalDisk(_Total)\Avg. Disk sec/Read`},
		{key: "disk_write_latency_ms", path: `\PhysicalDisk(_Total)\Avg. Disk sec/Write`},
	}
	for i := range counters {
		item := &counters[i]
		path, err := syscall.UTF16PtrFromString(item.path)
		if err != nil {
			return report, err
		}
		status, _, _ := addCounter.Call(query, uintptr(unsafe.Pointer(path)), 0, uintptr(unsafe.Pointer(&item.handle)))
		if status != 0 {
			item.handle = 0
			if item.required {
				return report, fmt.Errorf("add %s: 0x%x", item.key, status)
			}
		}
	}

	report.SystemDrive = filepath.VolumeName(systemPath)
	drive, err := syscall.UTF16PtrFromString(report.SystemDrive + `\`)
	if err != nil {
		return report, err
	}
	ok, _, err := getDiskFreeSpace.Call(uintptr(unsafe.Pointer(drive)), 0, uintptr(unsafe.Pointer(&report.SystemSize)), uintptr(unsafe.Pointer(&report.SystemFree)))
	if ok == 0 {
		return report, fmt.Errorf("read Windows volume: %v", err)
	}
	report.ProcessesStart = processSnapshot()
	start := time.Now()
	if status, _, _ := collectData.Call(query); status != 0 {
		return report, fmt.Errorf("prime performance query: 0x%x", status)
	}
	for range sampleCount {
		time.Sleep(time.Until(start.Add(time.Second)))
		start = time.Now()
		if status, _, _ := collectData.Call(query); status != 0 {
			return report, fmt.Errorf("sample performance query: 0x%x", status)
		}
		var memory performanceInfo
		memory.size = uint32(unsafe.Sizeof(memory))
		ok, _, err := getPerformanceInfo.Call(uintptr(unsafe.Pointer(&memory)), uintptr(memory.size))
		if ok == 0 {
			return report, fmt.Errorf("read memory counters: %v", err)
		}
		row := map[string]any{
			"time":                 start.UTC().Format(time.RFC3339Nano),
			"memory_total_mib":     float64(uint64(memory.physicalTotal)*uint64(memory.pageSize)) / (1 << 20),
			"memory_available_mib": float64(uint64(memory.physicalAvailable)*uint64(memory.pageSize)) / (1 << 20),
			"commit_bytes":         uint64(memory.commitTotal) * uint64(memory.pageSize),
			"commit_limit_bytes":   uint64(memory.commitLimit) * uint64(memory.pageSize),
		}
		for _, item := range counters {
			if item.handle == 0 {
				continue
			}
			const formatDouble = 0x200
			var value formattedCounter
			status, _, _ := readCounter.Call(item.handle, formatDouble, 0, uintptr(unsafe.Pointer(&value)))
			if status != 0 || value.status > 1 || value.value < 0 || math.IsNaN(value.value) || math.IsInf(value.value, 0) {
				if item.required {
					return report, fmt.Errorf("read %s: 0x%x (counter status 0x%x)", item.key, status, value.status)
				}
				continue
			}
			row[item.key] = value.value
		}
		for _, direction := range []string{"read", "write"} {
			key := "disk_" + direction + "_latency_ms"
			seconds, hasLatency := row[key].(float64)
			bytesPerSecond, hasActivity := row["disk_"+direction+"_bytes_sec"].(float64)
			if hasLatency && hasActivity && bytesPerSecond > 0 {
				row[key] = seconds * 1000
			} else {
				delete(row, key)
			}
		}
		report.Samples = append(report.Samples, row)
	}
	report.ProcessesEnd = processSnapshot()
	if len(report.ProcessesStart) == 0 || len(report.ProcessesEnd) == 0 {
		return report, fmt.Errorf("read process memory snapshots")
	}
	return report, nil
}

func main() {
	if len(os.Args) != 2 || os.Args[1] != "--allow" {
		fmt.Fprintln(os.Stderr, "Local diagnostics require --allow.")
		os.Exit(2)
	}
	report, err := collect()
	if err == nil {
		err = json.NewEncoder(os.Stdout).Encode(report)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
