#!/usr/bin/env python3
"""In-process coverage for decisions.py: scaffold (`new`), regenerate index (`index`), and validate
(`validate`) — including the error paths (unknown type, missing fields, duplicate number, dangling
supersede). Uses a throwaway library root; templates fall back to the skill's templates/ dir.

Run: python3 -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import decisions          # noqa: E402


class DecisionsCLI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, *args):
        old = sys.argv
        sys.argv = ["decisions", *args]
        try:
            decisions.main()
        finally:
            sys.argv = old

    def _write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def test_new_scaffolds_record(self):
        self._main("new", "--root", str(self.root), "--type", "adr",
                   "--title", "Use an event bus", "--status", "Accepted", "--decider", "Me",
                   "--date", "2026-06-13")
        made = list((self.root / "architecture-decisions").glob("*.md"))
        self.assertEqual(len(made), 1)
        body = made[0].read_text()
        self.assertIn("# ADR 0001 — Use an event bus", body)
        self.assertIn("- Status: Accepted", body)
        self.assertIn("- Date: 2026-06-13", body)
        self.assertIn("- Decider: Me", body)
        # a second new auto-increments the number
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Second")
        self.assertEqual(len(list((self.root / "architecture-decisions").glob("*.md"))), 2)

    def test_new_unknown_type_errors(self):
        with self.assertRaises(SystemExit):
            self._main("new", "--root", str(self.root), "--type", "zzz", "--title", "x")

    def test_index_regenerates_timeline(self):
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "First thing",
                   "--decider", "Me")
        self._main("index", "--root", str(self.root))
        readme = (self.root / "README.md").read_text()
        self.assertIn("Timeline", readme)
        self.assertIn("First thing", readme)
        self.assertIn(decisions.TIMELINE_START, readme)

    def test_validate_clean_then_index_again(self):
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Clean record",
                   "--decider", "Me")
        self._main("index", "--root", str(self.root))
        # clean library validates without raising
        self._main("validate", "--root", str(self.root))

    def test_validate_flags_errors(self):
        # missing required Decider + bad Status + dangling supersede + duplicate number
        self._write("architecture-decisions/0001-a.md",
                    "# ADR 0001 — A\n\n- Status: Bogus\n- Date: 2026-06-01\n\n## Context\n")
        self._write("architecture-decisions/0001-dup.md",
                    "# ADR 0001 — Dup\n\n- Status: Accepted\n- Date: 2026-06-01\n- Decider: Me\n"
                    "- Supersedes: ADR 0099\n\n## Context\n")
        with self.assertRaises(SystemExit):
            self._main("validate", "--root", str(self.root))

    def test_index_handles_unparseable_and_existing_readme(self):
        # a record with no parseable H1 is skipped with a warning (collect_records branch)
        self._write("architecture-decisions/0001-ok.md",
                    "# ADR 0001 — Ok\n\n- Status: Accepted\n- Date: 2026-06-01\n- Decider: Me\n\n## Context\n")
        self._write("architecture-decisions/junk.md", "no heading here\njust text\n")
        # pre-existing README WITHOUT timeline markers -> the append branch
        self._write("README.md", "# My index\n\nIntro prose.\n")
        self._main("index", "--root", str(self.root))
        self.assertIn(decisions.TIMELINE_START, (self.root / "README.md").read_text())
        # second index run hits the in-place re-substitution branch (markers already present)
        self._main("index", "--root", str(self.root))
        self.assertEqual((self.root / "README.md").read_text().count(decisions.TIMELINE_START), 1)

    def test_validate_warnings_only_passes(self):
        # valid record but non-kebab filename + no Sources -> warnings (not errors): must NOT raise
        self._write("architecture-decisions/0001-Bad_Name.md",
                    "# ADR 0001 — W\n\n- Status: Accepted\n- Date: 2026-06-01\n- Decider: Me\n\n## Context\n")
        self._main("validate", "--root", str(self.root))

    def test_default_root_resolution(self):
        # no --root, cwd has a decisions/ dir -> resolves there
        cwd = os.getcwd()
        (self.root / "decisions").mkdir()
        os.chdir(self.root)
        try:
            self._main("new", "--type", "adr", "--title", "Default rooted")
            self.assertTrue(list((self.root / "decisions" / "architecture-decisions").glob("*.md")))
        finally:
            os.chdir(cwd)

    def test_config_override_and_bad_config(self):
        # a malformed config.json is tolerated (warns, uses defaults)
        self._write("config.json", "{ not json")
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Despite bad config")
        self.assertTrue(list((self.root / "architecture-decisions").glob("*.md")))


class DecisionsHardening(unittest.TestCase):
    """Phase 1: atomic writes, race-safe numbering, supersede-cycle detection, --strict, slug cap."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, *args):
        old = sys.argv
        sys.argv = ["decisions", *args]
        try:
            decisions.main()
        finally:
            sys.argv = old

    def _write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def test_atomic_write_text_no_tmp_leftovers(self):
        target = self.root / "sub" / "x.md"
        decisions.atomic_write_text(target, "hello")
        self.assertEqual(target.read_text(), "hello")
        leftovers = [p.name for p in (self.root / "sub").iterdir() if p.name != "x.md"]
        self.assertEqual(leftovers, [])

    def test_new_then_index_leave_no_tmp_files(self):
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "First", "--decider", "Me")
        self._main("index", "--root", str(self.root))
        adr_dir = self.root / "architecture-decisions"
        self.assertFalse([p for p in adr_dir.iterdir() if p.name.startswith(".")],
                         "temp dotfiles left behind")
        self.assertFalse([p for p in self.root.iterdir() if p.name.startswith(".README")])

    def test_new_numbering_autobumps_on_collision(self):
        # pre-create the 0001 slot for this exact slug; `new` must reserve 0002, not crash/overwrite
        self._write("architecture-decisions/0001-shared-title.md", "# ADR 0001 — Shared title\n")
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Shared title",
                   "--decider", "Me")
        files = sorted(p.name for p in (self.root / "architecture-decisions").glob("*.md"))
        self.assertIn("0002-shared-title.md", files)
        self.assertEqual(len(files), 2)

    def test_width_expands_past_9999(self):
        self._write("architecture-decisions/9999-x.md", "# ADR 9999 — X\n")
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Big", "--decider", "Me")
        names = [p.name for p in (self.root / "architecture-decisions").glob("*.md")]
        self.assertIn("10000-big.md", names)

    def test_slug_is_capped(self):
        self._main("new", "--root", str(self.root), "--type", "adr",
                   "--title", "z" * 300, "--decider", "Me")
        made = next((self.root / "architecture-decisions").glob("*.md"))
        slug = made.stem.split("-", 1)[1]
        self.assertLessEqual(len(slug), decisions.MAX_SLUG)

    def test_validate_detects_supersede_cycle(self):
        self._write("architecture-decisions/0001-a.md",
                    "# ADR 0001 — A\n\n- Status: Superseded by ADR 0002\n- Date: 2026-06-01\n- Decider: Me\n\n## Context\n")
        self._write("architecture-decisions/0002-b.md",
                    "# ADR 0002 — B\n\n- Status: Superseded by ADR 0001\n- Date: 2026-06-02\n- Decider: Me\n\n## Context\n")
        with self.assertRaises(SystemExit):
            self._main("validate", "--root", str(self.root))

    def test_strict_fails_on_warnings(self):
        # valid record, but non-kebab filename triggers a WARNING; --strict must make it fail
        self._write("architecture-decisions/0001-Bad_Name.md",
                    "# ADR 0001 — W\n\n- Status: Accepted\n- Date: 2026-06-01\n- Decider: Me\n- Sources: x\n\n## Context\n")
        self._main("validate", "--root", str(self.root))            # non-strict: passes
        with self.assertRaises(SystemExit):
            self._main("validate", "--root", str(self.root), "--strict")

    def test_new_never_reuses_a_number_even_with_stale_counter(self):
        # counter says 5000 but a file already exists at 5001 (drift) → must bump past it, no dup number
        self._write("architecture-decisions/5001-existing.md", "# ADR 5001 — Existing\n")
        self._write(".counter.json", '{"adr": 5000}')
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Next", "--decider", "Me")
        names = [p.name for p in (self.root / "architecture-decisions").glob("*.md")]
        self.assertIn("5002-next.md", names)            # skipped the drifted 5001, no collision
        nums = [n.split("-")[0] for n in names]
        self.assertEqual(len(nums), len(set(nums)))      # all numbers unique

    def test_counter_lock_is_released(self):
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "One", "--decider", "Me")
        self.assertFalse((self.root / ".counter.lock").exists())   # lock cleaned up

    def test_supersede_raises_on_record_without_status_line(self):
        # malformed old record (no '- Status:' line) → supersede must FAIL loudly, not silently no-op
        self._write("architecture-decisions/0001-old.md", "# ADR 0001 — Old\n\nno frontmatter here\n")
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "New", "--decider", "Me")
        with self.assertRaises(SystemExit):
            self._main("supersede", "--root", str(self.root), "ADR 1", "--by", "ADR 2")

    def test_search_limit_surfaces_truncation(self):
        import io
        from contextlib import redirect_stdout
        for i in range(5):
            self._main("new", "--root", str(self.root), "--type", "adr",
                       "--title", f"common topic {i}", "--decider", "Me")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("search", "--root", str(self.root), "--text", "common topic", "--limit", "2")
        out = json.loads(buf.getvalue())
        self.assertEqual(out["returned"], 2)
        self.assertEqual(out["total_matches"], 5)
        self.assertTrue(out["truncated"])

    def test_clean_supersession_chain_validates(self):
        # a normal (acyclic) supersession must NOT be flagged as a cycle
        self._write("architecture-decisions/0001-old.md",
                    "# ADR 0001 — Old\n\n- Status: Superseded by ADR 0002\n- Date: 2026-06-01\n- Decider: Me\n- Sources: x\n\n## Context\n")
        self._write("architecture-decisions/0002-new.md",
                    "# ADR 0002 — New\n\n- Status: Accepted\n- Date: 2026-06-02\n- Decider: Me\n- Sources: x\n- Supersedes: ADR 0001\n\n## Context\n")
        self._main("validate", "--root", str(self.root))            # must not raise


