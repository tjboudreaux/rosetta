import json
import unittest
from pathlib import Path

from tests._loop_helpers import ProjectFixture, ROOT, parse_json, run_cli


class RunsCLITests(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()

    def tearDown(self):
        self.fx.cleanup()

    def runs(self, *args):
        return run_cli(["python3", "scripts/runs.py", *args])

    def test_new_append_close_index_validate(self):
        new = self.runs("new", "--project-root", str(self.fx.project), "--title", "Loop One",
                        "--runner", "agent", "--trigger", "manual", "--scope", "scope",
                        "--artifact", "logs/a.txt")
        self.assertEqual(new.returncode, 0)
        info = parse_json(new)
        self.assertEqual(info["schema"], "rosetta-runs/v1")
        path = Path(info["path"])
        self.assertEqual(path.relative_to(self.fx.project).parts[0], "loop-runs")
        append = self.runs("append", "--project-root", str(self.fx.project), "RUN 0001", "--note", "note",
                           "--artifact", "logs/b.txt", "--checker-result", "pass", "--outcome", "success",
                           "--harness-improvement", "better harness")
        self.assertEqual(append.returncode, 0)
        index = self.runs("index", "--project-root", str(self.fx.project))
        self.assertEqual(parse_json(index)["runs"][0]["checker_result"], "pass")
        close_missing = self.runs("close", "--project-root", str(self.fx.project), "RUN 0001")
        self.assertEqual(close_missing.returncode, 2)
        close = self.runs("close", "--project-root", str(self.fx.project), "RUN 0001",
                          "--stop-reason", "done", "--outcome", "success", "--checker-result", "pass")
        self.assertEqual(close.returncode, 0)
        append_closed = self.runs("append", "--project-root", str(self.fx.project), "RUN 0001", "--note", "late")
        self.assertNotEqual(append_closed.returncode, 0)
        validate = self.runs("validate", "--project-root", str(self.fx.project))
        self.assertEqual(validate.returncode, 0)

    def test_validate_catches_malformed_closed_run_and_decisions_ignore_runs(self):
        run_dir = self.fx.project / "loop-runs"
        run_dir.mkdir()
        (run_dir / "0001-bad.md").write_text(
            "# RUN 0001 — Bad\n\n- Status: Closed\n- Date: 2026-06-20\n- Runner: agent\n"
            "- Trigger: manual\n- Scope: scope\n- Budget: \n- Outcome: success\n- Stop reason: \n"
            "- Artifacts: \n- Checker result: pass\n- Harness improvement: \n- Sources: loop-run:0001\n"
        )
        validate = self.runs("validate", "--project-root", str(self.fx.project))
        self.assertEqual(validate.returncode, 1)
        self.assertIn("closed run missing Stop reason", validate.stdout)
        self.fx.write("decisions/architecture-decisions/0001-ok.md",
                      "# ADR 0001 — OK\n\n- Status: Accepted\n- Date: 2026-06-01\n- Decider: Me\n- Sources: x\n\n## Decision\n\nOK.\n")
        dec = run_cli(["python3", "scripts/decisions.py", "validate", "--root", str(self.fx.project / "decisions")])
        self.assertEqual(dec.returncode, 0)


if __name__ == "__main__":
    unittest.main()
