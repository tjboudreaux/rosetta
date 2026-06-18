"""Coverage for the decision-library HEALTH report (SPEC-03): provenance/code-anchoring (the primary,
gated signal), supersession stats, the agent-retrieval ambiguous-topics diagnostic, structural fields,
the `--min-coverage` gate, and the `resolve_query` refactor that `coverage` and `resolve` now share.
Hardened across 3 adversarial-review rounds; these tests pin every case in spec section 6.

Run: python3 -m unittest discover -s tests
"""
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import decisions          # noqa: E402


def _adr(num, title, status="Accepted", sources="", aliases=None, supersedes=None, related=None,
         body="Decision body."):
    lines = [f"# ADR {num:04d} — {title}", "", f"- Status: {status}",
             "- Date: 2026-01-01", "- Decider: Me", f"- Sources: {sources}"]
    if aliases is not None:
        lines.append(f"- Aliases: {aliases}")
    if supersedes is not None:
        lines.append(f"- Supersedes: {supersedes}")
    if related is not None:
        lines.append(f"- Related: {related}")
    lines += ["", "## Decision", "", body, ""]
    return "\n".join(lines)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "architecture-decisions").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, num, **kw):
        slug = kw.get("title", "x").lower().split(":")[0].replace(" ", "-")[:30]
        (self.root / "architecture-decisions" / f"{num:04d}-{slug}.md").write_text(_adr(num, **kw))

    def _touch(self, rel, is_dir=False):
        p = self.root / rel
        if is_dir:
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")
        return p

    def _run(self, cmd, *extra):
        old = sys.argv
        sys.argv = ["decisions", cmd, "--root", str(self.root), *extra]
        buf, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with redirect_stdout(buf), redirect_stderr(err):
                decisions.main()
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        finally:
            sys.argv = old
        raw = buf.getvalue()
        data = json.loads(raw) if raw.strip().startswith("{") else None
        return data, code, raw, err.getvalue()

    def _coverage(self, *extra):
        return self._run("coverage", *extra)

    def _resolve(self, *extra):
        data, _code, _raw, _err = self._run("resolve", *extra)
        return data


class CoverageAnchoring(_Base):
    def test_exact_relative_path_file_anchors(self):
        self._write(1, title="a", sources="scripts/real.py")
        self._touch("scripts/real.py")
        rep, code, *_ = self._coverage()
        self.assertEqual(code, 0)
        self.assertEqual(rep["anchoring"]["accepted_anchored"], 1)
        self.assertEqual(rep["anchoring"]["unanchored"], [])

    def test_basename_match_does_not_anchor(self):
        """Anchoring is by EXACT relative path, never basename: citing `b/real.py` must NOT anchor just
        because `a/real.py` exists elsewhere (the false-anchoring defect caught in review)."""
        self._write(1, title="a", sources="b/real.py")
        self._touch("a/real.py")
        rep, _code, *_ = self._coverage()
        self.assertEqual(rep["anchoring"]["accepted_anchored"], 0)
        self.assertEqual(rep["anchoring"]["unanchored"], ["ADR 0001"])

    def test_bare_directory_token_anchors(self):
        """Directory addendum (R2): a bare dir token like `Sources: scripts` that the path heuristic
        drops still anchors when it resolves to a real directory."""
        self._write(1, title="a", sources="scripts")
        self._touch("scripts", is_dir=True)
        rep, _code, *_ = self._coverage()
        self.assertEqual(rep["anchoring"]["accepted_anchored"], 1)

    def test_rate_denominator_is_accepted_and_all_is_separate(self):
        self._write(1, title="acc", status="Accepted", sources="x/f.py")
        self._write(2, title="prop", status="Proposed", sources="x/f.py")   # anchored, NOT accepted
        self._write(3, title="acc2", status="Accepted", sources="")         # accepted, unanchored
        self._touch("x/f.py")
        rep, _code, *_ = self._coverage()
        a = rep["anchoring"]
        self.assertEqual((a["accepted_anchored"], a["accepted_total"]), (1, 2))
        self.assertEqual(a["rate"], 0.5)
        self.assertEqual(a["rate_raw"], 0.5)
        self.assertEqual(a["unanchored"], ["ADR 0003"])
        self.assertEqual((a["all_anchored"], a["all_total"]), (2, 3))       # Proposed counts in all_*

    def test_repo_boundary_blocks_sibling_project_leak(self):
        """With git present, a citation that resolves OUTSIDE the repo (an unrelated sibling project)
        must NOT anchor, while an in-repo path still does."""
        if shutil.which("git") is None:
            self.skipTest("git not available")
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        self._touch("inside/real.py")
        out = tempfile.TemporaryDirectory()
        self.addCleanup(out.cleanup)
        leak = Path(out.name) / "leak.py"
        leak.write_text("x")
        self._write(1, title="in", sources="inside/real.py")
        self._write(2, title="leak", sources=str(leak))
        rep, _code, *_ = self._coverage()
        self.assertIn("ADR 0002", rep["anchoring"]["unanchored"])
        self.assertNotIn("ADR 0001", rep["anchoring"]["unanchored"])


