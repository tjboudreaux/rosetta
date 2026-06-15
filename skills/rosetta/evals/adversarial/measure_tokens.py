#!/usr/bin/env python3
"""Token-accounting harness for the GOAL-3 token-reduction stack (H1/H2/H3).

It measures *real* tokens (tiktoken cl100k_base — a provider-neutral proxy; Claude's tokenizer is
close enough for a ratio, and ratios are what we report) on deterministic eval fixtures, for the two
code-shippable levers:

  H1  resolve-instead-of-read: tokens a solver must ingest to answer a resolution query —
      RAW = read the whole decision library  vs  RESOLVE = one `decisions.py resolve` JSON.
  H2  deterministic scoring vs LLM judge: judge-side tokens — an LLM judge bundle (prompt + corpus +
      manifest + gold) vs `score.py` on a structured verdict block (ZERO model tokens).
  H3  prompt-prefix caching: estimate input-token savings from reusing the identical shared prefix
      across k samples / arms / same-provider models (cached reads are ~free / heavily discounted).

Pure stdlib + tiktoken. Outputs JSON so the result doc can quote exact numbers.

Usage:
  python3 measure_tokens.py                       # measure all and print the accounting JSON
  python3 measure_tokens.py --scenario decision-already-recorded
"""
import argparse
import io
import json
import subprocess
import sys
import shutil
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
import fixtures  # noqa: E402
import decisions  # noqa: E402

DATASET = HERE / "dataset.json"
DECISIONS_PY = HERE.parents[1] / "scripts" / "decisions.py"
JUDGE_PROMPT = HERE / "judge_prompt.md"

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")
    def ntok(s):
        return len(_ENC.encode(s))
    TOKENIZER = "tiktoken/cl100k_base"
