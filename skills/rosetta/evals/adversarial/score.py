#!/usr/bin/env python3
"""Deterministic, judge-INDEPENDENT scorer for the decision-history scenarios.

LESSON (recorded in ADR 0022): regex-grading free-form `ground-truth.md` prose is NOT reliable — on
real Haiku/Sonnet outputs it produced both false negatives (missing "ADR 0125\n…\nSuperseded by ADR
0251" across a title) and false positives (reading "migrated FROM Postgres" as "Postgres is current").
A heuristic that can invert the result is worse than none.

So authoritative deterministic scoring requires a **structured verdict block** the solver emits — a
fenced ```rosetta-verdict {json} ``` (or a bare JSON object) with the objective answer:

    {"superseded_adr": "ADR 0125", "created_superseding_adr": true,
     "near_miss_untouched": true, "current_store": "duckdb"}

`score.py` re-derives the correct needle/near-miss from the (deterministic) fixture and checks that
block EXACTLY — judge-independent, no prose parsing. If no block is present, it reports
`scorable: false` (exit 2) and routes the case to the LLM judge rather than guessing. A clearly-labeled,
NON-authoritative prose heuristic is available with --heuristic for triage only.

Usage:
  python3 score.py --scenario decision-supersession-lookup-100 --solver-output gt.md
  python3 score.py --scenario decision-already-recorded --solver-output gt.md [--heuristic]
"""
import argparse
import json
import re
import sys
import tempfile
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures  # noqa: E402


def _num(path):
    m = re.match(r"(\d+)-", Path(path).name)
    return int(m.group(1)) if m else None


_NEGATION = re.compile(r"untouch|unrelated|left alone|left\b|not\b|n't|unchanged|remain|"
                       r"no change|distinct|different subsystem|kept|keep|valid", re.I)
_W = 110   # bind window (chars, newlines allowed) — tuned against real Haiku/Sonnet/Opus outputs


def _was_superseded(text, num):
    """True if ADR <num> is reported as the record BEING superseded — either the status-flip form
    'ADR N … Superseded[ by …]' (N is the subject whose status flips) or the verb→object form
    'supersede ADR N' WITHOUT a 'by' (so 'Superseded by ADR M' does not count M, the new record).
    Allows newlines/titles between (real outputs put the title + a Status line in between)."""
    n = rf"ADR\s*0*{num}\b"
    if re.search(rf"{n}[\s\S]{{0,{_W}}}?supersed", text, re.I):
        return True
    for m in re.finditer(rf"supersed\w*(\s+by)?\s+(?:\w+\s+){{0,3}}{n}", text, re.I):
        if not m.group(1):
            return True
    return False


def _near_miss_touched(text, num):
    """True only if the near-miss ADR is ACTIVELY superseded/modified — and NOT in a sentence that
    negates it ('ADR N … left untouched / unrelated / different subsystem')."""
    n = rf"ADR\s*0*{num}\b"
    m = re.search(rf"{n}([\s\S]{{0,{_W}}}?)supersed", text, re.I)
    if m and not _NEGATION.search(m.group(1)):
        return True
    for mm in re.finditer(rf"supersed\w*(\s+by)?\s+(?:\w+\s+){{0,3}}{n}", text, re.I):
        if not mm.group(1):
            return True
    return False


def _asserts_postgres_current(text):
    """Conservative: fire only on an explicit PRESENT-TENSE claim that the event log IS in Postgres
    (e.g. 'the event log remains on Postgres'), not on 'migrated FROM Postgres' / parenthetical
    labels like '(event log in Postgres)'."""
    return bool(re.search(r"event\s*log[\s\S]{0,30}?\b(is|uses|stored in|persisted in|"
                          r"remains (?:on|in)|lives in|backed by)\b[\s\S]{0,15}?postgres", text, re.I))


def _adr_num(s):
    m = re.search(r"\d+", s or "")
    return int(m.group(0)) if m else None


def extract_verdict(text):
    """Find the solver's structured verdict block: a ```rosetta-verdict {...}``` fence or any bare
    JSON object containing a 'superseded_adr' / 'current_store' key. None if absent."""
    fence = re.search(r"```(?:rosetta-verdict)?\s*(\{.*?\})\s*```", text, re.S)
    cands = [fence.group(1)] if fence else []
    cands += re.findall(r"\{[^{}]*\"(?:superseded_adr|current_store|already_recorded_adr)\"[^{}]*\}",
                        text, re.S)
    for c in cands:
        try:
            return json.loads(c)
        except Exception:
            continue
    return None


