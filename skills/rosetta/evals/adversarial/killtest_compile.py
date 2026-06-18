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
     With --overlap N, chunks overlap by N chars so decisions split across chunk edges appear in full
     in at least one chunk (assemble dedupes the double-extraction).
  2. optional self-check pass (--self-check) — a second LLM call per chunk verifies each extracted row
     against the chunk and returns a diff (rows to fix/drop). The self-check sees ONLY the raw chunk +
     the extracted rows — never probes, gold, or the assembled ADRs (leakage control).
  3. deterministic assembly — group by (city, dimension), order by date, build ADRs with supersession
     (latest = current/Accepted, earlier = Superseded by next). IDs are assigned here (so id-hallucination
     is structurally impossible — a property of resolve-then-assemble), and Sources are transcript-style
     (`corpus · city · date`) so the ADR-0024 integrity gate validates structure + any ghost citations.
  4. gate + index — run `decisions.py validate --integrity` (recorded) and `index`.

Compile COST = sum of extraction-call tokens (+self-check tokens when enabled); reported so the
resolve-on-compiled arm can carry an amortized $/correct that includes it.

Variant isolation: --out-dir writes to a variant-specific directory so ablations don't clobber the
82% baseline. Default remains compiled-lib/ for backward compatibility.

Run: python3 killtest_compile.py [--compiler claude-sonnet-4-6] [--out-dir compiled-lib-overlap]
       [--overlap 4000] [--self-check] [--reassemble]
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import pathlib

import killtest_smoke as ks

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "killtest-outputs"
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

# Self-check prompt: verifies extracted rows against the raw chunk. NEVER sees probes/gold/assembled.
# Two functions:
#   1. CORRECT — fix wrong value/date on existing rows (a mis-dated row puts the wrong link as "current")
#   2. DROP — flag fabricated rows (not supported by the text)
#   3. MISSING — the chunk contains a (city, dimension) decision NOT in the extracted rows. This is the
#      "omitted" miss class: the chain's final/current decision was never extracted. The self-check can
#      ADD it back by emitting {"missing": true, "city":..., "dimension":..., "value":..., "date":...}.
# This is still chunk-scoped (only sees THIS chunk + ITS rows), so it can't invent rows from other chunks.
SELFCHECK = (
    "You are verifying extracted engineering decisions against the source text on stdin. Do three things:\n"
    "1. For each EXTRACTED row, if the value or date is WRONG, emit a correction (corrected_value and/or "
    "corrected_date). If the row is NOT supported by the text at all (fabricated), emit "
    "{\"drop\": true}. Correct rows are omitted.\n"
    "2. Look for decisions in the text that are NOT in the extracted rows — a (city, dimension) the text "
    "mentions but no row covers. For each MISSING decision, emit "
    "{\"missing\": true, \"city\":\"...\", \"dimension\":\"...\", \"value\":\"...\", "
    "\"date\":\"YYYY-MM-DD\"}.\n"
    "Reply with ONLY a ```json array of correction/drop/missing objects. No prose, no unchanged rows."
)


def slugify(s):
    s = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in s.lower())
    return re.sub(r"-+", "-", s).strip("-")


def _chunks_overlap(text, max_chars, overlap=0):
    """Split on record boundaries (## R...) into pieces under max_chars. If overlap > 0, each chunk
    (except the first) starts with the last `overlap` chars of the previous chunk, so decisions split
    across chunk boundaries appear in full in at least one chunk."""
    if overlap <= 0:
        return ks._chunks(text, max_chars)
    parts, buf = [], []
    size = 0
    tail = ""
    for block in re.split(r"(?=^## R\d)", text, flags=re.MULTILINE):
        if size + len(block) > max_chars and buf:
            chunk = "".join(buf)
            parts.append(chunk)
            # carry the last `overlap` chars as a prefix for the next chunk
            tail = chunk[-overlap:] if len(chunk) > overlap else chunk
            buf, size = [tail] if tail else [], len(tail)
        buf.append(block)
        size += len(block)
    if buf:
        parts.append("".join(buf))
    return parts


