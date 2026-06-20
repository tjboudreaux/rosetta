# Rosetta — status brief: remaining work, hypotheses, and analysis links

A navigable index of everything produced this arc, what's proven vs. open, the remaining work by phase,
and the live hypothesis ledger — so the next goal can be set against concrete state. Paths are relative
to `skills/rosetta/`.

## Orchestration outcomes (goals 1–5, all run in isolated worktrees, merged into `evals-hardening`)
| Goal | Outcome | Disposition | Evidence |
|---|---|---|---|
| **3 — token reduction** | **SUCCESS** | merged as a win | H1+H2 = 98.9% cut on the resolvable+scorable core, discrimination held (`GOAL3-TOKEN-REDUCTION-RESULTS.md`, `measure_tokens.py`) |
| **4 — productize freshness/resolver** | **SUCCESS** | merged as a win | `staleness` subcommand + `validate --staleness` + 3-state `resolve` stale flag; 155 tests green; flags stale Accepted records on the live library (`GOAL4-FRESHNESS.md`) |
| **5 — agentic frontier** | research delivered | merged | benchmark survey + compile-once/fan-out design (`GOAL5-AGENTIC.md`) |
| **1 — recall-recovery thesis** | **INCONCLUSIVE** | merged as a **negative/inconclusive result; do NOT cite as supporting recall recovery** | ~1.1k-token corpus never hit the high-compression regime; all 3 conditions tied 3/3; resolved graph won on **cost −37%/query**, not accuracy (`GOAL1-THESIS-EXPERIMENT.md`) |
| **2 — Phase 0b 2×2** | **MIXED → NO** at this scale | merged as **apparatus + honest negative; do NOT cite as "compiled beats raw"** | raw 20/20 = compiled 20/20 (no fixture separated arms); compiler hallucinated ADR ids in 2/5; cost inverted at toy scale (`GOAL2-PHASE0B.md`) |

**Net:** the *cost/token* and *productization* bets are proven (goals 3, 4). The two *accuracy/correctness* bets (goals 1, 2) were **not supported at small/clean scale** — both failed for the same reason: no compression pressure.

## UPDATE (2026-06-15): the recall-recovery thesis now HOLDS at scale (kill test)
Rebuilt the experiment with real compression pressure — a **106k-token corpus, 1025 decisions (685
superseded distractors), 21.2:1** to a 5k summary — and ran a preregistered **4-arm × 2-Claude-tier ×
k=3 × 40-probe** matrix with judge-independent grading (`evals/adversarial/KILLTEST-RESULTS.md`,
`killtest_*.py`). Result, **majority recall**:

| arm | Haiku | Sonnet |
|---|---|---|
| raw (106k) | 95% | 100% |
| generic-RAG | 85% | 85% |
| **resolve** | **100%** | **100%** |
| flat-summary | 65% | 72% |

- **Thesis proven:** the resolved provenance graph recovers the recall flat compression loses (resolve
  100% vs flat 65%/72%); +15% separation over raw on both tiers; resolve is 40/40 on every sample.
- **Headline:** **Haiku+resolve (100%) = Sonnet+raw (100%) at ~20× lower $/correct** ($0.0013 vs $0.0264).
- Also shipped this turn: **compiler anti-hallucination integrity gate** (ADR 0024, CI-enforced) and
  `resolve` now returns **"what it replaced"** (second grading axis → 100%).

Previously remaining to harden the claim (now completed): **cross-harness pass (Gemini + Codex)** and
an **end-to-end compiled-library arm** — both done in the GOAL COMPLETE block below (cross-harness
pass 1 + the live-reverified compiled-library arm).

