# GOAL 3 — Token-reduction stack: measured results

**Question (from `TOKEN-REDUCTION-HYPOTHESES.md`):** can the code-shippable levers (H1 resolve, H2
deterministic scoring, H3 prefix caching) clear **>75%** token reduction on the resolvable + scorable
core of the suite **without losing discrimination**?

**VERDICT: YES.** On the supersession-lookup-100 scorable core, **H1+H2 alone = 98.9%** token
reduction (well past 75%); discrimination is preserved (the deterministic scorer + resolver still
separate right from wrong). H3 adds an independent **80%** cut on the repeated input-prefix pool.

All numbers below are **real measurements** with `tiktoken` (`cl100k_base`) on deterministically-built
fixtures, reproducible via the committed harness:

```bash
python3 evals/adversarial/measure_tokens.py            # prints the JSON accounting for all scorable scenarios
python3 evals/adversarial/measure_tokens.py --scenario decision-supersession-lookup-100
```

`cl100k_base` is a provider-neutral proxy; we report **ratios**, which are stable across tokenizers.

---

## What I implemented / wired

1. **H2 wired as the default grading path** (README "Running Tier B", step 3). For scorable scenarios
   the grader now runs `score.py` FIRST and only falls back to the LLM judge on `scorable: false`
   (exit 2). `score.py` was already authoritative on a ```` ```rosetta-verdict {…}``` ```` block
   (judge-independent, re-derives the needle/near-miss from the deterministic fixture); GOAL 3 makes it
   the documented default so judge tokens are **skipped** wherever a scenario is scorable. The scorable
   set is `score.SCORERS` (the `decision-supersession-*` and `decision-already-recorded` families).
2. **`measure_tokens.py`** — a stdlib+tiktoken harness that produces the before/after accounting for
   H1/H2/H3 on the scorable fixtures (so the table below is regenerable, not hand-waved).
3. **`tests/test_measure_tokens.py`** — locks in (a) the H1/H2/H3 reductions and (b) the
   **discrimination guardrail** (correct verdict passes, wrong verdict fails; scorer uses the
   structured, not prose, path).

No solver/judge runtime code changed — H1 (`decisions.py resolve`) and H2 (`score.py`) already shipped;
GOAL 3 *measures* them and makes the deterministic path the default.

---

## H1 — resolve instead of read (measured, tiktoken)

Tokens a solver must ingest to answer the resolution query "what is the current event-log decision":
**RAW** = read the whole decision library into context vs **RESOLVE** = one `decisions.py resolve`
JSON. Resolve cost is ~constant; raw cost grows with library size, so the reduction grows with N.

| Scenario | Records | RAW read (tok) | RESOLVE (tok) | Reduction |
|---|---:|---:|---:|---:|
| decision-already-recorded | 8 | 815 | 127 | **84.4%** |
| decision-supersession-lookup-5 | 5 | 504 | 123 | **75.6%** |
| decision-supersession-lookup-25 | 25 | 2,471 | 123 | **95.0%** |
| decision-supersession-lookup-100 | 100 | 10,552 | 123 | **98.8%** |
| decision-supersession-lookup-250 | 250 | 26,877 | 123 | **99.5%** |

Even the smallest 5-record library clears 75%; at realistic scale (100–250 records) resolve eliminates
~99% of the read pool.

### Live-model corroboration (Agent-tool Haiku runs, identical question + fixture)

Two Haiku subagents answered the same resolution question on the 100-record fixture; both reached the
correct answer (ADR 0050, Accepted):

| Arm | tool calls | subagent tokens | how it found the answer |
|---|---:|---:|---|
| raw-read (Read/grep the library) | 5 | 20,261 | grepped across ~400 KB of library to gain confidence |
| **resolve** (`decisions.py resolve`) | **1** | **18,590** | one tool call → compact JSON |

**Honest caveat:** the live gap (~8%) is much smaller than the static gap (~99%) because a *smart*
agent greps instead of reading every file into context — grep keeps content out of the window. The
static number is the upper bound (an agent that reads the library); the resolve path **guarantees** the
compact path *and* the correct supersession/conflict resolution regardless of agent skill, whereas
raw-read correctness depends on the agent grepping exhaustively. On this fixture the needle is a single
un-superseded record, which flatters raw-read; on the implicit-glossary / superseded-chain corpora
(Phase 0.5) raw-read also loses *correctness*, not just tokens.

---

## H2 — deterministic scoring replaces the LLM judge (measured)

