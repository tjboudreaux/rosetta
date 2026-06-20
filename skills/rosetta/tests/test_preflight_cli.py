import json
import os
import sys
import unittest

from tests._loop_helpers import ProjectFixture, parse_json, run_cli


class PreflightCLITests(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()
        self.fx.write("src/App.tsx", "export default null\n")
        self.fx.write("artifacts/app.png", "png")
        self.fx.record("0001-onboarding.md", title="onboarding UI", sources="src/App.tsx",
                       extra="- Evidence for: change-1\n- Evidence artifacts: screenshot:artifacts/app.png\n",
                       body="Onboarding.")

    def tearDown(self):
        self.fx.cleanup()

    def preflight(self, *args, env=None):
        return run_cli(["python3", "scripts/preflight.py", "--project-root", str(self.fx.project),
                        "--decisions-root", str(self.fx.decisions), "--scope", "onboarding",
                        "--min-coverage", "1.0", "--changed-path", "src/App.tsx", "--change-id", "change-1",
                        *args], env=env)

    def make_ra1(self, body):
        bindir = self.fx.project / "bin"
        bindir.mkdir(exist_ok=True)
        ra1 = bindir / "ra1"
        ra1.write_text(body)
        ra1.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        return env

    def env_without_ra1(self):
        bindir = self.fx.project / "python-only-bin"
        bindir.mkdir(exist_ok=True)
        py = bindir / "python3"
        if not py.exists():
            py.symlink_to(sys.executable)
        env = os.environ.copy()
        env["PATH"] = str(bindir)
        return env

    def test_ra1_absent_skips_and_gates_failure_bubbles(self):
        env = self.env_without_ra1()
        proc = self.preflight(env=env)
        report = parse_json(proc)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(report["schema"], "rosetta-preflight/v1")
        self.assertEqual(report["sections"][0]["status"], "skip")
        # Remove evidence fields so the gates section fails and preflight exits 1.
        rec = self.fx.decisions / "architecture-decisions" / "0001-onboarding.md"
        rec.write_text(rec.read_text().replace("- Evidence for: change-1\n- Evidence artifacts: screenshot:artifacts/app.png\n", ""))
        proc2 = self.preflight(env=env)
        report2 = parse_json(proc2)
        self.assertEqual(proc2.returncode, 1)
        self.assertEqual(report2["sections"][2]["status"], "fail")

    def test_ra1_default_and_allow_github_argv(self):
        argv_path = self.fx.project / "argv.json"
        env = self.make_ra1(f"#!/usr/bin/env python3\nimport json, sys\nopen({str(argv_path)!r}, 'w').write(json.dumps(sys.argv[1:]))\nprint(json.dumps({{'ok': True}}))\n")
        proc = self.preflight(env=env)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(argv_path.read_text()), ["report", "--format", "json", "--no-github"])
        proc2 = self.preflight("--allow-ra1-github", env=env)
        self.assertEqual(proc2.returncode, 0)
        self.assertEqual(json.loads(argv_path.read_text()), ["report", "--format", "json"])
        self.assertTrue(parse_json(proc2)["network_allowed"])

    def test_ra1_failures_are_structured_json(self):
        cases = [
            ("nonzero_exit", "#!/usr/bin/env python3\nimport sys\nprint('bad', file=sys.stderr)\nsys.exit(7)\n"),
            ("stderr_only_failure", "#!/usr/bin/env python3\nimport sys\nprint('bad', file=sys.stderr)\n"),
            ("invalid_json", "#!/usr/bin/env python3\nprint('not json')\n"),
        ]
        for reason, body in cases:
            env = self.make_ra1(body)
            proc = self.preflight(env=env)
            report = parse_json(proc)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(report["sections"][0]["status"], "fail")
            self.assertEqual(report["sections"][0]["reason"], reason)
        env = self.make_ra1("#!/usr/bin/env python3\nimport time\ntime.sleep(1)\n")
        proc = self.preflight("--ra1-timeout", "0.01", env=env)
        report = parse_json(proc)
        self.assertEqual(report["sections"][0]["reason"], "timeout")

    def test_decision_state_failures_happen_before_no_live_skip(self):
        env = self.env_without_ra1()
        rec = self.fx.decisions / "architecture-decisions" / "0001-onboarding.md"
        rec.write_text(rec.read_text().replace("- Status: Accepted", "- Status: Proposed"))
        proc = self.preflight(env=env)
        report = parse_json(proc)
        self.assertEqual(report["sections"][1]["status"], "fail")
        self.assertIn("not_resolved_unique", report["sections"][1]["reason"])

        rec.write_text(
            "# ADR 0001 — First decision\n\n- Status: Accepted\n- Date: 2026-06-01\n"
            "- Decider: Me\n- Sources: src/App.tsx\n- Aliases: shared-alias\n\n## Decision\n\nOne.\n"
        )
        self.fx.record("0002-second.md", num="0002", title="Second decision", sources="src/App.tsx",
                       extra="- Aliases: shared-alias\n", body="Two.")
        proc2 = run_cli([
            "python3", "scripts/preflight.py", "--project-root", str(self.fx.project),
            "--decisions-root", str(self.fx.decisions), "--scope", "shared-alias",
            "--min-coverage", "1.0"
        ], env=env)
        report2 = parse_json(proc2)
        self.assertEqual(proc2.returncode, 1)
        self.assertEqual(report2["sections"][1]["status"], "fail")
        self.assertIn("alias_conflict", report2["sections"][1]["reason"])


if __name__ == "__main__":
    unittest.main()
