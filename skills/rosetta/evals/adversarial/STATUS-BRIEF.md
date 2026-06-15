# Rosetta — status brief: remaining work, hypotheses, and analysis links

A navigable index of everything produced this arc, what's proven vs. open, the remaining work by phase,
and the live hypothesis ledger — so the next goal can be set against concrete state. Paths are relative
to `skills/rosetta/`.

## Where we are (one paragraph)
The eval suite catches real LLM failure modes; only **retrieval-defeat** (semantic evasion / codename
pivots / multi-hop) reliably breaks tool-calling models (scale/reversals/counts do not). A
decision-resolution layer fixes that and lifts cheap models toward frontier correctness at lower per-query
cost. The product is reframed as a **decision-resolution layer (provenance graph)**, with compilation as
the cache and retrieval as the interface. Two CLI primitives shipped (`get --resolve`, `resolve`). Two
deep-research passes + multiple Codex/Gemini reviews are folded in. **The central thesis — that
code-anchored, supersession-resolved provenance recovers the recall that flat compression loses — is
unmeasured.**

## The single decisive open question (highest leverage)
**Does a code-anchored, supersession-resolved decision graph recover the ~33–35-pt factual-recall loss
that flat extraction/compression incurs — i.e., does Rosetta beat both raw long-context and generic
RAG/memory on accuracy, not just cost?** No source or experiment has tested this; it is the whole
product thesis. → `evals/adversarial/RESEARCH-workflows-x-rosetta.md` (open questions),
`evals/adversarial/PHASE0.5-RESULTS.md`.

## Remaining work by phase
| Phase | Work | Size | Status | Link |
|---|---|---|---|---|
| **0b** | Preregistered **2×2 over 20+ generated fixtures** (glossary present/absent/scattered, ambiguous-supersession, code-conflict) × {Haiku/Sonnet/Gemini-Flash} × k≥3; arms = raw / scaffold / **production LLM resolver** / **LLM-compiler graph**; report **$/correct incl. compile+retry**; grade **two axes** (decoded answer AND supported resolution). | Large (hundreds of runs) | **Not started — gates every external claim** | `evals/adversarial/PHASE0.5-RESULTS.md`, `EVAL-AND-PRODUCT-ROADMAP.md` |
| **1** | Build the full **resolver / evidence graph** (beyond the 2 shipped primitives): alias/codename resolution at compile time, scope/conditional handling, **freshness/drift guard** (staleness check + auto-supersede when code/git moves past an ADR). | Medium | 2 primitives shipped (`get --resolve`, `resolve`); rest open | `scripts/decisions.py`, `EVAL-AND-PRODUCT-ROADMAP.md` |
| **2** | Fold the retrieval-defeating archetypes (v5/v6) into `dataset.json` as first-class scenarios; add the review's **missing failure modes** (sycophancy, multi-document/conflicting-context, tokenization/counting, order bias, RAG retrieval-vs-generation); k≥3 + **CALIBRATED gate** + cost panel per tier; keep ceiling checks. | Medium | Designed; generators exist | `RESEARCH-llm-failure-modes.md`, `dataset.json`, `HARDER-V6.md` |
| **3** | **Agentic** benchmark research (SWE-bench/τ-bench/WebArena/GAIA) + agentic evals for Rosetta's own CLI loop; real-repo scale; live cost/value dashboard; the **compile-once → fan-out cheap workers** workflow pattern. | Large | Designed only; agentic = literature gap both passes | `RESEARCH-workflows-x-rosetta.md`, `RESEARCH-llm-failure-modes.md` (agentic gap) |

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
- **Provenance-recovers-recall** (the decisive question above) — **unmeasured.**
- **Compile break-even** on a real codebase (compile cost vs per-query savings) — **unmeasured.**

### Eval-integrity (lessons banked)
- **Never grep-grade; always claim-check** (a grep grader mis-graded Phase 0 — caught by Gemini). → `PHASE0-RESULTS.md`, `PHASE0-REVIEWS.md`.
- Fixtures must be **conflict-clean** (a stray distractor poisoned both Phase-0 arms). → `PHASE0-RESULTS.md`.
- **k≥3 + CALIBRATED gate** before any external number. → `CALIBRATION.md`.

## Document map
- **Eval design/quality:** `DESIGN.md` · `CALIBRATION.md` · `README.md` · `judge_prompt.md` · `RESULTS.md` · `REPORT.md`
- **Difficulty escalation:** `HARD-SUITE.md` · `HARDER-V3.md` (scale doesn't break) · `HARDER-V5.md` (broke Sonnet) · `HARDER-V6.md` (variety + broke Gemini-Pro) · `REVIEW-ablation.md`
- **Value / cost:** `VALUE.md` · `SWEEP.md` (14-model cross-harness) · `TOKEN-REDUCTION-HYPOTHESES.md`
- **Phase 0 program:** `EVAL-AND-PRODUCT-ROADMAP.md` · `PRODUCT-VALUE-PLAN.md` · `PHASE0-RESULTS.md` · `PHASE0.5-RESULTS.md` · `PHASE0-REVIEWS.md`
- **Research (cited, verified):** `RESEARCH-llm-failure-modes.md` · `RESEARCH-workflows-x-rosetta.md`
- **Shipped product:** `scripts/decisions.py` (`resolve`, `get --resolve`) · `commands/rosetta-grill.md` · `commands/rosetta-conflicts.md` · `commands/README.md`

## Candidate goals to choose from (pick one to set)
1. **Prove the thesis (recommended):** run the decision-graph-grounding vs long-context vs RAG experiment — does provenance recover the 33–35-pt recall loss? Settles accuracy + cost in one stroke.
2. **Phase 0b rigor:** the preregistered 20+-fixture 2×2 with production resolver + LLM compiler + $/correct — convert the strong signal into a defensible result.
3. **Token-reduction build+measure:** implement H1+H2+H3 and measure the >75% claim end-to-end (with discrimination held).
4. **Productize the resolver/freshness layer** (Phase 1 completion) + ship the commands for real use.
5. **Agentic frontier:** close the agentic eval gap (benchmark research → fixtures → the compile-once/fan-out pattern).
