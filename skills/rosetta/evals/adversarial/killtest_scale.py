#!/usr/bin/env python3
"""KILL TEST — context-window scaling experiment.

Question: what happens to each arm as the corpus grows past a model's context window?
Prediction: `raw` input scales linearly with corpus → eventually the model REJECTS it ("prompt too
long"); `resolve` input is INVARIANT to corpus size (it returns one resolved record regardless), so its
cost and recall don't move.

For each corpus size we measure, with NO model where possible:
  - corpus tokens, #decisions
  - resolve-arm input tokens for a fixed probe set (deterministic — proves cost-invariance)
  - resolve recall vs gold (deterministic resolve check — proves accuracy-invariance)
  - raw-arm input tokens (= corpus) and ONE real solver attempt → does it answer or get rejected?

Run: python3 killtest_scale.py [--sizes 120,300,600] [--solver claude-sonnet-4-6] [--probes 10]
"""
import argparse
import json
import re
import subprocess
import sys
import pathlib

import killtest_smoke as ks

HERE = pathlib.Path(__file__).resolve().parent
GEN = HERE / "killtest_gen.py"
DEC = HERE.parent.parent / "scripts" / "decisions.py"
SCALE = HERE / "killtest-outputs" / "scale"


def gen(services, out):
    subprocess.run([sys.executable, str(GEN), "--services", str(services), "--probes", "12",
                    "--out", str(out)], capture_output=True, text=True, check=True)


def resolve_blob_tokens(out, probes, gold):
    """The exact stdin the resolve arm would send for these probes (minus the question list) — its size
    is what stays constant as the corpus grows."""
    blobs = []
    hit = 0
    root = str(out / "decisions")
    for p in probes:
        g = gold[p["id"]]
        r = subprocess.run([sys.executable, str(DEC), "--root", root, "resolve",
                            "--text", f"{g['city']} {g['dimension']}", "--no-stale-check"],
                           capture_output=True, text=True)
        try:
            res = json.loads(r.stdout)
        except json.JSONDecodeError:
            res = {"current": []}
        live = res.get("current", [])
        titles = " | ".join(c["title"] for c in live)
        if len(live) == 1 and g["current"] in titles and not any(
                a in titles for a in g["avoid"] if a != g["current"]):
            hit += 1
        blobs.append(r.stdout.strip())
    return len("\n\n".join(blobs)) // 4, hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="120,300,600", help="service counts to generate")
    ap.add_argument("--solver", default="claude-sonnet-4-6")
    ap.add_argument("--probes", type=int, default=10)
    ap.add_argument("--raw-timeout", type=int, default=300)
    args = ap.parse_args()
    SCALE.mkdir(parents=True, exist_ok=True)
    ks.CALL_TIMEOUT = args.raw_timeout

    print(f"{'services':>8} {'corpus_tok':>11} {'decisions':>10} {'resolve_in':>11} "
          f"{'resolve_rec':>11} {'raw_in':>10} {'raw_result':>26}")
    rows = []
    for s in args.sizes.split(","):
        s = int(s)
        out = SCALE / f"n{s}"
        gen(s, out)
        corpus = (out / "corpus.md").read_text()
        probes = json.loads((out / "probes.json").read_text())[: args.probes]
        gold = {g["id"]: g for g in json.loads((out / "gold.json").read_text())}
        n_dec = len(list((out / "decisions" / "architecture-decisions").glob("*.md")))
        corpus_tok = len(corpus) // 4
        res_in, res_hit = resolve_blob_tokens(out, probes, gold)

        # one raw attempt: does the model accept ~corpus_tok of input or reject it?
        stdin = (f"DECISION HISTORY (raw):\n{corpus}\n\n{ks.ASK}{ks.questions_block(probes)}")
        raw_in = len(stdin) // 4
        out_text = ks.run_model(args.solver, "Answer strictly from the decision history above.", stdin)
        ans = ks.parse_answers(out_text)
        if not out_text.strip():
            raw_result = "REJECTED/empty (no answer)"
            raw_rec = None
        elif re.search(r"too long|exceed|context|maximum", out_text, re.I) and not ans:
            raw_result = "REJECTED (prompt too long)"
            raw_rec = None
        else:
            raw_hit = sum(1 for p in probes
                          if str(ans.get(p["id"], {}).get("current", "")).lower()
                          and (gold[p["id"]]["current"].lower()
                               in str(ans.get(p["id"], {}).get("current", "")).lower()))
            raw_rec = f"{raw_hit}/{len(probes)}"
            raw_result = f"answered {raw_rec}"
        rows.append((s, corpus_tok, n_dec, res_in, f"{res_hit}/{len(probes)}", raw_in, raw_result))
        print(f"{s:>8} {corpus_tok:>11} {n_dec:>10} {res_in:>11} {res_hit:>9}/{len(probes)} "
              f"{raw_in:>10} {raw_result:>26}", flush=True)

    (SCALE / "scale-results.json").write_text(json.dumps(
        [dict(zip(["services", "corpus_tok", "decisions", "resolve_in_tok", "resolve_recall",
                   "raw_in_tok", "raw_result"], r)) for r in rows], indent=2) + "\n")
    print(f"\nresolve input stays ~flat while raw input tracks the corpus — see scale-results.json")


if __name__ == "__main__":
    main()
