#!/usr/bin/env python3
"""CLI-level coverage for collect.main(): machine-wide discovery (--all-projects), the --since and
--agents filters, unknown-agent handling, per-message truncation, and the missing-out-dir error.
Driven against the synthetic fixture $HOME from tests/fixtures/build.py.

Run: python3 -m unittest discover -s tests   (pure stdlib, no deps)
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE / "fixtures"))
import collect          # noqa: E402
import build            # noqa: E402


class CollectCLI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.project = build.build(self.home)
        os.environ["ROSETTA_HOME"] = str(self.home)
        self._cwd = os.getcwd()

    def tearDown(self):
        os.environ.pop("ROSETTA_HOME", None)
        os.chdir(self._cwd)          # some tests chdir into the sandbox; restore before cleanup
        self._tmp.cleanup()

    def _main(self, *args):
        old = sys.argv
        sys.argv = ["collect", *args]
        try:
            collect.main()
        finally:
            sys.argv = old

    def test_all_projects_discovery(self):
        out = self.home / "disc"
        self._main("--all-projects", "--out", str(out))
        index = json.loads((out / "projects-index.json").read_text())
        self.assertGreaterEqual(index["totals"]["projects"], 1)
        self.assertTrue((out / "projects-index.md").exists())
        # the fixture project should appear with at least one agent's sessions
        self.assertTrue(any(self.project in cwd for cwd in index["projects"]))

    def test_all_projects_default_out(self):
        # exercises the default out-dir branch (no --out) for --all-projects
        os.chdir(self.home)
        self._main("--all-projects")
        self.assertTrue((self.home / ".agents" / "rosetta" / "discovery" / "projects-index.json").exists())

    def test_since_filters_timestamped_sessions(self):
        # claude sessions are timestamped (2026); --since in the far future drops them
        out = self.home / "since"
        self._main("--project", self.project, "--out", str(out), "--agents", "claude",
                   "--since", "2099-01-01")
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertEqual(manifest["agents"]["claude"]["sessions"], 0)
        self.assertEqual(manifest["options"]["since"][:4], "2099")

    def test_unknown_agent_records_error(self):
        out = self.home / "unk"
        self._main("--project", self.project, "--out", str(out), "--agents", "claude,bogus")
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertIn("error", manifest["agents"]["bogus"])

    def test_max_chars_truncates(self):
        # write a long claude turn, then collect with a tiny max-chars
        long_session = (self.home / ".claude" / "projects" / collect.enc_path(self.project) / "long.jsonl")
        long_session.write_text(json.dumps({
            "type": "assistant", "cwd": self.project, "timestamp": "2026-06-08T00:00:05Z",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "x" * 500}]}}) + "\n")
        out = self.home / "trunc"
        self._main("--project", self.project, "--out", str(out), "--agents", "claude", "--max-chars", "20")
        body = "\n".join(p.read_text() for p in out.glob("claude__*.md"))
        self.assertIn("truncated", body)

    def test_missing_out_dir_errors(self):
        with self.assertRaises(SystemExit):
            self._main("--project", self.project)


if __name__ == "__main__":
    unittest.main(verbosity=2)
