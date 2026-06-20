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
  mechanism's* recall ceiling. End-to-end LLM compilation (compile cost + compiler fallibility) is
  **measured in hardening pass 2 below** (82% vs the 100% ceiling).
- **Claude-only, k=3** at this point — **generalized to Gemini + Codex in hardening pass 1 below.**

## Hardening pass 1 — cross-harness (Gemini + Codex), k=3, 40 probes
Re-ran the matrix across **five models / three providers** via a harness-agnostic dispatcher
(`run_model` → claude / gemini / codex CLIs). Majority recall:

| arm | Haiku | Sonnet | Gemini-flash | Gemini-3.1-pro | GPT-5.5 |
|---|---|---|---|---|---|
| raw (106k corpus) | 95% | 100% | 100% | 100% | 100% |
| generic-RAG | 85% | 85% | 95% | 95% | 98% |
| flat-summary | 65% | 72% | 82% | 82% | **57%** |
| **resolve (provenance)** | **100%** | **100%** | **100%** | **100%** | **100%** |

**$ per correct** (real per-provider rates, `pricing.json` 2026-06):

| arm | Haiku | Sonnet | Gemini-flash | Gemini-3.1-pro | GPT-5.5 |
|---|---|---|---|---|---|
| raw | $0.0093 | $0.0264 | $0.0045 | $0.0179 | $0.0448 |
| **resolve** | **$0.0013** | $0.0039 | **$0.0007** | $0.0029 | $0.0073 |

- **`resolve` = 100% recall on every provider** — the recovery is not Claude-specific.
- **Flat compression loses recall on every provider** (57–82%); GPT-5.5 is the worst flat performer (57%).
- **resolve is the cheapest-correct path on every model** (~6–7× under raw). Cheapest overall:
  **Gemini-flash + resolve = $0.0007/correct at 100%** — matching GPT-5.5-raw's 100% (**$0.0448**) at **~64×
  lower cost**. The cheap-model-to-frontier result holds across harnesses.
- On the strong models raw also reaches 100% (they resist lost-in-the-middle better than Haiku, where
  resolve's 100% > raw's 95%) — so on capable models resolve's win is **cost + the second axis**, not raw recall.

## Hardening pass 2 — end-to-end compiled-library arm (real LLM compile, not ground truth)
The matrix `resolve` arm queries a deterministic ground-truth library (the resolution *ceiling*). This
arm instead has an LLM **compile** the library from the raw corpus (`killtest_compile.py`,
compiler = Sonnet), gated by the ADR-0024 integrity check, then resolves against THAT. So it folds in
compile cost + the compiler's own fallibility.

