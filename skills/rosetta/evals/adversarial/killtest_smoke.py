#!/usr/bin/env python3
"""KILL TEST — smoke run (small, real-model): does flat compression actually lose recall that the
resolved graph recovers? Cheap go/no-go before the full cross-harness matrix.

Three arms, all answered by the SAME cheap solver (Haiku), over the same k probes:
  A1 raw            — solver reads the FULL ~106k corpus, answers the probes.
  A2 flat-summary   — a stronger model (Sonnet) compresses the corpus to ~5k tokens ONCE; the solver
                      answers from ONLY that lossy summary (the generic-compression baseline).
  A4 resolve        — for each probe, `decisions.py resolve` returns the current decision; the solver
                      answers from ONLY those resolve blobs (the Rosetta provenance-graph arm).

Each arm must emit a ```json list of {id, current, replaced}. Scored against gold.json:
  current-correct (recall) is the headline; replaced-correct is a bonus. A "current" that equals any
  SUPERSEDED link in the chain is a recall failure (the exact thing compression causes).

Prediction the smoke tests: A1 ≈ A4 (high), A2 << both. If A2 ties A1/A4, the thesis is in trouble
even at this scale and we stop before the full matrix.

Run: python3 killtest_smoke.py [--k 10] [--solver claude-haiku-4-5-20251001]
Pure stdlib + the `claude` CLI.
"""
import argparse
import json
import re
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "killtest-outputs"
DECISIONS = HERE.parent.parent / "scripts" / "decisions.py"
RUNS = OUT / "smoke-runs"
SUMMARIZER = "claude-sonnet-4-6"


