#!/usr/bin/env python3
"""Unit coverage for collect.py's pure helpers and the schema-tolerant parsers, including the
malformed-input / fallback branches (count-and-skip, never crash). Pure stdlib.

Run: python3 -m unittest discover -s tests
"""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import collect          # noqa: E402


class Helpers(unittest.TestCase):
    def test_to_utc_iso_forms(self):
        self.assertIsNone(collect.to_utc_iso(None))
        self.assertIsNone(collect.to_utc_iso(""))
        self.assertIsNone(collect.to_utc_iso("not-a-date"))
        self.assertTrue(collect.to_utc_iso(1765352935).startswith("20"))     # epoch seconds
        self.assertTrue(collect.to_utc_iso(1765352935842).startswith("20"))  # epoch ms
        self.assertTrue(collect.to_utc_iso("1765352935").startswith("20"))   # numeric string
        self.assertIn("+00:00", collect.to_utc_iso("2026-06-08T00:00:00Z"))  # Z -> utc
        self.assertIn("+00:00", collect.to_utc_iso("2026-06-08T00:00:00"))   # naive -> utc

    def test_first_ts_nested_payload(self):
        self.assertTrue(collect.first_ts({"payload": {"timestamp": "2026-06-08T00:00:00Z"}}))
        self.assertIsNone(collect.first_ts({"nope": 1}))

    def test_blocks_to_text_variants(self):
        self.assertEqual(collect.blocks_to_text("hi", 100), "hi")
        self.assertEqual(collect.blocks_to_text(None, 100), "")
        self.assertEqual(collect.blocks_to_text({"type": "text", "text": "d"}, 100), "d")
        self.assertEqual(collect.blocks_to_text(123, 100), "123")            # non-list/str/dict
        blocks = [{"type": "text", "text": "a"},
                  {"type": "tool_use", "name": "grep", "input": {"q": "x"}},
                  {"type": "tool_result", "content": [{"type": "text", "text": "r"}]},
                  {"type": "thinking", "thinking": "hmm"},
                  "bare-string",
                  {"text": "fallback"}]
        out = collect.blocks_to_text(blocks, 1000)
        for frag in ("a", "[tool_use: grep]", "[tool_result]", "[thinking] hmm", "bare-string", "fallback"):
            self.assertIn(frag, out)
        self.assertIn("truncated", collect.blocks_to_text([{"type": "text", "text": "y" * 100}], 10))

    def test_normalize_role(self):
        self.assertIsNone(collect.normalize_role(None))
        self.assertEqual(collect.normalize_role("Human"), "user")
        self.assertEqual(collect.normalize_role("gemini"), "assistant")
        self.assertEqual(collect.normalize_role("model"), "assistant")
        self.assertEqual(collect.normalize_role("assistant"), "assistant")

    def test_cwd_matches(self):
        self.assertFalse(collect.cwd_matches(None, "/p", False))
        self.assertTrue(collect.cwd_matches("/p/", "/p", False))             # trailing slash
        self.assertFalse(collect.cwd_matches("/p/sub", "/p", False))
        self.assertTrue(collect.cwd_matches("/p/sub", "/p", True))           # include_subdirs

    def test_slug_and_enc(self):
        self.assertEqual(collect.slugify("a/b c"), "a_b_c")
        self.assertTrue(collect.enc_path("/a/b"))
        self.assertTrue(collect.cursor_enc("/a/b"))

    def test_probe_and_mentions_missing_file(self):
        self.assertIsNone(collect.probe_cwd("/no/such/file"))
        self.assertFalse(collect.file_mentions_path("/no/such/file", "x"))
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            fh.write(json.dumps({"cwd": "/proj/x"}))
            name = fh.name
        self.assertEqual(collect.probe_cwd(name), "/proj/x")
        self.assertTrue(collect.file_mentions_path(name, "/proj/x"))

    def test_mtime_range_empty(self):
        self.assertEqual(collect._mtime_range([]), [None, None])


