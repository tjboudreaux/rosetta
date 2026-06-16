#!/usr/bin/env python3
"""KILL TEST — the REAL baseline: a tool-calling agent over the raw corpus (not a context dump).

The matrix's `raw` arm dumps the whole corpus into context — a strawman that hits the context wall.
A modern agent instead GREPS/READS the repo on demand, so it handles a corpus far bigger than its
window. This arm measures that honest competitor on three axes the matrix didn't:
  - accuracy   (does grep-then-reason survive the supersession + stale-doc distractors?)
  - $ and tokens (tool outputs accumulate across turns)
  - wall-clock time + number of tool-call turns (sequential round-trips)

Each probe is a fresh Claude Code agent session (`claude -p … --output-format json`) run IN the corpus
directory with real Grep/Read/Bash tools on corpus.md. The JSON result carries result text, num_turns,
duration_ms, total_cost_usd, and token usage — measured, not estimated.

Run: python3 killtest_agentic.py [--corpus-dir killtest-outputs] [--model claude-sonnet-4-6] [--probes 20]
"""
import argparse
import json
import re
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

TASK = (
    "The file corpus.md in this directory is a large engineering decision history (many services, many "
    "decisions, interleaved by date). Using ONLY your Grep/Read/Bash tools on corpus.md — do NOT guess — "
    "determine for Project {city}: the CURRENT {dim} choice, and the choice it immediately replaced. "
    "Many decisions were SUPERSEDED over time and some stale docs still describe an OLD choice as current, "
    "so reason carefully about which value is truly current (latest, not superseded). "
    "Output ONLY a json object: {{\"current\": \"...\", \"replaced\": \"...\"}}"
)


def parse_obj(text):
    m = re.search(r"\{[^{}]*\"current\"[^{}]*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def run_probe(city, dim, model, corpus_dir, timeout):
    r = subprocess.run(
        ["claude", "-p", TASK.format(city=city, dim=dim), "--output-format", "json",
         "--model", model, "--allowedTools", "Grep,Read,Bash"],
        cwd=str(corpus_dir), capture_output=True, text=True, timeout=timeout)
    try:
        j = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"answer": {}, "turns": None, "ms": None, "cost": None, "tokens": None, "err": r.stderr[:200]}
    u = j.get("usage", {})
    tokens = (u.get("input_tokens", 0) + u.get("output_tokens", 0)
              + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))
    return {"answer": parse_obj(j.get("result", "")), "turns": j.get("num_turns"),
            "ms": j.get("duration_ms"), "cost": j.get("total_cost_usd"), "tokens": tokens}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus-dir", default="killtest-outputs")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    ap.add_argument("--probes", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=400)
    args = ap.parse_args()
    corpus_dir = (HERE / args.corpus_dir).resolve()
    out_dir = corpus_dir / "agentic"
    out_dir.mkdir(parents=True, exist_ok=True)

    probes = json.loads((corpus_dir / "probes.json").read_text())[: args.probes]
    gold = {g["id"]: g for g in json.loads((corpus_dir / "gold.json").read_text())}

    hit = cur_total = 0
    cost = ms = toks = turns = 0
    n_measured = 0
    rows = []
    print(f"agentic tool-calling over corpus.md — model={args.model}, {len(probes)} probes\n", flush=True)
    for p in probes:
        g = gold[p["id"]]
        r = run_probe(g["city"], g["dimension"], args.model, corpus_dir, args.timeout)
        ac = str(r["answer"].get("current", "")).lower()
        ok = bool(ac) and g["current"].lower() in ac
        hit += ok
        cur_total += 1
        if r["cost"] is not None:
            cost += r["cost"]; ms += r["ms"]; toks += r["tokens"]; turns += r["turns"]; n_measured += 1
        rows.append({"id": p["id"], "city": g["city"], "dim": g["dimension"],
                     "want": g["current"], "got": r["answer"].get("current", "—"), "ok": ok,
                     "turns": r["turns"], "ms": r["ms"], "cost": r["cost"], "tokens": r["tokens"]})
        flag = "OK " if ok else "XX "
        print(f"  {flag}{p['id']} {g['city']}/{g['dimension']}: want '{g['current']}' "
              f"got '{r['answer'].get('current','—')}'  turns={r['turns']} {r['ms']}ms "
              f"${r['cost']} {r['tokens']}tok", flush=True)

    n = cur_total
    print(f"\n=== agentic ({args.model}) over {n} probes ===")
    print(f"recall (current):  {hit}/{n} = {100*hit/n:.0f}%")
    if n_measured:
        print(f"total:  ${cost:.4f}  {toks} tokens  {ms/1000:.1f}s  {turns} tool-call turns")
        print(f"per probe avg:  ${cost/n_measured:.4f}  {toks//n_measured} tok  "
              f"{ms/n_measured/1000:.1f}s  {turns/n_measured:.1f} turns")
        print(f"$/correct:  ${cost/hit:.4f}" if hit else "$/correct: n/a")
    (out_dir / f"agentic-{args.model}.json").write_text(json.dumps(
        {"model": args.model, "probes": n, "recall": hit,
         "total_cost_usd": round(cost, 4), "total_tokens": toks, "total_ms": ms,
         "total_turns": turns, "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
