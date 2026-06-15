#!/usr/bin/env python3
"""KILL TEST — end-to-end compiled-library arm: build the decision library with an LLM (not the
deterministic ground truth), so resolve measures REAL Rosetta, compile cost + compiler fallibility
folded in.

The matrix's `resolve` arm queries a deterministic ground-truth library — that measures the resolution
mechanism's recall CEILING. This script instead has an LLM *compile* the library from the raw corpus, so
the resolve-on-compiled arm reflects what a user actually gets:

  1. map-reduce extraction — each ~22k-token corpus chunk → the compiler model emits JSON decisions
     {city, dimension, value, date} for every decision/migration it sees (it may mis-read, miss, or
     invent — that is the fallibility we want to measure). The compiler never sees the probes.
  2. deterministic assembly — group by (city, dimension), order by date, build ADRs with supersession
     (latest = current/Accepted, earlier = Superseded by next). IDs are assigned here (so id-hallucination
     is structurally impossible — a property of resolve-then-assemble), and Sources are transcript-style
     (`corpus · city · date`) so the ADR-0024 integrity gate validates structure + any ghost citations.
  3. gate + index — run `decisions.py validate --integrity` (recorded) and `index`.

Compile COST = sum of extraction-call tokens; reported so the resolve-on-compiled arm can carry an
amortized $/correct that includes it. Writes killtest-outputs/compiled-lib/.

Run: python3 killtest_compile.py [--compiler claude-sonnet-4-6]
"""
import argparse
import json
import re
import subprocess
import sys
import pathlib

import killtest_smoke as ks

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "killtest-outputs"
LIB = OUT / "compiled-lib"
DECISIONS = HERE.parent.parent / "scripts" / "decisions.py"

DIMS = ["session-auth", "datastore", "message-bus", "cache", "deploy-target"]

EXTRACT = (
    "From the engineering decision history on stdin, extract EVERY architecture decision/migration. "
    "For each, output the service codename (a city), the dimension (one of: session-auth, datastore, "
    "message-bus, cache, deploy-target), the chosen value (verbatim, e.g. 'PASETO v4 (local)'), and the "
    "date (YYYY-MM-DD). Include superseded/old decisions too — every decision, not just the latest. "
    "Reply with ONLY a ```json fenced array of {\"city\":\"...\",\"dimension\":\"...\",\"value\":\"...\","
    "\"date\":\"YYYY-MM-DD\"} objects, no prose."
)


def slugify(s):
    s = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in s.lower())
    return re.sub(r"-+", "-", s).strip("-")


def extract(corpus, compiler):
    # ~7k-token chunks: a 22k chunk has hundreds of decisions and blows the 32k output cap when the
    # model emits JSON for all of them. Smaller chunks keep each extraction's output within budget.
    chunks = ks._chunks(corpus, 28_000)
    decisions, compile_tokens = [], 0
    for i, c in enumerate(chunks, 1):
        out = ks.run_model(compiler, EXTRACT, c)
        compile_tokens += len(c) // 4 + 2500          # input + rough output budget
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", out, re.DOTALL) or \
            re.search(r"(\[\s*\{.*\}\s*\])", out, re.DOTALL)
        if not m:
            sys.stderr.write(f"chunk {i}: no JSON extracted\n")
            continue
        try:
            for d in json.loads(m.group(1)):
                if {"city", "dimension", "value", "date"} <= set(d):
                    decisions.append(d)
        except (json.JSONDecodeError, TypeError):
            sys.stderr.write(f"chunk {i}: JSON parse failed\n")
    return decisions, compile_tokens