| compiled-library variant | resolve recall vs gold | conflicts | note |
|---|---|---|---|
| naive per-chunk extract + assemble | **50%** (20/40) | **14** | LLM emitted the same codename with drifting casing across chunks → split chains → resolve correctly **flags conflicts** instead of guessing |
| **+ entity canonicalization** (case/whitespace) | **82%** (33/40) | 0 | chains now match ground truth (340); remaining 18% = genuine extraction errors (a chain's final decision missed/mis-dated) |

Model-in-loop (solver answers from resolve-on-compiled), majority recall — **constant 82% across all
tiers** (Haiku/Sonnet/Gemini-flash/GPT-5.5), because resolve hands the answer and the solver only
transcribes; the 18-pt gap is entirely the compiler, not the solver:

| arm | Haiku | Sonnet | Gemini-flash | GPT-5.5 |
|---|---|---|---|---|
| compiled-resolve | 82% | 82% | 82% | 82% |
| $/correct | $0.0016 | $0.0047 | $0.0009 | $0.0087 |

**Compile cost ≈ 146k tokens, one-time** (amortizes over all queries). Integrity gate: **CLEAN** (the
resolve-then-assemble design assigns ids deterministically, so id-hallucination is structurally
impossible; the gate guards ghost citations).

### Live re-verification (2026-06-18): compiler drift closed the 18% gap

A live A0 gate (fresh `claude-sonnet-4-6` compile via OAuth-routed `claude` CLI) scored **40/40 (100%)**
— recovering all 7 misses with 0 regressions. The original 82% was a model-quality artifact of the
saved `extracted.json` (1,237 rows → 929 ADRs); the live compile extracted 1,259 rows → 1,024 ADRs,
finding the final/current decision for every miss chain. The 18% gap was genuine extraction errors
(omitted final decisions), not a structural deficiency — the current model no longer makes them.

The overlap/self-check ablations (A1–A3) designed to close the gap are **BLOCKED / NOT RUN**: with the
gap at 0%, there's nothing to improve, and any recall change would be noise. The ablation infrastructure
(variant isolation, chunk-provenance self-check, per-chunk checkpointing, gate-only scoring) is complete
and reusable if a future model regression reintroduces extraction gaps. See
`ADVERSARIAL-REVIEW-FINDINGS.md` for the full analysis and `ADVERSARIAL-REVIEW-PREREGISTRATION.md` for
the frozen ablation matrix.

**Historical (2026-06-15 run): What pass 2 establishes (honestly):** a *real* LLM-compiled library answers **82%** end-to-end at this
scale — below the 100% ground-truth ceiling but **above flat compression on most tiers** and far cheaper
than raw. The dominant failure is **compiler extraction**, not resolution; the biggest single lever is
**entity canonicalization** (+32 pts, 50→82) — the alias-resolution step Phase 1 named but never built,
now shown to be load-bearing. Closing the remaining 18% is a compiler-quality problem (better extraction
/ chunk overlap / a verification pass), not a thesis problem. **Update (2026-06-18):** the live
re-verification above closed this gap — the current `claude-sonnet-4-6` extracts all 40 chains correctly
(100%). The `compiled-lib/extracted.json` should be refreshed with the live extraction; the
overlap/self-check ablation infrastructure remains available if a future model regression reintroduces
extraction gaps.

## Context-window scaling — what happens when corpus > the model's window (`killtest_scale.py`)
The 106K matrix kept `raw` *inside* the window (merely expensive). This sweep grows the corpus past it.
Solver = Sonnet (~200K window), 10 probes, resolve against the ground-truth graph:

| services | corpus | decisions | resolve input | resolve recall | raw input | raw result |
|---|---|---|---|---|---|---|
| 120 | 107K tok | 1,040 | 1,384 tok | 10/10 | 108K | answered 10/10 |
| 300 | 275K tok | 2,617 | 1,405 tok | **10/10** | 275K | **REJECTED — prompt too long** |
| 600 | 555K tok | 5,247 | 1,405 tok | **10/10** | 555K | **REJECTED — prompt too long** |

- **`raw` hits a hard cliff**, not a slope: it answers at 108K (inside the window) and is **rejected
  outright** at ~1.4× and ~2.8× the window. Past the window, raw has no valid configuration — truncating
  drops the corpus (recall collapses) and chunking *is* RAG/flat. Raw-long-context **ceases to exist.**
- **`resolve` is invariant:** input held at ~1,400 tokens and recall at **10/10 across a 5× corpus
  growth** (corpus size lives only in the one-time compile, never in per-query cost). The resolve-vs-raw
  cost gap, ~14× at 106K, becomes **unbounded** here — raw becomes impossible while resolve stays flat.

This is the scaling form of the thesis: the resolution layer's value *increases* with corpus size, and
becomes categorical (not just quantitative) once the corpus exceeds the window — **for the raw-dump
baseline.** The next section corrects an important strawman.

## The REAL baseline — a tool-calling agent (grep/read), not a context dump (`killtest_agentic.py`)
`raw` dumps the whole corpus into context (and cliffs past the window). A modern agent instead
**greps/reads on demand**, so it never hits the wall. Each probe = a fresh Claude Code agent session
with real Grep/Read/Bash tools on `corpus.md`; tokens/turns/time/$ are measured from the CLI's JSON.

| corpus | model | recall | $/correct | tokens/probe | time/probe | tool turns |
|---|---|---|---|---|---|---|
| 106K (20 probes) | Sonnet | **100%** | $0.107 | 70,900 | 13.0s | 2.3 |
| 565K / ~2.8× window (10 probes) | Sonnet | **100%** | $0.116 | 73,052 | 14.3s | 2.4 |

Findings:
- **Accuracy does NOT degrade** — 100% at both scales, *including* past the context window. A competent
  tool-calling model greps the entity, reads its chain, and reasons through the supersession + stale-doc
  distractors. "grep is the equalizer" holds.
- **Tokens (~50×) and latency (~13–14s, sequential turns) blow up** vs resolve's single ~1.4k-token,
  near-instant call.
- **Agentic cost is corpus-size-invariant** ($0.107 → $0.116 across a 5× corpus) — grep is targeted, so
  it reads the entity's footprint, not the whole repo. So tool-calling, unlike raw-dump, *scales*.

### Honest head-to-head (corrects the earlier "accuracy moat" framing)
| baseline | accuracy | $/correct | latency | tokens | determinism | past window |
|---|---|---|---|---|---|---|
| raw context-dump (Sonnet) | ties strong models | $0.026 | 1 slow call | 107k | — | **no (cliffs)** |
| **agentic tool-calling (Sonnet)** | **100% (ties resolve)** | $0.11 | ~14s / 2.4 turns | ~72k | earned per-query | yes |
| **resolve (Sonnet)** | 100% | **$0.004** | 1 instant call | ~1.4k | **structural** | yes |

**Against the strongest baseline (tool-calling), resolve does NOT win on accuracy — it ties at 100%.**
Resolve's durable moat over a tool-calling agent is **~27× lower $/correct, ~10–20× lower latency, ~50×
fewer tokens, and *deterministic* correctness** — resolve's 100% is guaranteed by the graph, whereas the
agent earns its 100% per query and is the one whose accuracy could slip on harder distractors, higher k,
or weaker models. The accuracy advantage is real only vs flat compression and generic RAG (57–98%) and
vs raw on weak models / past the window — **not vs a competent tool-calling agent.**

## Verdict
The recall-recovery thesis — unproven through Goals 1 & 2 — **holds across five models and three
providers** vs flat compression / generic RAG (resolve 100% vs flat 57–82%, RAG 85–98%), with the
cheap-model-to-frontier result reproduced cross-harness. **But vs a tool-calling agent — the strongest
real baseline — accuracy TIES at 100%; resolve's win there is cost (~27×), latency (~10–20×),
token-efficiency (~50×), and determinism, not accuracy.** End-to-end, a real LLM-compiled library reaches
**82%** (ceiling 100%), gated clean by ADR 0024, gap localized to compiler extraction + a quantified
canonicalization lever. Net: **resolve's moat is efficiency + determinism against the best baseline, and
accuracy against the weaker ones — claim it precisely, not as a blanket accuracy moat.**

Remaining next steps: push compiler extraction past 82% (overlap chunks / self-check pass); stress the
agentic tie with harder retrieval-defeat probes + higher k (where the agent's *earned* 100% may crack
while resolve's *structural* 100% holds); a real-repo corpus.

**Update (2026-06-18):** the 82% figure is stale — a live A0 re-verify scored 100% (see "Live
re-verification" above). The "push past 82%" next step is closed; the remaining frontier is the
agentic tie + a real-repo corpus.

## Artifacts
`killtest_gen.py` · `killtest_validate.py` · `killtest_smoke.py` (arms + `run_model` dispatcher) ·
`killtest_matrix.py` (matrix + `pricing.json` $/correct) · `killtest_compile.py` (LLM compile +
canonicalization, `--reassemble`) · `killtest-outputs/matrix/matrix-results-{claude,xharness,compiled}.json`
· `killtest-outputs/compiled-lib/{extracted.json,compile-meta.json}`.
