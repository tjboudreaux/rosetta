# Toward 10×-harder evals + the value of the compiled ADR folder

## The experiment (tool-calling, on-disk, 2026-06-14)

A high-churn fixture: 402 ADRs across 15 subsystems, a 6-hop event-store supersession chain
(Postgres→Kafka→DuckDB→ClickHouse), a **regional conditional** (EU kept on Postgres for GDPR while
global went ClickHouse), a **recent migration** (EU → managed Postgres/CloudSQL), and a **code
override** — among hundreds of distractors. Materialized two ways encoding the SAME truth:

- `raw-fixture/` — messy chronological transcripts + git log + code, **no decision library**.
- `adr-fixture/` — a **Rosetta-compiled `decisions/` ADR library** (Status/Supersedes links) + `decisions.py` CLI + code.

Needle question: *"For payments in the EU region, what is the CURRENT event-store backend new code must use?"*
Correct: **managed Postgres (CloudSQL)** — ADR 0489 + `payments/eu/store.py` — NOT global ClickHouse, NOT
self-hosted Postgres. Run on opus/sonnet/haiku (tool-calling subagents) and gemini-3.5-flash (CLI), in
both conditions, scaffolded with the truth hierarchy.

## Result: 8/8 correct — nobody dropped below 100%. But the folder paid off in cost.

Every model, both conditions, nailed it. The compiled ADR folder's value showed up as **efficiency**:

| Model | RAW tokens | ADR tokens | Δ | RAW tool-calls | ADR tool-calls |
|---|--:|--:|--:|--:|--:|
| opus 4.8 | 40,167 | 31,238 | −22% | 10 | 10 |
| sonnet 4.6 | 24,958 | 19,111 | −23% | 9 | 1 |
| haiku 4.5 | 37,435 | 20,866 | −44% | 18 | 9 |
| gemini-3.5-flash | ✓ (raw) | ✓ (adr) | — | — | — |

Same correct answer, **~22–44% fewer tokens and up to half the tool-calls** when querying the compiled
library instead of reconstructing from raw. That is real product value of automating ADR compilation —
**but at the efficiency margin, not the correctness margin, because the task was solvable both ways.**

## Why nobody broke (the load-bearing finding)

Three shortcuts let even Haiku win from raw, and each is a difficulty lever we must remove:

1. **A single unambiguous code file answered the question.** `payments/eu/store.py` literally sets
   `ENGINE='cloudsql-postgres'`. Per the truth hierarchy (code wins), one `grep eu` + read short-circuits
   the entire 402-ADR chain. **A hard eval's current state must NOT be readable from one obvious file.**
2. **The raw history fit in context (~10k tokens).** No forced retrieval, no lossy reconstruction. Models
   read everything. **Raw substrate must overflow the context window (100k–500k+ tokens) so retrieval is
   necessarily partial.**
3. **The needle was greppable.** "EU" + "cloudsql" returned it directly. **Distractor density must be high
   enough that naive search returns wrong/ambiguous hits.**

## What it would actually take to drop Sonnet / Gemini-3.5-Flash below 100%

Grounded in the above, concrete thresholds:

- **Scale that overflows context:** a project at "thousands of changes/week" → after ~6 months,
  ~50k–150k decision/commit/transcript events ≈ **300k–1M tokens of raw history**. Past the context
  window, a model *must* retrieve selectively; recall becomes lossy. This is the single biggest lever
  and the one this run lacked.
- **No single-file code oracle:** the current state must require **reasoning, not one read** — e.g. the
  backend is chosen by a config/feature-flag resolved across several files, or it's a policy/process
  decision with no code marker at all. Then the supersession chain + conditional actually have to be
  traced.
- **Deeper chains with a reversal where latest-date ≠ current:** e.g. 8–12 hops where the newest-dated
  ADR was itself superseded by an *earlier-numbered* amendment or a later git revert — so "sort by date,
  take newest" gives the wrong answer.
- **Conditional matrix, not one exception:** the answer depends on (subsystem × region × tenant tier ×
  flag) — e.g. 4 regions × 3 tiers each with different current backends. Models that collapse to one
  global answer fail.
- **High near-miss density:** ≥20–50 distractor ADRs mentioning the same keywords (event store,
  ClickHouse, EU) in *other* contexts, so keyword search alone misleads.
- **Partial supersession:** an ADR that supersedes only §2 of a prior ADR — the rest still stands.

Estimate: a fixture with **≥2,000 ADRs / ≥300k-token raw history, a 10-hop chain with a date-inverting
reversal, a 4×3 conditional matrix, no single-file code oracle, and ≥30 near-miss distractors** should
push mid-tier (Sonnet / Gemini-3.5-Flash) meaningfully below 100% **in the raw condition** — while the
**compiled ADR library + CLI keeps them at/near 100%** (search returns the resolved record directly).
That is the configuration where the folder's value converts from *efficiency* to *correctness*.

## The factorial we still want (folder × CLI × scaffolding), at that scale

| Cell | ADR folder | CLI | scaffold | measures |
|---|---|---|---|---|
| raw-naive | ✗ | ✗ | ✗ | floor: no Rosetta at all |
| raw-scaffold | ✗ | ✗ | ✓ | inference-time value only |
| folder-grep | ✓ | ✗ | ✓ | value of compilation alone (read the ADRs) |
| folder-cli | ✓ | ✓ | ✓ | full product (compile + indexed query) |

At context-overflowing scale, the expected ordering is raw-naive ≪ raw-scaffold < folder-grep ≤
folder-cli on correctness, with folder-cli cheapest per correct answer. This run is the bottom-right two
cells at *sub*-overflow scale — where they tie on correctness and the folder wins only on cost.

## Honest status

- This run is **real and blind-checkable** (`/tmp/v3/out/*`, fixture generator `gen.py`), but it
  **did not** achieve the difficulty goal — it proved the *efficiency* value of the folder and
  **diagnosed exactly why correctness didn't separate**. The 10×-harder build (above) is specified but
  not yet run.
- gemini-3.5-flash needed `--skip-trust` to use tools in /tmp; both conditions then succeeded.
- Single sample per cell.
