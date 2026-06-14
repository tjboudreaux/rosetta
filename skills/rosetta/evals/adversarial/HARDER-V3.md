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

## Round 2 (v4): the 10×-harder build — and the real finding

Built exactly the spec above: **1,100 ADRs, ~184k-token ADR library / ~160k-token raw history** (both
overflow context), a **date-inverting reversal** (ADR 0980 newest-dated → ClickHouse, but
Superseded-by 0985 which reverts to CloudSQL per 0500), a **region×tier conditional** (EU *pro/free*
legitimately ClickHouse; only EU *enterprise* is CloudSQL), and **misleading legacy code** (the EU
enterprise service file still says `self-hosted-postgres`). Governance question: what must NEW EU
enterprise billing services use? Gold = managed Postgres (CloudSQL), ADR 0985/0500. Run on
opus/sonnet/haiku + gemini-3.5-flash, raw vs ADR-folder, tool-calling.

**Result: 8/8 correct AGAIN.** Every model, both conditions, traced the reversal, respected the
tier split, ignored the stale code, and answered CloudSQL. Tokens: opus 34.7k/35.3k, sonnet
39.7k/24.9k, haiku 37.2k/22.9k (raw/adr). Tool-calls were a near-wash (raw grep is efficient).

### Why scale STILL didn't break them — the load-bearing lesson

**grep is the great equalizer.** Total corpus size is irrelevant when the needle is keyword-findable:
`grep "EU enterprise event-store"` returns the ~3 relevant records out of 1,100 regardless of the
160k-token total, and the reversal is *explicitly worded* ("REVERT", "FAILED GDPR review"), so the
model reads it and reasons correctly. Scale + reversal + conditional + misleading code are **not
enough** — modern tool-calling models clear all of them.

To actually drop correctness, you must defeat **retrieval precision**, not scale:
- **Semantic evasion at scale** — the governing decision uses *different terminology* than the
  question (no shared keywords), so grep misses it and reading-everything is infeasible. (This is the
  one trap that DID break Haiku earlier — in v2 semantic-evasion — now needed at retrieval scale.)
- **Implicit reversal** — no "REVERT"/"FAILED" keyword; the change is undone by a later, neutrally-
  worded decision that doesn't reference the old one. Only reconstructing the full timeline reveals it.
- **Aggregation needles** — the answer requires combining 20+ records (e.g. "which regions have NO
  approved standard"); any missed record flips the answer, so partial retrieval fails.
- **Adversarial keyword density** — distractors share MORE keywords with the query than the needle, so
  grep ranks traps first and the model stops early.

### Why this is exactly where the compiled ADR folder wins on CORRECTNESS

Those four retrieval-defeating traps are precisely what Rosetta's **compilation step neutralizes**:
it normalizes terminology (defeats semantic evasion), sets explicit `Status:`/`Supersedes:` links
(defeats implicit reversal — the superseded record is *tagged*, not inferred), and produces a queryable
index (aggregation becomes a `--status Accepted` filter). So the v5 prediction is concrete: **on a
semantic-evasion / implicit-reversal fixture at retrieval scale, the raw condition should drop below
100% while the compiled ADR folder holds** — converting the folder's value from *efficiency* (shown in
v3/v4) to *correctness*. That is the experiment that would finally separate them.

### Net across v3 + v4
Two harder builds, 16/16 correct. The compiled ADR folder's measured value so far is **efficiency**
(v3: −22–44% tokens, up to ½ the tool-calls). Tool-calling models are far more robust to *scale,
reversal, and conditionals* than expected — grep carries them. The correctness value of compilation
will show only once the needle is made **unfindable by keyword search**.

## Honest status

- This run is **real and blind-checkable** (`/tmp/v3/out/*`, fixture generator `gen.py`), but it
  **did not** achieve the difficulty goal — it proved the *efficiency* value of the folder and
  **diagnosed exactly why correctness didn't separate**. The 10×-harder build (above) is specified but
  not yet run.
- gemini-3.5-flash needed `--skip-trust` to use tools in /tmp; both conditions then succeeded.
- Single sample per cell.
