#!/usr/bin/env python3
"""Adversarial review runner for compiler-extraction ablations (overlap + self-check).

Runs 4 preregistered ablations against the SAME frozen fixture and produces the review table:
  recall, conflicts, compile-cost, miss-taxonomy, and per-probe diffs vs the 82% baseline (A0).

The ablations:
  A0 baseline   — no overlap, no self-check (reproduce 82%)
  A1 overlap     — 4k-char chunk overlap, no self-check
  A2 self-check  — no overlap, verification pass
  A3 both        — 4k overlap + self-check

This script SCORES already-compiled variants (run killtest_compile.py first for each variant).
It does NOT run the LLM compiler itself — that's the gated Phase 1 step (requires API spend).
Phase 0 (this script) is fully deterministic: it scores whatever variant dirs exist and reports
the review table + miss taxonomy + per-probe diffs.

Frozen-fixture audit: every variant's compile-meta.json must carry matching corpus/probes/gold
SHA256s. A variant with a drifted fixture is rejected (the comparison would be invalid).

Usage:
  # Phase 0 — score existing variants (deterministic, no API):
  python3 killtest_adversarial.py --score-only

  # Phase 1 — compile all 4 variants then score (requires claude CLI + API key):
  python3 killtest_adversarial.py --compiler claude-sonnet-4-6 --compile
"""
import argparse
import hashlib
import json
import subprocess
import sys
import pathlib
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "killtest-outputs"
DECISIONS = HERE.parent.parent / "scripts" / "decisions.py"

# Preregistered ablation matrix (frozen before any live run)
ABLATIONS = {
    "baseline":  {"out_dir": "compiled-lib-baseline",  "overlap": 0,    "self_check": False},
    "overlap":   {"out_dir": "compiled-lib-overlap",   "overlap": 4000, "self_check": False},
    "selfcheck": {"out_dir": "compiled-lib-selfcheck", "overlap": 0,    "self_check": True},
    "both":      {"out_dir": "compiled-lib-both",      "overlap": 4000, "self_check": True},
}

OVERLAP_SIZE = 4000  # chars — preregistered


def _resolve(city, dim, root):
    r = subprocess.run([sys.executable, str(DECISIONS), "--root", str(root),
                        "resolve", "--text", f"{city} {dim}", "--no-stale-check"],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


def score_variant(variant_dir, probes, gold):
    """Score one compiled variant against gold. Returns a detailed result dict."""
    root = variant_dir / "decisions"
    if not root.exists():
        return {"error": f"no decisions dir at {root}"}

    hits = miss = conflict = 0
    per_probe = {}
    misses = []
    for p in probes:
        g = gold[p["id"]]
        res = _resolve(g["city"], g["dimension"], root)
        live = res.get("current", [])
        has_conflict = res.get("conflict", False)
        if has_conflict:
            conflict += 1
        titles = " | ".join(c["title"] for c in live)
        ok = (len(live) == 1 and g["current"] in titles
              and not any(a in titles for a in g["avoid"] if a != g["current"]))
        per_probe[p["id"]] = {
            "correct": ok,
            "conflict": has_conflict,
            "resolved_title": titles[:120],
            "gold_current": g["current"],
            "gold_chain": g["chain"],
            "n_results": len(live),
        }
        if ok:
            hits += 1
        else:
            miss += 1
            misses.append({
                "id": p["id"], "city": g["city"], "dimension": g["dimension"],
                "want": g["current"], "got": titles[:80], "chain": g["chain"],
            })

    # load compile meta
    meta_path = variant_dir / "compile-meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    return {
        "variant": variant_dir.name,
        "recall": hits,
        "total": len(probes),
        "recall_pct": round(hits / len(probes) * 100, 1),
        "conflicts": conflict,
        "compile_tokens": meta.get("compile_tokens", 0),
        "extracted_rows": meta.get("extracted_rows", 0),
        "adrs": meta.get("adrs", 0),
        "chains": meta.get("chains", 0),
        "integrity_clean": meta.get("integrity_clean", None),
        "overlap": meta.get("overlap", 0),
        "self_check": meta.get("self_check", False),
        "selfcheck_added": meta.get("selfcheck_added", 0),
        "selfcheck_fixed": meta.get("selfcheck_fixed", 0),
        "selfcheck_dropped": meta.get("selfcheck_dropped", 0),
        "per_probe": per_probe,
        "misses": misses,
        "corpus_sha256": meta.get("corpus_sha256"),
        "probes_sha256": meta.get("probes_sha256"),
        "gold_sha256": meta.get("gold_sha256"),
    }


