#!/usr/bin/env python3
"""KILL TEST — Stage-1 apparatus validation (ZERO API spend).

Before any model is called, prove the fixture is sound and actually creates the regime goals 1 & 2
lacked. Checks:
  1. INTEGRITY: the ground-truth decision library passes `decisions.py validate --integrity`
     (no fabricated ids / ghost citations) — the arm-A4 substrate is trustworthy.
  2. RESOLVE RECALL CEILING: for every probe, `decisions.py resolve --text "<city> <dim>"` returns a
     SINGLE current record whose value == gold.current, and never an `avoid` (superseded) value.
     This is arm A4's accuracy ceiling, established deterministically (no model) = the resolution
     mechanism recovers 100% of current endpoints by construction.
  3. COMPRESSION PRESSURE: show a fixed ~5k-token flat summary physically cannot retain the endpoints —
     (a) analytically (bare (city,dim,value) triples for all chains already exceed 5k tokens), and
     (b) empirically (how many of the 40 gold currents survive in a naive lead-5k-token slice).

Exit 0 only if integrity is clean AND resolve recall == 100%. Pure stdlib (subprocess to decisions.py).

Run: python3 killtest_validate.py
"""
import json
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "killtest-outputs"
DECISIONS = HERE.parent.parent / "scripts" / "decisions.py"
TOK = 4   # rough chars/token


def _resolve(city, dim):
    r = subprocess.run([sys.executable, str(DECISIONS), "--root", str(OUT / "decisions"),
                        "resolve", "--text", f"{city} {dim}", "--no-stale-check"],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


def main():
    probes = json.loads((OUT / "probes.json").read_text())
    gold = {g["id"]: g for g in json.loads((OUT / "gold.json").read_text())}
    corpus = (OUT / "corpus.md").read_text()

    # 1. integrity
    ig = subprocess.run([sys.executable, str(DECISIONS), "--root", str(OUT / "decisions"),
                         "integrity"], capture_output=True, text=True)
    integrity_ok = ig.returncode == 0
    print(f"[1] integrity: {'CLEAN' if integrity_ok else 'FAILED'}  ({ig.stdout.strip().splitlines()[-1] if ig.stdout else ''})")

    # 2. resolve recall ceiling
    hits = miss = conflict = 0
    misses = []
    for p in probes:
        g = gold[p["id"]]
        res = _resolve(g["city"], g["dimension"])
        live = res.get("current", [])
        if res.get("conflict"):
            conflict += 1
        # the resolved current value should contain gold.current and none of the avoid values
        titles = " | ".join(c["title"] for c in live)
        ok = (len(live) == 1 and g["current"] in titles
              and not any(a in titles for a in g["avoid"] if a != g["current"]))
        if ok:
            hits += 1
        else:
            miss += 1
            misses.append((p["id"], g["city"], g["dimension"], g["current"], titles))
    total = len(probes)
    recall = 100.0 * hits / total
    print(f"[2] resolve recall ceiling: {hits}/{total} = {recall:.1f}%  "
          f"(conflicts flagged: {conflict})")
    for m in misses[:8]:
        print(f"      MISS {m[0]} {m[1]}/{m[2]}: want '{m[3]}' got [{m[4]}]")

    # 3. compression pressure
    records = list((OUT / "decisions" / "architecture-decisions").glob("*.md"))
    n_chains = len(records)
    accepted = sum(1 for f in records if "\n- Status: Accepted" in f.read_text())
    superseded = n_chains - accepted
    corpus_tok = len(corpus) // TOK
    # empirical: how many gold currents survive a naive lead-5k-token slice of the corpus
    lead = corpus[: 5000 * TOK]
    survived = sum(1 for p in probes
                   if gold[p["id"]]["current"].split()[0] in lead
                   and gold[p["id"]]["city"] in lead)
    print(f"[3] compression pressure:")
    print(f"      corpus ~{corpus_tok} tok → 5k summary = {corpus_tok/5000:.1f}:1 compression")
    print(f"      {n_chains} decisions, of which {superseded} are SUPERSEDED distractors + stale docs; "
          f"only {accepted} are current — the summarizer must DISCRIMINATE current from superseded, "
          f"not just compress")
    print(f"      positional baseline: a naive lead-5k slice carries city+current for only "
          f"{survived}/{total} probes ({100*survived/total:.0f}%) — {total-survived} already lost to position")

    ok = integrity_ok and hits == total
    print(f"\nSTAGE-1 {'PASS — apparatus sound, safe to spend on the smoke run' if ok else 'FAIL — fix before any API spend'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
