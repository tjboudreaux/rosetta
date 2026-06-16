#!/usr/bin/env python3
"""Phase-1 freshness/staleness guard for decisions.py (GOAL 4).

A decision can be Accepted yet stale: the code it cites under `Sources:` changed in git AFTER the
record's Date. These tests stand up a real throwaway git repo (records + committed code files) and
assert that:
  - `staleness` flags exactly the records whose cited code moved after their Date;
  - records whose code predates their Date are reported fresh;
  - the path extractor ignores transcript citations (`agent · id · date`) and prose;
  - `resolve` surfaces a `stale` flag on returned records;
  - with NO git (or unresolvable paths) the check degrades cleanly to skipped/unknown — never a false pass.

Pure stdlib (subprocess to the git binary; ADR 0013).

Run: python3 -m unittest discover -s tests
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import decisions          # noqa: E402


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, text=True)


def _have_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


# --- pure unit tests for the path extractor (no git needed) ---------------------------
class ExtractSourcePaths(unittest.TestCase):
    def test_picks_backticked_and_bare_paths(self):
        src = "code `scripts/decisions.py`, .github/workflows/ci.yml, tests/"
        self.assertEqual(decisions.extract_source_paths(src),
                         ["scripts/decisions.py", ".github/workflows/ci.yml", "tests"])

    def test_ignores_transcript_citations(self):
        src = "`claude · 4b80b004 · 2026-06-07` (this conversation); code `scripts/decisions.py`"
        self.assertEqual(decisions.extract_source_paths(src), ["scripts/decisions.py"])

    def test_ignores_prose_words(self):
        src = "this conversation, requirement number five; from a sibling project's library"
        self.assertEqual(decisions.extract_source_paths(src), [])

    def test_dedupes_preserving_order(self):
        src = "scripts/a.py, scripts/a.py, scripts/b.py"
        self.assertEqual(decisions.extract_source_paths(src), ["scripts/a.py", "scripts/b.py"])

    def test_empty_sources(self):
        self.assertEqual(decisions.extract_source_paths(""), [])
        self.assertEqual(decisions.extract_source_paths(None), [])


@unittest.skipUnless(_have_git(), "git binary not available")
class StalenessWithGit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "Test")
        (self.root / "architecture-decisions").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, *args):
        old = sys.argv
        sys.argv = ["decisions", *args]
        try:
            decisions.main()
        finally:
            sys.argv = old

    def _commit(self, rel, content, date):
        """Write a file and commit it with an explicit author+committer date."""
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        _git(self.root, "add", rel)
        env = dict(os.environ, GIT_AUTHOR_DATE=f"{date}T12:00:00",
                   GIT_COMMITTER_DATE=f"{date}T12:00:00")
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "-m", f"touch {rel}"],
                       check=True, capture_output=True, text=True, env=env)

    def _record(self, rel, title, status, date, sources):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# ADR {title}\n\n- Status: {status}\n- Date: {date}\n- Decider: Me\n"
                     f"- Sources: {sources}\n\n## Decision\n\nbody\n")
        return p

    def _run_staleness(self, *extra):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("staleness", "--root", str(self.root), *extra)
        return json.loads(buf.getvalue())

    def test_flags_record_whose_code_moved_after_its_date(self):
        # code committed 2026-06-10, record dated 2026-06-01 -> the code moved AFTER the decision: STALE
        self._commit("src/store.py", "DB = 'dynamo'\n", "2026-06-10")
        self._record("architecture-decisions/0001-store.md", "0001 — store",
                     "Accepted", "2026-06-01", "code `src/store.py`")
        out = self._run_staleness()
        self.assertTrue(out["git"])
        self.assertEqual([s["id"] for s in out["stale"]], ["ADR 0001"])
        self.assertEqual(out["stale"][0]["stale_paths"][0]["path"], "src/store.py")

    def test_fresh_when_code_predates_the_record(self):
        # code committed 2026-05-01, record dated 2026-06-01 -> decision is newer than the code: FRESH
        self._commit("src/store.py", "DB = 'dynamo'\n", "2026-05-01")
        self._record("architecture-decisions/0001-store.md", "0001 — store",
                     "Accepted", "2026-06-01", "code `src/store.py`")
        out = self._run_staleness()
        self.assertEqual(out["stale"], [])
        self.assertEqual(out["fresh_count"], 1)

    def test_only_accepted_records_are_checked_by_default(self):
        self._commit("src/store.py", "x\n", "2026-06-10")
        self._record("architecture-decisions/0001-prop.md", "0001 — proposed",
                     "Proposed", "2026-06-01", "code `src/store.py`")
        out = self._run_staleness()
        self.assertEqual(out["checked_records"], 0)        # Proposed skipped

    def test_unknown_when_path_not_in_git(self):
        # cited path was never committed -> unknown (not stale, not fresh)
        self._commit("src/other.py", "x\n", "2026-06-10")
        self._record("architecture-decisions/0001-x.md", "0001 — x",
                     "Accepted", "2026-06-01", "code `src/never-committed.py`")
        out = self._run_staleness()
        self.assertEqual(out["stale"], [])
        self.assertEqual([u["id"] for u in out["unknown"]], ["ADR 0001"])

    def test_strict_exits_nonzero_on_stale(self):
        self._commit("src/store.py", "x\n", "2026-06-10")
        self._record("architecture-decisions/0001-store.md", "0001 — store",
                     "Accepted", "2026-06-01", "code `src/store.py`")
        with self.assertRaises(SystemExit) as cm:
            self._main("staleness", "--root", str(self.root), "--strict")
        self.assertEqual(cm.exception.code, 1)

    def test_validate_staleness_flag_warns(self):
        self._commit("src/store.py", "x\n", "2026-06-10")
        self._record("architecture-decisions/0001-store.md", "0001 — store",
                     "Accepted", "2026-06-01", "code `src/store.py`")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("validate", "--root", str(self.root), "--staleness")
        self.assertIn("1 stale", buf.getvalue())
        # under --strict the stale warning becomes a failure
        with self.assertRaises(SystemExit):
            self._main("validate", "--root", str(self.root), "--staleness", "--strict")

    def test_resolve_surfaces_stale_flag(self):
        self._commit("src/store.py", "x\n", "2026-06-10")
        self._record("architecture-decisions/0001-store.md", "0001 — widget store",
                     "Accepted", "2026-06-01", "code `src/store.py`")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("resolve", "--root", str(self.root), "--text", "widget store")
        res = json.loads(buf.getvalue())
        self.assertTrue(res["freshness_checked"])
        self.assertTrue(res["current"][0]["stale"])
        self.assertTrue(res.get("stale"))

    def test_resolve_no_stale_check_skips_git(self):
        self._commit("src/store.py", "x\n", "2026-06-10")
        self._record("architecture-decisions/0001-store.md", "0001 — widget store",
                     "Accepted", "2026-06-01", "code `src/store.py`")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("resolve", "--root", str(self.root), "--text", "widget store",
                       "--no-stale-check")
        res = json.loads(buf.getvalue())
        self.assertFalse(res["freshness_checked"])
        self.assertNotIn("stale", res["current"][0])

    def test_decisions_root_relative_path_resolves(self):
        # Sources cites a path relative to the decisions root (here == repo root); it must resolve.
        self._commit("code/widget.py", "x\n", "2026-06-10")
        self._record("architecture-decisions/0001-w.md", "0001 — widget",
                     "Accepted", "2026-06-01", "code `code/widget.py`")
        out = self._run_staleness()
        self.assertEqual([s["id"] for s in out["stale"]], ["ADR 0001"])


class StalenessNoGit(unittest.TestCase):
    """With no git repo at all, the check must skip cleanly (never report a false all-fresh)."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "architecture-decisions").mkdir(parents=True)
        # a non-git temp dir; ensure no ancestor .git interferes by checking explicitly below

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, *args):
        old = sys.argv
        sys.argv = ["decisions", *args]
        try:
            decisions.main()
        finally:
            sys.argv = old

    def test_staleness_skips_outside_git(self):
        if decisions._git_repo_root(self.root) is not None:
            self.skipTest("temp dir unexpectedly inside a git work tree")
        (self.root / "architecture-decisions" / "0001-x.md").write_text(
            "# ADR 0001 — x\n\n- Status: Accepted\n- Date: 2026-06-01\n- Decider: Me\n"
            "- Sources: code `src/store.py`\n\n## Decision\n\nbody\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("staleness", "--root", str(self.root))
        out = json.loads(buf.getvalue())
        self.assertFalse(out["git"])
        self.assertTrue(out["skipped"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
