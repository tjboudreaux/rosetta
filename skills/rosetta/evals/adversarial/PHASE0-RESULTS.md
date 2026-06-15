# Phase 0 — prove-or-kill head-to-head (RESULT: thesis revised)

**Question:** does Rosetta's *pre-compilation* beat cheap *inference-time* tooling at fixing the
retrieval-defeating failures that break models? **Answer: no — they tie on correctness.** The value is
real and large, but it lives in the **retrieval/decoding capability**, not in pre-compilation.

## Setup
- Fixture: the double-pivot breaker (user-profile datastore; codenames "Project Nimbus" + "unified
  ledger tier"; keyword-obvious wrong answers DynamoDB/Postgres-distractor; gold = **Cloud Spanner**).
  ~650 records, raw history overflows easy reading. Each arm **physically isolated** (own dir; no
  cross-access after an initial contamination bug was caught and fixed).
- 4 arms × {Sonnet, Haiku} × **k=3**, blind, graded as correct only if the answer names the decoded
  product ("Cloud Spanner") — stopping at the codename "unified ledger tier" counts as a miss.

## Result

| Arm | What the model got | Correctness (k=3, Sonnet+Haiku) | Mean tokens |
|---|---|---|---|
| **1 — raw, naive** | raw history + tools, no help | **0/6** (Postgres / undecoded / DynamoDB) | ~26.5k |
| **2 — raw + scaffolding** | + "watch for codenames/supersession/stale code" prompt | **~6/6** (5/6 clean) | ~26k |
| **3 — raw + alias-retriever** | + a stateless inference-time tool that decodes codenames from the corpus glossary | **6/6** | ~20.6k (−22%) |
| **4 — Rosetta compiled folder** | normalized ADRs (codenames decoded, Status/Supersedes resolved) + `decisions.py` | **6/6** | ~19.5k (−26%) |

(Haiku tracked Sonnet in every arm — including 0/3 at baseline and 3/3 with any of the three fixes.)

## What this means (the honest, load-bearing conclusion)

1. **The product value is real and big:** a reliably-broken baseline (**0/6**) becomes **6/6**, and a
   *cheap model (Haiku) reaches Sonnet-level correctness* — while spending **~22–26% fewer tokens** than
   raw. Both value dimensions the goal named are achieved.
2. **But pre-compilation is NOT the unique antidote** — the falsification both reviewers predicted holds.
   Scaffolding (arm 2), a stateless alias-retriever (arm 3), and the compiled folder (arm 4) are
   **tied on correctness (all 6/6)**. Compilation wins only a marginal token edge (−26% vs −22%).
3. **Therefore the moat is the *retrieval/decoding capability*, not the compiled artifact per se.** The
   cheapest-to-operate form — a stateless **alias-aware retriever** (no compile step, no staleness
   problem) — matches the compiled folder here.

## Where compilation still earns its place (nuance, to test in later phases)
Arm 3's retriever only works because the **glossary was present and findable** in the corpus. Compilation's
durable advantages appear exactly where that breaks:
- **Alias derivation is hard/scattered/absent** → the compiler resolves it once, thoroughly,
  **code/git-anchored**, instead of every query re-deriving it heuristically.
- **Supersession is pre-resolved** (a `--status Accepted` filter) instead of reasoned per query.
- **Amortization** across many queries + **persistence/auditability** across sessions.
So the right product is likely a **hybrid**: a compiler that emits a normalized, supersession-resolved,
code-anchored library **and** exposes an alias-aware retriever — but Phase 0 says lead with the
*retrieval capability*, and treat the heavy compile/freshness machinery as an **optimization to justify
per-query**, not the headline.

## Revised value proposition (per the goal's invitation to propose a better one)
> **Rosetta's value is turning retrieval-defeating decision questions from wrong answers into right ones
> — bringing cheap/distilled models up to frontier-level correctness at lower token cost — via an
> alias-aware, supersession-resolving retrieval layer. Pre-compilation is one (marginally cheaper)
> implementation of that layer, not the value itself.**

## Decision gate → Phase 1
Proceed, but **redirected**: build the **alias-aware retriever in `decisions.py`** first (the winner on
simplicity), keep the normalizing compiler as the optimization, and design Phase 1 to test the nuance
above (glossary-absent / large-scale, where compilation should pull ahead). Caveats: single fixture,
k=3, one trap family; the next phases must widen fixtures and run the falsification checklist again.
