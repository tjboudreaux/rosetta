#!/usr/bin/env python3
"""Compiler anti-hallucination gate for decisions.py (integrity pass).

Goal-2 finding: an LLM that compiles a decision library can fabricate provenance — it referenced
ADR ids that did not exist (2/5 fixtures) and could just as easily cite a source file that isn't
there. A "verified provenance graph" that invents its own ids/citations is worse than no library.
These tests stand up a throwaway git repo (so basename grounding has tracked files to resolve
against) and assert that the integrity pass:
  - flags a `LABEL NNNN` reference (frontmatter OR body) that resolves to no real record;
  - flags a file-shaped `Sources:` citation that exists nowhere in the repo (ghost citation);
  - does NOT flag a record's reference to itself, a real cross-reference, a directory citation
    (`tests/`), a code-symbol citation (`load_counter/save_counter`), or a basename-only citation
    whose file exists somewhere in the repo (the real library's loose citation style);
  - turns those into hard errors under `validate --integrity` (exit 1) but not under plain validate;
  - exits 1 from the standalone `integrity` subcommand when anything is found, 0 when clean.

Pure stdlib (subprocess to the git binary; ADR 0013).

Run: python3 -m unittest discover -s tests
"""
import io
import json
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
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _have_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


@unittest.skipUnless(_have_git(), "git binary not available")
class Integrity(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "Test")
        # a couple of real source files so basename/path grounding has something to resolve to
        (self.root / "src").mkdir()
        (self.root / "src" / "store.py").write_text("DB = 'duck'\n")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_store.py").write_text("def test(): pass\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "seed")
        (self.root / "architecture-decisions").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _record(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        return p

    def _assess(self):
        records = decisions.collect_records(self.root, decisions.load_config(self.root))
        return decisions.assess_integrity(records, decisions.load_config(self.root), self.root)

    def _main(self, *args):
        old = sys.argv
        sys.argv = ["decisions", *args]
        try:
            decisions.main()
        finally:
            sys.argv = old

    def _real(self):
        # a clean, fully-grounded record: real source path, self/peer references that resolve
        self._record("architecture-decisions/0001-store.md",
                     "# ADR 0001 — Store\n\n- Status: Accepted\n- Date: 2026-06-01\n"
                     "- Decider: Me\n- Sources: src/store.py, tests/test_store.py\n\n"
                     "## Decision\n\nUse duck. See ADR 0001 (this record).\n")

    # --- catches the two hallucination modes ----------------------------------------
    def test_flags_dangling_adr_reference(self):
        self._real()
        self._record("architecture-decisions/0002-x.md",
                     "# ADR 0002 — X\n\n- Status: Accepted\n- Date: 2026-06-02\n"
                     "- Decider: Me\n- Sources: src/store.py\n- Related: ADR 0099\n\n"
                     "## Decision\n\nThis supersedes ADR 0099.\n")
        r = self._assess()
        self.assertEqual([d["ref"] for d in r["dangling_refs"]], ["ADR 0099"])
        self.assertEqual(r["ghost_sources"], [])

    def test_flags_ghost_source_citation(self):
        self._record("architecture-decisions/0001-x.md",
                     "# ADR 0001 — X\n\n- Status: Accepted\n- Date: 2026-06-01\n"
                     "- Decider: Me\n- Sources: src/ghost_module_xyz.py\n\n## Decision\n\nbody\n")
        r = self._assess()
        self.assertEqual([g["source"] for g in r["ghost_sources"]], ["src/ghost_module_xyz.py"])
        self.assertEqual(r["dangling_refs"], [])

    def test_dangling_ref_in_body_only_is_caught(self):
        self._real()
        self._record("architecture-decisions/0002-y.md",
                     "# ADR 0002 — Y\n\n- Status: Accepted\n- Date: 2026-06-02\n"
                     "- Decider: Me\n- Sources: src/store.py\n\n"
                     "## Decision\n\nUnlike ADR 0042, we ship now.\n")
        r = self._assess()
        self.assertEqual([d["ref"] for d in r["dangling_refs"]], ["ADR 0042"])

    # --- no false positives ----------------------------------------------------------
    def test_clean_library_is_ok(self):
        self._real()
        r = self._assess()
        self.assertEqual(r["dangling_refs"], [])
        self.assertEqual(r["ghost_sources"], [])

    def test_self_and_peer_references_not_flagged(self):
        self._real()
        self._record("architecture-decisions/0002-peer.md",
                     "# ADR 0002 — Peer\n\n- Status: Accepted\n- Date: 2026-06-02\n"
                     "- Decider: Me\n- Sources: src/store.py\n- Related: ADR 0001\n\n"
                     "## Decision\n\nBuilds on ADR 0001 and ADR 0002 (self).\n")
        self.assertEqual(self._assess()["dangling_refs"], [])

    def test_symbol_citation_not_flagged(self):
        # `load_counter/save_counter` is a code-symbol citation (no file extension on the last
        # segment), not a path — must not be treated as a ghost file.
        self._record("architecture-decisions/0001-sym.md",
                     "# ADR 0001 — Sym\n\n- Status: Accepted\n- Date: 2026-06-01\n"
                     "- Decider: Me\n- Sources: load_counter/save_counter, cmd_get/resolve\n\n"
                     "## Decision\n\nbody\n")
        self.assertEqual(self._assess()["ghost_sources"], [])

    def test_directory_citation_not_flagged(self):
        self._record("architecture-decisions/0001-dir.md",
                     "# ADR 0001 — Dir\n\n- Status: Accepted\n- Date: 2026-06-01\n"
                     "- Decider: Me\n- Sources: tests/, src/\n\n## Decision\n\nbody\n")
        self.assertEqual(self._assess()["ghost_sources"], [])

    def test_basename_only_citation_grounded_by_repo(self):
        # cited as a bare basename (no dir) — grounded because `store.py` exists somewhere in the repo
        self._record("architecture-decisions/0001-base.md",
                     "# ADR 0001 — Base\n\n- Status: Accepted\n- Date: 2026-06-01\n"
                     "- Decider: Me\n- Sources: store.py\n\n## Decision\n\nbody\n")
        self.assertEqual(self._assess()["ghost_sources"], [])

    def test_transcript_citation_not_flagged(self):
        self._record("architecture-decisions/0001-tr.md",
                     "# ADR 0001 — Tr\n\n- Status: Accepted\n- Date: 2026-06-01\n"
                     "- Decider: Me\n- Sources: `claude · 4b80b004 · 2026-06-07`, src/store.py\n\n"
                     "## Decision\n\nbody\n")
        self.assertEqual(self._assess()["ghost_sources"], [])

    # --- CLI exit codes --------------------------------------------------------------
    def test_standalone_integrity_exit_codes(self):
        self._real()
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("integrity", "--root", str(self.root))     # clean -> exit 0
        self.assertTrue(json.loads(buf.getvalue())["ok"])

        self._record("architecture-decisions/0002-bad.md",
                     "# ADR 0002 — Bad\n\n- Status: Accepted\n- Date: 2026-06-02\n"
                     "- Decider: Me\n- Sources: src/store.py\n\n## Decision\n\nSee ADR 0099.\n")
        with self.assertRaises(SystemExit) as cm:
            with redirect_stdout(io.StringIO()):
                self._main("integrity", "--root", str(self.root))
        self.assertEqual(cm.exception.code, 1)

    def test_validate_integrity_flag_is_a_hard_error(self):
        self._real()
        self._record("architecture-decisions/0002-bad.md",
                     "# ADR 0002 — Bad\n\n- Status: Accepted\n- Date: 2026-06-02\n"
                     "- Decider: Me\n- Sources: src/store.py\n\n## Decision\n\nSee ADR 0099.\n")
        # plain validate: no integrity pass, so no error from the dangling ref
        with redirect_stdout(io.StringIO()):
            self._main("validate", "--root", str(self.root))      # exits 0 (no SystemExit raised)
        # with --integrity: the dangling ref is a hard error -> exit 1
        with self.assertRaises(SystemExit) as cm:
            with redirect_stdout(io.StringIO()):
                self._main("validate", "--root", str(self.root), "--integrity")
        self.assertEqual(cm.exception.code, 1)


class IntegrityWithoutGit(unittest.TestCase):
    """The gate must work with no git: basename grounding falls back to a filesystem rglob, and
    exact-path resolution still works. A non-git checkout is the worst case, not an excuse to pass."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "store.py").write_text("DB = 'duck'\n")
        (self.root / "architecture-decisions").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _record(self, rel, body):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)

    def _assess(self):
        cfg = decisions.load_config(self.root)
        return decisions.assess_integrity(decisions.collect_records(self.root, cfg), cfg, self.root)

    def test_real_path_grounds_and_ghost_is_flagged_without_git(self):
        self._record("architecture-decisions/0001-x.md",
                     "# ADR 0001 — X\n\n- Status: Accepted\n- Date: 2026-06-01\n"
                     "- Decider: Me\n- Sources: src/store.py, src/ghost_xyz.py\n\n## Decision\n\nbody\n")
        r = self._assess()
        self.assertEqual([g["source"] for g in r["ghost_sources"]], ["src/ghost_xyz.py"])
        self.assertEqual(r["dangling_refs"], [])

    def test_basename_grounding_via_rglob_without_git(self):
        # cited as a bare basename; no git, so grounding must come from the rglob fallback
        self._record("architecture-decisions/0001-b.md",
                     "# ADR 0001 — B\n\n- Status: Accepted\n- Date: 2026-06-01\n"
                     "- Decider: Me\n- Sources: store.py\n\n## Decision\n\nbody\n")
        self.assertEqual(self._assess()["ghost_sources"], [])


if __name__ == "__main__":
    unittest.main()
