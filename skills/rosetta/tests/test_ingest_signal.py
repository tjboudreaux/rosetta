import json
import unittest

from tests._loop_helpers import ProjectFixture, ROOT, run_cli


def signal(**overrides):
    item = {
        "id": "sig-1",
        "source": "support",
        "product_area": "onboarding",
        "platform": "ios",
        "app_version": "1.0",
        "device_os": "iOS 18",
        "content_summary": "Users cannot complete onboarding",
        "raw_refs": [{"url_or_path": "support/ticket-1"}],
        "customer_impact": "high",
        "actionability": "immediately_actionable",
        "privacy_class": "internal",
        "suggested_owner": "PM",
        "created_at": "2026-06-18T12:30:00Z",
    }
    item.update(overrides)
    return item


class IngestSignalTests(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()
        self.src = self.fx.project / "input.json"

    def tearDown(self):
        self.fx.cleanup()

    def ingest(self, data, *args):
        self.src.write_text(json.dumps(data))
        return run_cli(["python3", "scripts/ingest.py", "--root", str(self.fx.decisions), "--from", str(self.src), *args])

    def records(self):
        return list(self.fx.decisions.rglob("*.md"))

    def test_valid_signal_writes_proposed_record(self):
        proc = self.ingest([signal()])
        self.assertEqual(proc.returncode, 0)
        files = list((self.fx.decisions / "product-decisions").glob("*.md"))
        self.assertEqual(len(files), 1)
        text = files[0].read_text()
        self.assertIn("# PDR 0001 — Signal [support/onboarding]", text)
        self.assertIn("- Status: Proposed", text)
        self.assertIn("`signal:sig-1`", text)
        self.assertIn("`support/ticket-1`", text)

    def test_signal_errors_exit_before_writes(self):
        bad = signal()
        del bad["id"]
        proc = self.ingest([bad], "--schema", "signals")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.records(), [])
        bad_enum = signal(source="bogus")
        proc2 = self.ingest([bad_enum])
        self.assertNotEqual(proc2.returncode, 0)
        self.assertEqual(self.records(), [])

    def test_sensitive_refuses_by_default_and_requires_redaction(self):
        sensitive = signal(privacy_class="sensitive", content_summary="email user@example.com",
                           raw_refs=[{"url_or_path": "https://secret.example/replay"}])
        proc = self.ingest([sensitive])
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.records(), [])
        proc2 = self.ingest([sensitive], "--allow-sensitive")
        self.assertNotEqual(proc2.returncode, 0)
        self.assertEqual(self.records(), [])
        proc3 = self.ingest([dict(sensitive, redacted=True)], "--allow-sensitive")
        self.assertEqual(proc3.returncode, 0)
        text = self.records()[0].read_text()
        self.assertIn("[redacted: sensitive signal]", text)
        self.assertNotIn("user@example.com", text)
        self.assertNotIn("https://secret.example/replay", text)


if __name__ == "__main__":
    unittest.main()