def score_supersession(solver_text, planted, heuristic=False):
    lib = planted["decision_library"]
    needle = _num(lib["needle_path"])
    nearmiss = _num(lib["distractor_paths"][0]) if lib.get("distractor_paths") else None
    v = extract_verdict(solver_text)
    if v is not None:                      # authoritative: exact check of the structured block
        # strict typing — a JSON string "false" is truthy in Python, so require real booleans
        # (else a model could game the block); ADR 0023.
        checks = {
            "superseded_correct_adr": _adr_num(v.get("superseded_adr")) == needle,
            "created_superseding_adr": v.get("created_superseding_adr") is True,
            "left_near_miss_untouched": v.get("near_miss_untouched") is True,
            "current_state_columnar": "duck" in str(v.get("current_store", "")).lower()
                                      or "columnar" in str(v.get("current_store", "")).lower(),
        }
        return {"method": "structured", "needle_adr": needle, "near_miss_adr": nearmiss,
                "checks": checks, "passed": all(checks.values())}
    if not heuristic:
        return {"method": "none", "scorable": False, "needle_adr": needle, "near_miss_adr": nearmiss,
                "reason": "no structured verdict block; route to the LLM judge (prose is not reliably "
                          "regex-scorable). Re-run the solver asking for a ```rosetta-verdict``` block."}
    t = solver_text                        # NON-authoritative triage only (do not gate on this)
    checks = {
        "superseded_correct_adr": _was_superseded(t, needle),
        "left_near_miss_untouched": not (_near_miss_touched(t, nearmiss) if nearmiss else False),
        "current_state_columnar": bool(re.search(r"duckdb|columnar", t, re.I)),
        "did_not_assert_postgres_current": not _asserts_postgres_current(t),
    }
    return {"method": "heuristic-best-effort", "authoritative": False,
            "needle_adr": needle, "near_miss_adr": nearmiss,
            "checks": checks, "passed": all(checks.values())}


def score_already_recorded(solver_text, planted, heuristic=False):
    lib = planted["decision_library"]
    needle = _num(lib["needle_path"])
    v = extract_verdict(solver_text)
    if v is not None:                      # strict: created_new_adr must be a real False (ADR 0023)
        checks = {
            "cites_existing_adr": _adr_num(v.get("already_recorded_adr")) == needle,
            "did_not_duplicate": v.get("created_new_adr") is False,
        }
        return {"method": "structured", "existing_adr": needle, "checks": checks,
                "passed": all(checks.values())}
    if not heuristic:
        return {"method": "none", "scorable": False, "existing_adr": needle,
                "reason": "no structured verdict block; route to the LLM judge."}
    t = solver_text
    cites_existing = bool(re.search(rf"\bADR\s*0*{needle}\b", t))
    says_already = bool(re.search(r"already (recorded|captured|exists|decided|present)", t, re.I)
                        or re.search(r"no (new|duplicate) (adr|record)", t, re.I)
                        or re.search(r"do(es)? not (create|need|require) a (new|duplicate)", t, re.I))
    checks = {"cites_existing_adr": cites_existing, "recognizes_already_recorded": says_already}
    return {"method": "heuristic-best-effort", "authoritative": False,
            "existing_adr": needle, "checks": checks, "passed": all(checks.values())}


SCORERS = {
    "decision-supersession-lookup-5": score_supersession,
    "decision-supersession-lookup-25": score_supersession,
    "decision-supersession-lookup-100": score_supersession,
    "decision-supersession-lookup-250": score_supersession,
    "decision-already-recorded": score_already_recorded,
}


def fixture_for(scenario_id):
    """Return the planted manifest for a scenario by rebuilding its (deterministic) fixture."""
    data = json.loads((HERE / "dataset.json").read_text())
    scn = next((s for s in data["scenarios"] if s["id"] == scenario_id), None)
    if not scn:
        raise SystemExit(f"unknown scenario: {scenario_id}")
    tmp = tempfile.mkdtemp(prefix="rosetta-score-")
    try:
        return fixtures.build(scn["fixture"], tmp), tmp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def score(scenario_id, solver_text, heuristic=False):
    if scenario_id not in SCORERS:
        raise SystemExit(f"no deterministic scorer for '{scenario_id}' "
                         f"(have: {', '.join(sorted(SCORERS))})")
    planted, tmp = fixture_for(scenario_id)
    try:
        result = SCORERS[scenario_id](solver_text, planted, heuristic=heuristic)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    result["scenario_id"] = scenario_id
    return result


def main():
    ap = argparse.ArgumentParser(description="Deterministic scorer for decision-history eval outputs")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--solver-output", required=True, help="path to the solver's ground-truth.md")
    ap.add_argument("--heuristic", action="store_true",
                    help="fall back to a NON-authoritative prose heuristic when no verdict block exists")
    args = ap.parse_args()
    text = Path(args.solver_output).read_text(errors="replace")
    verdict = score(args.scenario, text, heuristic=args.heuristic)
    print(json.dumps(verdict, indent=2))
    if verdict.get("scorable") is False:
        return 2                            # not deterministically scorable → route to LLM judge
    return 0 if verdict.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