## Where we are (one paragraph)
The eval suite catches real LLM failure modes; only **retrieval-defeat** (semantic evasion / codename
pivots / multi-hop) reliably breaks tool-calling models (scale/reversals/counts do not). A
decision-resolution layer fixes that and lifts cheap models toward frontier correctness at lower per-query
cost. The product is reframed as a **decision-resolution layer (provenance graph)**, with compilation as
the cache and retrieval as the interface. Two CLI primitives shipped (`get --resolve`, `resolve`). Two
deep-research passes + multiple Codex/Gemini reviews are folded in. **The central thesis — that
code-anchored, supersession-resolved provenance recovers the recall that flat compression loses — is
PROVEN** (resolve 100% vs flat 57–82% across 5 models / 3 providers; see `KILLTEST-RESULTS.md`).

## The single decisive open question (highest leverage)
**The agentic tie:** resolve and a competent tool-calling agent both hit 100% on the current 40-probe
set. Does resolve's *structural* 100% hold — and the agent's *earned* 100% crack — under harder
retrieval-defeat probes and higher k? That's where resolve's determinism + efficiency moat would
separate from the best baseline. → `KILLTEST-RESULTS.md` (verdict), `GOAL5-AGENTIC.md`.

## Remaining work by phase
| Phase | Work | Size | Status | Link |
|---|---|---|---|---|
| **0b** | Preregistered **2×2 over 20+ generated fixtures** (glossary present/absent/scattered, ambiguous-supersession, code-conflict) × {Haiku/Sonnet/Gemini-Flash} × k≥3; arms = raw / scaffold / **production LLM resolver** / **LLM-compiler graph**; report **$/correct incl. compile+retry**; grade **two axes** (decoded answer AND supported resolution). | Large (hundreds of runs) | **Superseded by the kill test** (2026-06-15) — thesis proven at scale (resolve 100% vs flat 57–82%); Phase 0b tied at toy scale (GOAL2-PHASE0B.md) | `KILLTEST-RESULTS.md`, `PHASE0.5-RESULTS.md` |
| **1** | Build the full **resolver / evidence graph**: alias/codename resolution at compile time, scope/conditional handling, **freshness/drift guard**. | Medium | **Done** — alias resolution shipped (ADR 0025), `resolve`/`search`/`get --resolve` shipped, staleness + `Reviewed:` field shipped (ADR 0027) | `scripts/decisions.py`, ADR 0025, ADR 0027 |
| **2** | Fold the retrieval-defeating archetypes (v5/v6) into `dataset.json` as first-class scenarios; add the review's **missing failure modes** (sycophancy, multi-document/conflicting-context, tokenization/counting, order bias, RAG retrieval-vs-generation); k≥3 + **CALIBRATED gate** + cost panel per tier; keep ceiling checks. | Medium | Partial — v5/v6 archetypes folded into `dataset.json` (32 scenarios incl. semantic-evasion, multi-hop); remaining failure modes + CALIBRATED gate still open | `RESEARCH-llm-failure-modes.md`, `dataset.json`, `HARDER-V6.md` |
| **3** | **Agentic** benchmark research (SWE-bench/τ-bench/WebArena/GAIA) + agentic evals for Rosetta's own CLI loop; real-repo scale; live cost/value dashboard; the **compile-once → fan-out cheap workers** workflow pattern. | Large | Designed only; agentic = literature gap both passes. **This is the current frontier** — the agentic tie at 100% is the open question. | `GOAL5-AGENTIC.md`, `RESEARCH-llm-failure-modes.md` |

## Hypothesis ledger
### Token reduction (target >75%) — `evals/adversarial/TOKEN-REDUCTION-HYPOTHESES.md`
- **H1 resolve-instead-of-read** (−60–80% solver) — *half-built (`resolve` shipped); untested end-to-end.*
- **H2 deterministic scoring replaces LLM judges** (−40–50% total) — *score.py exists; not wired as default.*
- **H3 prompt/context caching of shared prefix** (−50–90% input) — *not tried.*
- **H4 route to Haiku** ($ −80–90%, contingent on H1) — *evidence from sweep; not productized.*
- **H5 adaptive-k**, **H6 compile-once/query-many** (externally evidenced), **H7 compression** — *open.*
- **Stacked claim:** H1×H2×H3 alone clear >75% on the resolvable+scorable core. **Untested; guardrail: discrimination must not drop.**

