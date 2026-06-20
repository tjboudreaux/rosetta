import unittest

from tests._loop_helpers import ProjectFixture, parse_json, run_cli


class DriftCLITests(unittest.TestCase):
    def test_git_stale_fixture_reports_stale_without_writing(self):
        fx = ProjectFixture()
        try:
            fx.init_git()
            fx.write("src/a.py", "print(1)\n")
            fx.commit_all("add source")
            rec = fx.record("0001-a.md", sources="src/a.py")
            rec.write_text(rec.read_text().replace("2026-06-01", "2020-01-01"))
            before = sorted(p.relative_to(fx.project).as_posix() for p in fx.project.rglob("*"))
            proc = run_cli(["python3", "scripts/drift.py", "report", "--project-root", str(fx.project),
                            "--decisions-root", str(fx.decisions)])
            after = sorted(p.relative_to(fx.project).as_posix() for p in fx.project.rglob("*"))
            report = parse_json(proc)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(report["schema"], "rosetta-drift/v1")
            self.assertEqual(report["status"], "stale")
            self.assertEqual(report["stale_count"], 1)
            self.assertEqual(before, after)
        finally:
            fx.cleanup()

    def test_non_git_fixture_skips(self):
        fx = ProjectFixture()
        try:
            fx.record("0001-a.md", sources="src/a.py")
            proc = run_cli(["python3", "scripts/drift.py", "report", "--project-root", str(fx.project),
                            "--decisions-root", str(fx.decisions)])
            report = parse_json(proc)
            self.assertEqual(report["status"], "skip")
            self.assertEqual(report["skip_reason"], "not_git")
        finally:
            fx.cleanup()


if __name__ == "__main__":
    unittest.main()
