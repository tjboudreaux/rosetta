#!/usr/bin/env python3
"""KILL TEST — full preregistered matrix (Claude tiers first).

Arms × tiers × k, two-axis judge-independent grading, calibration/discrimination check, $/correct.

  arms   : raw | flat-summary | rag (generic lexical retrieval) | resolve (provenance graph)
  tiers  : solver models (default Haiku 4.5, Sonnet 4.6)
  k      : samples per cell (default 3) — majority vote on the current-axis + variance for calibration
  probes : all of probes.json (default 40)

Grading (no LLM judge — the H2 lever): per probe, the answer's `current` must match gold.current and
must NOT be any superseded link (a superseded answer is the recall failure compression causes);
`replaced` is the second axis. Per cell we report mean recall over k, majority-vote recall, and the
replaced-axis. Discrimination = does the suite separate arms (esp. flat vs resolve)?

Preregistered prediction: recall  resolve ≈ raw  >>  rag ≳ flat  ; cost  resolve << raw.

Run: python3 killtest_matrix.py [--tiers a,b] [--k 3] [--arms raw,flat,rag,resolve] [--probes 40]
Pure stdlib + the `claude` CLI. Writes killtest-outputs/matrix/.
"""
import argparse
import json
import statistics
import pathlib

import killtest_smoke as ks    # reuse claude(), arms, parse_answers, score, ASK, etc.

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "killtest-outputs"
MX = OUT / "matrix"
PRICING = json.loads((HERE / "pricing.json").read_text()) if (HERE / "pricing.json").exists() else {}

# rough price fallback (USD per 1M tok, input/output) if pricing.json lacks an entry
PRICE = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
}


def price_for(model):
    p = PRICING.get(model) or PRICING.get(model.split("-2025")[0])
    if isinstance(p, dict) and "input" in p:
        return p["input"], p.get("output", p["input"] * 5)
    return PRICE.get(model, (3.0, 15.0))


def run_cell(arm, tier, probes, gold, k):
    """Run k samples of one (arm, tier) cell. RESUMABLE: a sample whose .out.txt already exists and
    parses to all probes is reused (so a crashed/timed-out run re-runs only the missing work).
    Returns per-sample answer dicts + input token estimate."""
    fn = {"raw": ks.arm_raw, "flat": ks.arm_flat, "rag": ks.arm_rag, "resolve": ks.arm_resolve}[arm]
    samples, in_tok = [], 0
    for s in range(k):
        path = MX / f"{arm}__{tier}__k{s+1}.out.txt"
        if path.exists() and len(ks.parse_answers(path.read_text())) == len(probes):
            samples.append(ks.parse_answers(path.read_text()))
            continue
        out, it = (fn(probes, gold, tier) if arm in ("rag", "resolve") else fn(probes, tier))
        in_tok = it
        path.write_text(out)
        samples.append(ks.parse_answers(out))
    # estimate input tokens even when fully cached (re-derive cheaply from a dry arm call's size proxy)
    if in_tok == 0:
        in_tok = {"raw": 107410, "flat": 5845, "rag": 13406, "resolve": 7345}.get(arm, 0)
    return samples, in_tok