def classify_miss(miss, gold_entry):
    """Classify a miss into the taxonomy. Returns one of:
    edge-split, mis-dated, omitted, invented, canonicalization, wrong-value, no-result.
    """
    got = miss["got"]
    chain = miss["chain"]
    want = miss["want"]

    if not got or got == " | ":
        return "no-result"  # resolve returned nothing

    # check if the resolved value is a superseded link from the chain (got an old value, not the current)
    for link in chain[:-1]:  # all except the last (current)
        if link.lower() in got.lower():
            return "wrong-value"  # resolve found an earlier link, not the current

    # check if the resolved value isn't in the chain at all (fabricated / canonicalization split)
    if not any(link.lower() in got.lower() for link in chain):
        return "invented"

    # check if the want value is missing from the resolved results entirely (omitted)
    if want.lower() not in got.lower():
        # the current value wasn't extracted at all → the chain is missing its final link
        return "omitted"

    return "wrong-value"


def miss_taxonomy(result):
    """Classify all misses in a result into the taxonomy."""
    gold = {g["id"]: g for g in json.loads((OUT / "gold.json").read_text())}
    taxonomy = Counter()
    for m in result["misses"]:
        g = gold[m["id"]]
        cat = classify_miss(m, g)
        taxonomy[cat] += 1
        m["taxonomy"] = cat
    return dict(taxonomy)


def per_probe_diff(baseline, variant):
    """Compare per-probe results vs the baseline. Returns flipped-correct→incorrect and vice versa."""
    flipped_to_wrong = []
    flipped_to_right = []
    for pid in baseline["per_probe"]:
        b_ok = baseline["per_probe"][pid]["correct"]
        v_ok = variant["per_probe"].get(pid, {}).get("correct")
        if v_ok is None:
            continue
        if b_ok and not v_ok:
            flipped_to_wrong.append(pid)
        elif not b_ok and v_ok:
            flipped_to_right.append(pid)
    return {"flipped_to_wrong": flipped_to_wrong, "flipped_to_right": flipped_to_right,
            "regressions": len(flipped_to_wrong), "recoveries": len(flipped_to_right)}


def audit_fixture(result, expected_hashes):
    """Verify the variant used the same frozen fixture as the baseline."""
    issues = []
    for name, expected in expected_hashes.items():
        actual = result.get(f"{name}_sha256")
        if actual is None:
            issues.append(f"missing {name}_sha256")
        elif actual != expected:
            issues.append(f"{name} hash mismatch (expected {expected[:12]}, got {(actual or '')[:12]})")
    return issues


