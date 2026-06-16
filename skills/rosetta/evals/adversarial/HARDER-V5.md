# v5 — the eval that finally breaks a Sonnet-level model on the base condition

**Goal:** progressively increase difficulty until a model at ≥ Sonnet / Gemini-3.5-Flash level fails
the **base** condition (raw history, NO Rosetta CLI, NO ADR folder). **Achieved.**

## What made v5 different from v3/v4

v3 (402 ADRs) and v4 (1,100 ADRs, ~160–184k tokens, reversal + conditional + misleading code) both
ended 16/16 correct — because **grep is the equalizer**: a keyword-findable needle is trivial at any
scale. v5 abandons scale as the lever and attacks **retrieval precision** instead:

- **The keyword-obvious answer is WRONG.** Many distractors + two records (one recent, "reaffirmed,
  all teams") say *"EU enterprise billing event-store: ClickHouse"*. `grep "EU enterprise billing
  event store"` → ClickHouse everywhere.
- **The correct answer is behind a terminology pivot.** The current decision (most recent, 2026-06-12)
  uses only codenames: *"Project Meridian persistence migrates to the managed relational tier."* It
  shares **no keywords** with the question.
- **A glossary decodes it** (findable via "EU enterprise billing"): *Project Meridian = EU enterprise
  billing event sink; managed relational tier = CloudSQL Postgres; columnar tier = ClickHouse.* You
  must find it, decode two terms, then realize the codenamed record (latest) supersedes the ClickHouse
  reaffirmation.
- **Misleading legacy code** (`eu_enterprise/store.py = self-hosted-postgres`) as a third wrong attractor.

Gold: **managed Postgres (CloudSQL)**. Fixture: 1,000 ADRs, ~85k-token raw history (`scale_fixture_gen_v5.py`).

## Result (single sample per cell)

| Condition (base = raw, naive, no CLI, no folder) | Model | Answer | Verdict |
|---|---|---|---|
| base | **Sonnet 4.6** | ClickHouse | ✗ **WRONG** |
| base | Haiku 4.5 | ClickHouse | ✗ WRONG |
| base | Gemini-3.5-Flash | CloudSQL | ✓ |
| base | Opus 4.8 | CloudSQL | ✓ |
| raw **+ Rosetta scaffolding** | Sonnet 4.6 | CloudSQL | ✓ |

**Sonnet broke on base** (answered ClickHouse) — goal met. It found the keyword-dense "reaffirmed"
ClickHouse record and the legacy code, but never found the glossary or the codenamed superseding
record, so it confidently returned the trap.

## Why this is a *real* eval, not an unfair one

The same fixture is **solvable**: Opus got it, Gemini-3.5-Flash got it (it explored the codename), and
**Sonnet got it once given Rosetta's inference scaffolding** ("watch for codenames/glossaries,
keyword-less decisions, tier scoping, and overridden reaffirmations; cross-check the most recent
records"). So the failure is a genuine retrieval/reconciliation gap that better prompting and stronger
models overcome — exactly what an eval should discriminate. It is hard-but-deducible.

## Two findings that matter

1. **The difficulty frontier for tool-calling agents is retrieval precision, not corpus size.** Scaling
   ADRs/history does nothing (v3/v4). Making the needle *unfindable by the obvious keyword* — via a
   codename pivot, a keyword-less superseding record, and adversarial keyword density — is what drops a
   Sonnet-level model. This is the design rule for hard Rosetta evals going forward.
2. **Rosetta's value finally shows on CORRECTNESS, not just cost.** Inference-time scaffolding flipped
   Sonnet wrong→right on the base raw fixture. The complementary prediction (now well-grounded): a
   Rosetta-**compiled** ADR library that *normalizes the codenames at compile time* (title:
   "EU enterprise billing event-store → managed Postgres (CloudSQL)", `Status:` resolved) would make the
   needle keyword-findable again — turning this from a break into a pass without any inference cleverness.
   That is the automation-of-compilation value, on correctness.

## Honest caveats

- **Single sample per cell.** Gemini-3.5-Flash passed here but is plausibly fragile to the same trap on
  other samples/phrasings; Sonnet's failure is the load-bearing result. k≥3 would quantify the rate.
- The "compiled folder normalizes codenames" claim is a *prediction* grounded in how Rosetta compiles;
  the v5 generator does NOT pre-normalize the ADR titles, so a folder run here would face the same pivot.
  The clean correctness demo is: normalize titles at compile time, then re-run folder vs raw.
- Fair-but-hard rests on the glossary being discoverable; that's by construction (it contains the
  natural keyword "EU enterprise billing").