class Parsers(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _f(self, name, text):
        p = self.d / name
        p.write_text(text)
        return p

    def test_default_jsonl_with_garbage(self):
        p = self._f("s.jsonl", "\n".join([
            json.dumps({"role": "user", "content": "hi"}),
            "{ not json",                                   # skipped
            json.dumps({"role": "assistant", "content": [{"type": "text", "text": "yo"}]}),
            json.dumps(["not", "a", "dict"]),               # skipped (not dict)
        ]) + "\n")
        data = collect.parse_default({"path": p}, 4000)
        self.assertEqual(data["kept"], 2)
        self.assertGreaterEqual(data["skipped"], 2)

    def test_default_whole_doc_messages(self):
        p = self._f("h.json", json.dumps({"session_start": "2026-06-08T00:00:00Z",
                                          "last_updated": "2026-06-08T00:01:00Z",
                                          "messages": [{"role": "user", "content": "hi"}]}))
        data = collect.parse_default({"path": p}, 4000)
        self.assertEqual(data["kept"], 1)
        self.assertTrue(data["first_ts"])

    def test_gemini_seed_and_lines(self):
        p = self._f("g.jsonl", "\n".join([
            json.dumps({"sessionId": "x"}),
            "garbage",
            json.dumps({"$set": {"messages": [{"type": "user", "content": [{"text": "hi"}]}]}}),
            json.dumps({"type": "gemini", "content": "yo", "timestamp": "2026-06-08T00:00:00Z"}),
        ]) + "\n")
        data = collect.parse_gemini({"path": p}, 4000)
        self.assertEqual(data["kept"], 2)

    def test_opencode_dir_sorted_and_malformed(self):
        (self.d / "msg_2.json").write_text(json.dumps({"role": "assistant", "time": {"created": 200},
                                                       "summary": {"body": "second"}}))
        (self.d / "msg_1.json").write_text(json.dumps({"role": "user", "time": {"created": 100},
                                                       "parts": [{"text": "first"}]}))
        (self.d / "bad.json").write_text("{oops")
        data = collect.parse_opencode({"path": self.d}, 4000)
        self.assertEqual(data["kept"], 2)
        self.assertEqual(data["messages"][0]["text"], "first")   # sorted by time.created
        self.assertGreaterEqual(data["skipped"], 1)

    def test_continue_timeline_and_bad_file(self):
        p = self._f("c.json", json.dumps({"history": {"timeline": [
            {"observation": {"user_input": "hi"}, "step": {"name": "User Input"}},
            {"step": {"name": "Edit", "description": "did a thing"}},
        ]}}))
        data = collect.parse_continue({"path": p}, 4000)
        self.assertEqual(data["kept"], 2)
        self.assertEqual(collect.parse_continue({"path": self.d / "missing.json"}, 4000)["skipped"], 1)

    def test_aider_markdown_and_missing(self):
        p = self._f("a.md", "# aider chat started at 2026-06-08\n\n#### hello\n\nan answer\n\n> echo line\n")
        data = collect.parse_aider({"path": p}, 4000)
        self.assertEqual(data["kept"], 2)
        self.assertEqual(collect.parse_aider({"path": self.d / "missing.md"}, 4000)["skipped"], 1)

    def test_crush_sqlite_and_missing_db(self):
        db = self.d / "c.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE messages (id TEXT, session_id TEXT, role TEXT, parts TEXT, created_at INTEGER)")
        con.executemany("INSERT INTO messages VALUES (?,?,?,?,?)",
                        [("m1", "s1", "user", "hi", 1), ("m2", "s1", "assistant", "yo", 2),
                         ("m3", "s1", "tool", "ignored", 3)])
        con.commit(); con.close()
        data = collect.parse_crush({"db": str(db), "session_id": "s1"}, 4000)
        self.assertEqual(data["kept"], 2)
        # missing db -> exception path, logged, empty session (no crash)
        miss = collect.parse_crush({"db": str(self.d / "nope.db"), "session_id": "s1"}, 4000)
        self.assertEqual(miss["kept"], 0)


class ParserSkipBranches(unittest.TestCase):
    """Exercise the count-and-skip branches: non-dict records, non-conversational roles, empty text."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _f(self, name, text):
        p = self.d / name
        p.write_text(text)
        return p

    def test_collect_session_response_item_and_skips(self):
        p = self._f("s.jsonl", "\n".join([
            json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user",
                                                             "content": [{"type": "input_text", "text": "hi"}]}}),
            json.dumps({"role": "system", "content": "ignored"}),         # role not user/assistant
            json.dumps({"role": "assistant", "content": "   "}),          # empty after strip
            json.dumps({"no": "recognizable shape"}),                     # falls through -> skipped
        ]) + "\n")
        data = collect.parse_default({"path": p}, 4000)
        self.assertEqual(data["kept"], 1)
        self.assertGreaterEqual(data["skipped"], 3)

    def test_gemini_skip_branches(self):
        p = self._f("g.jsonl", "\n".join([
            json.dumps({"$set": {"messages": ["not-a-dict", {"type": "system", "content": [{"text": "x"}]},
                                              {"type": "user", "content": [{"text": "   "}]}]}}),
            json.dumps({"type": "user", "content": [{"text": "real"}], "timestamp": "2026-06-08T00:00:00Z"}),
        ]) + "\n")
        data = collect.parse_gemini({"path": p}, 4000)
        self.assertEqual(data["kept"], 1)
        self.assertGreaterEqual(data["skipped"], 3)

    def test_opencode_skip_branches(self):
        (self.d / "msg_1.json").write_text(json.dumps({"role": "system", "time": {"created": 1},
                                                       "summary": {"body": "ignored"}}))
        (self.d / "msg_2.json").write_text(json.dumps({"role": "user", "time": {"created": 2},
                                                       "summary": {"body": "   "}}))
        (self.d / "msg_3.json").write_text(json.dumps({"role": "assistant", "time": {"created": 3},
                                                       "summary": {"body": "kept"}}))
        data = collect.parse_opencode({"path": self.d}, 4000)
        self.assertEqual(data["kept"], 1)
        self.assertGreaterEqual(data["skipped"], 2)

    def test_continue_messages_format_and_dup(self):
        p = self._f("c.json", json.dumps({"messages": [
            {"role": "user", "content": "hi"},
            {"role": "user", "content": "hi"},          # dup -> skipped
            {"role": "tool", "content": "x"},           # role skip
            {"role": "assistant", "content": "yo"},
        ]}))
        data = collect.parse_continue({"path": p}, 4000)
        self.assertEqual(data["kept"], 2)
        self.assertGreaterEqual(data["skipped"], 2)

    def test_crush_json_encoded_parts_and_empty(self):
        db = self.d / "c.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE messages (id TEXT, session_id TEXT, role TEXT, parts TEXT, created_at INTEGER)")
        con.executemany("INSERT INTO messages VALUES (?,?,?,?,?)", [
            ("m1", "s1", "user", json.dumps([{"type": "text", "text": "from json parts"}]), 1),
            ("m2", "s1", "assistant", "", 2),            # empty -> skipped
        ])
        con.commit(); con.close()
        data = collect.parse_crush({"db": str(db), "session_id": "s1"}, 4000)
        self.assertEqual(data["kept"], 1)
        self.assertIn("from json parts", data["messages"][0]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