class CoverageSignals(_Base):
    def test_supersession_distribution_and_chain_depth(self):
        """A→B→C chain plus a standalone accepted record: depth(A)=2, depth(B)=1 → max 2, mean 1.5."""
        self._write(1, title="v1", status="Superseded by ADR 0002")
        self._write(2, title="v2", status="Superseded by ADR 0003", supersedes="ADR 0001")
        self._write(3, title="v3", supersedes="ADR 0002")
        self._write(4, title="standalone")
        rep, _code, *_ = self._coverage()
        s = rep["supersession"]
        self.assertEqual(s["max_chain_depth"], 2)
        self.assertEqual(s["mean_chain_depth"], 1.5)
        self.assertEqual(s["active"], 2)               # ADR 0003 + ADR 0004
        self.assertEqual(s["retired"], 2)              # two superseded
        self.assertEqual(rep["status_distribution"]["superseded"], 2)
        self.assertEqual(rep["status_distribution"]["accepted"], 2)

    def test_retrieval_clean_library_has_no_ambiguity(self):
        self._write(1, title="alpha service")
        self._write(2, title="beta service")
        rep, _code, *_ = self._coverage()
        self.assertEqual(rep["retrieval"]["ambiguous_count"], 0)
        self.assertEqual(rep["retrieval"]["ambiguous_topics"], [])

    def test_retrieval_title_substring_collision(self):
        """`store` is a literal substring of `widget store`, so resolving the topic `store` returns two
        endpoints → reported (non-gated) with its collider."""
        self._write(1, title="store")
        self._write(2, title="widget store")
        rep, _code, *_ = self._coverage()
        topics = rep["retrieval"]["ambiguous_topics"]
        self.assertEqual(topics, [{"id": "ADR 0001", "title": "store",
                                   "collides_with": ["ADR 0002"]}])

    def test_retrieval_alias_conflict_collides_with(self):
        """When a title's text is itself a colliding ALIAS (candidates not in `endpoints`), collides_with
        is sorted((endpoints ∪ alias_conflict candidates) − self) — the precise R3 definition."""
        self._write(1, title="central topic")
        self._write(2, title="other a", aliases="central topic")
        self._write(3, title="other b", aliases="central topic")
        rep, _code, *_ = self._coverage()
        topics = {t["id"]: t for t in rep["retrieval"]["ambiguous_topics"]}
        self.assertIn("ADR 0001", topics)
        self.assertEqual(topics["ADR 0001"]["collides_with"], ["ADR 0002", "ADR 0003"])

    def test_orphans_only_unlinked_records(self):
        self._write(1, title="linked target")
        self._write(2, title="links out", related="ADR 0001")
        self._write(3, title="orphan")
        rep, _code, *_ = self._coverage()
        self.assertEqual(rep["orphans"], ["ADR 0003"])

    def test_alias_coverage_rate(self):
        self._write(1, title="a", aliases="codename one")
        self._write(2, title="b")
        self._write(3, title="c")
        rep, _code, *_ = self._coverage()
        self.assertEqual(rep["alias_coverage"]["with_aliases"], 1)
        self.assertEqual(rep["alias_coverage"]["rate"], 0.333)

    def test_staleness_skipped_without_git(self):
        self._write(1, title="a", sources="x.py")
        rep, _code, *_ = self._coverage()
        self.assertEqual(rep["staleness"], {"git": False, "skipped": True})