Judge-side tokens to grade ONE solver output: an LLM-judge bundle (judge prompt + task prompt +
normalized corpus + manifest + gold + the solver's answer) vs `score.py` on the structured verdict
block (runs locally → **zero model tokens**).

| Scenario | LLM-judge tokens | det-score model tokens | Reduction |
|---|---:|---:|---:|
| decision-already-recorded | 4,109 | 0 | **100%** |
| decision-supersession-lookup-5 | 4,783 | 0 | **100%** |
| decision-supersession-lookup-25 | 4,417 | 0 | **100%** |
| decision-supersession-lookup-100 | 4,407 | 0 | **100%** |
| decision-supersession-lookup-250 | 4,406 | 0 | **100%** |

The only added cost is the ~43-token ```` ```rosetta-verdict``` ```` block the solver emits anyway. The
judge token pool (~4.4k/grade, ×k samples ×models in a sweep) is **eliminated** wherever a scenario is
scorable.

---

## H3 — prompt-prefix caching (estimate from identical-prefix reuse)

The shared prefix (task prompt + library substrate) is identical across k samples and across
same-provider models. With Anthropic prompt caching, the first call pays full input and subsequent
cached reads cost ~0.1× base input. Modeled on a k=3 × 3-same-provider-model cell, supersession-100
prefix = 10,628 tok:

| | input tokens |
|---|---:|
| uncached (9 calls × full prefix) | 95,652 |
| **cached** (1 full + 8 × 0.1×) | **19,130** |
| reduction | **80.0%** |

**Caveat:** H3 acts on the *input-prefix* pool. After H1, the per-call prefix is the tiny resolve JSON,
not the library — so H3 is **largely subsumed by H1** on the resolvable core (you can't cache a library
you no longer read). H3 is the lever for the paths where you still must put a large shared prefix in
front of many calls (e.g. free-form scenarios with a big substrate, or a no-tools long-context arm).
The 80% is a real, separate cut on *that* pool; it does not stack naively on top of the H1 number.

---

## The compounding stack: before / after (supersession-100 core)

The headline pools are solver-read (H1) and judge (H2). For one scorable scenario, end-to-end:

| | tokens |
|---|---:|
| **BEFORE** — solver reads raw 100-record library (10,552) + LLM judge grades (4,407) | **14,959** |
| **AFTER** — solver resolves (123) + emits verdict block (43) + deterministic score (0) | **166** |
| **Reduction** | **98.9%** |

**H1+H2 alone clear >75% with enormous margin (98.9%).** H3 adds 80% on the separate repeated-input
pool where a large shared prefix survives. H4 (route the surviving tokens to Haiku) is a **$** lever,
not a token lever, and is out of scope for the token gate.

---

## Discrimination preserved (guardrail — the falsifier check)

A cheaper suite is worthless if it stops separating right from wrong. Verified, and locked in by
`tests/test_measure_tokens.py::TestDiscriminationGuardrail`:

- **Deterministic scorer discriminates.** On supersession-100, a *correct* verdict
  (`superseded_adr: ADR 0050, current_store: duckdb, near_miss_untouched: true`) → **all checks pass /
  exit 0**; a *wrong* verdict (superseded the near-miss ADR 0025, said Postgres) → **all checks fail /
  exit 1**. Same for `decision-already-recorded` (cite ADR 0004 + no-duplicate passes; create-new-ADR
  fails). The scorer uses the authoritative **structured** path (`method: "structured"`), not prose
  regex — so it can't be fooled by phrasing (the ADR 0022/0023 lesson).
- **Resolver discriminates the near-miss.** `resolve --text "rate limit"` → ADR 0004 (needle);
  `resolve --text "leaky bucket"` → ADR 0002 (the distractor). The resolution layer does **not**
  conflate the two — the exact failure that trips naive search.

So the token cut comes from *removing redundant reading/judging*, not from removing signal.

---

## Honest caveats / limits

1. **Scope.** These numbers are the **resolvable + scorable core** (the decision-supersession /
   already-recorded families). Free-form scenarios still need the LLM judge (H2 doesn't apply) and
   novel questions the library can't resolve still need raw exploration (H1 doesn't apply). The >75%
   claim is for the core, exactly as the hypotheses doc scopes it — not the whole suite.
2. **Static vs live H1 gap.** The ~99% static H1 number assumes an agent reads the library into
   context; a grep-savvy agent narrows the live gap to single digits (measured ~8% on Haiku). The
   durable win of resolve is **guaranteed compact path + correct supersession/conflict resolution**,
   which on harder corpora is a *correctness* win, not just tokens.
3. **H3 doesn't stack on H1.** Caching saves on a prefix you still send; H1 removes the prefix. Report
   them as alternatives on the resolvable core, not a naive product. The "~90–95%" multiplicative
   figure in the hypotheses doc overstates the stack on the *resolvable* core for this reason —
   H1+H2's measured 98.9% is the honest headline there.
4. **Tokenizer proxy.** `cl100k_base`, not Claude's exact tokenizer; ratios are stable, absolute counts
   are approximate. The H3 0.1× cached-read multiplier is Anthropic's published ratio, modeled not
   billed.
5. **Verdict-block dependency.** H2's zero-token scoring requires the solver to emit a
   `rosetta-verdict` block. Without it `score.py` returns `scorable: false` and routes to the judge (by
   design — no silent guessing).

---

## Merge recommendation

**Merge: YES (code + doc).** Changes are additive and isolated: a measurement harness
(`measure_tokens.py`), tests (`test_measure_tokens.py`), a README wiring of deterministic-scoring-first,
and this results doc. No runtime behavior of the shipped collector/resolver/scorer changed. Full suite:
**140 tests, OK.**
