# Adversarial Review — Preregistration

> **SUPERSEDED (2026-06-18):** The live A0 gate scored 40/40 (100%), eliminating the 18% compiler gap
> this review was designed to close. A1–A3 are BLOCKED / NOT RUN — with the gap at 0%, the ablations
> are not interpretable. See `ADVERSARIAL-REVIEW-FINDINGS.md` for the full analysis. The frozen
> ablation matrix, prompts, and infrastructure below remain valid for a future model regression.

**Frozen before any live compiler run.** This document commits the ablation matrix, prompts,
parameters, and scoring methodology *before* seeing Phase 1 results. No post-hoc tuning of the
overlap size, self-check prompt, or scoring after results are observed.

## Frozen fixture (SHA256s)

| Artifact | SHA256 |
|---|---|
| `killtest-outputs/corpus.md` | `845ad39e088dd12cf17e6d079259bb7ce17c88fd27650e616103c0e525680e50` |
| `killtest-outputs/probes.json` | `d416de5456d31046e4ea384ee567d60c42ccffb6d4a61ffef5bce5a09f6d8780` |
| `killtest-outputs/gold.json` | `e40c9e7d8e5c522ba6eeec2493f42c6852ec962b677f727f9a1905f69d67f83d` |

Every variant's `compile-meta.json` must carry matching SHA256s. A variant with a drifted fixture
is rejected by `killtest_adversarial.py` — the comparison would be invalid.

## Baseline (A0) — reproduced from saved `extracted.json`

- **Recall:** 33/40 = **82.5%** (matches the KILLTEST-RESULTS hardening-pass-2 finding)
- **Conflicts:** 0
- **Integrity:** CLEAN (ADR 0024 gate)
- **Compile tokens:** 145,924
- **Extracted rows:** 1,237 → 929 ADRs across 340 (city,dim) chains
- **Miss taxonomy:** all 7 misses are `wrong-value` (resolve returns an earlier superseded link,
  not the current — the chain's final decision was either omitted or mis-dated so supersession
  order put an older value as "Accepted")

## Ablation matrix (preregistered)

| Variant | Out-dir | Overlap | Self-check | Purpose |
|---|---|---|---|---|
| **A0 baseline** | `compiled-lib-baseline` | 0 | no | control (reproduce 82%) |
| **A1 overlap** | `compiled-lib-overlap` | 4,000 chars | no | isolate Fix A (edge-split) |
| **A2 selfcheck** | `compiled-lib-selfcheck` | 0 | yes | isolate Fix B (correct/missing/drop) |
| **A3 both** | `compiled-lib-both` | 4,000 chars | yes | combined fix |

- **Overlap size:** 4,000 chars (~1k tokens). Preregistered; not tuned after results.
- **Compiler model:** `claude-sonnet-4-6` (same as the baseline run).
- **Chunk size:** 28,000 chars (unchanged from baseline).

## Prompts (preregistered, frozen)

### EXTRACT (extraction — unchanged from baseline)
```
From the engineering decision history on stdin, extract EVERY architecture decision/migration.
For each, output the service codename (a city), the dimension (one of: session-auth, datastore,
message-bus, cache, deploy-target), the chosen value (verbatim, e.g. 'PASETO v4 (local)'), and the
date (YYYY-MM-DD). Include superseded/old decisions too — every decision, not just the latest.
Reply with ONLY a ```json fenced array of {"city":"...","dimension":"...","value":"...",
"date":"YYYY-MM-DD"} objects, no prose.
```

### SELFCHECK (verification — chunk-scoped, never sees probes/gold/assembled)
```
You are verifying extracted engineering decisions against the source text on stdin. Do three things:
1. For each EXTRACTED row, if the value or date is WRONG, emit a correction (corrected_value and/or
   corrected_date). If the row is NOT supported by the text at all (fabricated), emit {"drop": true}.
   Correct rows are omitted.
2. Look for decisions in the text that are NOT in the extracted rows — a (city, dimension) the text
   mentions but no row covers. For each MISSING decision, emit
   {"missing": true, "city":"...", "dimension":"...", "value":"...", "date":"YYYY-MM-DD"}.
Reply with ONLY a ```json array of correction/drop/missing objects. No prose, no unchanged rows.
```

## Leakage controls (non-negotiable)

1. **Self-check sees only raw chunk + that chunk's extracted rows.** Never probes, gold, or
   assembled ADRs. The `_chunk` tag tracks provenance; a chunk only adjudicates its own rows.
2. **Missing rows are chunk-scoped.** The self-check can only add a missing row for a decision
   found in THAT chunk — it cannot invent rows from other chunks.
3. **Drop logic is consensus-based.** With overlap, the same row may be extracted from two chunks.
   A row is only dropped if ALL chunks that extracted it also drop it (`drop_by_rowkey >= dup_counts`).
4. **Corrections are chunk-scoped.** A correction from chunk N only applies to the row from chunk N,
   not to the duplicate from chunk M (which may have different evidence).
5. **No probe-shaped queries.** The self-check verifies row support, not "does Darwin use k8s?"
6. **Frozen corpus hash.** Verified before scoring.

## What the review measures (beyond ">82%")

Each ablation reports:
1. **Recall** — correct/40, with per-probe breakdown
2. **Regressions** — did any already-correct chain flip to wrong? (A self-check that second-guesses
   right answers is a failure even if net recall rises)
3. **Conflicts** — must stay 0 (overlap dedupe failure → split chains → conflict)
4. **Compile cost** — tokens (overlap increases chunk count; self-check doubles extraction calls)
5. **Miss taxonomy** — edge-split, mis-dated, omitted, invented, canonicalization, wrong-value
6. **Integrity** — every variant must pass the ADR-0024 gate
7. **Self-check counts** — added/fixed/dropped (for A2/A3)

## Execution

- **Phase 0 (deterministic, no API):** `killtest_adversarial.py --score-only` — scores existing
  variant dirs. A0 is verified. A1/A2/A3 require Phase 1.
- **Phase 1 (live compiler, gated):** `killtest_adversarial.py --compiler claude-sonnet-4-6 --compile`
  — compiles all 4 variants, then scores. Requires `claude` CLI + API key.
- **Phase 2 (adversarial adjudication):** inspect per-probe diffs, regressions, cost-correctness
  tradeoff, and miss-taxonomy shifts. A fix that improves recall by fixing the *wrong* miss class
  is a confound to report.

## Acceptance

The review is **complete** when all 4 ablations are scored with per-probe diffs, no regressions are
hidden, the self-check is audited for leakage, integrity passes on all variants, and the
cost-correctness tradeoff is evaluated. The review **does not require recall > 82% to be a success**
— a well-run review that finds the fixes are confounded or not worth the cost is a successful review.
