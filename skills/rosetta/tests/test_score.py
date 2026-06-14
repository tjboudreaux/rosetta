#!/usr/bin/env python3
"""Coverage for the deterministic (judge-independent) scorer evals/adversarial/score.py.

Authoritative scoring is via a structured ```rosetta-verdict``` block (prose regex proved unreliable —
ADR 0022); the prose heuristic is non-authoritative triage only.

Run: python3 -m unittest discover -s tests
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evals" / "adversarial"))
import score          # noqa: E402

PLANTED = {"decision_library": {
    "needle_path": "decisions/architecture-decisions/0050-persist-the-event-log-in-postgres.md",
    "distractor_paths": ["decisions/architecture-decisions/0025-use-postgres-for-the-analytics-warehouse.md"]}}


def _verdict_block(superseded, created=True, untouched=True, store="duckdb"):
    return ('```rosetta-verdict\n{"superseded_adr": "%s", "created_superseding_adr": %s, '
            '"near_miss_untouched": %s, "current_store": "%s"}\n```'
            % (superseded, str(created).lower(), str(untouched).lower(), store))


class StructuredScoring(unittest.TestCase):
    def test_correct_verdict_passes(self):
        text = "…prose…\n" + _verdict_block("ADR 0050")
        v = score.score_supersession(text, PLANTED)
        self.assertEqual(v["method"], "structured")
        self.assertTrue(v["passed"])

    def test_wrong_adr_fails(self):
        v = score.score_supersession(_verdict_block("ADR 0025"), PLANTED)   # the near-miss
        self.assertFalse(v["passed"])
        self.assertFalse(v["checks"]["superseded_correct_adr"])

    def test_near_miss_touched_fails(self):
        v = score.score_supersession(_verdict_block("ADR 0050", untouched=False), PLANTED)
        self.assertFalse(v["passed"])

    def test_postgres_store_fails(self):
        v = score.score_supersession(_verdict_block("ADR 0050", store="postgres"), PLANTED)
        self.assertFalse(v["passed"])

    def test_truthy_string_does_not_game_booleans(self):
        # a JSON string "false" is truthy in Python — strict typing must NOT let it pass (ADR 0023)
        block = ('```rosetta-verdict\n{"superseded_adr": "ADR 0050", "created_superseding_adr": "true", '
                 '"near_miss_untouched": "false", "current_store": "duckdb"}\n```')
        v = score.score_supersession(block, PLANTED)
        self.assertFalse(v["passed"])
        self.assertFalse(v["checks"]["left_near_miss_untouched"])   # "false" string rejected
        self.assertFalse(v["checks"]["created_superseding_adr"])    # "true" string rejected

    def test_no_block_is_not_scorable(self):
        v = score.score_supersession("free-form prose with no verdict block", PLANTED)
        self.assertFalse(v.get("scorable"))
        self.assertEqual(v["method"], "none")

    def test_already_recorded_structured(self):
        planted = {"decision_library": {
            "needle_path": "decisions/architecture-decisions/0004-rate-limit.md", "distractor_paths": []}}
        good = '```rosetta-verdict\n{"already_recorded_adr": "ADR 0004", "created_new_adr": false}\n```'
        self.assertTrue(score.score_already_recorded(good, planted)["passed"])
        bad = '```rosetta-verdict\n{"already_recorded_adr": "ADR 0004", "created_new_adr": true}\n```'
        self.assertFalse(score.score_already_recorded(bad, planted)["passed"])


class HeuristicFallback(unittest.TestCase):
    """The prose heuristic is best-effort triage only — never authoritative."""
    def test_heuristic_flagged_non_authoritative(self):
        text = ("Event log now on columnar DuckDB; supersede ADR 0050 (event log in Postgres); "
                "ADR 0025 (warehouse) left untouched.")
        v = score.score_supersession(text, PLANTED, heuristic=True)
        self.assertEqual(v["method"], "heuristic-best-effort")
        self.assertFalse(v["authoritative"])
        self.assertTrue(v["passed"])

    def test_heuristic_handles_newline_spanning_supersede(self):
        # the real-output failure mode: "ADR 0050 …title…\nSuperseded by ADR 0101"
        text = ("## ADR 0050 — Persist the event log in Postgres\n\n"
                "Status Change: Accepted -> Superseded by ADR 0101. Event log now uses a columnar "
                "DuckDB store. ADR 0025 (warehouse) is a different subsystem, left untouched.")
        v = score.score_supersession(text, PLANTED, heuristic=True)
        self.assertTrue(v["checks"]["superseded_correct_adr"])     # newline-spanning bind found
        self.assertTrue(v["checks"]["left_near_miss_untouched"])   # 0025 negated → not touched

    def test_heuristic_not_fooled_by_migrated_from_postgres(self):
        text = ("Migrated the event log from Postgres to DuckDB. ## ADR 0050\nSuperseded by ADR 0101. "
                "columnar store now. ADR 0025 unrelated, untouched.")
        v = score.score_supersession(text, PLANTED, heuristic=True)
        self.assertTrue(v["checks"]["did_not_assert_postgres_current"])   # 'from Postgres' != current


class ScoreApi(unittest.TestCase):
    def test_score_rebuilds_fixture_and_resolves_needle(self):
        v = score.score("decision-supersession-lookup-5", _verdict_block("ADR 0002"))
        self.assertEqual(v["needle_adr"], 2)
        self.assertTrue(v["passed"])

    def test_unknown_scenario_raises(self):
        with self.assertRaises(SystemExit):
            score.score("not-a-decision-scenario", "x")

    def test_fixture_for_unknown_scenario_raises(self):
        with self.assertRaises(SystemExit):
            score.fixture_for("no-such-scenario-id")

    def test_main_cli_structured_pass(self):
        import io
        import tempfile
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "gt.md"
            f.write_text("prose\n" + _verdict_block("ADR 0002"))
            old = sys.argv
            sys.argv = ["score", "--scenario", "decision-supersession-lookup-5", "--solver-output", str(f)]
            try:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = score.main()
            finally:
                sys.argv = old
            self.assertEqual(rc, 0)
            self.assertIn('"passed": true', buf.getvalue())

    def test_main_cli_no_block_routes_to_judge(self):
        import io
        import tempfile
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "gt.md"
            f.write_text("prose only, no verdict block")
            old = sys.argv
            sys.argv = ["score", "--scenario", "decision-supersession-lookup-5", "--solver-output", str(f)]
            try:
                with redirect_stdout(io.StringIO()):
                    rc = score.main()
            finally:
                sys.argv = old
            self.assertEqual(rc, 2)        # not scorable → route to LLM judge


if __name__ == "__main__":
    unittest.main(verbosity=2)
