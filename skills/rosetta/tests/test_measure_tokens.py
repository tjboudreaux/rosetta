#!/usr/bin/env python3
"""Tests for the GOAL-3 token-reduction measurement harness + discrimination guardrail.

These lock in the two claims the GOAL3 results doc makes:
  1. measure_tokens.py produces a real before/after where resolve << raw and det-score == 0 model tok,
     clearing the >75% gate on the resolvable+scorable core.
  2. The deterministic scorer + resolver still DISCRIMINATE — they pass a correct verdict / return the
     right record, and fail/separate a wrong one. (A "cheaper" path that lost discrimination would be
     a regression, per the falsifier in TOKEN-REDUCTION-HYPOTHESES.md.)
"""
import sys
import unittest
from pathlib import Path

ADV = Path(__file__).resolve().parents[1] / "evals" / "adversarial"
sys.path.insert(0, str(ADV))

import measure_tokens  # noqa: E402
import score  # noqa: E402


class TestMeasureH1(unittest.TestCase):
    def test_resolve_beats_raw_over_75pct(self):
        # the 100-record scorable core: resolve must cut >75% of the raw-read tokens
        r = measure_tokens.measure_h1("decision-supersession-lookup-100")
        self.assertGreater(r["raw_read_tokens"], r["resolve_tokens"])
        self.assertGreater(r["reduction_pct"], 75.0)
        self.assertEqual(r["records"], 100)

    def test_reduction_grows_with_library_size(self):
        small = measure_tokens.measure_h1("decision-supersession-lookup-25")
        big = measure_tokens.measure_h1("decision-supersession-lookup-250")
        # resolve cost is ~constant; raw cost grows with N, so reduction% increases
        self.assertGreater(big["reduction_pct"], small["reduction_pct"])


class TestMeasureH2(unittest.TestCase):
    def test_det_score_eliminates_judge_tokens(self):
        r = measure_tokens.measure_h2("decision-supersession-lookup-100")
        self.assertGreater(r["llm_judge_tokens"], 0)
        self.assertEqual(r["deterministic_score_model_tokens"], 0)
        self.assertEqual(r["reduction_pct"], 100.0)


class TestMeasureH3(unittest.TestCase):
    def test_caching_cuts_repeated_prefix_input(self):
        r = measure_tokens.measure_h3("decision-supersession-lookup-100", k=3,
                                      models_same_provider=3)
        self.assertLess(r["cached_input_tokens"], r["uncached_input_tokens"])
        self.assertGreater(r["reduction_pct"], 50.0)


class TestDiscriminationGuardrail(unittest.TestCase):
    """The token-reduced path must still separate right from wrong."""

    CORRECT = ('I superseded ADR 0050.\n'
               '```rosetta-verdict {"superseded_adr": "ADR 0050", "created_superseding_adr": true, '
               '"near_miss_untouched": true, "current_store": "duckdb"}```')
    WRONG = ('The event log still uses Postgres.\n'
             '```rosetta-verdict {"superseded_adr": "ADR 0025", "created_superseding_adr": false, '
             '"near_miss_untouched": false, "current_store": "postgres"}```')

    def test_deterministic_scorer_discriminates(self):
        good = score.score("decision-supersession-lookup-100", self.CORRECT)
        bad = score.score("decision-supersession-lookup-100", self.WRONG)
        self.assertTrue(good["passed"], "correct verdict must pass")
        self.assertFalse(bad["passed"], "wrong verdict must fail — discrimination preserved")

    def test_scorer_is_structured_not_prose(self):
        # both use the authoritative structured path (judge-independent), not the prose heuristic
        good = score.score("decision-supersession-lookup-100", self.CORRECT)
        self.assertEqual(good["method"], "structured")


if __name__ == "__main__":
    unittest.main()
