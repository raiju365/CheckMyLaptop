package main

import (
	"os"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"unsafe"
)

var getProcessMemoryInfo = kernel.NewProc("K32GetProcessMemoryInfo")

type processMemoryCounters struct {
	size, pageFaultCount                                                      uint32
	peakWorkingSet, workingSet, quotaPeakPagedPool, quotaPagedPool            uintptr
	quotaPeakNonPagedPool, quotaNonPagedPool, pagefile, peakPagefile, private uintptr
}

type processGroup struct {
	Name       string `json:"name"`
	Count      int    `json:"count"`
	WorkingSet uint64 `json:"working_set_bytes"`
	Private    uint64 `json:"private_bytes"`
}

func processSnapshot() []processGroup {
	snapshot, err := syscall.CreateToolhelp32Snapshot(syscall.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return nil
	}
	defer syscall.CloseHandle(snapshot)
	var entry syscall.ProcessEntry32
	entry.Size = uint32(unsafe.Sizeof(entry))
	groups := make(map[string]processGroup)
	for err := syscall.Process32First(snapshot, &entry); err == nil; err = syscall.Process32Next(snapshot, &entry) {
		if entry.ProcessID <= 4 || entry.ProcessID == uint32(os.Getpid()) {
			continue
		}
		name := syscall.UTF16ToString(entry.ExeFile[:])
		name = strings.TrimSuffix(name, filepath.Ext(name))
		if name == "" {
			continue
		}
		const queryLimitedInformation = 0x1000
		handle, err := syscall.OpenProcess(queryLimitedInformation, false, entry.ProcessID)
		if err != nil {
			continue
		}
		var memory processMemoryCounters
		memory.size = uint32(unsafe.Sizeof(memory))
		ok, _, _ := getProcessMemoryInfo.Call(uintptr(handle), uintptr(unsafe.Pointer(&memory)), uintptr(memory.size))
		syscall.CloseHandle(handle)
		if ok == 0 {
			continue
		}
		key := strings.ToLower(name)
		group := groups[key]
		group.Name = key
		group.Count++
		group.WorkingSet += uint64(memory.workingSet)
		group.Private += uint64(memory.private)
		groups[key] = group
	}
	rows := make([]processGroup, 0, len(groups))
	for _, group := range groups {
		rows = append(rows, group)
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].WorkingSet == rows[j].WorkingSet {
			return rows[i].Name < rows[j].Name
		}
		return rows[i].WorkingSet > rows[j].WorkingSet
	})
	return rows[:min(len(rows), 12)]
}
