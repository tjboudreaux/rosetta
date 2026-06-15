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


# Per-call wall-clock budget (seconds). A module global so a long matrix run can raise it once
# (ks.CALL_TIMEOUT = N) without threading the value through every arm function.
CALL_TIMEOUT = 1800


def claude(model, instruction, stdin_text, timeout=None):
    """One non-interactive claude call: instruction via -p, bulk context via stdin. Retries on
    nonzero/empty/timeout so a single slow or flaky call never crashes a long matrix run."""
    timeout = CALL_TIMEOUT if timeout is None else timeout
    out = ""
    for attempt in (1, 2, 3):
        try:
            r = subprocess.run(["claude", "-p", instruction, "--model", model],
                               input=stdin_text, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            sys.stderr.write(f"[claude {model}] attempt {attempt} TIMEOUT after {timeout}s\n")
            continue
        out = r.stdout
        if r.returncode == 0 and out.strip():
            return out
        sys.stderr.write(f"[claude {model}] attempt {attempt} rc={r.returncode}: "
                         f"{(r.stderr or out)[:300]}\n")
    return out


def _gemini(model, instruction, stdin_text, timeout):
    import os
    env = dict(os.environ, GEMINI_CLI_TRUST_WORKSPACE="true")
    r = subprocess.run(["gemini", "-m", model, "--skip-trust", "-p", instruction],
                       input=stdin_text, capture_output=True, text=True, timeout=timeout, env=env)
    return r.returncode, r.stdout, r.stderr


def _codex(model, instruction, stdin_text, timeout):
    # codex reads the piped context on stdin; the prompt arg carries the instruction. Output is wrapped
    # in hook/token noise — the tolerant JSON parser strips that downstream.
    r = subprocess.run(["codex", "exec", "--skip-git-repo-check", "-m", model, instruction],
                       input=stdin_text, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def run_model(model, instruction, stdin_text, timeout=None):
    """Harness-agnostic single call, routed by model id: claude-* → claude CLI, gemini* → gemini CLI,
    everything else (gpt-*/codex) → codex CLI. Retries on nonzero/empty/timeout so one flaky provider
    call never crashes a long matrix. Returns the raw stdout (the tolerant parser extracts the answer)."""
    timeout = CALL_TIMEOUT if timeout is None else timeout
    if model.startswith("claude"):
        return claude(model, instruction, stdin_text, timeout)
    runner = _gemini if model.startswith("gemini") else _codex
    out = ""
    for attempt in (1, 2, 3):
        try:
            rc, out, err = runner(model, instruction, stdin_text, timeout)
        except subprocess.TimeoutExpired:
            sys.stderr.write(f"[{model}] attempt {attempt} TIMEOUT after {timeout}s\n")
            continue
        if rc == 0 and out.strip():
            return out
        sys.stderr.write(f"[{model}] attempt {attempt} rc={rc}: {(err or out)[:300]}\n")
    return out


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
    return run_model(solver, "Answer strictly from the decision history above.", stdin), len(stdin) // 4


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
    return run_model(solver, "Answer strictly from the summary above.", stdin), len(stdin) // 4


def _bm25_index(corpus):
    """Pure-Python BM25 over the corpus's ## R#### records (the generic-RAG arm's retriever).
    Returns (records[list[str]], score_fn(query)->ranked idxs). No embeddings/model — a standard
    lexical baseline that retrieves raw chunks WITHOUT resolving supersession (so it can surface a
    superseded decision as readily as the current one — the generic-memory failure mode)."""
    import math
    from collections import Counter
    blocks = [b for b in re.split(r"(?=^## R\d)", corpus, flags=re.MULTILINE) if b.strip()]
    def toks(s):
        return re.findall(r"[a-z0-9]+", s.lower())
    docs = [toks(b) for b in blocks]
    N = len(docs)
    avgdl = sum(len(d) for d in docs) / max(1, N)
    df = Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    idf = {t: math.log(1 + (N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
    tfs = [Counter(d) for d in docs]
    k1, b = 1.5, 0.75
    def rank(query, top):
        qt = toks(query)
        scored = []
        for i, tf in enumerate(tfs):
            dl = len(docs[i])
            s = 0.0
            for t in qt:
                if t not in tf:
                    continue
                s += idf.get(t, 0.0) * (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * dl / avgdl))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [blocks[i] for _, i in scored[:top]]
    return rank


def arm_rag(probes, gold, solver, top=8):
    corpus = (OUT / "corpus.md").read_text()
    rank = _bm25_index(corpus)
    blobs = []
    for p in probes:
        g = gold[p["id"]]
        chunks = rank(f"{g['city']} {g['dimension']}", top)
        blobs.append(f'{p["id"]} retrieved for "{g["city"]} {g["dimension"]}":\n' + "\n".join(chunks))
    stdin = ("RETRIEVED DECISION RECORDS (top-k lexical retrieval; may include superseded ones):\n"
             + "\n\n".join(blobs) + f"\n\n{ASK}{questions_block(probes)}")
    return run_model(solver, "Answer strictly from the retrieved records above.", stdin), len(stdin) // 4


def _resolve_arm(probes, gold, solver, root):
    blobs = []
    for p in probes:
        g = gold[p["id"]]
        r = subprocess.run([sys.executable, str(DECISIONS), "--root", str(root),
                            "resolve", "--text", f"{g['city']} {g['dimension']}", "--no-stale-check"],
                           capture_output=True, text=True)
        blobs.append(f'{p["id"]} resolve({g["city"]} {g["dimension"]}): {r.stdout.strip()}')
    stdin = "RESOLVED CURRENT DECISIONS (from the provenance graph):\n" + "\n\n".join(blobs) + \
            f"\n\n{ASK}{questions_block(probes)}"
    return run_model(solver, "Answer strictly from the resolved decisions above.", stdin), len(stdin) // 4


def arm_resolve(probes, gold, solver):
    """resolve against the DETERMINISTIC ground-truth library (resolution recall CEILING)."""
    return _resolve_arm(probes, gold, solver, OUT / "decisions")


def arm_compiled(probes, gold, solver):
    """resolve against the LLM-COMPILED library (end-to-end Rosetta: extraction fallibility folded in;
    compile cost is in compiled-lib/compile-meta.json). Build it first: python3 killtest_compile.py."""
    return _resolve_arm(probes, gold, solver, OUT / "compiled-lib" / "decisions")


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

    arms = {"raw": arm_raw, "flat": arm_flat, "rag": arm_rag, "resolve": arm_resolve, "compiled": arm_compiled}
    results = {}
    for name in args.arms.split(","):
        fn = arms[name]
        out, in_tok = (fn(probes, gold, args.solver) if name in ("resolve", "rag", "compiled")
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
