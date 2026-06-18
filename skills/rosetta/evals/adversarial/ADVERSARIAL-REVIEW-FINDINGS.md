# Adversarial Review — Findings

## Outcome: GATE FAILED — compiler drift eliminated the measured 82% gap

The live A0 gate was designed to verify that a fresh `claude-sonnet-4-6` compile reproduces the saved
baseline's 82% recall before running the overlap/self-check ablations (A1–A3). **It did not reproduce
it** — the live compile scored **40/40 (100%)**, recovering all 7 baseline misses with 0 regressions.

**A1–A3 (overlap, self-check, both) are BLOCKED / NOT RUN.** The preregistered review is not
interpretable because the premise — an 18% compiler-quality gap to close — no longer holds.

## Evidence

| Metric | Saved baseline (A0) | Live A0 |
|---|---|---|
| Recall | 33/40 = 82.5% | 40/40 = 100% |
| Conflicts | 0 | 0 |
| Integrity | CLEAN | CLEAN |
| Extracted rows | 1,237 | 1,259 (+22) |
| ADRs | 929 | 1,024 (+95) |
| Chains | 340 | 340 (same) |
| Compile tokens | 145,924 | 145,924 (same) |

Gate artifact: `killtest-outputs/gate-compiled-lib-baseline-live.json`

## Root cause: the live compiler extracts the final/current decision for all 7 miss chains

The saved baseline's 7 misses were all `wrong-value` — resolve returned an earlier superseded link
because the chain's final (current) decision was never extracted. The live compiler extracted those
missing final decisions:

| Probe | City/Dim | Want (current) | Saved chain | Live chain |
|---|---|---|---|---|
| Q004 | Jakarta/message-bus | NATS JetStream | 1 row (SQS) | 2 rows (+ NATS JetStream 2026-07-03) |
| Q006 | Faro/deploy-target | HashiCorp Nomad | 3 rows | 4 rows (+ Nomad 2026-04-03) |
| Q017 | Ballina/message-bus | Apache Kafka | 3 rows | 4 rows (+ Kafka 2026-03-20) |
| Q025 | Barwon/datastore | CockroachDB | 1 row (DynamoDB) | 2 rows (+ CockroachDB 2026-03-16) |
| Q026 | Eltham/deploy-target | GKE Autopilot | 4 rows | 5 rows (+ GKE Autopilot 2026-02-26) |
| Q034 | Delft/datastore | MySQL 8 | 4 rows | 5 rows (+ MySQL 8 2026-03-13) |
| Q038 | Limerick/session-auth | mutual-TLS client certs | 1 row (PASETO) | 2 rows (+ mTLS 2026-03-02) |

In every case, the live compiler found the final/current decision that the saved baseline missed.
The chains have the same structure (340 (city,dim) pairs in both) — the live compiler just extracted
more complete chains.

## What this means

1. **The 18% compiler-quality gap (KILLTEST-RESULTS hardening-pass-2) is stale.** The
   `claude-sonnet-4-6` model (via OAuth-routed `claude` CLI) now extracts all 40 chains' current
   decisions correctly. The gap was a model-quality artifact of the original compile run, not a
   structural deficiency in the chunking or extraction approach.

2. **The overlap/self-check ablations are not interpretable.** A1 (overlap) and A2 (self-check)
   were designed to close the 18% gap by fixing edge-split and omitted/mis-dated decisions. With
   the gap already at 0%, there's nothing to improve — any recall change would be noise, not signal.

3. **The review infrastructure worked as designed.** The gate caught the drift before spending API
   budget on 3 ablation compiles (A1–A3 × 16 chunks each × ~2 min/chunk = ~96 min of API spend).
   The per-chunk checkpointing preserved the live A0 spend across two timeout-resume cycles.

## What was built (still valuable)

The adversarial review infrastructure is complete and reusable for future compiler-quality reviews:

- **Variant isolation** (`--out-dir`, `--lib-dir`) — ablations don't clobber baselines
- **Chunk-provenance self-check** — leakage-controlled verification (correct/drop/missing)
- **Per-chunk checkpointing** with param + row-hash validation — timeout-safe resume
- **Gate-only path** (`--score-dir`) — verifies live A0 before running ablations
- **Strict skip guard** — requires complete, valid, param-matching artifacts before skipping a compile
- **Miss-taxonomy classifier** + per-probe diff comparator — the scoring the review would use
- **Preregistration** — frozen fixture, prompts, overlap size, leakage controls, acceptance criteria

## Recommendation

Update the KILLTEST-RESULTS to reflect that the compiler arm now reaches 100% on the 40-probe
harness with the current `claude-sonnet-4-6`. The `compiled-lib/extracted.json` (the saved 82%
baseline) should be refreshed with the live 100% extraction so the matrix's `compiled` arm reflects
current model quality. The overlap/self-check fixes remain available if a future model regression
reintroduces extraction gaps — the infrastructure is ready to run them.