class CoverageGateAndContract(_Base):
    def _half_anchored(self):
        self._write(1, title="acc", sources="x/f.py")
        self._write(2, title="acc2", sources="")
        self._touch("x/f.py")

    def test_gate_fails_below_threshold(self):
        self._half_anchored()
        rep, code, *_ = self._coverage("--min-coverage", "0.9")
        self.assertEqual(code, 1)
        self.assertFalse(rep["ok"])
        self.assertEqual(len(rep["failures"]), 1)
        self.assertIn("0.5", rep["failures"][0])

    def test_gate_passes_at_or_above_threshold(self):
        self._half_anchored()
        rep, code, *_ = self._coverage("--min-coverage", "0.4")
        self.assertEqual(code, 0)
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["failures"], [])

    def test_null_rate_skips_gate_without_error(self):
        """Zero Accepted records → anchoring rate is null; the gate must SKIP (no TypeError, exit 0)."""
        self._write(1, title="prop", status="Proposed")
        rep, code, *_ = self._coverage("--min-coverage", "0.9")
        self.assertEqual(code, 0)
        self.assertTrue(rep["ok"])
        self.assertIsNone(rep["anchoring"]["rate_raw"])
        self.assertIn("notes", rep)

    def test_threshold_must_be_in_unit_interval(self):
        self._write(1, title="a")
        _rep, code_hi, _raw, _err = self._coverage("--min-coverage", "1.5")
        self.assertEqual(code_hi, 2)
        _rep2, code_lo, _raw2, _err2 = self._coverage("--min-coverage", "-0.1")
        self.assertEqual(code_lo, 2)

    def test_output_is_deterministic(self):
        self._write(1, title="store", aliases="codename one", sources="x/f.py")
        self._write(2, title="widget store")
        self._touch("x/f.py")
        _d1, _c1, raw1, _e1 = self._coverage()
        _d2, _c2, raw2, _e2 = self._coverage()
        self.assertEqual(raw1, raw2)                   # byte-identical between runs


class ResolveRefactorParity(_Base):
    """SPEC-03 R3 codex: the `resolve_query` extraction must leave `cmd_resolve`'s FULL JSON unchanged.
    `--no-stale-check` removes git variance so the entire object is asserted deterministically."""

    def test_single_literal_hit_full_json(self):
        self._write(1, title="alpha service")
        out = self._resolve("--text", "alpha", "--no-stale-check")
        self.assertEqual(out, {
            "query": "alpha",
            "current": [{"id": "ADR 0001", "title": "alpha service", "status": "Accepted",
                         "date": "2026-01-01", "reviewed": None, "baseline_date": "2026-01-01",
                         "path": "architecture-decisions/0001-alpha-service.md",
                         "aliases": "", "superseded_from": []}],
            "matched_records": 1, "conflict": False, "via_alias": [],
            "resolved_unique": True, "freshness_checked": False})

    def test_superseded_chain_replaced_and_superseded_from_full_json(self):
        self._write(1, title="store v1", status="Superseded by ADR 0002")
        self._write(2, title="store v2", supersedes="ADR 0001")
        out = self._resolve("--text", "store v1", "--no-stale-check")
        self.assertEqual(out, {
            "query": "store v1",
            "current": [{"id": "ADR 0002", "title": "store v2", "status": "Accepted",
                         "date": "2026-01-01", "reviewed": None, "baseline_date": "2026-01-01",
                         "path": "architecture-decisions/0002-store-v2.md",
                         "aliases": "", "superseded_from": ["ADR 0001"],
                         "replaced": {"id": "ADR 0001", "title": "store v1"}}],
            "matched_records": 1, "conflict": False, "via_alias": [],
            "resolved_unique": True, "freshness_checked": False})

    def test_alias_only_hit_full_json(self):
        self._write(1, title="message bus", aliases="Zephyr")
        out = self._resolve("--text", "zephyr", "--no-stale-check")
        self.assertEqual(out, {
            "query": "zephyr", "current": [], "matched_records": 0, "conflict": False,
            "via_alias": [{"id": "ADR 0001", "title": "message bus", "alias": "zephyr",
                           "target_id": "ADR 0001",
                           "path": "architecture-decisions/0001-message-bus.md"}],
            "resolved_unique": True, "freshness_checked": False})

    def test_alias_conflict_full_json(self):
        self._write(1, title="thing one", aliases="shared scope")
        self._write(2, title="thing two", aliases="shared scope")
        out = self._resolve("--text", "shared scope", "--no-stale-check")
        note = ("no current (Accepted) record matches; all matches are superseded or none found "
                "ambiguous codename(s) — an alias maps to multiple current decisions; "
                "disambiguate by scope.")
        self.assertEqual(out, {
            "query": "shared scope", "current": [], "matched_records": 0, "conflict": False,
            "via_alias": [],
            "alias_conflict": [{"alias": "shared scope", "candidates": ["ADR 0001", "ADR 0002"]}],
            "resolved_unique": False, "freshness_checked": False, "note": note})


if __name__ == "__main__":
    unittest.main()
