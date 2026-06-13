#!/usr/bin/env python3
"""Incremental-collect tests — the processed-session ledger lets `collect` skip sessions it has
already normalized (default on), re-process sessions that gained new messages, and rebuild
everything under --reprocess. Driven through collect.main() against the synthetic fixture $HOME.

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


class IncrementalCollect(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.project = build.build(self.home)
        os.environ["ROSETTA_HOME"] = str(self.home)
        self.ledger = self.home / "ledger.json"
        self.claude_session = (self.home / ".claude" / "projects"
                               / collect.enc_path(self.project) / "s.jsonl")

    def tearDown(self):
        os.environ.pop("ROSETTA_HOME", None)
        self._tmp.cleanup()

    def _run(self, label, extra=None):
        out = self.home / label
        argv = ["collect", "--project", self.project, "--out", str(out),
                "--agents", "claude", "--processed-ledger", str(self.ledger)]
        argv += extra or []
        old = sys.argv
        sys.argv = argv
        try:
            collect.main()
        finally:
            sys.argv = old
        manifest = json.loads((out / "manifest.json").read_text())
        md_files = sorted(p.name for p in out.glob("claude__*.md"))
        return manifest, md_files

    def test_first_run_processes_and_seeds_ledger(self):
        manifest, md = self._run("run1")
        self.assertEqual(manifest["totals"]["sessions"], 1)
        self.assertEqual(manifest["totals"]["skipped_sessions"], 0)
        self.assertEqual(len(md), 1)
        self.assertTrue(self.ledger.exists())
        led = json.loads(self.ledger.read_text())
        self.assertEqual(len(led["entries"]), 1)

    def test_second_run_skips_unchanged(self):
        self._run("run1")
        manifest, md = self._run("run2")
        self.assertEqual(manifest["totals"]["sessions"], 0)
        self.assertEqual(manifest["totals"]["skipped_sessions"], 1)
        self.assertEqual(manifest["agents"]["claude"]["skipped_sessions"], 1)
        self.assertEqual(md, [])   # nothing re-emitted

    def test_grown_session_is_reprocessed(self):
        self._run("run1")
        # append a later assistant turn -> last_ts advances past the ledger entry
        with self.claude_session.open("a") as fh:
            fh.write(json.dumps({
                "type": "assistant", "cwd": self.project,
                "timestamp": "2026-06-09T00:00:00Z",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "more"}]},
            }) + "\n")
        manifest, md = self._run("run2")
        self.assertEqual(manifest["totals"]["sessions"], 1)
        self.assertEqual(manifest["totals"]["skipped_sessions"], 0)
        self.assertEqual(len(md), 1)

    def test_reprocess_rebuilds_everything(self):
        self._run("run1")
        manifest, md = self._run("run2", extra=["--reprocess"])
        self.assertEqual(manifest["totals"]["sessions"], 1)
        self.assertEqual(manifest["totals"]["skipped_sessions"], 0)
        self.assertEqual(len(md), 1)
        self.assertTrue(manifest["options"]["reprocess"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