except Exception:                                     # pragma: no cover - fallback
    def ntok(s):
        # ~4 chars/token English-prose heuristic if tiktoken is unavailable
        return max(1, len(s) // 4)
    TOKENIZER = "heuristic/4-chars"


# H1 query: the term a solver resolves for each scorable scenario.
H1_QUERY = {
    "decision-already-recorded": "rate limit",
    "decision-supersession-lookup-5": "event log",
    "decision-supersession-lookup-25": "event log",
    "decision-supersession-lookup-100": "event log",
    "decision-supersession-lookup-250": "event log",
}


def _materialize(scenario_id):
    data = json.loads(DATASET.read_text())
    scn = next((s for s in data["scenarios"] if s["id"] == scenario_id), None)
    if not scn:
        raise SystemExit(f"unknown scenario: {scenario_id}")
    tmp = tempfile.mkdtemp(prefix="rosetta-measure-")
    planted = fixtures.build(scn["fixture"], tmp)
    return scn, planted, tmp


def _library_blob(project, lib):
    d = Path(project) / lib["dir"]
    recs = sorted(d.glob("*.md"))
    return "\n\n".join(f"===== {p.name} =====\n{p.read_text()}" for p in recs), len(recs)


def _resolve_json(project, query):
    """Call decisions.cmd_resolve in-process and capture its JSON stdout (the resolve tool output)."""
    root = (Path(project) / "decisions").resolve()
    cfg = decisions.load_config(root)
    args = argparse.Namespace(text=query, type=None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        decisions.cmd_resolve(args, root, cfg)
    return buf.getvalue()


def measure_h1(scenario_id):
    """RAW (read whole library) vs RESOLVE (one tool-call JSON). Returns token accounting."""
    scn, planted, tmp = _materialize(scenario_id)
    try:
        lib = planted["decision_library"]
        blob, n = _library_blob(planted["project"], lib)
        query = H1_QUERY.get(scenario_id, lib.get("needle_contains", ["event log"])[0])
        resolve_out = _resolve_json(planted["project"], query)
        raw_tok = ntok(blob)
        # resolve cost = the tool-call JSON the solver ingests + a modest fixed tool-call overhead
        # (the `resolve --text "<q>"` invocation). We count the JSON output; the invocation string is
        # tiny and counted separately for honesty.
        invocation = f'decisions.py resolve --text "{query}"'
        resolve_tok = ntok(resolve_out) + ntok(invocation)
        return {
            "scenario": scenario_id, "query": query, "records": n,
            "raw_read_tokens": raw_tok,
            "resolve_tokens": resolve_tok,
            "reduction_pct": round(100 * (raw_tok - resolve_tok) / raw_tok, 1),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def measure_h2(scenario_id):
    """LLM-judge token cost vs deterministic score.py (0 model tokens).

    Judge cost = judge_prompt + the bundle a judge must read to grade one solver output:
    prompt + normalized corpus + manifest + gold + the solver output itself. We approximate the
    solver output by the gold-supported answer length (a real judge reads a full solver answer, so
    this is conservative-low). score.py reads a tiny structured verdict block, runs locally, emits
    ZERO model tokens — so the eliminated judge tokens ARE the saving.
    """
    scn, planted, tmp = _materialize(scenario_id)
    try:
        # Emit a judge bundle for this scenario via run_evals (reuses the canonical bundle writer).
        bundle_root = tempfile.mkdtemp(prefix="rosetta-bundle-")
        try:
            subprocess.run([sys.executable, str(HERE / "run_evals.py"),
                            "--scenario", scenario_id, "--emit-bundle", bundle_root],
                           capture_output=True, text=True, check=True)
            bdir = Path(bundle_root) / scenario_id
            judge_prompt_tok = ntok(JUDGE_PROMPT.read_text()) if JUDGE_PROMPT.exists() else 0
            prompt_tok = ntok((bdir / "prompt.txt").read_text())
            corpus_tok = sum(ntok(p.read_text()) for p in (bdir / "normalized").glob("*"))
            manifest_tok = ntok((bdir / "manifest.json").read_text())
            gold_tok = ntok((bdir / "gold.json").read_text())
            # a judge also reads the solver's full answer; estimate by the gold answer text size *2
            # (a real free-form answer is longer than the gold). Conservative-low.
            solver_answer_tok = gold_tok * 2
            judge_total = (judge_prompt_tok + prompt_tok + corpus_tok + manifest_tok
                           + gold_tok + solver_answer_tok)
            # the structured verdict block score.py needs (what the solver emits anyway):
            verdict_block = ('```rosetta-verdict {"superseded_adr":"ADR 0050",'
                             '"created_superseding_adr":true,"near_miss_untouched":true,'
                             '"current_store":"duckdb"}```')
            return {
                "scenario": scenario_id,
                "llm_judge_tokens": judge_total,
                "judge_breakdown": {"judge_prompt": judge_prompt_tok, "task_prompt": prompt_tok,
                                    "corpus": corpus_tok, "manifest": manifest_tok,
                                    "gold": gold_tok, "solver_answer": solver_answer_tok},
                "deterministic_score_model_tokens": 0,
                "verdict_block_tokens_solver_emits": ntok(verdict_block),
                "reduction_pct": 100.0,
            }
        finally:
            shutil.rmtree(bundle_root, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def measure_h3(scenario_id, k=3, models_same_provider=3):
    """Estimate prompt-prefix caching savings on INPUT tokens.

    The shared prefix (task prompt + corpus/library substrate) is identical across k samples and
    across same-provider models. With caching, the first call pays full input; subsequent calls pay
    a heavily-discounted cached-read (Anthropic: cached reads ~0.1x). We model the prefix as the raw
    library + task prompt (the bulk of input) and report uncached vs cached input tokens over
    k * models calls.
    """
    scn, planted, tmp = _materialize(scenario_id)
    try:
        lib = planted["decision_library"]
        blob, _ = _library_blob(planted["project"], lib)
        prompt = scn["prompt"].replace("{project}", planted["project"])
        prefix_tok = ntok(blob) + ntok(prompt)
        calls = k * models_same_provider
        uncached = prefix_tok * calls
        CACHE_READ_MULT = 0.1                          # Anthropic cached-read ≈ 0.1x base input
        cached = prefix_tok + prefix_tok * CACHE_READ_MULT * (calls - 1)
        return {
            "scenario": scenario_id, "shared_prefix_tokens": prefix_tok,
            "calls_modeled": calls, "k": k, "same_provider_models": models_same_provider,
            "uncached_input_tokens": uncached,
            "cached_input_tokens": round(cached),
            "cache_read_multiplier": CACHE_READ_MULT,
            "reduction_pct": round(100 * (uncached - cached) / uncached, 1),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="GOAL-3 token-reduction measurement harness")
    ap.add_argument("--scenario", help="single scenario id (default: all scorable)")
    args = ap.parse_args()
    scenarios = [args.scenario] if args.scenario else list(H1_QUERY)
    out = {"tokenizer": TOKENIZER, "h1_resolve_vs_raw": [], "h2_score_vs_judge": [],
           "h3_prefix_caching": []}
    for sid in scenarios:
        out["h1_resolve_vs_raw"].append(measure_h1(sid))
        out["h2_score_vs_judge"].append(measure_h2(sid))
        out["h3_prefix_caching"].append(measure_h3(sid))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
