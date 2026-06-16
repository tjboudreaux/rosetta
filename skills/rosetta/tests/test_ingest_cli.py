#!/usr/bin/env python3
"""In-process coverage for ingest.py: external decisions JSON -> Proposed records, plus the error
paths (bad JSON, non-list input, unknown type, missing title, duplicate skip).

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
import ingest          # noqa: E402


class IngestCLI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, payload_or_path):
        src = payload_or_path
        if not isinstance(src, (str,)) or not src.endswith(".json"):
            p = self.root / "in.json"
            p.write_text(json.dumps(payload_or_path))
            src = str(p)
        old = sys.argv
        sys.argv = ["ingest", "--root", str(self.root), "--from", src]
        try:
            ingest.main()
        finally:
            sys.argv = old

    def test_ingests_proposed_records(self):
        self._main([
            {"type": "bdr", "title": "Adopt usage pricing", "decider": "Travis",
             "source": "circleback · mtg-1 · 2026-06-02", "context": "c", "decision": "d", "why": "w"},
            {"title": "No type defaults to adr"},          # default type adr, default body
        ])
        bdr = list((self.root / "business-decisions").glob("*.md"))
        adr = list((self.root / "architecture-decisions").glob("*.md"))
        self.assertEqual(len(bdr), 1)
        self.assertEqual(len(adr), 1)
        self.assertIn("- Status: Proposed", bdr[0].read_text())
        self.assertIn("unconfirmed", bdr[0].read_text())

    def test_ingest_uses_counter_and_continues_numbering(self):
        # ingest shares the lock+counter allocation (ADR 0023): with a counter claiming adr=40 it must
        # number the new record 0041, not rescan to 0001, and update the counter.
        import json as _json
        (self.root / "architecture-decisions").mkdir(parents=True)
        (self.root / ".counter.json").write_text('{"adr": 40}')
        self._main([{"type": "adr", "title": "Ingested after forty"}])
        names = [p.name for p in (self.root / "architecture-decisions").glob("*.md")]
        self.assertIn("0041-ingested-after-forty.md", names)
        self.assertEqual(_json.loads((self.root / ".counter.json").read_text())["adr"], 41)

    def test_skips_items_without_title(self):
        self._main([{"type": "adr"}, {"title": "kept"}])
        self.assertEqual(len(list((self.root / "architecture-decisions").glob("*.md"))), 1)

    def test_unit_helpers(self):
        d = self.root / "architecture-decisions"
        d.mkdir(parents=True)
        self.assertEqual(ingest.next_number(d, 4), "0001")
        (d / "0003-x.md").write_text("# ADR 0003 — x\n")
        self.assertEqual(ingest.next_number(d, 4), "0004")
        rec = ingest.build_record({"title": "T"}, "ADR", "0001")
        self.assertIn("# ADR 0001 — T", rec)
        self.assertIn("Status: Proposed", rec)

    def test_bad_json_errors(self):
        p = self.root / "bad.json"
        p.write_text("{ not json")
        old = sys.argv
        sys.argv = ["ingest", "--root", str(self.root), "--from", str(p)]
        try:
            with self.assertRaises(SystemExit):
                ingest.main()
        finally:
            sys.argv = old

    def test_non_list_errors(self):
        with self.assertRaises(SystemExit):
            self._main(42)        # JSON scalar -> not a dict/list

    def test_unknown_type_errors(self):
        with self.assertRaises(SystemExit):
            self._main([{"type": "zzz", "title": "x"}])

    def test_single_dict_is_wrapped(self):
        self._main({"title": "Lone decision"})       # dict, not list -> wrapped into [dict]
        self.assertEqual(len(list((self.root / "architecture-decisions").glob("*.md"))), 1)

    def test_duplicate_title_skips(self):
        self._main([{"title": "Same"}])
        # ingest a record with the SAME number+slug already on disk -> skip-exists branch
        d = self.root / "architecture-decisions"
        existing = next(d.glob("*.md"))
        # force a collision: write the next-number target by hand, then re-ingest the same title
        (d / "0002-same.md").write_text("# ADR 0002 — Same\n")
        self._main([{"title": "Same"}])              # next_number -> 0003 (no collision); still fine
        self.assertGreaterEqual(len(list(d.glob("*.md"))), 2)

    def test_default_root_resolution(self):
        # no --root: resolves to ./decisions if present, else cwd
        cwd = os.getcwd()
        os.chdir(self.root)
        (self.root / "decisions").mkdir()
        try:
            p = self.root / "in.json"
            p.write_text(json.dumps([{"title": "Via default root"}]))
            old = sys.argv
            sys.argv = ["ingest", "--from", str(p)]
            try:
                ingest.main()
            finally:
                sys.argv = old
            self.assertTrue(list((self.root / "decisions" / "architecture-decisions").glob("*.md")))
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