class DecisionsScale(unittest.TestCase):
    """Phase 2 (ADR 0021): O(1) numbering via counter, query subcommands, deterministic supersede."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
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

    def _write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def test_new_uses_counter_not_glob_scan(self):
        # Only 2 real files, but the counter claims 5000. If `new` used the counter (O(1)) it picks
        # 5001; if it fell back to globbing the dir it would pick 0003. This pins the O(1) path.
        self._write("architecture-decisions/0001-a.md", "# ADR 0001 — A\n")
        self._write("architecture-decisions/0002-b.md", "# ADR 0002 — B\n")
        self._write(".counter.json", '{"adr": 5000}')
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Next", "--decider", "Me")
        names = [p.name for p in (self.root / "architecture-decisions").glob("*.md")]
        self.assertIn("5001-next.md", names)
        self.assertEqual(json.loads((self.root / ".counter.json").read_text())["adr"], 5001)

    def test_missing_counter_initializes_from_disk_once(self):
        self._write("architecture-decisions/0007-x.md", "# ADR 0007 — X\n")
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "After seven", "--decider", "Me")
        names = [p.name for p in (self.root / "architecture-decisions").glob("*.md")]
        self.assertIn("0008-after-seven.md", names)           # scanned once, max(7)+1
        self.assertEqual(json.loads((self.root / ".counter.json").read_text())["adr"], 8)

    def test_index_emits_index_json_and_counter(self):
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "One", "--decider", "Me")
        self._main("index", "--root", str(self.root))
        idx = json.loads((self.root / "INDEX.json").read_text())
        self.assertEqual(len(idx), 1)
        self.assertEqual(idx[0]["id"], "ADR 0001")
        self.assertIn("status", idx[0])
        self.assertTrue((self.root / ".counter.json").exists())

    def test_search_filters_by_text_status_type(self):
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Adopt msgpack wire format", "--decider", "Me", "--status", "Accepted")
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Use redis queue", "--decider", "Me", "--status", "Proposed")
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("search", "--root", str(self.root), "--text", "msgpack")
        hits = json.loads(buf.getvalue())["hits"]
        self.assertEqual(len(hits), 1)
        self.assertIn("msgpack", hits[0]["title"].lower())

    def test_supersede_flips_status_and_links(self):
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Old way", "--decider", "Me", "--status", "Accepted")
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "New way", "--decider", "Me", "--status", "Accepted")
        self._main("supersede", "--root", str(self.root), "ADR 1", "--by", "ADR 2")
        old = (self.root / "architecture-decisions" / "0001-old-way.md").read_text()
        new = (self.root / "architecture-decisions" / "0002-new-way.md").read_text()
        self.assertIn("- Status: Superseded by ADR 0002", old)
        self.assertIn("- Supersedes: ADR 0001", new)
        self._main("index", "--root", str(self.root))
        self._main("validate", "--root", str(self.root))      # acyclic; must not raise

    def test_supersede_rejects_self_and_unknown(self):
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Solo", "--decider", "Me")
        with self.assertRaises(SystemExit):
            self._main("supersede", "--root", str(self.root), "ADR 1", "--by", "ADR 1")
        with self.assertRaises(SystemExit):
            self._main("supersede", "--root", str(self.root), "ADR 1", "--by", "ADR 99")

    def test_get_prints_one_record(self):
        import io
        from contextlib import redirect_stdout
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Gettable", "--decider", "Me")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("get", "--root", str(self.root), "ADR 1")
        self.assertIn("# ADR 0001 — Gettable", buf.getvalue())

    def test_search_status_and_type_filters(self):
        import io
        from contextlib import redirect_stdout
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Accepted one", "--decider", "Me", "--status", "Accepted")
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Proposed one", "--decider", "Me", "--status", "Proposed")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("search", "--root", str(self.root), "--status", "Accepted", "--type", "adr")
        hits = json.loads(buf.getvalue())["hits"]
        self.assertEqual([h["title"] for h in hits], ["Accepted one"])

    def test_resolve_id_ambiguous_across_types(self):
        # same number 1 as both an ADR and a PDR -> bare 'get 1' is ambiguous, must error; qualified ok
        import io
        from contextlib import redirect_stdout
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "A one", "--decider", "Me")
        self._main("new", "--root", str(self.root), "--type", "pdr", "--title", "P one", "--decider", "Me")
        with self.assertRaises(SystemExit):
            self._main("get", "--root", str(self.root), "1")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("get", "--root", str(self.root), "PDR 1")
        self.assertIn("# PDR 0001 — P one", buf.getvalue())

    def test_scale_3000_records_new_and_search(self):
        # Build a sizable library directly, then confirm `new` (counter) and `search` work over it.
        d = self.root / "architecture-decisions"
        for i in range(1, 3001):
            (d / f"{i:04d}-filler-{i}.md").write_text(
                f"# ADR {i:04d} — Filler {i}\n\n- Status: Accepted\n- Date: 2026-01-01\n- Decider: Me\n- Sources: x\n\n## Decision\n\nUse approach {i}.\n")
        # plant a needle
        (d / "1500-the-needle-decision.md").write_text(
            "# ADR 1500 — The needle decision\n\n- Status: Accepted\n- Date: 2026-02-02\n- Decider: Me\n- Sources: x\n\n## Decision\n\nPersist events in QuantumDB.\n")
        self._write(".counter.json", '{"adr": 3000}')
        self._main("new", "--root", str(self.root), "--type", "adr", "--title", "Three thousand one", "--decider", "Me")
        self.assertTrue((d / "3001-three-thousand-one.md").exists())   # O(1) append, no rescan
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("search", "--root", str(self.root), "--text", "quantumdb")
        hits = json.loads(buf.getvalue())["hits"]
        self.assertEqual([h["id"] for h in hits], ["ADR 1500"])        # needle found by content


    def test_get_resolve_follows_supersession_to_current(self):
        """Phase 0 retrieval layer: `get --resolve` on a stale record prints the CURRENT one."""
        import io
        from contextlib import redirect_stdout
        d = self.root / "architecture-decisions"; d.mkdir(parents=True, exist_ok=True)
        d.joinpath("0001-old-store.md").write_text(
            "# ADR 0001 — user-profile datastore: DynamoDB\n\n- Status: Superseded by ADR 0002\n"
            "- Date: 2025-11-10\n- Decider: Me\n- Sources: x\n\n## Decision\n\nUse DynamoDB.\n")
        d.joinpath("0002-new-store.md").write_text(
            "# ADR 0002 — user-profile datastore: Cloud Spanner\n\n- Status: Accepted\n"
            "- Date: 2026-06-08\n- Decider: Me\n- Sources: x\n\n## Decision\n\nUse Cloud Spanner.\n")
        # plain get on the stale record shows the stale (DynamoDB) content
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("get", "--root", str(self.root), "ADR 0001")
        self.assertIn("DynamoDB", buf.getvalue())
        self.assertNotIn("Cloud Spanner", buf.getvalue())
        # get --resolve follows the chain and prints the CURRENT (Spanner) record + a redirect note
        buf = io.StringIO()
        with redirect_stdout(buf):
            self._main("get", "--root", str(self.root), "ADR 0001", "--resolve")
        out = buf.getvalue()
        self.assertIn("Cloud Spanner", out)
        self.assertIn("ADR 0002", out)
        self.assertIn("resolved", out.lower())

    def test_resolve_current_is_cycle_safe(self):
        """A supersede cycle must not hang resolve_current (validate flags the cycle separately)."""
        cfg = decisions.load_config(self.root)
        recs = [
            {"label": "ADR", "number": 1, "title": "a", "type": "adr",
             "fields": {"Status": "Superseded by ADR 2"}, "path": Path("a")},
            {"label": "ADR", "number": 2, "title": "b", "type": "adr",
             "fields": {"Status": "Superseded by ADR 1"}, "path": Path("b")},
        ]
        current, chain = decisions.resolve_current(recs, recs[0], cfg)
        self.assertIsNotNone(current)          # terminates, doesn't loop forever


if __name__ == "__main__":
    unittest.main(verbosity=2)
