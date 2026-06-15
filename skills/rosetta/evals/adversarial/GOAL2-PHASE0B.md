# Phase 0b — preregistered compiler-vs-inference-time across 5 fixture types

> **The gate.** Phase 0.5 gave a strong *single-fixture* signal that an LLM-compiled decision library
> lifts cheap Haiku (2/3 → 3/3, −31% tokens/query) on a messy implicit-glossary corpus. Both reviewers
> (Codex, Gemini) said that is **a signal, not a result** — it must be reproduced *preregistered, across
> multiple fixture types, read-verified on two axes* before any external claim. Phase 0b is that test,
> scoped to be completable: 5 fixture types, 2 arms, 2 model tiers, k=2, READ-VERIFIED grading.

## VERDICT

**Mixed, leaning NO — compiled resolution did NOT reliably *beat* raw on these fixtures; it *tied*.**
Both arms scored **40/40** (20/20 each). The Phase-0.5 redirect's own **falsifier partially fired**:
a capable model reading the raw corpus — when prompted to look for supersession / aliases / code-wins —
matched the compiled-library arm on correctness across all five retrieval-defeat patterns. The
**correctness** case for compilation is **not** demonstrated at this scale. The durable case for
compilation (token-collapse + multi-hop caching at scale, and a citation-integrity guard the *compiler
itself* needs) is left to Phase 1 — and Phase 0b surfaced concrete evidence for why those, not
correctness-on-toy-fixtures, are the real product.

---

## Preregistered design (fixed before runs)

- **Fixture types (5), each a distinct reason naive search / raw reading should fail:**
  1. `glossary-present` — explicit "X is internally Y" exists but is buried; an older record names a
     now-superseded value. Tests *decode + supersession*.
  2. `glossary-absent` — codename never defined; gold inferable only from scattered co-occurrence;
     a stray unresolved-TODO distractor. Tests *implicit-glossary inference + distractor rejection*.
  3. `scattered-alias` — one service, 3+ aliases across files; current decision and code use
     different names. Tests *alias unification + supersession*.
  4. `ambiguous-supersession` — two same-day conflicting decisions, then a later amendment
     superseding **both**. Naive "latest-of-the-day wins" picks wrong. Tests *chain-following*.
  5. `code-vs-decision-conflict` — an Accepted ADR asserts value A; code + git show B shipped.
     Tests *truth hierarchy (code wins) + staleness flagging*.
- **Arms (2):**
  - `raw` — model answers from the raw normalized corpus (inference-time reasoning).
  - `compiled` — an **Opus LLM compiler** reads the raw corpus → writes a normalized, validated
    `decisions/` library (ADRs with supersession links); the answerer queries it via
    `decisions.py resolve/search/get`.
- **Models:** Haiku, Sonnet (the cheap tiers we want to lift, plus one step up). Compiler = Opus.
- **k = 2** independent attempts per (fixture × arm × model) → **40 answerer runs** + 5 compiles.
- **Grading: READ-VERIFIED, two axes, never grep.** An Opus judge with **judge-only gold** reads each
  answer and the raw corpus and assigns:
  - `axis_answer` — decoded current value matches gold (or alias) **and is asserted as current**.
  - `axis_resolution` — satisfies every `rubric.must` and violates no `rubric.must_not` (e.g. must
    not assert a superseded/stale value as current; must acknowledge the supersession/alias/code-wins).
    Confident-hedge rule enforced: naming the right answer while *also* asserting a wrong one anywhere
    fails this axis.
  - `pass` = both axes pass.
- **Generator:** `goal2_gen.py` — deterministic (`--seed`), code-anchored, regenerable
  (contamination-resistant). `--per-type N` scales the count.

**Falsifier (declared in Phase 0.5, carried in):** *if a capable model reading raw matches the
compiled graph across messy fixtures (and on amortized cost), lead with retrieval/inference-time
tooling instead.* Phase 0b is the first place that could fire — and on correctness, it did.