def _parse_json_array(text):
    """Extract a JSON array from a model reply (fenced or bare). Returns None on failure."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL) or \
        re.search(r"(\[\s*\{.*\}\s*\])", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except (json.JSONDecodeError, TypeError):
        return None


def extract(corpus, compiler, overlap=0):
    """Map-reduce extraction. Returns (decisions, rows_by_chunk, compile_tokens).
    Each decision row is tagged with _chunk (its source chunk index) so the self-check can verify
    a row against ONLY the chunk that produced it (leakage control: a chunk never adjudicates rows
    from other chunks, which would cause false drops)."""
    chunks = _chunks_overlap(corpus, 28_000, overlap)
    decisions, rows_by_chunk, compile_tokens = [], {}, 0
    for i, c in enumerate(chunks, 1):
        out = ks.run_model(compiler, EXTRACT, c)
        compile_tokens += len(c) // 4 + 2500
        arr = _parse_json_array(out)
        if arr is None:
            sys.stderr.write(f"chunk {i}: no JSON extracted\n")
            continue
        chunk_rows = []
        for d in arr:
            if {"city", "dimension", "value", "date"} <= set(d):
                d = dict(d)
                d["_chunk"] = i
                decisions.append(d)
                chunk_rows.append(d)
        rows_by_chunk[i] = chunk_rows
    return decisions, rows_by_chunk, compile_tokens


def self_check(corpus, compiler, decisions, rows_by_chunk, overlap=0, meta=None):
    """Verification pass: for each chunk, verify ONLY the rows extracted from THAT chunk against that
    same chunk. Returns (corrected_decisions, selfcheck_tokens). The self-check sees ONLY the raw chunk
    + its own rows — never probes, gold, or the assembled ADRs (leakage control). It returns a diff
    (rows to fix/drop), not a re-extraction. Rows from other chunks are never sent to this chunk, so a
    chunk can't drop rows it doesn't contain evidence for."""
    chunks = _chunks_overlap(corpus, 28_000, overlap)
    corrections = {}
    added_rows = []
    dropped_count = 0
    fixed_count = 0
    selfcheck_tokens = 0
    for i, c in enumerate(chunks, 1):
        chunk_rows = rows_by_chunk.get(i, [])
        if not chunk_rows:
            continue
        # strip _chunk metadata before sending to the model (it's internal bookkeeping)
        rows_clean = [{k: v for k, v in r.items() if k != "_chunk"} for r in chunk_rows]
        rows_json = json.dumps(rows_clean)
        out = ks.run_model(compiler, SELFCHECK, f"{c}\n\n--- EXTRACTED ROWS ---\n{rows_json}")
        selfcheck_tokens += len(c) // 4 + len(rows_json) // 4 + 2500
        arr = _parse_json_array(out)
        if arr is None:
            sys.stderr.write(f"self-check chunk {i}: no JSON extracted\n")
            continue
        for fix in arr:
            if fix.get("missing"):
                # MISSING row: the chunk contains a (city, dim, value, date) not in the extracted rows.
                # Validate the row shape (same keys as extract) before adding — the self-check can't
                # invent arbitrary rows, only ones it found in THIS chunk.
                if {"city", "dimension", "value", "date"} <= set(fix):
                    dim = fix["dimension"].strip().lower()
                    if dim in DIMS:
                        added_rows.append({"city": fix["city"].strip(), "dimension": dim,
                                           "value": fix["value"].strip(),
                                           "date": str(fix["date"]).strip()[:10], "_chunk": i})
                continue
            key = (i, fix.get("city", "").strip(), fix.get("dimension", "").strip().lower(),
                   fix.get("value", "").strip(), str(fix.get("date", "")).strip()[:10])
            if not key[1]:
                continue
            corrections[key] = fix
    # apply corrections: key includes _chunk so a drop from one chunk doesn't kill the duplicate
    # extracted from an overlapping chunk (the duplicate from the other chunk survives independently).
    # A row is only dropped if ALL chunks that extracted it drop it — tracked via a drop count.
    drop_counts = {}
    for d in decisions:
        ck = (d.get("_chunk"), d["city"].strip(), d["dimension"].strip().lower(),
              d["value"].strip(), str(d["date"]).strip()[:10])
        drop_counts[ck] = 0
    for (chunk_id, city, dim, val, dt), fix in corrections.items():
        if fix.get("drop"):
            ck = (chunk_id, city, dim, val, dt)
            if ck in drop_counts:
                drop_counts[ck] += 1
    # count how many chunks extracted each (city,dim,value,date) regardless of chunk id
    from collections import Counter
    dup_counts = Counter()
    for d in decisions:
        rk = (d["city"].strip(), d["dimension"].strip().lower(),
              d["value"].strip(), str(d["date"]).strip()[:10])
        dup_counts[rk] += 1
    drop_by_rowkey = Counter()
    for (chunk_id, city, dim, val, dt), cnt in drop_counts.items():
        if cnt > 0:
            rk = (city, dim, val, dt)
            drop_by_rowkey[rk] += cnt
    corrected = []
    for d in decisions:
        rk = (d["city"].strip(), d["dimension"].strip().lower(),
              d["value"].strip(), str(d["date"]).strip()[:10])
        chunk_id = d.get("_chunk")
        ck = (chunk_id, d["city"].strip(), d["dimension"].strip().lower(),
              d["value"].strip(), str(d["date"]).strip()[:10])
        fix = corrections.get(ck)
        if fix and fix.get("drop"):
            # only drop if ALL chunks that extracted this row also dropped it
            if drop_by_rowkey.get(rk, 0) >= dup_counts.get(rk, 1):
                continue
            # otherwise keep the row but skip applying the other-chunk's correction to it
        if fix and not fix.get("drop"):
            d = dict(d)
            if fix.get("corrected_value"):
                d["value"] = fix["corrected_value"].strip()
            if fix.get("corrected_date"):
                d["date"] = str(fix["corrected_date"]).strip()[:10]
        d_clean = {k: v for k, v in d.items() if k != "_chunk"}
        corrected.append(d_clean)
        if fix and not fix.get("drop"):
            fixed_count += 1
    # append missing rows discovered by the self-check (dedupe by (city,dim,value,date))
    seen = {(r["city"].strip(), r["dimension"].strip().lower(),
             r["value"].strip(), str(r["date"]).strip()[:10]) for r in corrected}
    for ar in added_rows:
        rk = (ar["city"].strip(), ar["dimension"].strip().lower(),
              ar["value"].strip(), str(ar["date"]).strip()[:10])
        if rk not in seen:
            corrected.append({k: v for k, v in ar.items() if k != "_chunk"})
            seen.add(rk)
    if meta is not None:
        meta["selfcheck_added"] = len([r for r in added_rows if (r["city"].strip(), r["dimension"].strip().lower(), r["value"].strip(), str(r["date"]).strip()[:10]) not in {(d["city"].strip(), d["dimension"].strip().lower(), d["value"].strip(), str(d["date"]).strip()[:10]) for d in decisions}])
        meta["selfcheck_dropped"] = sum(1 for d in decisions if (d.get("_chunk"), d["city"].strip(), d["dimension"].strip().lower(), d["value"].strip(), str(d["date"]).strip()[:10]) in drop_counts and drop_by_rowkey.get((d["city"].strip(), d["dimension"].strip().lower(), d["value"].strip(), str(d["date"]).strip()[:10]), 0) >= dup_counts.get((d["city"].strip(), d["dimension"].strip().lower(), d["value"].strip(), str(d["date"]).strip()[:10]), 1))
        meta["selfcheck_fixed"] = fixed_count
    return corrected, selfcheck_tokens


def assemble(decisions, lib_dir):
    """Group into (city, dimension) chains, dedupe, order by date, write ADRs with supersession."""
    adr_dir = lib_dir / "decisions" / "architecture-decisions"
    if adr_dir.exists():
        for f in adr_dir.glob("*.md"):
            f.unlink()
    adr_dir.mkdir(parents=True, exist_ok=True)
    cfg = {"record_types": {"adr": {"label": "ADR", "dir": "architecture-decisions",
                                    "title": "Architecture Decision Record"}},
           "statuses": ["Proposed", "Accepted", "Superseded", "Deprecated", "Rejected"],
           "required_fields": ["Status", "Date", "Decider"], "recommended_fields": ["Sources"],
           "number_width": 4}
    (lib_dir / "decisions" / ".rosetta-decisions.json").write_text(json.dumps(cfg, indent=2) + "\n")

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
    ap.add_argument("--out-dir", default="compiled-lib",
                    help="output directory under killtest-outputs/ (variant isolation: e.g. "
                         "compiled-lib-overlap, compiled-lib-selfcheck, compiled-lib-both)")
    ap.add_argument("--overlap", type=int, default=0,
                    help="chunk overlap in chars (e.g. 4000); 0 = no overlap (the baseline)")
    ap.add_argument("--self-check", action="store_true",
                    help="run a verification pass after extraction (adds compile cost; never sees "
                         "probes/gold/assembled — leakage control)")
    ap.add_argument("--reassemble", action="store_true",
                    help="skip extraction; re-assemble from a saved extracted.json (free, for tuning "
                         "the assembly/canonicalization step)")
    args = ap.parse_args()

    lib_dir = OUT / args.out_dir
    lib_dir.mkdir(parents=True, exist_ok=True)
    rows_path = lib_dir / "extracted.json"

    selfcheck_meta = {}
    if args.reassemble and rows_path.exists():
        saved = json.loads(rows_path.read_text())
        decisions, compile_tokens = saved["rows"], saved["compile_tokens"]
        print(f"re-assembling from {len(decisions)} saved rows (no API calls)")
    else:
        corpus = (OUT / "corpus.md").read_text()
        print(f"compiling with {args.compiler} (overlap={args.overlap}) …", flush=True)
        decisions, rows_by_chunk, compile_tokens = extract(corpus, args.compiler, args.overlap)
        if args.self_check:
            print(f"self-check pass (verifying {len(decisions)} rows against corpus) …", flush=True)
            decisions, sc_tokens = self_check(corpus, args.compiler, decisions, rows_by_chunk,
                                              args.overlap, meta=selfcheck_meta)
            compile_tokens += sc_tokens
            print(f"self-check: {sc_tokens} tokens, {len(decisions)} rows after corrections "
                  f"(added={selfcheck_meta.get('selfcheck_added',0)} "
                  f"fixed={selfcheck_meta.get('selfcheck_fixed',0)} "
                  f"dropped={selfcheck_meta.get('selfcheck_dropped',0)})")
        # strip _chunk metadata before saving (it's internal to this run)
        rows_clean = [{k: v for k, v in d.items() if k != "_chunk"} for d in decisions]
        rows_path.write_text(json.dumps({"rows": rows_clean, "compile_tokens": compile_tokens}) + "\n")

    n_adrs, n_chains = assemble(decisions, lib_dir)
    print(f"extracted {len(decisions)} decision rows → {n_adrs} ADRs across {n_chains} (city,dim) chains")
    print(f"compile cost ≈ {compile_tokens} tokens")

    root = str(lib_dir / "decisions")
    subprocess.run([sys.executable, str(DECISIONS), "--root", root, "index"],
                   capture_output=True, text=True)
    ig = subprocess.run([sys.executable, str(DECISIONS), "--root", root, "integrity"],
                        capture_output=True, text=True)
    print(f"integrity gate: {'CLEAN' if ig.returncode == 0 else 'VIOLATIONS'}")
    if ig.returncode != 0:
        print(ig.stdout[-600:])

    # record the corpus hash for frozen-fixture audit
    corpus_hash = hashlib.sha256((OUT / "corpus.md").read_bytes()).hexdigest()
    probes_hash = hashlib.sha256((OUT / "probes.json").read_bytes()).hexdigest()
    gold_hash = hashlib.sha256((OUT / "gold.json").read_bytes()).hexdigest()
    (lib_dir / "compile-meta.json").write_text(json.dumps(
        {"compiler": args.compiler, "compile_tokens": compile_tokens,
         "extracted_rows": len(decisions), "adrs": n_adrs, "chains": n_chains,
         "integrity_clean": ig.returncode == 0,
         "overlap": args.overlap, "self_check": args.self_check,
         "selfcheck_added": selfcheck_meta.get("selfcheck_added", 0),
         "selfcheck_fixed": selfcheck_meta.get("selfcheck_fixed", 0),
         "selfcheck_dropped": selfcheck_meta.get("selfcheck_dropped", 0),
         "corpus_sha256": corpus_hash,
         "probes_sha256": probes_hash,
         "gold_sha256": gold_hash}, indent=2) + "\n")
    print(f"wrote {lib_dir}")


if __name__ == "__main__":
    main()