def assemble(decisions):
    """Group into (city, dimension) chains, dedupe, order by date, write ADRs with supersession."""
    adr_dir = LIB / "decisions" / "architecture-decisions"
    if adr_dir.exists():
        for f in adr_dir.glob("*.md"):
            f.unlink()
    adr_dir.mkdir(parents=True, exist_ok=True)
    cfg = {"record_types": {"adr": {"label": "ADR", "dir": "architecture-decisions",
                                    "title": "Architecture Decision Record"}},
           "statuses": ["Proposed", "Accepted", "Superseded", "Deprecated", "Rejected"],
           "required_fields": ["Status", "Date", "Decider"], "recommended_fields": ["Sources"],
           "number_width": 4}
    (LIB / "decisions" / ".rosetta-decisions.json").write_text(json.dumps(cfg, indent=2) + "\n")

    chains = {}
    for d in decisions:
        # Entity canonicalization (the compile-time alias step): the LLM emits the same codename with
        # drifting casing/whitespace across chunks ('Cordoba' vs 'cordoba'); without normalizing, each
        # variant becomes a separate chain and resolve correctly flags a CONFLICT instead of an answer.
        # This models the canonicalization a real provenance compiler must do — it is NOT probe leakage.
        dim = d["dimension"].strip().lower()
        if dim not in DIMS:
            continue
        key = (" ".join(d["city"].strip().split()).title(), dim)
        chains.setdefault(key, {})
        # dedupe by value, keep earliest date seen for that value
        v = d["value"].strip()
        dt = str(d["date"]).strip()[:10]
        if v not in chains[key] or dt < chains[key][v]:
            chains[key][v] = dt

    n = 0
    for (city, dim), vmap in sorted(chains.items()):
        links = sorted(vmap.items(), key=lambda kv: kv[1])      # (value, date) by date
        ids = list(range(n + 1, n + 1 + len(links)))
        for j, (val, date) in enumerate(links):
            num = ids[j]
            is_last = j == len(links) - 1
            status = "Accepted" if is_last else f"Superseded by ADR {ids[j + 1]:04d}"
            lines = [f"# ADR {num:04d} — {city} {dim}: {val}", "",
                     f"- Status: {status}", f"- Date: {date}", f"- Decider: {city} pod",
                     f"- Sources: `corpus · {city} · {date}`"]
            if j > 0:
                lines.append(f"- Supersedes: ADR {ids[j - 1]:04d}")
            lines += ["", "## Decision", "", f"{city} uses **{val}** for {dim}."]
            (adr_dir / f"{num:04d}-{slugify(city + '-' + dim + '-' + val.split()[0])}.md").write_text(
                "\n".join(lines) + "\n")
        n += len(links)
    return n, len(chains)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compiler", default="claude-sonnet-4-6")
    ap.add_argument("--reassemble", action="store_true",
                    help="skip extraction; re-assemble from a saved extracted.json (free, for tuning "
                         "the assembly/canonicalization step)")
    args = ap.parse_args()
    LIB.mkdir(parents=True, exist_ok=True)
    rows_path = LIB / "extracted.json"

    if args.reassemble and rows_path.exists():
        saved = json.loads(rows_path.read_text())
        decisions, compile_tokens = saved["rows"], saved["compile_tokens"]
        print(f"re-assembling from {len(decisions)} saved rows (no API calls)")
    else:
        corpus = (OUT / "corpus.md").read_text()
        print(f"compiling with {args.compiler} …", flush=True)
        decisions, compile_tokens = extract(corpus, args.compiler)
        rows_path.write_text(json.dumps({"rows": decisions, "compile_tokens": compile_tokens}) + "\n")
    n_adrs, n_chains = assemble(decisions)
    print(f"extracted {len(decisions)} decision rows → {n_adrs} ADRs across {n_chains} (city,dim) chains")
    print(f"compile cost ≈ {compile_tokens} tokens")

    root = str(LIB / "decisions")
    subprocess.run([sys.executable, str(DECISIONS), "--root", root, "index"],
                   capture_output=True, text=True)
    ig = subprocess.run([sys.executable, str(DECISIONS), "--root", root, "integrity"],
                        capture_output=True, text=True)
    print(f"integrity gate: {'CLEAN' if ig.returncode == 0 else 'VIOLATIONS'}")
    if ig.returncode != 0:
        print(ig.stdout[-600:])

    (LIB / "compile-meta.json").write_text(json.dumps(
        {"compiler": args.compiler, "compile_tokens": compile_tokens,
         "extracted_rows": len(decisions), "adrs": n_adrs, "chains": n_chains,
         "integrity_clean": ig.returncode == 0}, indent=2) + "\n")
    print(f"wrote {LIB}")


if __name__ == "__main__":
    main()
