import unittest
from unittest.mock import patch

from checkmylaptop import collect
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