---

## Results matrix (per fixture × arm × model, k=2; cell = pass_k / k)

| Fixture type | Gold | raw·Haiku | raw·Sonnet | compiled·Haiku | compiled·Sonnet |
|---|---|---|---|---|---|
| glossary-present | Postgres | 2/2 | 2/2 | 2/2 | 2/2 |
| glossary-absent | MySQL | 2/2 | 2/2 | 2/2 | 2/2 |
| scattered-alias | Pub/Sub | 2/2 | 2/2 | 2/2 | 2/2 |
| ambiguous-supersession | Keycloak | 2/2 | 2/2 | 2/2 | 2/2 |
| code-vs-decision-conflict | MySQL | 2/2 | 2/2 | 2/2 | 2/2 |
| **Arm total** | | **10/10** | **10/10** | **10/10** | **10/10** |

Both axes (`axis_answer` and `axis_resolution`) passed in **every one of the 40 cells**. Full
per-attempt verdicts with the judge's one-line reasons are in `goal2-grades/*.json`; the aggregate is
`goal2-results.json`.

**Arm totals:** raw **20/20**, compiled **20/20**. No fixture type separated the arms.

---

## Where compiled wins / loses / ties

- **Ties everywhere on correctness (5/5 types).** Neither arm failed a single fixture. The
  compiled arm is *not wrong* — but it bought nothing on correctness here.
- **Compiled *loses* on a hidden axis: compiler-as-LLM hallucination.** The judge flagged that in
  **2/5 fixtures** (`scattered-alias`, `code-vs-decision-conflict`) the compiled answerers cited
  **ADR numbers that the Opus compiler invented** (e.g. an "ADR 0002 superseding ADR 0001" where file
  02 was an impl note, not an ADR). The *final answers stayed correct*, so the two-axis rubric did not
  fail them — but this is exactly the "compiler moves hallucination upstream" risk the roadmap names.
  Raw reading cannot fabricate an ADR id because there are no ADR ids to fabricate. **On
  citation integrity, raw was cleaner.**
- **Compiled *should* win at scale (untested here).** These corpora are 3–5 short notes; the
  raw-arm context is tiny and one model pass resolves everything. Compilation's structural advantages —
  collapsing a large raw corpus into a small queryable library (token/$ at query time), and caching
  multi-hop resolution so it is paid **once** not per-query — only materialize when the raw corpus is
  large and queried repeatedly. Phase 0b is deliberately too small to show that; it was scoped to test
  *correctness*, and correctness tied.

## Rough tokens / $ note (this run, observed)

| Item | ~tokens | Notes |
|---|---|---|
| Compile (Opus), per fixture | ~36.5k | one-time, amortized over all future queries of that library |
| Answer · raw, per run | ~21.1k | reads the full raw corpus each query |
| Answer · compiled, per run | ~22.2k | CLI resolve + read 1–3 ADRs; *slightly higher here* |

At this fixture size the compiled answerer used **marginally more** tokens/query than raw (the raw
corpus is already tiny, so there is nothing to collapse), and it carries a ~36.5k one-time Opus
compile bill on top. **On amortized $/correct, raw is cheaper at this scale.** This *inverts* only when
the raw corpus is large enough that reading it per-query exceeds (compile-amortized + small-library-read)
— the regime Phase 1 must test on a real repo. Dollar figures are illustrative (input-heavy, public
per-Mtok rates); the durable comparison is corpus-size-dependent and is explicitly **not settled here**.

---

## Honest caveats

1. **n = 1 fixture per type (5 total), k = 2.** This is a scoped gate, not the "20+ fixtures, k≥3,
   3 tiers" population study the reviewers ultimately require. Treat every cell as a point, not a rate.
   The generator (`goal2_gen.py --per-type N`) scales to that study directly; doing so is the natural
   Phase-0b-full follow-up.
