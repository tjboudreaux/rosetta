# Claude workflows × Rosetta — cited research (token cost & accuracy)

Adversarially-verified deep-research pass (3-vote refute; 22 sources, 25 claims verified, 19 confirmed /
6 killed). **Answer to the core question: yes, workflows + a Rosetta decision-layer can both cut tokens
AND raise accuracy — but via *different* mechanisms that rarely co-occur in one topology.**

## The two mechanisms (don't conflate them)

- **Accuracy ↑ = spend MORE tokens.** Anthropic's orchestrator-worker multi-agent system beat
  single-agent Opus 4 by **90.2%** on its internal research eval — but **token spend alone explained
  ~80% of the performance variance**, and multi-agent runs cost **~15× chat** (single agents ~4×)
  [anthropic.com/engineering/multi-agent-research-system]. Fan-out buys accuracy by paying for breadth.
- **Token ↓ = the Rosetta/memory half (compile-once / query-many).** A fact/memory layer is **decisively
  cheaper than raw long-context even with the 90% prompt-caching discount** — break-even ~10 turns at
  100k ctx, ~26% cheaper at 20 turns [arXiv:2407.16833; arXiv:2603.04814]; subagent summaries compress
  tens-of-thousands of explored tokens into **~1–2k** [Anthropic context-engineering]; plan/route caching
  (Self-Route) cuts cost large at near-parity accuracy [arXiv:2506.14852].
- **The catch:** the compression that powers the savings **loses factual recall** (~33–35 pts on memory
  benchmarks at high compression). **So Rosetta's distinctive bet is that code-anchored, supersession-
  resolved *provenance* recovers what flat extraction loses** — that's the thing to actually measure.

## Map: dev workflow × topology × where Rosetta plugs in × effect

| Workflow | Best topology | Rosetta plug-in | Token | Accuracy |
|---|---|---|---|---|
| Onboarding / catch-up | **single grounded agent** | `ground-truth.md` + `resolve` (don't read whole history) | **↓↓** | ↑ |
| Codebase Q&A | single agent → fan-out only if broad | `resolve`/`search` as the index; workers query, not re-read | ↓ | ↑ |
| PR review | **pipeline** (dimensions → verify) | resolve "the decided pattern/ADR" to ground each reviewer | ~flat | ↑ (grounding) |
| Large refactor / migration | **orchestrator-worker fan-out** | shared **pre-resolved** decision graph each worker queries | ↑ (justified) | ↑↑ |
| Architecture review | fan-out (breadth-first) | the compiled library *is* the map of prior decisions | ↑ | ↑ |
| Incident response | **single agent** (tight inter-step deps) | fast `resolve` of recent/superseded decisions | ↓ | ↑ |
| Spec / feature planning | single agent + **/rosetta-grill** | resolve → grill → record (the command we shipped) | ↓ | ↑ |

Rule of thumb (Anthropic "simplest solution first"): **default to one well-grounded agent; reserve
fan-out for genuinely breadth-first work** where parallel exploration earns back the ~15× premium.
Multi-agent is explicitly a **poor fit for sequential coding** (inter-file deps, shared mutable state,
error compounding) — grounding helps but doesn't erase that.

## How this lands for Rosetta (and ties to #1/#2)

1. **Rosetta is the token-reduction lever, not the accuracy lever.** It makes the *cheap single-agent
   default* strong enough that you need expensive fan-out less often — exactly the
   `TOKEN-REDUCTION-HYPOTHESES` stack (H1 resolve-instead-of-read, H6 compile-once/query-many) but now
   backed by external evidence (memory < long-context after ~10 turns).
2. **The accuracy win is compositional:** a workflow that **compiles once (Rosetta) then fans out
   cheap, resolution-fed workers** gets breadth-accuracy *and* cost control — the resolved layer keeps
   each worker's context tiny. That's the highest-value pattern for refactors/arch-review.
3. **`/rosetta-grill` and `/rosetta-conflicts` are the single-agent-grounded pattern** the evidence
   favors for most dev work (no fan-out tax).

## Open questions = the next experiments (Rosetta-specific, unmeasured by any source)
- Does a **code-anchored, supersession-resolved decision graph recover the 33–35-pt recall loss** that
  flat extraction incurs? No source tested decision-graph grounding vs long-context — this is Rosetta's
  whole thesis and it's **unmeasured**. (→ a Phase-0b arm.)
- What's the **compile break-even** for building a supersession-resolved library vs per-query savings on
  a *real* codebase? Memory papers measure conversation extraction, not ADR compilation.
- For **coding tasks specifically**, does grounding workers in a resolved library make fan-out worthwhile
  despite the inter-file-dependency problem?

## Honest caveats
- The 90.2% / 4×/15× / 80%-variance figures are **Anthropic's own non-public research-task evals**, not
  coding, and prove multi-agent *raises* cost ~15× — never cite them as a token-saving result.
- Cost figures (Mem0 break-even, 35:1, Self-Route 39–65%, plan-caching ~47–50%) are mostly single-study,
  author-reported on specific models/benchmarks; **6 related claims were refuted** (incl. "long-context
  consistently beats RAG" and two cost-Pareto/cache-coherence frameworks) — don't lean on those.
- Mechanisms/directions are the durable takeaway; absolute percentages are time- and model-sensitive.

> **Update (2026-06-18):** The thesis is now MEASURED — resolve 100% vs flat 57-82% across 5 models/3 providers (KILLTEST-RESULTS.md). The remaining open question is the agentic tie at 100%, not whether provenance recovers recall.
