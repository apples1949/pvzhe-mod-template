import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from runtime_diagnostics import assess


class RuntimeDiagnosticsTests(unittest.TestCase):
    def test_completion_does_not_hide_initialization_failure(self):
        report = assess("ERROR: Built-in Packet config is not registered: false\n at MowerInit()\nDONE", ["DONE"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["errors"][0]["line"], 1)
        self.assertIn("MowerInit", report["errors"][0]["context"][0])

    def test_clean_exit_without_business_result_is_incomplete(self):
        self.assertEqual(assess("game exit 0", ["BUSINESS_PASS"])["missingMarkers"], ["BUSINESS_PASS"])

    def test_loader_rollback_warning_is_a_fatal_runtime_failure(self):
        report=assess("WARNING: [ModLoader] package rolled back after runtime entry failure: local.example\nDONE",["DONE"])
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["errors"]),1)

    def test_script_and_presentation_faults_are_detected(self):
        for text in ["SCRIPT ERROR: invalid property", "WARNING: Local presentation stopped: frozen", "AUDIT_TEST_ERROR: not planted"]:
            self.assertFalse(assess(text)["passed"])

    def test_known_diagnostic_is_not_automatically_a_host_exception(self):
        self.assertTrue(assess("unsupported package file\nWARNING: shutdown requires restart\nDONE", ["DONE"])["passed"])

    def test_projectile_callback_warning_cannot_be_hidden_by_success_marker(self):
        report = assess("WARNING: [BulletField] Spawn callback failed: initializer failed\nDONE", ["DONE"])
        self.assertFalse(report['passed'])
        self.assertEqual(report['errors'][0]['line'], 1)
