import json
import unittest

from tests._loop_helpers import ProjectFixture, parse_json, run_cli


class HarnessExportTests(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()
        self.contract_path = self.fx.project / "contract.json"
        self.contract_path.write_text(json.dumps({
            "schema": "rosetta-harness-export/v1",
            "architecture": {"summary": "New arch", "components": [], "status": "accepted"},
            "mobile": {"summary": "New mobile", "facts": ["fact"], "decisions": [], "status": "accepted"},
            "domains": [{"slug": "payments", "title": "Payments", "summary": "Pay domain",
                         "paths": ["src/payments"], "decisions": [], "status": "confirm"},
                        {"slug": "Bad Slug", "title": "Bad"}],
        }))

    def tearDown(self):
        self.fx.cleanup()

    def harness(self, *args):
        return run_cli(["python3", "scripts/harness.py", "export", "--project-root", str(self.fx.project),
                        "--from-json", str(self.contract_path), *args])

    def test_dry_run_and_patch_write_nothing(self):
        self.fx.write("ARCHITECTURE.md", "Before\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\n")
        self.fx.write("docs/MOBILE.md", "Before\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\n")
        before = sorted(p.relative_to(self.fx.project).as_posix() for p in self.fx.project.rglob("*"))
        dry = self.harness()
        after_dry = sorted(p.relative_to(self.fx.project).as_posix() for p in self.fx.project.rglob("*"))
        report = parse_json(dry)
        self.assertEqual(before, after_dry)
        self.assertEqual([t["path"] for t in report["targets"]],
                         ["ARCHITECTURE.md", "docs/MOBILE.md", "domains/payments/README.md"])
        self.assertEqual(report["warnings"][0]["code"], "invalid_domain_slug")
        patch = self.harness("--patch")
        after_patch = sorted(p.relative_to(self.fx.project).as_posix() for p in self.fx.project.rglob("*"))
        self.assertEqual(before, after_patch)
        self.assertIn("New arch", patch.stdout)

    def test_apply_only_updates_existing_marked_allowlisted_docs(self):
        self.fx.write("src/App.tsx", "do not touch")
        self.fx.write("ARCHITECTURE.md", "Before\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\nAfter\n")
        self.fx.write("docs/MOBILE.md", "Before\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\nAfter\n")
        # Missing domain target blocks all writes.
        fail = self.harness("--apply")
        self.assertEqual(fail.returncode, 3)
        self.assertIn("New arch", fail.stdout)
        self.assertIn("old", (self.fx.project / "ARCHITECTURE.md").read_text())
        self.fx.write("domains/payments/README.md", "Before\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\n")
        ok = self.harness("--apply")
        self.assertEqual(ok.returncode, 0)
        self.assertIn("New arch", (self.fx.project / "ARCHITECTURE.md").read_text())
        self.assertEqual((self.fx.project / "src/App.tsx").read_text(), "do not touch")
        (self.fx.project / "docs" / "MOBILE.md").write_text("no markers\n")
        unmarked = self.harness("--apply")
        self.assertEqual(unmarked.returncode, 3)


if __name__ == "__main__":
    unittest.main()
