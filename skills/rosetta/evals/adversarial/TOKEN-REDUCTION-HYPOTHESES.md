# Hypotheses: cutting eval token usage >75%

Goal: reduce token usage of the Rosetta eval runs by **>75%** without losing discrimination or
correctness signal. Each hypothesis lists the mechanism, an **expected reduction** (grounded in this
session's measurements where possible), how to **test** it, and the **risk**. The headline is a
compounding stack (bottom) that clears 75% on both raw tokens and $.

Baseline (measured this session): solver runs ~20–40k tokens each; LLM judges ~25–30k each; the
14-model sweep ≈ 3.5M tokens; a single resolve-vs-raw query already showed **−31%** tokens.

## Single-lever hypotheses

**H1 — Resolve instead of read.** Solver calls `decisions.py resolve --text <q>` (1 tool call → JSON
with the current decision + provenance) instead of grep+read over the corpus. The corpus never enters
context.
- *Expected:* **−60–80%** of solver tokens on resolution-type scenarios (reading the corpus is the bulk;
  measured −31% even with a naive compiled folder, more with a tight resolver). *Test:* re-run the
  Phase-0.5 question via `resolve` vs raw, compare tokens. *Risk:* only covers questions the library
  resolves; raw exploration still needed for novel questions.

**H2 — Deterministic scoring replaces LLM judges.** For scenarios with a structured `rosetta-verdict`
(score.py), drop the LLM judge entirely.
- *Expected:* **−40–50% of total eval tokens** (judges were ~half the sweep). *Test:* score the
  decision-family + any verdict-emitting scenario with score.py only; reserve the LLM judge for
  subjective ones. *Risk:* free-form scenarios still need a judge; must avoid the grep-grading trap
  (use claim-checking, not keywords — Phase 0 lesson).

**H3 — Prompt/context caching of the shared prefix.** The bundle/prompt prefix is identical across k
samples, across arms, and across same-provider models. Cache it.
- *Expected:* **−50–90% of INPUT tokens** on repeated-prefix runs (input dominates a ~9k-prompt × many
  runs). *Test:* enable provider prompt caching; measure input-token billing across a k=3 cell. *Risk:*
  5-min cache TTL; only same-provider; output tokens unaffected.

**H4 — Route to distilled models.** Run solver + (deterministic) scoring on Haiku, which Phase-0.5
showed reaches the right current state with the resolver.
- *Expected:* token *count* similar, but **$ −80–90%** (Haiku ≈ 5× cheaper/token than Opus). *Test:* the
  $/correct panel per tier. *Risk:* the goal may be tokens not $ — H4 is a $ lever, not a token lever;
  pair with H1/H3 for raw-token cuts. *Honest caveat (Codex):* "cheap matches frontier" only holds when
  the resolution evidence is materialized — i.e., H4 depends on H1/compilation.

**H5 — Confidence-gated k (adaptive sampling).** Replace fixed k=3 with k=1, escalating to k=3 only when
the deterministic scorer or a cheap self-consistency check is uncertain.
- *Expected:* **−50–66% of solver runs** (most cells are unanimous). *Test:* compare adaptive-k pass-
  rates to fixed-k on a known cell. *Risk:* under-samples genuinely high-variance cells; gate must be
  calibrated.

**H6 — Compile-once / query-many amortization.** The LLM compile is expensive (~89k once) but paid once;
each eval query against the compiled library is cheap (~19k vs ~29k raw).
- *Expected:* amortized per-query cost → the cheap resolve cost as #queries grows; for a suite of M
  scenarios on one library, **−~30% and falling with M**. *Test:* total tokens for (1 compile + M cheap
  queries) vs (M raw queries). *Risk:* compile cost dominates for tiny suites; freshness re-compiles
  re-incur it.

**H7 — Substrate/prompt compression.** Trim bundles to the minimal solver-visible substrate; emit the
normalized corpus once; compact tool outputs (search/resolve already return tight JSON).
- *Expected:* **−10–20%.** *Test:* diff bundle sizes. *Risk:* over-trimming removes needed evidence.

## The path to >75% (compounding stack)

These multiply because they hit different token pools (solver-read, judge, input-cache, sampling):

```
start                              100%   tokens
× H1 resolve-instead-of-read       ~30%   (−70% solver read on resolvable scenarios)
× H2 deterministic scoring         ~18%   (judges eliminated where scorable: ~×0.6 of remaining)
× H3 prompt caching (input)        ~10%   (input is most of what's left; ~×0.55)
× H5 adaptive-k                    ~5–7%  (fewer samples: ~×0.5–0.66)
```
→ **~90–95% raw-token reduction** on the resolvable + scorable core of the suite; **>75% is cleared by
H1+H2+H3 alone.** On **$**, add H4 (route to Haiku) for a further ~5× on the surviving tokens.

## Recommended test order (cheapest, highest-signal first)
1. **H2** (deterministic scoring) — pure win where scorable, no model calls. 2. **H1** (resolve) — the
biggest solver-side cut and it's already half-built (`resolve` shipped). 3. **H3** (caching) — config
change, large input cut. 4. **H5** (adaptive-k). Measure tokens **and** $/correct at each step; keep the
CALIBRATED + two-axis grading gates so a "cheaper" suite can't quietly lose discrimination.

## What would falsify ">75% achievable without quality loss"
If H1/H2 drop discrimination (the suite stops separating tiers), or resolve-only runs miss scenarios that
raw reading would catch, or caching/adaptive-k introduce variance that needs k back up — then the
reduction trades against signal and the real ceiling is lower. Test discrimination at every step, not
just token count.