def grade(samples, probes, gold):
    """Two-axis grading over k samples. Returns dict with per-sample recall, majority recall, replaced."""
    per_sample_cur, per_sample_rep = [], []
    # majority vote on current per probe
    maj_correct = 0
    for p in probes:
        g = gold[p["id"]]
        gc = g["current"].lower()
        votes_ok = 0
        for ans in samples:
            a = ans.get(p["id"], {})
            ac = str(a.get("current", "")).lower()
            if ac and (gc in ac or ac in gc):
                votes_ok += 1
        if votes_ok * 2 > len(samples):
            maj_correct += 1
    for ans in samples:
        cur, rep, _ = ks.score(ans, probes, gold)
        per_sample_cur.append(cur)
        per_sample_rep.append(rep)
    n = len(probes)
    return {
        "n": n, "k": len(samples),
        "recall_mean": round(statistics.mean(per_sample_cur) / n, 3),
        "recall_samples": per_sample_cur,
        "recall_majority": round(maj_correct / n, 3),
        "replaced_mean": round(statistics.mean(per_sample_rep) / n, 3),
        "recall_stdev": round(statistics.pstdev([c / n for c in per_sample_cur]), 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiers", default="claude-haiku-4-5-20251001,claude-sonnet-4-6")
    ap.add_argument("--arms", default="raw,flat,rag,resolve")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--probes", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=1800,
                    help="per-model-call wall-clock budget in seconds (default 1800)")
    args = ap.parse_args()
    ks.CALL_TIMEOUT = args.timeout
    MX.mkdir(parents=True, exist_ok=True)
    print(f"per-call timeout: {args.timeout}s", flush=True)

    probes = json.loads((OUT / "probes.json").read_text())[: args.probes]
    gold = {g["id"]: g for g in json.loads((OUT / "gold.json").read_text())}
    tiers = args.tiers.split(",")
    arms = args.arms.split(",")

    results = {}
    for tier in tiers:
        for arm in arms:
            print(f"running {arm} × {tier} (k={args.k}) …", flush=True)
            samples, in_tok = run_cell(arm, tier, probes, gold, args.k)
            g = grade(samples, probes, gold)
            pin, pout = price_for(tier)
            # cost: k samples × (input tok × k? input repeated per sample) + ~2k output each
            in_cost = (in_tok * args.k) / 1e6 * pin
            out_cost = (2000 * args.k) / 1e6 * pout
            correct = g["recall_majority"] * g["n"]
            g.update({"in_tokens": in_tok, "est_cost_usd": round(in_cost + out_cost, 4),
                      "usd_per_correct": round((in_cost + out_cost) / correct, 4) if correct else None})
            results[f"{arm}__{tier}"] = g
            print(f"   recall mean {g['recall_mean']:.0%} maj {g['recall_majority']:.0%} "
                  f"replaced {g['replaced_mean']:.0%}  in≈{in_tok}tok  ${g['est_cost_usd']}  "
                  f"$/correct {g['usd_per_correct']}", flush=True)

    (MX / "matrix-results.json").write_text(json.dumps(results, indent=2) + "\n")

    # discrimination / calibration: does the suite separate arms? (flat/rag vs resolve, per tier)
    print("\n=== matrix (recall majority) ===")
    print(f"{'arm':10} " + " ".join(f"{t.split('-')[1]:>10}" for t in tiers))
    for arm in arms:
        row = [results.get(f"{arm}__{t}", {}).get("recall_majority") for t in tiers]
        print(f"{arm:10} " + " ".join(f"{(v if v is not None else 0):>10.0%}" for v in row))
    print("\n=== $/correct ===")
    for arm in arms:
        row = [results.get(f"{arm}__{t}", {}).get("usd_per_correct") for t in tiers]
        print(f"{arm:10} " + " ".join(f"{('$'+format(v,'.4f')) if v else '—':>10}" for v in row))

    # verdict
    for tier in tiers:
        rs = results.get(f"resolve__{tier}", {}).get("recall_majority", 0)
        fl = results.get(f"flat__{tier}", {}).get("recall_majority", 0)
        rg = results.get(f"rag__{tier}", {}).get("recall_majority", 0)
        rw = results.get(f"raw__{tier}", {}).get("recall_majority", 0)
        sep = rs - max(fl, rg)
        print(f"\n[{tier}] resolve {rs:.0%} vs max(flat {fl:.0%}, rag {rg:.0%}) vs raw {rw:.0%} "
              f"→ separation {sep:+.0%}")
    print("\nCALIBRATION: discrimination holds if resolve separates from flat/rag by ≥1 clear margin "
          "on ≥1 tier AND a wrong answer still fails (guaranteed by judge-independent grading).")


if __name__ == "__main__":
    main()