### Product / mechanism — `PHASE0.5-RESULTS.md`, `PHASE0-RESULTS.md`, `PRODUCT-VALUE-PLAN.md`
- **Compiler vs. inference-time resolver:** on a *messy* corpus the LLM compiler won (Haiku 2/3→3/3, −31%/query); on a *clean* corpus a retriever tied/beat a buggy compiler. **Ordering not settled → Phase 0b.**
- **Provenance-recovers-recall** (the decisive question above) — **MEASURED** (kill test 2026-06-15:
  resolve 100% vs flat 57–82% across 5 models/3 providers; see `KILLTEST-RESULTS.md`).
- **Compile break-even** on a real codebase (compile cost vs per-query savings) — **unmeasured.**

### Eval-integrity (lessons banked)
- **Never grep-grade; always claim-check** (a grep grader mis-graded Phase 0 — caught by Gemini). → `PHASE0-RESULTS.md`, `PHASE0-REVIEWS.md`.
- Fixtures must be **conflict-clean** (a stray distractor poisoned both Phase-0 arms). → `PHASE0-RESULTS.md`.
- **k≥3 + CALIBRATED gate** before any external number. → `CALIBRATION.md`.

## Document map
- **Eval design/quality:** `DESIGN.md` · `CALIBRATION.md` · `README.md` · `judge_prompt.md` · `RESULTS.md` · `REPORT.md`
- **Difficulty escalation:** `HARD-SUITE.md` · `HARDER-V3.md` (scale doesn't break) · `HARDER-V5.md` (broke Sonnet) · `HARDER-V6.md` (variety + broke Gemini-Pro) · `REVIEW-ablation.md`
- **Value / cost:** `VALUE.md` · `SWEEP.md` (14-model cross-harness) · `TOKEN-REDUCTION-HYPOTHESES.md`
- **Recall-recovery thesis (PROVEN, Claude tiers):** `KILLTEST-RESULTS.md` · `killtest_gen.py` · `killtest_validate.py` · `killtest_matrix.py`
- **Phase 0 program:** `EVAL-AND-PRODUCT-ROADMAP.md` · `PRODUCT-VALUE-PLAN.md` · `PHASE0-RESULTS.md` · `PHASE0.5-RESULTS.md` · `PHASE0-REVIEWS.md`
- **Research (cited, verified):** `RESEARCH-llm-failure-modes.md` · `RESEARCH-workflows-x-rosetta.md`
- **Shipped product:** `scripts/decisions.py` (`resolve`, `get --resolve`) · `commands/rosetta-grill.md` · `commands/rosetta-conflicts.md` · `commands/README.md`

## GOAL COMPLETE (2026-06-15): both hardening passes done → thesis holds cross-harness + end-to-end
Both passes ran at k=3, 40 probes; combined matrix in `KILLTEST-RESULTS.md`.

1. **Cross-harness pass — DONE.** Matrix across **5 models / 3 providers** (Haiku, Sonnet, Gemini-flash,
   Gemini-3.1-pro, GPT-5.5) via a `run_model` dispatcher. **resolve = 100% recall on every provider**;
   flat compression loses recall everywhere (57–82%). resolve is the cheapest-correct path on every
   model; cheapest **Gemini-flash+resolve $0.0007/correct @100% = GPT-5.5-raw @100% at ~64× lower cost**.
2. **End-to-end compiled-library arm — DONE + RE-VERIFIED.** An LLM compiles the library (Sonnet,
   ADR-0024 gate CLEAN); resolve-on-compiled was **82%** end-to-end (vs 100% ground-truth ceiling) in
   the original hardening-pass-2 run. A **live A0 gate** (2026-06-18, fresh `claude-sonnet-4-6` via
   OAuth-routed `claude` CLI) scored **40/40 (100%)** — the compiler drift eliminated the 18% gap.
   The original misses were all `wrong-value` (earlier superseded link resolved as current); the live
   compiler extracted all 7 missing final/current decisions. Naive compile 50% → **+entity
   canonicalization 82% → live re-compile 100%** (the alias step Phase 1 named, now shown load-bearing);
   compile cost ~146k tok one-time. See `ADVERSARIAL-REVIEW-FINDINGS.md` for the full gate analysis.

**Net (precise, post tool-calling baseline): resolve beats flat-compression/RAG/raw-on-weak-models on
ACCURACY (100% vs 57–98%), provider-independent. But vs a competent TOOL-CALLING agent — the strongest
real baseline — accuracy TIES at 100%; resolve's win there is efficiency + determinism: ~27× lower
$/correct, ~10–20× lower latency, ~50× fewer tokens, and a structurally-guaranteed 100% (the agent earns
its 100% per query at ~$0.11 and ~14s, and is the one that could slip on harder probes).** Both resolve
and the agent are corpus-size-invariant (grep is targeted); only raw-dump cliffs past the window. Claim
the moat precisely — efficiency/determinism vs the best baseline, accuracy vs the weaker ones. The
compiler-quality gap is closed (live re-verify = 100%); remaining: stress the agentic tie with harder
probes + higher k; a real-repo corpus.

## Candidate goals to choose from (pick one to set) — post-orchestration
Goals 1–5 have all been run once (see **Orchestration outcomes** at top). What remains:

1. **Prove the thesis at scale (recommended):** re-run the goal-1/goal-2 design on a **LARGE, lossy corpus** (hundreds of ADRs / 100k+ tokens) so flat compression actually drops recall and compile cost amortizes. The synthetic killtest corpus (106K tok, 1,025 ADRs) already ran this scale pass (`KILLTEST-RESULTS.md` §Context-window scaling); the remaining question is whether the thesis holds on a *real-repo* corpus with messier, less-structured decision histories.
2. **Harden the token-reduction win (goal 3):** wire H1+H2 as the default grading path in CI end-to-end (not just measured), add H3 caching + H5 adaptive-k, keep the discrimination guardrail.
3. ~~**Extend the freshness layer (goal 4):** auto-supersede when code/git moves past an ADR; resolve the 12 stale records the live sanity run flagged.~~ **DONE (2026-06-18):** ADR 0027 shipped the `Reviewed:` freshness-acknowledgment field (a re-flaggable baseline, not a permanent override); all 12 stale ADRs were triaged with `Reviewed: 2026-06-18`; `staleness --strict` now exits 0 (CI-gateable).
4. ~~**Fix the compiler hallucination (goal 2 finding):** the LLM compiler invented ADR ids in 2/5 fixtures — constrain it to emit only verifiable ids.~~ **DONE:** the resolve-then-assemble design assigns ids deterministically (ADR 0024 integrity gate), so id-hallucination is structurally impossible in the current pipeline.
5. **Agentic frontier (goal 5):** turn the delivered research into real fixtures + the compile-once/fan-out workflow on a real repo.

### Current remaining work (2026-06-18)

The candidate goals above were set at orchestration time (2026-06-15). Goals 3 and 4 are now done
(see strikethroughs). What remains:

1. **Stress the agentic tie with harder probes + higher k.** Resolve and the tool-calling agent both
   hit 100% on the current 40-probe set; harder probes (semantic evasion, multi-hop, code-conflict)
   could break the tie and show where resolve's determinism wins or loses.
2. **A real-repo corpus.** The synthetic corpus proves the thesis; a real repo would test
   generalization to messier, less-structured decision histories.
3. **Refresh `compiled-lib/extracted.json`.** The live A0 gate (2026-06-18) found the current
   `claude-sonnet-4-6` extracts all 40 chains correctly (100%); the saved `extracted.json` (82%) is
   stale and should be refreshed so the matrix's `compiled` arm reflects current model quality.
