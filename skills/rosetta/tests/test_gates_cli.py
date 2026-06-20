import json
import unittest

from tests._loop_helpers import ProjectFixture, ROOT, parse_json, run_cli


class GatesCLITests(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()

    def tearDown(self):
        self.fx.cleanup()

    def gates(self, *extra):
        return run_cli(["python3", "scripts/gates.py", "check", "--project-root", str(self.fx.project),
                        "--decisions-root", str(self.fx.decisions), "--min-coverage", "1.0", *extra])

    def test_validation_and_coverage_failures_are_structured(self):
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.record("0001-a.md", sources="")
        proc = self.gates()
        report = parse_json(proc)
        self.assertEqual(proc.returncode, 1)
        by_gate = {g["gate"]: g for g in report["gates"]}
        self.assertEqual(by_gate["validation"]["status"], "fail")
        self.assertEqual(by_gate["anchoring"]["status"], "fail")

    def test_staleness_failure_is_structured(self):
        self.fx.init_git()
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.commit_all("add source")
        self.fx.record("0001-a.md", sources="src/a.py")
        path = self.fx.decisions / "architecture-decisions" / "0001-a.md"
        path.write_text(path.read_text().replace("2026-06-01", "2020-01-01"))
        proc = self.gates()
        report = parse_json(proc)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual({g["gate"]: g for g in report["gates"]}["staleness"]["status"], "fail")

    def test_no_changed_paths_skips_joins_and_writes_no_files(self):
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.record("0001-a.md", sources="src/a.py")
        before = sorted(p.relative_to(self.fx.project).as_posix() for p in self.fx.project.rglob("*"))
        proc = self.gates()
        after = sorted(p.relative_to(self.fx.project).as_posix() for p in self.fx.project.rglob("*"))
        report = parse_json(proc)
        self.assertEqual(proc.returncode, 0)
        by_gate = {g["gate"]: g for g in report["gates"]}
        self.assertEqual(by_gate["denylist"]["status"], "skip")
        self.assertEqual(by_gate["evidence_presence"]["status"], "skip")
        self.assertEqual(before, after)
        self.assertTrue(all(isinstance(g["evidence"], list) for g in report["gates"]))

    def test_human_gated_path_requires_exact_approval(self):
        self.fx.write("src/payments/Pay.tsx", "export const Pay = () => null\n")
        self.fx.record("0001-gate.md", sources="src/payments/Pay.tsx",
                       extra="- Human gated paths: src/payments/**\n")
        proc = self.gates("--changed-path", "src/payments/Pay.tsx", "--change-id", "change-1")
        self.assertEqual({g["gate"]: g for g in parse_json(proc)["gates"]}["denylist"]["status"], "fail")
        self.fx.record("0002-approve.md", num="0002", title="Approve", sources="src/payments/Pay.tsx",
                       extra="- Human approval for: change-1\n")
        proc2 = self.gates("--changed-path", "src/payments/Pay.tsx", "--change-id", "change-1")
        self.assertEqual({g["gate"]: g for g in parse_json(proc2)["gates"]}["denylist"]["status"], "pass")

    def test_ui_change_requires_existing_evidence_artifact(self):
        self.fx.write("src/App.tsx", "export default null\n")
        self.fx.record("0001-ui.md", sources="src/App.tsx")
        proc = self.gates("--changed-path", "src/App.tsx", "--change-id", "change-1")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual({g["gate"]: g for g in parse_json(proc)["gates"]}["evidence_presence"]["status"], "fail")
        self.fx.write("artifacts/app.png", "png")
        self.fx.record("0002-evidence.md", num="0002", title="Evidence", sources="src/App.tsx",
                       extra="- Evidence for: change-1\n- Evidence artifacts: screenshot:artifacts/app.png\n")
        proc2 = self.gates("--changed-path", "src/App.tsx", "--change-id", "change-1")
        self.assertEqual({g["gate"]: g for g in parse_json(proc2)["gates"]}["evidence_presence"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
