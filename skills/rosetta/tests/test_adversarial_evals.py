#!/usr/bin/env python3
"""CI wiring for the adversarial eval dataset's Tier-A (deterministic substrate) checks.

This does NOT grade model judgment (that's Tier B, LLM-judged — see evals/adversarial/judge_prompt.md).
It proves, for every scenario, that: the fixture builds, the collector surfaces exactly the planted
sessions, the citation anchors and code/doc/git markers exist, no gold token leaked into any
solver-visible file, and git-dependent scenarios have the expected commit history (skipped loudly if
git is unavailable). One subtest per scenario so a failure names the scenario and the exact check.

Run: python3 -m unittest discover -s tests   (pure stdlib, no deps)
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evals" / "adversarial"))
import run_evals    # noqa: E402
import fixtures      # noqa: E402


class AdversarialEvalsTierA(unittest.TestCase):
    def test_every_scenario_passes_tier_a(self):
        data = run_evals.load_dataset()
        self.assertGreaterEqual(len(data["scenarios"]), 1, "dataset has no scenarios")
        for scenario in data["scenarios"]:
            with self.subTest(scenario=scenario["id"]):
                result = run_evals.run_scenario(scenario)
                if result["status"] == "skipped":
                    self.skipTest(result["reason"])
                failed = [f"{name} ({detail})" for name, ok, detail in result["checks"] if not ok]
                self.assertEqual(result["status"], "pass",
                                 f"{scenario['id']} Tier-A failures: {failed}")

    def test_runner_main_single_scenario(self):
        old = sys.argv
        sys.argv = ["run_evals", "--scenario", "cold-project"]
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = run_evals.main()
        finally:
            sys.argv = old
        self.assertEqual(rc, 0)

    def test_runner_main_unknown_scenario_errors(self):
        old = sys.argv
        sys.argv = ["run_evals", "--scenario", "does-not-exist"]
        try:
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                run_evals.main()
        finally:
            sys.argv = old

    def test_emit_bundle_writes_judge_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = sys.argv
            sys.argv = ["run_evals", "--scenario", "contradiction-code-resolved", "--emit-bundle", tmp]
            try:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    run_evals.main()
            finally:
                sys.argv = old
            b = Path(tmp) / "contradiction-code-resolved"
            for artifact in ("prompt.txt", "gold.json", "anchors.json", "manifest.json"):
                self.assertTrue((b / artifact).exists(), f"missing {artifact}")
            self.assertTrue((b / "normalized").is_dir())
            self.assertTrue(any((b / "project").rglob("*")))

    def test_emit_bundle_writes_notools_library_for_decision_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = sys.argv
            sys.argv = ["run_evals", "--scenario", "decision-supersession-lookup-5", "--emit-bundle", tmp]
            try:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    run_evals.main()
            finally:
                sys.argv = old
            lib = Path(tmp) / "decision-supersession-lookup-5" / "library.txt"
            self.assertTrue(lib.exists())
            # the no-tools blob contains the buried needle record (event log in Postgres)
            self.assertIn("event log in Postgres", lib.read_text())

    def test_report_flag_writes_results_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            rpath = Path(tmp) / "results.json"
            old = sys.argv
            sys.argv = ["run_evals", "--scenario", "cold-project", "--report", str(rpath)]
            try:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    run_evals.main()
            finally:
                sys.argv = old
            import json as _json
            doc = _json.loads(rpath.read_text())
            self.assertEqual(doc["schema"], "rosetta-eval-results/v1")
            self.assertEqual(doc["runs"][0]["scenarios"][0]["id"], "cold-project")

    def test_requires_git_skips_loudly_without_git(self):
        saved = run_evals.fixtures.GIT
        run_evals.fixtures.GIT = None      # simulate git-absent environment
        try:
            scenario = next(s for s in run_evals.load_dataset()["scenarios"]
                            if s["id"] == "contradiction-code-resolved")
            r = run_evals.run_scenario(scenario)
            self.assertEqual(r["status"], "skipped")
            self.assertIn("git", r["reason"])
        finally:
            run_evals.fixtures.GIT = saved

    def test_main_reports_skips_without_git(self):
        saved = run_evals.fixtures.GIT
        run_evals.fixtures.GIT = None
        old = sys.argv
        sys.argv = ["run_evals", "--scenario", "contradiction-code-resolved"]
        try:
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                rc = run_evals.main()
            self.assertIn("SKIP", buf.getvalue())
            self.assertEqual(rc, 0)
        finally:
            sys.argv = old
            run_evals.fixtures.GIT = saved

    def test_dataset_and_fixtures_are_consistent(self):
        """Every scenario names a real fixture builder; ids are unique."""
        data = run_evals.load_dataset()
        ids = [s["id"] for s in data["scenarios"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate scenario ids")
        for s in data["scenarios"]:
            self.assertIn(s["fixture"], run_evals.fixtures.REGISTRY,
                          f"{s['id']}: unknown fixture {s['fixture']}")
            self.assertIn("judge_only", s, f"{s['id']}: missing judge_only gold")


if __name__ == "__main__":
    unittest.main(verbosity=2)