def compile_variant(name, config, compiler):
    """Run killtest_compile.py for one variant. Returns the out-dir."""
    cmd = [sys.executable, str(HERE / "killtest_compile.py"),
           "--compiler", compiler, "--out-dir", config["out_dir"]]
    if config["overlap"]:
        cmd += ["--overlap", str(config["overlap"])]
    if config["self_check"]:
        cmd += ["--self-check"]
    print(f"  compiling {name} ({' '.join(cmd[4:])}) …", flush=True)
    r = subprocess.run(cmd, cwd=str(HERE))
    if r.returncode != 0:
        print(f"  FAIL: {name} exited {r.returncode}", file=sys.stderr)
        return None
    return OUT / config["out_dir"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compiler", default="claude-sonnet-4-6",
                    help="compiler model for Phase 1 live runs")
    ap.add_argument("--compile", action="store_true",
                    help="Phase 1: compile all 4 variants (requires API spend), then score")
    ap.add_argument("--score-only", action="store_true",
                    help="Phase 0: score existing variant dirs (deterministic, no API)")
    ap.add_argument("--variants", default="baseline,overlap,selfcheck,both",
                    help="comma-separated variant names to score/compile")
    args = ap.parse_args()

    if not args.compile and not args.score_only:
        args.score_only = True  # default to Phase 0

    probes = json.loads((OUT / "probes.json").read_text())
    gold = {g["id"]: g for g in json.loads((OUT / "gold.json").read_text())}

    # frozen-fixture hashes (from the baseline's compile-meta, or computed fresh)
    corpus_hash = hashlib.sha256((OUT / "corpus.md").read_bytes()).hexdigest()
    probes_hash = hashlib.sha256((OUT / "probes.json").read_bytes()).hexdigest()
    gold_hash = hashlib.sha256((OUT / "gold.json").read_bytes()).hexdigest()
    expected_hashes = {"corpus": corpus_hash, "probes": probes_hash, "gold": gold_hash}

    variants_to_run = args.variants.split(",")

    # Phase 1: compile variants that need it
    if args.compile:
        for name in variants_to_run:
            config = ABLATIONS[name]
            vdir = OUT / config["out_dir"]
            if (vdir / "extracted.json").exists() and not name == "baseline":
                print(f"  {name}: extracted.json exists, skipping compile (use --reassemble to force)")
                continue
            compile_variant(name, config, args.compiler)

    # Phase 0/1: score all variants
    results = {}
    print("\n" + "=" * 90)
    print("ADVERSARIAL REVIEW — compiler extraction ablations")
    print("=" * 90)

    for name in variants_to_run:
        config = ABLATIONS[name]
        vdir = OUT / config["out_dir"]
        if not (vdir / "decisions").exists():
            print(f"\n[{name}] SKIPPED — no compiled library at {vdir}")
            continue
        result = score_variant(vdir, probes, gold)
        if "error" in result:
            print(f"\n[{name}] ERROR: {result['error']}")
            continue
        # fixture audit
        issues = audit_fixture(result, expected_hashes)
        if issues:
            print(f"\n[{name}] FIXTURE AUDIT FAIL: {'; '.join(issues)}")
            continue
        # miss taxonomy
        tax = miss_taxonomy(result)
        result["miss_taxonomy"] = tax
        results[name] = result
        sc_info = ""
        if result.get("self_check"):
            sc_info = (f"  sc:added={result['selfcheck_added']} "
                       f"fixed={result['selfcheck_fixed']} "
                       f"dropped={result['selfcheck_dropped']}")
        print(f"\n[{name}] recall {result['recall']}/{result['total']} = {result['recall_pct']}%  "
              f"conflicts={result['conflicts']}  tokens={result['compile_tokens']}  "
              f"overlap={result['overlap']}  self_check={result['self_check']}  "
              f"integrity={'CLEAN' if result['integrity_clean'] else 'FAIL'}{sc_info}")
        print(f"  miss taxonomy: {tax}")
        for m in result["misses"]:
            print(f"  MISS {m['id']} {m['city']}/{m['dimension']}: want '{m['want']}' got '{m['got']}' "
                  f"[{m.get('taxonomy','?')}]")

    # per-probe diffs vs baseline
    if "baseline" in results:
        print("\n" + "-" * 90)
        print("PER-PROBE DIFFS vs baseline (A0)")
        print("-" * 90)
        for name, result in results.items():
            if name == "baseline":
                continue
            diff = per_probe_diff(results["baseline"], result)
            net = diff["recoveries"] - diff["regressions"]
            print(f"[{name:10}] recoveries={diff['recoveries']}  regressions={diff['regressions']}  "
                  f"net={net:+d}  recall {results['baseline']['recall']}→{result['recall']}")
            if diff["flipped_to_wrong"]:
                print(f"  REGRESSED: {', '.join(diff['flipped_to_wrong'])}")
            if diff["flipped_to_right"]:
                print(f"  RECOVERED: {', '.join(diff['flipped_to_right'])}")

    # summary table
    print("\n" + "=" * 90)
    print("SUMMARY TABLE")
    print("=" * 90)
    print(f"{'variant':12} {'recall':>8} {'conflicts':>10} {'tokens':>8} {'taxonomy':>40}")
    for name, r in results.items():
        tax_str = str(r.get("miss_taxonomy", {}))
        print(f"{name:12} {r['recall_pct']:>7}% {r['conflicts']:>10} {r['compile_tokens']:>8} {tax_str:>40}")

    # write results
    out_path = OUT / "adversarial-review-results.json"
    # strip per_probe from the saved file (it's verbose; the misses carry the detail)
    slim = {name: {k: v for k, v in r.items() if k != "per_probe"} for name, r in results.items()}
    if "baseline" in results:
        slim["diffs"] = {name: per_probe_diff(results["baseline"], r)
                         for name, r in results.items() if name != "baseline"}
    out_path.write_text(json.dumps(slim, indent=2) + "\n")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()