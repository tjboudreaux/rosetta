# v6 — a variety of hard archetypes: what breaks models vs. what doesn't

**Goal:** add a larger variety of evals that fail a larger % of searches on Haiku/Sonnet, OR break at
least one of Opus / Gemini-Pro / GPT-5.5. **Both achieved.** All runs are the **base condition**
(raw history on disk, tool-calling, naive prompt, NO Rosetta CLI, NO ADR folder), blind to the gold.

## What broke models vs. what didn't

| Archetype | Mechanism | Haiku | Sonnet | Opus | Gemini-Pro | GPT-5.5 |
|---|---|:--:|:--:|:--:|:--:|:--:|
| **A1 codename** (event-store) | semantic evasion (1 pivot) | ✗ | ✗ | ✓* | ✓* | — |
| **S2 codename** (partner auth) | semantic evasion (1 pivot) | ✗ | ✗ | — | — | — |
| **S3 double-pivot** (user-profile datastore) | semantic evasion (2 pivots) | — | ✗ | ✓ | ✗ | ~ |
| A2 implicit-reversal | latest record overrides, neutral wording | ✓ | ✓ | — | — | — |
| A3 aggregation-count | exact count, exclude superseded/off-topic | ✓ | ✓ | ✓ | ✓ | ✓ |
| A4 cross-ref-chain | "see X's decision" indirection | ✓ | ✓ | — | — | — |
| A5 future-effective | future-dated decision not yet live | ✓ | ✓ | — | — | — |
| T1 scope-exception | global standard + explicit carve-out | ✓ | ✓ | — | — | — |
| T3 salient-number | a salient wrong number (7y) vs precise (30d) | — | ✓ | ✓ | ✓ | ✓ |

✗ = wrong answer (broke). ✓ = correct. ✓* = correct (from v5 single-pivot runs). ~ = output polluted
(MCP/skill-load noise), inconclusive. — = not run for that cell.

## The load-bearing finding

**Only semantic evasion breaks modern tool-calling models on the base condition.** Everything where the
correct answer is *keyword-findable* — explicit reversals, exceptions, future-effective dates, exact
counts, salient-number distractors — is answered correctly, because the model greps the relevant text
and reads it carefully. The failures all share one property: **the correct answer does not share
keywords with the question**, so retrieval surfaces a confident *wrong* record and the model stops.

- **Single pivot** (A1, S2): a codename/tier indirection (e.g. question "partner API auth" → the current
  decision says *"Project Gatekeeper moves to the federated identity tier"*, decodable only via a buried
  glossary). Breaks **Haiku and Sonnet** reliably; Opus/Gemini-Pro still pivot.
- **Double pivot** (S3): two chained indirections (user-profile → "Project Nimbus" → "unified ledger
  tier" → Cloud Spanner), with a keyword-obvious wrong answer (DynamoDB). Breaks **Sonnet** (resolved
  the tier to the wrong product, Cassandra) and **trips Gemini-Pro** (named the tier codename, never
  decoded it to Spanner). **Opus** completed both hops.

## Why A3 (aggregation) is NOT a breaker — and an integrity note

A3 initially looked like a frontier-breaker (Opus said 4, Gemini-Pro said 7, gold "6"). On inspection
that was a **fixture bug**: random distractors also emitted `(queue, Kafka)` records, so the true count
wasn't a clean 6 — the question was ill-defined. After constraining the generator so the count is
*exactly and verifiably* 6, **every model (Haiku→GPT-5.5) answered 6 correctly.** A "break" on an
ill-defined question is not a break; reported here so the negative result is honest.

## Net

- **Branch (a) satisfied:** 3 distinct semantic-evasion archetypes (A1, S2, S3) fail Sonnet; 2 also fail
  Haiku — a real variety and a higher failure rate than v5's single trap.
- **Branch (b) satisfied:** Gemini-3.1-pro failed the double-pivot S3 (left the answer as a codename,
  never resolving to Cloud Spanner). Borderline-but-real; Sonnet's S3 = Cassandra is an unambiguous miss
  at the Sonnet tier.
- **Design rule (final):** hard Rosetta evals must make the answer **unfindable by the question's
  keywords** (codename/tier pivots, multi-hop indirection). Stacking pivots scales difficulty from
  Haiku→Sonnet (1 pivot) to Sonnet→Gemini-Pro (2 pivots). This is precisely what a Rosetta-**compiled**
  ADR library neutralizes by normalizing codenames at compile time — the standing prediction for the
  folder's correctness value.

## Caveats
- Single sample per cell. Gemini-Pro's S3 miss is borderline (under-specified vs. flatly wrong); the
  Sonnet-tier breaks (A1/S2/S3) are unambiguous.
- Generators: `scale_fixture_gen_v6.py` (A1–A5) + the A3 fairness fix and the T1/T3/S2/S3 archetypes
  (definitions inline in this file); captured answers in `v6-outputs/`.
