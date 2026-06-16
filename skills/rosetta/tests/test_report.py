#!/usr/bin/env python3
"""Coverage for the eval report renderer (evals/adversarial/report.py): scorecard math, the
scenario×run matrix, drift-curve SVG, discrimination across runs, schema rejection, and the
end-to-end main() that writes REPORT.md + drift.svg + HTML. Pure stdlib, deterministic.

Run: python3 -m unittest discover -s tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "evals" / "adversarial"))
import report          # noqa: E402


def _doc(runs):
    return {"schema": "rosetta-eval-results/v1", "runs": runs}


def _run(tier, model, scenarios):
    return {"tier": tier, "model": model, "scenarios": scenarios}


def _s(sid, status, drift=None, ap=None):
    return {"id": sid, "status": status, "drift_size": drift, "anti_pattern": ap}


class ReportRenderer(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, doc):
        p = self.dir / name
        p.write_text(json.dumps(doc))
        return str(p)

    def test_rejects_bad_schema(self):
        p = self.dir / "bad.json"
        p.write_text(json.dumps({"schema": "nope", "runs": []}))
        with self.assertRaises(SystemExit):
            report.load_runs([str(p)])

    def test_scorecard_rate(self):
        run = _run("A", "deterministic", [_s("a", "pass"), _s("b", "fail"), _s("c", "skipped")])
        # pass-rate ignores skipped: 1 of 2 completed = 50%
        passed, done, rate = report._rate(run)
        self.assertEqual((passed, done), (1, 2))
        self.assertAlmostEqual(rate, 50.0)
        md = report.scorecard_md([run])
        self.assertIn("1/2", md)
        self.assertIn("50%", md)

    def test_drift_svg_has_series_and_points(self):
        runs = [
            _run("B", "opus", [_s("d5", "pass", 5), _s("d25", "pass", 25), _s("d100", "pass", 100)]),
            _run("B", "haiku", [_s("d5", "pass", 5), _s("d25", "fail", 25), _s("d100", "fail", 100)]),
        ]
        svg = report.drift_svg(runs)
        self.assertIsNotNone(svg)
        self.assertEqual(svg.count("<polyline"), 2)          # one series per run
        self.assertIn("N=5", svg)
        self.assertIn("N=100", svg)
        self.assertIn("opus", svg)
        self.assertIn("haiku", svg)

    def test_drift_svg_none_without_drift(self):
        self.assertIsNone(report.drift_svg([_run("A", "x", [_s("a", "pass")])]))

    def test_matrix_and_discrimination(self):
        runs = [
            _run("B", "opus", [_s("x", "pass"), _s("y", "pass")]),
            _run("B", "haiku", [_s("x", "pass"), _s("y", "fail")]),
        ]
        matrix = report.matrix_md(runs)
        self.assertIn("opus", matrix)
        self.assertIn("haiku", matrix)
        self.assertIn("✓", matrix)
        self.assertIn("✗", matrix)
        disc = report.discrimination_md(runs)
        self.assertIn("y", disc)            # y separates the tiers
        self.assertNotIn("- x", disc)       # x agrees, not listed

    def test_single_run_discrimination_note(self):
        disc = report.discrimination_md([_run("A", "x", [_s("a", "pass")])])
        self.assertIn("one run", disc.lower())

    def test_main_writes_report_svg_and_html(self):
        # Tier B carries the judgment drift curve; Tier A (substrate) is intentionally excluded.
        a = self._write("a.json", _doc([_run("B", "opus",
                                              [_s("d5", "pass", 5, "drift"), _s("d25", "pass", 25, "drift")])]))
        out_md = self.dir / "REPORT.md"
        out_html = self.dir / "REPORT.html"
        old = sys.argv
        sys.argv = ["report", a, "--out", str(out_md), "--html", str(out_html)]
        try:
            report.main()
        finally:
            sys.argv = old
        self.assertTrue(out_md.exists())
        self.assertTrue((self.dir / "REPORT.drift.svg").exists())
        self.assertTrue(out_html.exists())
        self.assertIn("![drift curve](REPORT.drift.svg)", out_md.read_text())
        self.assertIn("<svg", out_html.read_text())

    def _vrun(self, model, tier, condition, sset, scen):
        # scen: list of (id, status, total_tokens)
        r = {"tier": "B", "model": model, "model_tier": tier, "condition": condition,
             "scenario_set": sset,
             "scenarios": [{"id": i, "status": st, "anti_pattern": "x", "tokens": {"total": tok}}
                           for i, st, tok in scen]}
        return r

    def test_value_lenses_sota_on_cheaper_and_savings(self):
        # opus baseline 2/2; haiku baseline 1/2 (gap); haiku+rosetta 2/2 (gap closed, cheaper).
        runs = [
            self._vrun("opus-base", "opus", "baseline", "hard", [("a", "pass", 30000), ("b", "pass", 30000)]),
            self._vrun("haiku-base", "haiku", "baseline", "hard", [("a", "pass", 20000), ("b", "fail", 20000)]),
            self._vrun("haiku-rosetta", "haiku", "rosetta", "hard", [("a", "pass", 22000), ("b", "pass", 22000)]),
        ]
        lenses = {L["set"]: L for L in report.value_lenses(runs)}
        hard = lenses["hard"]
        # Lens 3: haiku-rosetta (cheaper tier) matches opus baseline correctness at lower cost.
        self.assertIsNotNone(hard["transfer"])
        self.assertEqual(hard["transfer"]["cheap"]["label"], "B:haiku-rosetta")
        self.assertEqual(hard["transfer"]["sota"]["tier"], "opus")
        self.assertGreater(hard["transfer"]["mult"], 1)      # cheaper per correct than SoTA
        md = report.cost_md(runs)
        self.assertIn("SoTA on a cheaper model", md)
        self.assertIn("Product value", md)
        # Efficacy gate: haiku-base is 50% (<80%) → $/correct withheld, never shown as a cheap win.
        self.assertIn("withheld", md)

    def test_value_efficacy_gate_blocks_cheap_but_wrong(self):
        # A run that fails everything must not surface a (cheap) $/correct.
        runs = [self._vrun("cheapfail", "haiku", "baseline", "s", [("a", "fail", 100), ("b", "fail", 100)])]
        row = report._cost_row(runs[0])
        self.assertTrue(row["gated"])
        self.assertIn("withheld", report._usd_pp_cell(row))

    def test_detail_section_md_and_html(self):
        run = _run("B", "opus", [{
            "id": "x-scenario", "status": "pass", "anti_pattern": "hallucination",
            "expected": "EXP: must not assert payments", "actual": "ACT: only CSV importer",
            "judge": {"decision": "pass", "reasoning": "JUDGE-TRACE: verified against code"}}])
        md = report.detail_md([run])
        for frag in ("Per-test detail", "x-scenario", "EXP: must not assert payments",
                     "ACT: only CSV importer", "JUDGE-TRACE: verified against code"):
            self.assertIn(frag, md)
        html = report.detail_html([run])
        self.assertIn("<details", html)
        self.assertIn("JUDGE-TRACE", html)
        self.assertIn("Expected", html)

    def test_detail_absent_when_no_detail_fields(self):
        run = _run("A", "deterministic", [_s("a", "pass")])
        self.assertEqual(report.detail_md([run]), "")
        self.assertEqual(report.detail_html([run]), "")

    def test_detail_html_escapes(self):
        run = _run("B", "opus", [{"id": "x", "status": "fail", "anti_pattern": "y",
                                  "expected": "a<b>c", "actual": "d&e", "judge": {"reasoning": "f<g"}}])
        html = report.detail_html([run])
        self.assertIn("a&lt;b&gt;c", html)
        self.assertIn("d&amp;e", html)

    def test_anti_pattern_section(self):
        run = _run("A", "deterministic", [_s("a", "pass", ap="hallucination"),
                                          _s("b", "fail", ap="contradiction")])
        md = report.antipattern_md([run])
        self.assertIn("hallucination", md)
        self.assertIn("contradiction", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