2. **The answerer prompt was scaffolded** (both arms were told to look for supersession / aliases /
   code-wins). That scaffold is the single most likely reason the **raw arm did not fail** — it is the
   inference-time `resolve`-style tooling the roadmap names as the cannibalization risk, delivered as a
   prompt. An *un-scaffolded* raw arm would likely fail several fixtures (cf. Phase 0.5 raw-cheap k1,
   which fell for a distractor with a thinner prompt). **So Phase 0b shows: a good inference-time
   prompt ≈ the compiled library on correctness at this scale.** That is the falsifier, fired.
3. **Compiler hallucination is real** (2/5 fixtures) and is currently invisible to a final-answer
   rubric. A citation-integrity gate on the *compiler output* (validate that every cited ADR id /
   anchor actually exists — `decisions.py validate` covers structure but not "the answerer cited a real
   id") is a Phase-1 must.
4. **No tier failed, so the suite did not discriminate** on these fixtures (CALIBRATED: NO for the
   arm-vs-arm contrast). A non-discriminating suite cannot prove a win *or* a loss strongly — it can
   only fail to reject the null. Harder/larger fixtures are needed to make the contrast measurable.
5. **Single grader (Opus).** No inter-judge agreement check. The grades are read-verified and the
   reasons are auditable in `goal2-grades/`, but a second judge would harden the citation-integrity calls.

---

## PASS / FAIL of the Phase-0.5 redirect

**The Phase-0.5 correctness claim does NOT clear the Phase-0b gate.** The redirect's headline —
"on messy corpora the compiled library lifts cheap models where raw reading fails" — was **not
reproduced** when the test was widened to 5 fixture types and the raw arm got a competent prompt:
raw reached 100% too. The honest read is the one the roadmap already pre-committed to:

> *Lead the pitch with **cost-down at scale**, not the correctness gap.* The correctness gap is
> **frontier/prompt-sensitive** and, on small corpora with a decent prompt, **closes to zero**.

What **survives** Phase 0b intact:
- The **product framing** — a verified decision-resolution layer (aliases + supersession + scope +
  code-evidence + conflict/stale flags) — is sound; the compiler produced correct, validated libraries
  for all 5 patterns and the resolver returned the right current decision each time.
- The **durable value hypotheses** (token-collapse + multi-hop caching at scale; freshness guard
  against stale oracles) are **untouched and untested** — Phase 0b was too small to probe them.

What is **falsified / weakened**:
- "Cheap models are lifted to frontier correctness *by compilation specifically*" — at this scale a
  prompt does the same lift. Compilation's correctness premium over a good inference-time resolver is
  **unproven**.

**Recommendation: DO NOT MERGE as a correctness win.** Merge the **harness, generator, fixtures, and
this honest negative-leaning result** (they are the reusable Phase-0b apparatus and a defensible record
that the correctness claim did not hold at n=5/k=2). Then run **Phase-0b-full** before any external
correctness claim: (a) add a **scaffolded-raw / `resolve`-tool arm vs un-scaffolded-raw** to isolate
how much of raw's success is the prompt; (b) scale to a **large real corpus** to test the *cost/scale*
thesis that is compilation's actual moat; (c) add the **compiler citation-integrity gate**; (d)
`--per-type ≥4`, **k ≥ 3**, ≥3 tiers, two judges.

---

## Artifacts (all under this worktree)

- `goal2_gen.py` — deterministic 5-type fixture generator (`--seed`, `--per-type`).
- `goal2-fixtures/` — the 5 generated bundles (`raw/`, `query.txt`, judge-only `gold.json`).
- `compiled/<fixture>/decisions/` — the 5 Opus-compiled, validated decision libraries.
- `goal2-answers/` — all 40 answerer outputs (`<fixture>__<arm>__<model>__k{1,2}.txt`).
- `goal2-grades/<fixture>.json` — per-attempt two-axis verdicts + judge reasons.
- `goal2-results.json` — aggregated matrix, totals, token note, caveats.
- `GOAL2-PHASE0B.md` — this report.
