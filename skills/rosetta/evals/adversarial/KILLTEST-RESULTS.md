# Kill test — large, high-compression recall experiment (results)

The decisive thesis experiment: **does a code-anchored, supersession-resolved decision graph recover
the factual recall that flat compression loses?** Goals 1 & 2 returned NULL only because their corpora
(~1k tokens) had no compression pressure. This fixture restores it — and the answer, on the first
valid run, is **yes**.

## Apparatus (Stage 1 — validated with ZERO API spend)
`killtest_gen.py` emits a deterministic, seeded fixture: **118 services × 2–4 decision dimensions**,
each dimension a **supersession chain** (length 2–4). Evidence (eng-log + code + dashboard + stale
docs) is interleaved by date so a chain's links are scattered far apart.

- **corpus.md**: ~106k tokens, **1025 decisions**, of which **685 are superseded distractors + stale
  docs**; only 340 are current. → **21.2:1** compression to a 5k-token summary.
- **decisions/**: a ground-truth, **integrity-clean** (ADR 0024 gate), resolvable library built
  deterministically from the chains (this tests the *resolution mechanism's* recall ceiling, not the
  fallible LLM compiler — compile cost is accounted separately).
- `killtest_validate.py` (no model calls) proves: integrity **CLEAN**; `resolve` recovers
  **40/40 = 100%** of current endpoints with **zero conflicts**; a naive positional 5k slice already
  carries only 18/40 (45%).

## Smoke run (Stage 2 — real models, go/no-go before the full matrix)
Three arms, **same cheap solver (Haiku 4.5)**, same 10 probes, answers scored against gold
(current-correct = recall; a current that names a *superseded* link is a recall failure):

| Arm | What the solver sees | **Recall (current)** | Input tokens |
|---|---|---|---|
| **A1 raw** | the full ~106k corpus | 8 / 10 | ~106,000 |
| **A2 flat-summary** | a ~4.4k map-reduce summary (Sonnet compressed the corpus once; never saw the probes) | **3 / 10** | ~4,817 |
| **A4 resolve** | per-probe `decisions.py resolve` output | **10 / 10** | ~1,673 |

**Separation confirmed, all arms valid:**
- **Flat compression loses recall:** 8 → 3 (a ~50-pt drop) at a realistic fixed budget — at or beyond
  the 33–35-pt loss the memory-benchmark literature reports.
- **The resolved graph recovers it fully and then some:** 10/10 at **1.5% of raw's tokens**, and it
  **beats raw** — raw Haiku twice picked a *superseded* value (lost-in-the-middle / distractor
  confusion in 106k tokens), which resolve structurally cannot do.

## Honest caveats (this is a SMOKE, not the result)
- k=1, 10 probes, a single solver tier — no calibration gate yet. The full preregistered matrix
  (cross-harness Claude + Gemini + Codex, 40 probes, k≥3, + a generic-RAG arm A3) is required before
  any external claim.
- The **resolve arm is handed the answer** by a deterministic library — that is the mechanism under
  test, but it means A4 measures the *resolution ceiling with a model in the loop*, not end-to-end
  compilation. Compile cost (and the compiler's own fallibility, now gated by ADR 0024) is a separate
  line item.
- **Finding / product gap:** `resolve` scored **0/10 on "what it replaced"** — its output names the
  current decision and the superseded ADR *ids*, but not the prior *value*. To answer "what did it
  replace," `resolve` should optionally surface the immediately-superseded record's value. (Next-step.)
- Flat-summary might improve with a larger budget or a stronger solver; the matrix tests tiers.

## Verdict
Per the pre-committed stop rule (tie → retire the accuracy thesis), this is the **opposite of a tie**:
clean separation at scale. **Proceed to the full cross-harness matrix.**

## Artifacts
`killtest_gen.py` · `killtest_validate.py` · `killtest_smoke.py` · `killtest-outputs/` (corpus,
decisions library, probes, gold, smoke-runs/).