def claude(model, instruction, stdin_text, timeout=900):
    """One non-interactive claude call: instruction via -p, bulk context via stdin. One retry."""
    for attempt in (1, 2):
        r = subprocess.run(["claude", "-p", instruction, "--model", model],
                           input=stdin_text, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
        sys.stderr.write(f"[claude {model}] attempt {attempt} rc={r.returncode}: "
                         f"{(r.stderr or r.stdout)[:300]}\n")
    return r.stdout


def _chunks(text, max_chars):
    """Split on record boundaries (## R...) into pieces under max_chars (map-reduce summarization)."""
    parts, buf = [], []
    size = 0
    for block in re.split(r"(?=^## R\d)", text, flags=re.MULTILINE):
        if size + len(block) > max_chars and buf:
            parts.append("".join(buf))
            buf, size = [], 0
        buf.append(block)
        size += len(block)
    if buf:
        parts.append("".join(buf))
    return parts


def parse_answers(text):
    """Pull the JSON list of {id,current,replaced} out of a model reply (tolerant of fences/prose)."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    blob = m.group(1) if m else None
    if blob is None:
        m = re.search(r"(\[\s*\{.*\}\s*\])", text, re.DOTALL)
        blob = m.group(1) if m else None
    if blob is None:
        return {}
    try:
        return {d["id"]: d for d in json.loads(blob) if "id" in d}
    except (json.JSONDecodeError, TypeError):
        return {}


ASK = ("You are answering questions about an engineering org's CURRENT architecture decisions. "
       "For EACH question, give the CURRENT choice and the one it immediately replaced. "
       "Many decisions were later superseded — answer with the CURRENT state, not a superseded one. "
       "Reply with ONLY a ```json fenced array of objects {\"id\":\"Q001\",\"current\":\"...\","
       "\"replaced\":\"...\"} — one per question, no prose.\n\nQUESTIONS:\n")


def questions_block(probes):
    return "\n".join(f'{p["id"]}: {p["question"]}' for p in probes)


def arm_raw(probes, solver):
    corpus = (OUT / "corpus.md").read_text()
    stdin = f"DECISION HISTORY (raw):\n{corpus}\n\n{ASK}{questions_block(probes)}"
    return claude(solver, "Answer strictly from the decision history above.", stdin), len(stdin) // 4


def arm_flat(probes, solver):
    """Generic flat-compression baseline via map-reduce summarization (the standard way real systems
    compress a corpus that exceeds the context window): summarize each ~26k-char chunk down to a small
    budget, then concatenate into a single ~5k-token lossy knowledge base. The summarizer never sees the
    probes — it must guess what matters, which is exactly where flat compression loses recall."""
    summ_path = RUNS / "flat_summary.md"
    if not summ_path.exists() or not summ_path.read_text().strip():
        corpus = (OUT / "corpus.md").read_text()
        chunks = _chunks(corpus, 90_000)                 # ~22k tokens/chunk, safely in-context
        budget_words = max(300, 3500 // max(1, len(chunks)))
        instr = (f"Compress this slice of an engineering decision history to AT MOST ~{budget_words} "
                 f"words. It will answer questions about each service's CURRENT architecture. Keep the "
                 f"CURRENT state of as many services as you can; you cannot keep everything.")
        pieces = [claude(SUMMARIZER, instr, c) for c in chunks]
        summ_path.write_text("\n\n".join(p.strip() for p in pieces if p.strip()))
    summary = summ_path.read_text()
    stdin = f"ARCHITECTURE SUMMARY:\n{summary}\n\n{ASK}{questions_block(probes)}"
    return claude(solver, "Answer strictly from the summary above.", stdin), len(stdin) // 4


def arm_resolve(probes, gold, solver):
    blobs = []
    for p in probes:
        g = gold[p["id"]]
        r = subprocess.run([sys.executable, str(DECISIONS), "--root", str(OUT / "decisions"),
                            "resolve", "--text", f"{g['city']} {g['dimension']}", "--no-stale-check"],
                           capture_output=True, text=True)
        blobs.append(f'{p["id"]} resolve({g["city"]} {g["dimension"]}): {r.stdout.strip()}')
    stdin = "RESOLVED CURRENT DECISIONS (from the provenance graph):\n" + "\n\n".join(blobs) + \
            f"\n\n{ASK}{questions_block(probes)}"
    return claude(solver, "Answer strictly from the resolved decisions above.", stdin), len(stdin) // 4


def score(answers, probes, gold):
    cur = rep = 0
    fails = []
    for p in probes:
        g = gold[p["id"]]
        a = answers.get(p["id"], {})
        ac, ar = str(a.get("current", "")).lower(), str(a.get("replaced", "")).lower()
        gc = g["current"].lower()
        cur_ok = bool(ac) and (gc in ac or ac in gc)
        # a current that names a superseded link is an explicit recall failure
        if cur_ok:
            cur += 1
        else:
            fails.append((p["id"], g["city"], g["dimension"], g["current"], a.get("current", "—")))
        if g["replaced"].lower() in ar and ar:
            rep += 1
    return cur, rep, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--solver", default="claude-haiku-4-5-20251001")
    ap.add_argument("--arms", default="raw,flat,resolve")
    args = ap.parse_args()
    RUNS.mkdir(parents=True, exist_ok=True)

    all_probes = json.loads((OUT / "probes.json").read_text())
    probes = all_probes[: args.k]
    gold = {g["id"]: g for g in json.loads((OUT / "gold.json").read_text())}

    arms = {"raw": arm_raw, "flat": arm_flat, "resolve": arm_resolve}
    results = {}
    for name in args.arms.split(","):
        fn = arms[name]
        out, in_tok = (fn(probes, gold, args.solver) if name == "resolve"
                       else fn(probes, args.solver))
        (RUNS / f"{name}.out.txt").write_text(out)
        ans = parse_answers(out)
        cur, rep, fails = score(ans, probes, gold)
        results[name] = {"current": cur, "replaced": rep, "parsed": len(ans),
                         "in_tokens": in_tok, "fails": fails}
        print(f"[{name:8}] current(recall) {cur}/{len(probes)}  replaced {rep}/{len(probes)}  "
              f"parsed {len(ans)}/{len(probes)}  input≈{in_tok} tok")
        for f in fails[:5]:
            print(f"            MISS {f[0]} {f[1]}/{f[2]}: want '{f[3]}' got '{f[4]}'")

    (RUNS / "smoke-results.json").write_text(json.dumps(results, indent=2) + "\n")
    if {"raw", "flat", "resolve"} <= set(results):
        r, fl, rs = results["raw"]["current"], results["flat"]["current"], results["resolve"]["current"]
        n = len(probes)
        print(f"\nSMOKE VERDICT (recall): raw {r}/{n} · flat-summary {fl}/{n} · resolve {rs}/{n}")
        if rs >= r and fl < r:
            print("  → SEPARATION CONFIRMED: flat compression loses recall; resolve recovers it. "
                  "Proceed to the full cross-harness matrix.")
        elif fl >= r:
            print("  → NO SEPARATION: flat-summary ties raw even here. Thesis in doubt — stop and rethink "
                  "before spending on the full matrix.")
        else:
            print("  → MIXED: inspect per-probe misses before scaling.")


if __name__ == "__main__":
    main()
