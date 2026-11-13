"""Summarize repeated measurements and keep process attribution conservative."""

from math import ceil
from statistics import median

MIB = 1024**2
GIB = 1024**3


def summarize_performance(data: dict) -> dict:
    samples = data.get("samples", [])
    low = []
    paging = []
    commit_high = []
    commit_and_low = 0
    cpu_high = []
    queue_high = []
    available = []
    thresholds = []
    commit_ratios = []
    for row in samples:
        is_low = False
        total, free = row.get("memory_total_mib"), row.get("memory_available_mib")
        if total and free is not None:
            available.append(free)
            threshold = min(1024, total * 0.10)
            thresholds.append(threshold)
            if free < threshold:
                is_low = True
                low.append(row)
                if (row.get("pages_input_sec") or 0) >= 50 and (row.get("disk_queue") or 0) >= 1:
                    paging.append(row)
        committed, limit = row.get("commit_bytes"), row.get("commit_limit_bytes")
        if committed is not None and limit:
            ratio = committed / limit
            commit_ratios.append(ratio)
            if ratio >= 0.90:
                commit_high.append(row)
                commit_and_low += is_low
        if (row.get("cpu_percent") or 0) >= 90:
            cpu_high.append(row)
        if (row.get("disk_queue") or 0) >= 2:
            queue_high.append(row)

    early = {row["name"]: row for row in data.get("processes_start", []) if row.get("name")}
    apps = []
    for row in data.get("processes_end", []):
        name, working = row.get("name"), row.get("working_set_bytes")
        if not name or working is None:
            continue
        previous = early.get(name, {}).get("working_set_bytes")
        private = row.get("private_bytes")
        apps.append({
            "name": name, "count": row["count"], "working_set_mib": round(working / MIB, 1),
            "private_mib": round(private / MIB, 1) if private is not None else None,
            "working_set_change_mib": round((working - previous) / MIB, 1)
            if previous is not None else None,
        })

    def measurement(key: str) -> list:
        return [row[key] for row in samples if row.get(key) is not None]

    cpu, queue, page_reads = (measurement(key) for key in
                              ("cpu_percent", "disk_queue", "pages_input_sec"))
    return {
        "samples": len(samples), "required": max(3, ceil(len(samples) * 0.6)),
        "low_count": len(low), "paging_count": len(paging), "commit_high_count": len(commit_high),
        "commit_and_low_count": commit_and_low,
        "cpu_high_count": len(cpu_high), "queue_high_count": len(queue_high),
        "available_min_mib": min(available, default=None),
        "available_median_mib": median(available) if available else None,
        "available_max_mib": max(available, default=None),
        "threshold_mib": median(thresholds) if thresholds else None,
        "commit_peak_ratio": max(commit_ratios, default=None),
        "cpu_median_percent": median(cpu) if cpu else None,
        "disk_queue_median": median(queue) if queue else None,
        "pages_input_median": median(page_reads) if page_reads else None,
        "processes": sorted(apps, key=lambda row: row["working_set_mib"], reverse=True)[:5],
    }
