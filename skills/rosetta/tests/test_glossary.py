#!/usr/bin/env python3
"""Coverage for the alias / glossary resolution layer (SPEC-04): deterministic codename resolution via
Direct Record Mapping, literal-vs-alias signal split (`conflict` stays literal-only; `resolved_unique`
is the union-aware flag), hard-error collisions/invalid-chains in `validate`, and the GLOSSARY.* index
artifacts. Hardened across 4 adversarial-review rounds; these tests pin every case in spec section 6.

Run: python3 -m unittest discover -s tests
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import decisions          # noqa: E402


def _adr(num, title, status="Accepted", aliases=None, supersedes=None, body="Decision body."):
    lines = [f"# ADR {num:04d} — {title}", "", f"- Status: {status}",
             "- Date: 2026-01-01", "- Decider: Me", "- Sources: x"]
    if aliases is not None:
        lines.append(f"- Aliases: {aliases}")
    if supersedes is not None:
        lines.append(f"- Supersedes: {supersedes}")
    lines += ["", "## Decision", "", body, ""]
    return "\n".join(lines)


class GlossaryHelpers(unittest.TestCase):
    """Pure-function behavior: normalization, field parsing, the empty-alias guard, query matching."""

    def test_normalize_collapses_only_separators(self):
        n = decisions.normalize_alias
        self.assertEqual(n("Project-Meridian"), "project meridian")
        self.assertEqual(n("project_meridian"), "project meridian")
        self.assertEqual(n("  Project   Meridian "), "project meridian")
        # everything else is preserved verbatim, so these stay DISTINCT (no false collisions)
        self.assertNotEqual(n("C++"), n("C#"))
        self.assertNotEqual(n("C++"), n(".NET"))
        self.assertEqual(n("C++"), "c++")

    def test_parse_alias_field_drops_empty_and_dedupes(self):
        p = decisions.parse_alias_field
        self.assertEqual(p("Zephyr; Project Meridian"), ["zephyr", "project meridian"])
        self.assertEqual(p("foo;;bar"), ["foo", "bar"])          # blank middle segment dropped
        self.assertEqual(p(" - ; / ; ___ "), [])                # separator-only segments → nothing
        self.assertEqual(p(""), [])
        self.assertEqual(p("Dup; dup ; DUP"), ["dup"])          # case-insensitive de-dup

    def test_find_query_aliases_longest_then_leftmost(self):
        amap = {"a b": ["ADR 0001"], "b c": ["ADR 0002"], "b": ["ADR 0003"]}
        # "a b c": longest-leftmost picks "a b" at pos 0, consuming b → "b c"/"b" cannot reuse it
        self.assertEqual(decisions.find_query_aliases("a b c", amap, set()), ["a b"])

    def test_stoplist_suppresses_single_token_only(self):
        amap = {"api": ["ADR 0001"], "api gateway": ["ADR 0002"]}
        stop = {"api"}
        # bare "api" suppressed; the multi-word "api gateway" is NOT suppressed
        self.assertEqual(decisions.find_query_aliases("api", amap, stop), [])
        self.assertEqual(decisions.find_query_aliases("api gateway", amap, stop), ["api gateway"])

    def test_two_letter_acronym_not_suppressed_by_default(self):
        amap = {"qd": ["ADR 0001"]}
        self.assertEqual(decisions.find_query_aliases("qd", amap, set()), ["qd"])


class GlossaryResolve(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "architecture-decisions").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, num, **kw):
        slug = kw.get("title", "x").lower().split(":")[0].replace(" ", "-")[:30]
        (self.root / "architecture-decisions" / f"{num:04d}-{slug}.md").write_text(_adr(num, **kw))

    def _resolve(self, *extra):
        old = sys.argv
        sys.argv = ["decisions", "resolve", "--root", str(self.root), *extra]
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                decisions.main()
        finally:
            sys.argv = old
        return json.loads(buf.getvalue())

    def test_golden_regression_alias_free_library(self):
        """An alias-free library resolves EXACTLY as before; the new keys are additive."""
        self._write(1, title="widget store: Spanner")
        res = self._resolve("--text", "widget store")
        self.assertEqual([c["id"] for c in res["current"]], ["ADR 0001"])
        self.assertFalse(res["conflict"])
        self.assertEqual(res["via_alias"], [])           # additive, empty
        self.assertTrue(res["resolved_unique"])          # exactly one endpoint

    def test_alias_field_text_excluded_from_literal_haystack(self):
        """A codename that lives ONLY in the Aliases field must NOT match literally — only via the map."""
        self._write(1, title="message bus: Kafka", aliases="Zephyr")
        res = self._resolve("--text", "zephyr")
        self.assertEqual(res["current"], [])             # no literal match (alias field excluded)
        self.assertEqual([v["id"] for v in res["via_alias"]], ["ADR 0001"])
        self.assertEqual(res["via_alias"][0]["alias"], "zephyr")
        self.assertTrue(res["resolved_unique"])

    def test_body_prose_mention_still_matches_literally(self):
        """The same codename in BOTH Aliases and the body still matches literally via the body prose."""
        self._write(1, title="message bus", aliases="Zephyr", body="Internally we call this Zephyr.")
        res = self._resolve("--text", "zephyr")
        self.assertEqual([c["id"] for c in res["current"]], ["ADR 0001"])   # literal (body) hit
        self.assertEqual(res["via_alias"], [])           # deduped against current
        self.assertTrue(res["resolved_unique"])

    def test_alias_resolves_through_supersession_chain(self):
        """An alias on a SUPERSEDED record resolves to its current endpoint (chain collapse, no conflict)."""
        self._write(1, title="store v1", status="Superseded by ADR 0002", aliases="Meridian")
        self._write(2, title="store v2", supersedes="ADR 0001")
        res = self._resolve("--text", "meridian")
        self.assertEqual([v["id"] for v in res["via_alias"]], ["ADR 0002"])
        self.assertTrue(res["resolved_unique"])

    def test_disjoint_literal_and_alias_breaks_resolved_unique_not_conflict(self):
        """The Option-A case: one literal hit + one DIFFERENT alias target → conflict stays False but
        resolved_unique is False (the ambiguity literal `conflict` cannot see)."""
        self._write(1, title="payment gateway: Adyen")          # literal match on "payment"
        self._write(2, title="billing system", aliases="payment", body="Use Stripe.")
        res = self._resolve("--text", "payment")
        self.assertEqual([c["id"] for c in res["current"]], ["ADR 0001"])
        self.assertEqual([v["id"] for v in res["via_alias"]], ["ADR 0002"])
        self.assertFalse(res["conflict"])                # literal-only: a single literal hit
        self.assertFalse(res["resolved_unique"])         # but union has TWO endpoints

    def test_ambiguous_alias_reports_alias_conflict(self):
        """One alias mapping to two distinct current decisions → alias_conflict (NOT `conflict`),
        resolved_unique False, nothing injected into via_alias."""
        self._write(1, title="thing one", aliases="shared")
        self._write(2, title="thing two", aliases="shared")
        res = self._resolve("--text", "shared")
        self.assertFalse(res["conflict"])                # literal-only signal is clean
        self.assertEqual(res["via_alias"], [])
        self.assertEqual(res["alias_conflict"][0]["alias"], "shared")
        self.assertEqual(sorted(res["alias_conflict"][0]["candidates"]), ["ADR 0001", "ADR 0002"])
        self.assertFalse(res["resolved_unique"])

    def test_multi_alias_union_and_deterministic_order(self):
        self._write(1, title="concept A", aliases="alpha")
        self._write(2, title="concept B", aliases="beta")
        res = self._resolve("--text", "beta alpha")      # query order beta-then-alpha
        # via_alias is sorted by (id, alias) for determinism, regardless of query order
        self.assertEqual([v["id"] for v in res["via_alias"]], ["ADR 0001", "ADR 0002"])
        self.assertFalse(res["resolved_unique"])         # two distinct endpoints

    def test_no_alias_expand_disables_layer(self):
        self._write(1, title="message bus", aliases="Zephyr")
        res = self._resolve("--text", "zephyr", "--no-alias-expand")
        self.assertNotIn("via_alias", res)
        self.assertNotIn("alias_conflict", res)
        self.assertIn("resolved_unique", res)            # literal-only safety flag still present
        self.assertEqual(res["current"], [])
        self.assertFalse(res["resolved_unique"])

    def test_type_scoping_resolves_within_type(self):
        """resolve ambiguity is --type-scoped: a cross-type alias collision resolves uniquely per type."""
        (self.root / "product-decisions").mkdir(parents=True, exist_ok=True)
        (self.root / "architecture-decisions" / "0001-a.md").write_text(_adr(1, title="arch thing", aliases="shared"))
        (self.root / "product-decisions" / "0001-p.md").write_text(
            _adr(1, title="prod thing", aliases="shared").replace("ADR", "PDR"))
        scoped = self._resolve("--text", "shared", "--type", "adr")
        self.assertEqual([v["id"] for v in scoped["via_alias"]], ["ADR 0001"])
        self.assertTrue(scoped["resolved_unique"])       # unambiguous within the type
        unscoped = self._resolve("--text", "shared")
        self.assertTrue(unscoped["alias_conflict"])      # globally still ambiguous
        self.assertFalse(unscoped["resolved_unique"])

    def test_empty_alias_line_contributes_nothing(self):
        self._write(1, title="thing", aliases="")        # blank template line
        res = self._resolve("--text", "thing")
        self.assertEqual([c["id"] for c in res["current"]], ["ADR 0001"])
        self.assertEqual(res["via_alias"], [])
        self.assertTrue(res["resolved_unique"])


class GlossaryMapAndChains(unittest.TestCase):
    """build_alias_map: chain collapse vs forked/mismatched chains, C-family non-collapse."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.d = self.root / "architecture-decisions"
        self.d.mkdir(parents=True)
        self.cfg = decisions.load_config(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def _w(self, num, **kw):
        (self.d / f"{num:04d}-x.md").write_text(_adr(num, **kw))

    def _map(self):
        return decisions.build_alias_map(decisions.collect_records(self.root, self.cfg), self.cfg)

    def test_converging_chain_is_not_a_collision(self):
        """A→C and B→C: the SAME alias on both predecessors collapses to one endpoint C (not a collision)."""
        self._w(1, title="a", status="Superseded by ADR 0003", aliases="omega")
        self._w(2, title="b", status="Superseded by ADR 0003", aliases="omega")
        self._w(3, title="c", supersedes="ADR 0001")
        m = self._map()
        self.assertEqual(m["map"]["omega"], ["ADR 0003"])
        self.assertEqual(m["collisions"], {})

    def test_c_family_aliases_do_not_collapse(self):
        """`C++`, `C#`, `.NET` normalize distinctly → three separate aliases, NOT one colliding `c`."""
        self._w(1, title="cpp", aliases="C++")
        self._w(2, title="csharp", aliases="C#")
        self._w(3, title="dotnet", aliases=".NET")
        m = self._map()
        self.assertEqual(m["collisions"], {})
        self.assertEqual(set(m["map"]), {"c++", "c#", ".net"})

    def test_forked_chain_is_invalid(self):
        """A record superseded by TWO distinct records cannot collapse → invalid (alias dropped)."""
        self._w(1, title="a", status="Superseded by ADR 0002", aliases="forky")
        self._w(2, title="b", supersedes="ADR 0001")
        self._w(3, title="c", supersedes="ADR 0001")     # second superseder → fork
        m = self._map()
        self.assertIn("ADR 0001", m["invalid_chains"])
        self.assertIn("forked", m["invalid_chains"]["ADR 0001"])
        self.assertIn("forky", m["invalid_aliases"])
        self.assertNotIn("forky", m["map"])              # not resolvable

    def test_mismatched_back_link_is_invalid(self):
        """X says 'Superseded by Y' but Y's Supersedes names someone else → contradiction (invalid)."""
        self._w(1, title="a", status="Superseded by ADR 0002", aliases="mis")
        self._w(2, title="b", supersedes="ADR 0009")     # claims to supersede a DIFFERENT record
        self._w(9, title="i")
        m = self._map()
        self.assertIn("ADR 0001", m["invalid_chains"])
        self.assertNotIn("mis", m["map"])


class GlossaryValidateAndIndex(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.d = self.root / "architecture-decisions"
        self.d.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, *args):
        old = sys.argv
        sys.argv = ["decisions", *args]
        try:
            decisions.main()
        finally:
            sys.argv = old

    def _w(self, num, **kw):
        (self.d / f"{num:04d}-x.md").write_text(_adr(num, **kw))

    def test_collision_is_hard_validate_error_without_strict(self):
        self._w(1, title="thing one", aliases="shared")
        self._w(2, title="thing two", aliases="shared")
        with self.assertRaises(SystemExit):
            self._main("validate", "--root", str(self.root))      # NOT --strict

    def test_clean_aliases_validate_ok(self):
        self._w(1, title="thing one", aliases="alpha")
        self._w(2, title="thing two", aliases="beta")
        self._main("validate", "--root", str(self.root))          # must not raise

    def test_forked_alias_chain_is_validate_error(self):
        self._w(1, title="a", status="Superseded by ADR 0002", aliases="forky")
        self._w(2, title="b", supersedes="ADR 0001")
        self._w(3, title="c", supersedes="ADR 0001")
        with self.assertRaises(SystemExit):
            self._main("validate", "--root", str(self.root))

    def test_index_emits_sorted_glossary_artifacts(self):
        self._w(1, title="concept B", aliases="beta")
        self._w(2, title="concept A", aliases="alpha")
        self._main("index", "--root", str(self.root))
        gjson = json.loads((self.root / "GLOSSARY.json").read_text())
        self.assertEqual(list(gjson["aliases"]), ["alpha", "beta"])   # deterministically sorted
        self.assertEqual(gjson["aliases"]["alpha"][0]["id"], "ADR 0002")
        self.assertEqual(gjson["_alias_conflicts"], [])
        self.assertEqual(gjson["_invalid_chains"], [])
        md = (self.root / "GLOSSARY.md").read_text()
        self.assertIn("| alpha |", md)
        self.assertIn("Do not edit by hand", md)

    def test_index_surfaces_collisions_in_artifact_and_stderr(self):
        self._w(1, title="thing one", aliases="shared")
        self._w(2, title="thing two", aliases="shared")
        buf = io.StringIO()
        with redirect_stderr(buf):
            self._main("index", "--root", str(self.root))             # index does not fail (exit 0)
        self.assertIn("ambiguous", buf.getvalue().lower())
        gjson = json.loads((self.root / "GLOSSARY.json").read_text())
        self.assertEqual(gjson["_alias_conflicts"][0]["alias"], "shared")


if __name__ == "__main__":
    unittest.main(verbosity=2)
