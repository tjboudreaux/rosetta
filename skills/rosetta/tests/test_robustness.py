#!/usr/bin/env python3
"""Robustness tests — crash-safe writes and count-and-skip resilience.

Rosetta's promise is "nothing disappears," so the write and parse paths must degrade gracefully:
durability-critical files are written atomically (temp + os.replace), a corrupt ledger is reported
and recovered from rather than silently crashing, and a malformed transcript line is skipped while
the valid ones are still counted. Driven through collect.main() against the synthetic fixture $HOME.

Run: python3 -m unittest discover -s tests   (pure stdlib, no deps)
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE / "fixtures"))
import collect          # noqa: E402
import build            # noqa: E402


class AtomicWrite(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_content(self):
        target = self.dir / "sub" / "f.json"
        collect.atomic_write_text(target, '{"a": 1}')
        self.assertEqual(json.loads(target.read_text()), {"a": 1})

    def test_overwrites_existing(self):
        target = self.dir / "f.txt"
        collect.atomic_write_text(target, "old")
        collect.atomic_write_text(target, "new")
        self.assertEqual(target.read_text(), "new")

    def test_leaves_no_tmp_siblings(self):
        target = self.dir / "f.txt"
        collect.atomic_write_text(target, "x")
        leftovers = [p.name for p in self.dir.iterdir() if p.name != "f.txt"]
        self.assertEqual(leftovers, [], f"unexpected leftovers: {leftovers}")


class CollectRobustness(unittest.TestCase):
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
        err = io.StringIO()
        try:
            with redirect_stderr(err):
                collect.main()
        finally:
            sys.argv = old
        manifest = json.loads((out / "manifest.json").read_text())
        return manifest, err.getvalue()

    def test_manifest_schema(self):
        manifest, _ = self._run("run1")
        for key in ("project", "generated_at", "options", "agents", "unknown_stores", "totals"):
            self.assertIn(key, manifest, f"manifest missing top-level key: {key}")
        for key in ("sessions", "messages", "skipped_lines", "skipped_sessions"):
            self.assertIn(key, manifest["totals"], f"totals missing key: {key}")
        self.assertEqual(manifest["project"], self.project)

    def test_manifest_written_atomically(self):
        out_label = "run1"
        self._run(out_label)
        out = self.home / out_label
        leftovers = [p.name for p in out.iterdir() if p.name.startswith(".manifest.json")]
        self.assertEqual(leftovers, [], f"temp leftovers: {leftovers}")

    def test_corrupt_ledger_recovers_loudly(self):
        self._run("run1")                       # seed the ledger
        self.ledger.write_text("{ not json")    # corrupt it
        manifest, stderr = self._run("run2")    # must not crash
        self.assertGreater(manifest["totals"]["sessions"], 0,
                           "corrupt ledger should fall back to reprocessing")
        self.assertIn("unreadable", stderr.lower(),
                      "corruption should be reported loudly on stderr")
        # ledger is healthy again afterward
        self.assertIsInstance(json.loads(self.ledger.read_text())["entries"], dict)

    def test_malformed_transcript_line_is_skipped_not_fatal(self):
        # Append one garbage line and one valid later turn to the claude fixture session.
        with self.claude_session.open("a") as fh:
            fh.write("{ truncated json that never closes\n")
            fh.write(json.dumps({
                "type": "assistant", "cwd": self.project,
                "timestamp": "2026-06-09T00:00:00Z",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "more"}]},
            }) + "\n")
        manifest, _ = self._run("run1")
        agent = manifest["agents"]["claude"]
        self.assertEqual(manifest["totals"]["sessions"], 1)      # still processed the session
        self.assertGreaterEqual(agent["messages"], 2)            # valid turns kept
        self.assertGreaterEqual(manifest["totals"]["skipped_lines"], 1)  # garbage counted, not fatal


if __name__ == "__main__":
    unittest.main(verbosity=2)
