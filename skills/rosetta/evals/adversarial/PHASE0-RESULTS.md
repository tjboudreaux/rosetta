# Phase 0 — prove-or-kill head-to-head

> ⚠️ **CORRECTED after Gemini adversarial review (2026-06-14).** The first version of this doc reported
> arm-4 (compiled folder) as 6/6 and concluded "compilation ties inference-time tooling." **Both were
> wrong.** Gemini caught that my keyword-grep grader false-positived on passing mentions of "Spanner";
> reading the actual answers shows **arm-4 = 4/6** (it answered *Postgres* twice, from a stray
> distractor it never resolved). Corrected grades and a corrected, narrower conclusion are below; the
> original over-conclusion is retracted.

**Question:** does Rosetta's *pre-compilation* beat cheap *inference-time* tooling at fixing the
retrieval-defeating failures that break models? **Answer: not established by this experiment** — it was
"fake vs fake" (a regex retriever vs a hand-normalized, buggy compiled library) with a fixture bug, so
the compiler-vs-retriever *ordering* is unreliable. What IS solid: raw-naive reliably fails; any
retrieval/decoding help fixes it; and a cheap model (Haiku) reaches ~Sonnet level with that help.

## Setup
- Fixture: the double-pivot breaker (user-profile datastore; codenames "Project Nimbus" + "unified
  ledger tier"; keyword-obvious wrong answers DynamoDB/Postgres-distractor; gold = **Cloud Spanner**).
  ~650 records, raw history overflows easy reading. Each arm **physically isolated** (own dir; no
  cross-access after an initial contamination bug was caught and fixed).
- 4 arms × {Sonnet, Haiku} × **k=3**, blind, graded as correct only if the answer names the decoded
  product ("Cloud Spanner") — stopping at the codename "unified ledger tier" counts as a miss.

## Result

**Corrected grades (read-verified from the answer files, gold = "Cloud Spanner"; an undecoded
"unified ledger tier" counts as a miss):**

| Arm | What the model got | Sonnet | Haiku | **Total** | Mean tokens |
|---|---|---|---|---|---|
| **1 — raw, naive** | raw history + tools, no help | 0/3 | 0/3 | **0/6** | ~26.5k |
| **2 — raw + scaffolding** | + "watch for codenames/supersession/stale code" prompt | 3/3 | 2/3 | **5/6** | ~26k |
| **3 — raw + alias-retriever** | + a stateless inference-time tool that expands codenames from the corpus glossary | 3/3 | 3/3 | **6/6** | ~20.6k (−22%) |
| **4 — compiled folder** | hand-normalized ADRs + `decisions.py` | **1/3** | 3/3 | **4/6** | ~19.5k (−26%) |

The two arm-4 Sonnet misses both answered **Postgres**, citing a stray "ADR 0621 profile datastore:
Postgres" record — a distractor my generator emitted that the (hand-)compiler **failed to resolve or
supersede**, so two `Accepted` records collided. That is simultaneously a real lesson (a naive compiler
that doesn't resolve *all* conflicts can be *worse* than a good retriever, because it lends false
authority) **and** a fixture bug. Haiku tracked Sonnet at the floor (0/3 raw) and ceiling (3/3 with
help) in every arm.

## What this means (corrected, honest, narrower conclusion)

1. **SOLID — the product value is real and big.** Raw-naive reliably fails (**0/6**); any
   retrieval/decoding help lifts it (scaffold 5/6, retriever 6/6, compiled 4/6); and a **cheap model
   (Haiku) reaches ~Sonnet-level** with help, at **~22–26% fewer tokens** than raw. Both value
   dimensions the goal named are demonstrated.
2. **NOT ESTABLISHED — compiler vs. inference-time tooling.** The original "compilation ties/loses"
   claim is **retracted**. This was Gemini's core hit: the head-to-head was *fake vs fake* — arm 3's
   retriever is an **overfitted regex** tuned to this glossary's exact syntax, and arm 4's library was
   **hand-normalized by me** (and buggy: it left an unresolved conflicting record). Neither used the
   real production tech (an LLM compiler / an LLM resolve-tool). So the *ordering* (retriever 6/6 >
   compiled 4/6) does **not** generalize — a correctly-resolved compile would score higher, and a
   real-world LLM retriever on a messy corpus would score lower.
3. **Process lesson (own it):** I mis-graded arm 4 with a keyword grep (false-positived on passing
   "Spanner" mentions) — the *exact* eval-integrity failure this whole project warns about. Grades are
   now read-verified. Lesson folded into the eval program: **never grep-grade; always claim-check.**

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

## Value proposition (supported by the SOLID findings only)
> **Rosetta's value is turning retrieval-defeating decision questions from wrong answers into right ones
> — bringing cheap/distilled models up to ~frontier correctness at lower token cost.** *Which*
> mechanism delivers that (an LLM-compiled+indexed library vs. an inference-time resolve/retriever tool)
> is **undecided** and is the subject of Phase 0.5. Gemini's caution applies: the alias_retriever here
> does **no** supersession resolution — the base model did the timeline reasoning — so do not credit a
> "supersession-resolving retrieval layer" until a real tool demonstrably does it.

## Decision gate → insert Phase 0.5 (per Gemini), before committing Phase 1's direction
**Do NOT pivot the product on this experiment.** Run a **true LLM-vs-LLM** test first:
1. A bare LLM **compiler** (does it hallucinate aliases / drop supersessions / leave conflicts, like the
   hand-version did?).
2. A bare LLM **inference-time resolve tool** (a real `resolve_codename`/search tool, not a regex).
3. On a corpus where the glossary is **implicit and scattered** (off-hand mentions, PR-style dumps), not
   a single clean record — the condition where the regex retriever would collapse.
**Falsifies the retriever direction:** if the LLM resolve-tool needs many tool-hops/$$ per query or
can't find scattered aliases, then **amortized compilation is the moat after all.**
Independently useful regardless of the gate: `decisions.py get --resolve` (supersession-following) is a
real capability shipped in Phase 1 — it's correct on its own merits, not contingent on this result.
Caveats: single fixture, k=3, one trap family, fixture-bug present; widen fixtures + re-run the
falsification checklist in 0.5.
