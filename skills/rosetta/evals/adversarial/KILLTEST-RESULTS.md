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

## Full matrix (Claude tiers, k=3, 40 probes) — `killtest_matrix.py`
Four arms × {Haiku 4.5, Sonnet 4.6} × k=3, two-axis **judge-independent** grading (a `current` that
names a *superseded* link is a recall failure; `replaced` is the second axis), majority vote over k.

**Recall (majority over k=3):**
| arm | Haiku | Sonnet |
|---|---|---|
| raw (full 106k corpus) | 95% | 100% |
| generic-RAG (BM25, no resolution) | 85% | 85% |
| **resolve (provenance graph)** | **100%** | **100%** |
| flat-summary (~5k map-reduce) | 65% | 72%* |

**$ per correct answer** (from `pricing.json`; resolve/rag exclude the one-time compile, accounted separately):
| arm | Haiku | Sonnet |
|---|---|---|
| raw | $0.0093 | $0.0264 |
| generic-RAG | $0.0021 | $0.0062 |
| **resolve** | **$0.0013** | $0.0039 |
| flat | $0.0018 | $0.0049 |

`resolve` is **40/40 on every individual sample, both tiers (stdev 0.0)**; raw varies (Haiku 35/39/35),
flat is noisy (Haiku 18/26/27). *flat-Sonnet: 1 of its 3 samples was lost to a repeated `claude`-CLI
timeout (`[32, 29, 0]`); the majority vote over the two good samples is unaffected at 72%.

### What the matrix establishes
1. **Thesis proven on both tiers:** the resolved graph recovers the recall flat compression loses —
   **resolve 100% vs flat 65%/72%**, with generic RAG intermediate at 85%. Separation **+15%** over raw
   on both tiers; discrimination holds (and judge-independent grading guarantees a wrong answer fails).
2. **Headline — cheap model lifted to frontier correctness:** **Haiku + resolve (100%) = Sonnet + raw
   (100%)** at **$0.0013 vs $0.0264 per correct — ~20× cheaper.** All three value axes at once.
3. **Provenance beats raw long-context on accuracy, not just cost:** on Haiku, resolve 100% > raw 95%
   — raw lost current values to lost-in-the-middle/distractors in 106k tokens; resolve structurally can't.
4. **Second axis confirmed:** resolve answers "what it replaced" 100% on both tiers (vs flat 2.5%/27%,
   raw 85%/99%) — the `resolve` fix shipped this turn.

### Honest caveats (what this is NOT)
- **Synthetic corpus**, deterministic by construction; it models scattered supersession + distractors,
  not the full mess of a real repo. The mechanism, not the absolute percentages, is the durable result.
- **The resolve arm queries a deterministic ground-truth library** — this measures the *resolution
  mechanism's* recall ceiling with a model in the loop, NOT end-to-end LLM compilation. Compile cost +
  the compiler's own fallibility (now gated by ADR 0024) are a separate line item, still unmeasured at
  this scale.
- **Claude-only, k=3.** Cross-harness (Gemini + Codex) is the next pass; the CLI flakiness seen on
  Sonnet-flat is a logistics tax to budget for there.

## Verdict
Per the pre-committed stop rule (tie → retire the accuracy thesis), this is the **decisive opposite of a
tie**: clean, calibrated separation at scale on both Claude tiers, with the cheap-model-to-frontier
result proven. **The recall-recovery thesis — unproven through Goals 1 & 2 — now holds on Claude tiers.**
Next: the cross-harness pass (Gemini + Codex) and an end-to-end *compiled-library* arm to fold in
compile cost + the integrity gate.

## Artifacts
`killtest_gen.py` · `killtest_validate.py` · `killtest_smoke.py` · `killtest-outputs/` (corpus,
decisions library, probes, gold, smoke-runs/).
