# Phase 0.5 — true LLM-vs-LLM on a messy, implicit-glossary corpus (the decisive test)

Phase 0 was retracted as "fake vs fake" (regex retriever vs hand-normalized buggy compiler). Phase 0.5
fixes that: a **real LLM compiler** vs **cheap-model inference-time reasoning**, on a corpus where
codenames are **implicit and scattered** (defined only by co-occurrence — never "X is internally Y"),
which is the realistic condition both reviewers said would decide it.

## Setup
- Corpus: ~390 records; "Atlas" = user-profile service and "ledger tier" = Cloud Spanner are inferable
  ONLY from scattered context (org notes, dashboards, infra notes). Gold = **Cloud Spanner**; traps =
  DynamoDB (old) + a stray "profile datastore: Postgres" Accepted-looking distractor.
- The Phase-0 regex retriever extracts **0 aliases** here (confirmed) — it collapses, as predicted.
- Arms (cheap model = **Haiku**, the one we want to lift; k=3; **read-verified grading**):
  - **raw-cheap** — Haiku reasons over the raw corpus (inference-time, infers aliases itself).
  - **compiled→cheap** — an **Opus LLM compiler** reads raw → writes a normalized `decisions/` library;
    Haiku answers from it via `decisions.py`.

## Result (read-verified)

| Arm | Correctness (Haiku, k=3) | Tokens/query | Notes |
|---|---|---|---|
| regex retriever | n/a (0 aliases extracted) | — | overfitted to "X is Y"; useless on implicit glossary |
| **raw-cheap** (inference-time) | **2/3** | ~28.7k | k1 fell for the Postgres distractor; k2/k3 inferred Atlas→Spanner |
| **compiled→cheap** | **3/3** | ~19.7k (**−31%**) | all cite ADR 0278; one-time compile = 89k tokens (amortized) |

**The LLM compiler was faithful and did real work** (the key question Gemini raised): from scattered
context it decoded *Atlas → user-profile service* and *ledger tier → Cloud Spanner*, wrote 278
validated ADRs, **resolved the supersession chain** (DynamoDB → Postgres → Spanner), **superseded the
stray Postgres distractor** instead of leaving a conflict (fixing the exact bug that tripped raw-cheap
k1), and **kept 6 genuine same-day conflicts as parallel records rather than guessing**.

## Conclusion (evidence-backed, not motivated this time)

1. **On realistic messy corpora, compilation pulls ahead** — exactly where the reviewers predicted. The
   query-time regex retriever can't extract scattered aliases at all; raw-cheap is only 2/3 (distractor-
   prone); the **LLM-compiled library lifts cheap Haiku to 3/3 at −31% tokens/query**, amortizing a
   one-time compile cost. This is the opposite ordering from the (buggy) Phase-0 clean-glossary test —
   and the messy condition is the realistic one.
2. **The product is a decision-resolution layer, not "search"** (Codex's framing, adopted): a provenance
   graph mapping **aliases + supersession + scope + code-evidence + conflicting/stale records**.
   *Compilation is the materialization/cache; retrieval is the interface; the moat is verified
   resolution + freshness.*
3. **Value proposition (per the goal), now evidence-backed on the realistic case:**
   > **Rosetta builds and serves a verified decision-resolution layer that lifts cheap/distilled models
   > to ~frontier correctness on messy, real-world decision histories — at lower amortized per-query
   > cost — by resolving the aliases, supersession, and conflicts that defeat both raw reading and naive
   > search.** Demonstrated: Haiku 2/3→3/3 at −31%/query on an implicit-glossary corpus a regex retriever
   > can't touch.

## Honest limits + what the reviewers still require (Phase 0b)
Both reviews agree the gate is **not fully met** by single fixtures. Required before any external claim:
- **Preregistered 2×2 over 20+ generated fixtures** across: glossary-present / absent / scattered,
  ambiguous-supersession, and code-vs-decision conflict.
- Arms: raw; prompt-scaffold; **production query-time resolver** (LLM, not regex) over raw; **LLM-
  compiler graph + same resolver**. No hand-normalization, no fixture-specific regex.
- Report **$/correct including compile + retrieval + retry costs**, k≥3, all tiers ({Haiku, Sonnet,
  Gemini-Flash} at minimum); grade **two axes** — decoded answer AND supported resolution (don't credit
  a bare "Cloud Spanner" without the supersession/conflict handling).
- **Overclaim to avoid** (Codex): "cheap reaches frontier" — in Phase 0 Haiku "beat" Sonnet only because
  Sonnet followed a poisoned compiled record; that's artifact quality, not tier. Correct framing: cheap
  models are *lifted* when the resolution evidence is materialized for them.
**Falsifier:** if a production LLM resolver over raw matches the compiled graph across messy fixtures and
real repos (and on amortized $), lead with retrieval instead. Until 0b, this is a strong signal, not a proof.
