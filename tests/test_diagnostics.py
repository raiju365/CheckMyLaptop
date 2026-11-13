import unittest
from io import StringIO
from unittest.mock import patch

from checkmylaptop import collect
from checkmylaptop.__main__ import main
from checkmylaptop.demo import snapshot
from checkmylaptop.report import build_report, render_text


class DiagnosticTests(unittest.TestCase):
    def test_demo_prioritizes_storage_and_explains_correlations(self):
        report = build_report(snapshot(), demo=True)
        self.assertEqual(report["findings"][0]["code"], "storage_health")
        self.assertIn("same Windows disk number", report["findings"][0]["evidence"][-1])
        self.assertIn("memory_paging", [item["code"] for item in report["findings"]])
        self.assertIn("DEMO · Simulated data", render_text(report))

    def test_old_and_unmapped_retries_do_not_correlate_with_current_disk(self):
        data = snapshot()
        events = data["sections"]["events"]["data"]["entries"]
        events[0]["current_boot"] = False
        events[1]["disk"] = None
        finding = build_report(data)["findings"][0]
        self.assertEqual(finding["code"], "storage_health")
        self.assertEqual(len(finding["evidence"]), 2)

    def test_missing_paging_does_not_infer_disk_cause(self):
        data = snapshot()
        for sample in data["sections"]["performance"]["data"]["samples"]:
            sample["pages_input_sec"] = None
            sample["commit_bytes"] = None
        codes = [item["code"] for item in build_report(data)["findings"]]
        self.assertIn("memory_low", codes)
        self.assertNotIn("memory_paging", codes)

    def test_restart_alone_leaves_cause_undetermined(self):
        data = snapshot()
        restart = data["sections"]["events"]["data"]["entries"][-1]
        data["sections"] = {"events": {"state": "checked", "data": {"entries": [restart]}}}
        report = build_report(data)
        self.assertEqual([item["code"] for item in report["findings"]], ["restart"])
        self.assertIn("Cause undetermined", render_text(report))

    def test_graphics_and_crash_timing_is_correlated(self):
        data = snapshot()
        data["sections"]["events"]["data"]["entries"] = [
            {"provider": "Display", "id": 4101, "time": "2026-11-13T01:00:00+00:00"},
            {"provider": "Microsoft-Windows-WER-SystemErrorReporting", "id": 1001,
             "time": "2026-11-13T01:01:00+00:00"},
        ]
        report = build_report(data)
        codes = [item["code"] for item in report["findings"]]
        self.assertIn("graphics_crash_timing", codes)
        self.assertIn("Graphics: Demo Graphics", render_text(report))

    def test_partial_and_unavailable_data_are_visible(self):
        report = build_report(snapshot())
        self.assertEqual(report["coverage"]["Storage"]["state"], "partial")
        empty = build_report({"scanned_at": "example", "sections": {}})
        self.assertTrue(all(item["state"] == "unavailable"
                            for item in empty["coverage"].values()))
        self.assertIn("No diagnostic data available", render_text(empty))
        self.assertTrue(empty["not_tested"])

    @patch("checkmylaptop.collect.subprocess.run")
    def test_bad_collector_json_is_unavailable(self, run):
        run.return_value.stdout = b'"wrong shape"'
        self.assertEqual(collect.read_section("storage")["state"], "unavailable")

    @patch("checkmylaptop.collect.subprocess.run")
    def test_empty_storage_is_valid_json(self, run):
        run.return_value.stdout = b"[]"
        self.assertEqual(collect.read_section("storage"), {"state": "checked", "data": []})

    def test_ram_measurements_and_process_deltas_are_reported(self):
        report = build_report(snapshot())
        metrics = report["measurements"]["performance"]
        self.assertEqual(metrics["available_min_mib"], 480)
        self.assertEqual(metrics["commit_peak_ratio"], 15 / 16)
        top = metrics["processes"][0]
        self.assertEqual(top["working_set_change_mib"], 300)
        self.assertIn("demo-browser (6) · 2500 MiB", render_text(report))
        self.assertIn("Demo Wi-Fi adapter", render_text(report))
        self.assertIn("Device reliability counters unavailable", render_text(report))
        self.assertIn("disk #153", render_text(report))

    def test_commit_and_low_memory_require_overlapping_samples(self):
        data = snapshot()
        rows = data["sections"]["performance"]["data"]["samples"]
        for index, row in enumerate(rows):
            row.update(memory_available_mib=480 if index < 5 else 3000,
                       commit_bytes=15 if index >= 3 else 5, commit_limit_bytes=16,
                       pages_input_sec=0, disk_queue=0)
        codes = {item["code"] for item in build_report(data)["findings"]}
        self.assertIn("memory_low", codes)
        self.assertIn("commit_limit", codes)
        self.assertNotIn("memory_commit", codes)

    def test_short_spikes_do_not_raise_sustained_cpu_and_disk_findings(self):
        data = snapshot()
        rows = data["sections"]["performance"]["data"]["samples"]
        for index, row in enumerate(rows):
            row.update(cpu_percent=100 if index < 4 else 40, disk_queue=3 if index < 4 else 0,
                       memory_available_mib=2000, pages_input_sec=0)
        codes = {item["code"] for item in build_report(data)["findings"]}
        self.assertFalse({"cpu_load", "disk_activity", "memory_paging"} & codes)
        rows[4].update(cpu_percent=100, disk_queue=3)
        codes = {item["code"] for item in build_report(data)["findings"]}
        self.assertTrue({"cpu_load", "disk_activity"} <= codes)

    def test_missing_process_data_keeps_memory_finding_and_partial_coverage(self):
        data = snapshot()
        data["sections"]["performance"]["data"].pop("processes_end")
        report = build_report(data)
        self.assertIn("memory_paging", {item["code"] for item in report["findings"]})
        self.assertEqual(report["coverage"]["Live performance and free space"]["state"], "partial")

    def test_only_nearby_selected_hardware_events_raise_crash_priority(self):
        data = snapshot()
        entries = [
            {"provider": "Microsoft-Windows-WHEA-Logger", "id": 17,
             "time": "2026-11-13T01:00:00+00:00"},
            {"provider": "Microsoft-Windows-WER-SystemErrorReporting", "id": 1001,
             "time": "2026-11-13T01:01:00+00:00"},
            {"provider": "Microsoft-Windows-WHEA-Logger", "id": 18,
             "time": "2026-11-13T02:00:00+00:00"},
        ]
        data["sections"]["events"]["data"]["entries"] = entries
        codes = {item["code"] for item in build_report(data)["findings"]}
        self.assertNotIn("hardware_crash_timing", codes)
        entries[2]["time"] = "2026-11-13T00:59:30+00:00"
        finding = next(item for item in build_report(data)["findings"]
                       if item["code"] == "hardware_crash_timing")
        self.assertEqual(finding["severity"], "high")

    def test_storage_and_dirty_volume_require_the_same_unambiguous_disk(self):
        data = snapshot()
        volume = data["sections"]["volumes"]["data"]["disk_map"]
        summary = lambda: build_report(data)["conclusions"][0]
        self.assertIn("same mapped disk", summary()["title"])
        self.assertEqual(summary()["confidence"], "corroborated")
        volume["data"].append({"drive": "C:", "disk": 1})
        self.assertEqual(summary()["title"], "Storage needs attention")
        volume["data"] = [{"drive": "C:", "disk": 1}]
        self.assertEqual(summary()["title"], "Storage needs attention")

    def test_historical_commit_event_alone_is_not_a_current_memory_conclusion(self):
        data = snapshot()
        data["sections"]["events"]["data"]["entries"].append({
            "provider": "Microsoft-Windows-Resource-Exhaustion-Detector", "id": 2004,
            "time": "2026-11-13T01:00:00+00:00",
        })
        self.assertTrue(any("Sustained memory pressure" in item["title"]
                            for item in build_report(data)["conclusions"]))
        data["sections"].pop("performance")
        report = build_report(data)
        self.assertIn("memory_exhaustion", {item["code"] for item in report["findings"]})
        self.assertFalse(any("Sustained memory pressure" in item["title"] for item in report["conclusions"]))

    def test_current_component_verification_overrides_older_health_record(self):
        data = snapshot()
        data["sections"]["windows_health"] = {"state": "checked", "data": {
            "component_store": {"state": "checked", "data": {"health": "Repairable"}},
        }}
        data["sections"]["windows_verification"] = {"state": "unavailable"}
        report = build_report(data)
        self.assertIn("component_store", {item["code"] for item in report["findings"]})
        self.assertEqual(report["coverage"]["Windows servicing and page file"]["state"], "partial")
        data["sections"]["windows_verification"] = {"state": "checked", "data": {"health": "Healthy"}}
        report = build_report(data)
        self.assertNotIn("component_store", {item["code"] for item in report["findings"]})
        self.assertEqual(report["measurements"]["component_store"], {"health": "Healthy", "verified": True})

    @patch("checkmylaptop.collect.subprocess.run")
    def test_scan_without_consent_never_starts_a_collector(self, run):
        with self.assertRaises(PermissionError):
            collect.scan()
        run.assert_not_called()

    @patch("checkmylaptop.__main__.scan")
    def test_cli_requires_allow_when_stdin_is_redirected(self, scan):
        with (patch("sys.platform", "win32"), patch("sys.stdin", StringIO()),
              patch("sys.stderr", StringIO()) as stderr, self.assertRaises(SystemExit) as error):
            main(["--cli"])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("require --allow", stderr.getvalue())
        scan.assert_not_called()

    @patch("checkmylaptop.__main__.scan", side_effect=lambda **_: snapshot())
    def test_cli_passes_explicit_consent_and_verification(self, scan):
        with patch("sys.platform", "win32"), patch("sys.stdout", StringIO()):
            self.assertEqual(main(["--cli", "--allow", "--verify-windows"]), 0)
        scan.assert_called_once_with(allow=True, verify_windows=True)
