# Rosetta — maximal product-value plan (grounded in this session's evidence + the literature)

## The thesis (what actually makes Rosetta valuable)

This session ran 16+ tool-calling experiments (v3→v6) and a verified literature review. They converge
on one conclusion:

> **The failures that actually break LLMs are retrieval-defeating, not scale-related.** grep/long-context
> handle size, reversals, conditionals, counts, and future-dates fine. Models break when the answer is
> **unfindable by the question's keywords** — semantic-evasion / codename pivots / multi-hop indirection
> (our v5 broke Sonnet; v6's double-pivot broke Sonnet and tripped Gemini-Pro). The literature names the
> same thing: NoLiMa (remove literal lexical overlap → 10/12 models ≤50% at 32K), "lost in the middle,"
> distractor sensitivity, context rot.

**Rosetta's compiled, normalized, supersession-resolved decision library is the antidote to exactly
that failure class.** So the product's leverage is **the compilation step**, not inference-time
prompting. Everything below maximizes that leverage and proves it.

Value is measured on three axes (established this session): (1) **correctness**, (2) **correctness at
token savings**, (3) **bringing SoTA correctness to cheaper/distilled models**. So far we've shown the
folder's value as *efficiency* (−22–44% tokens); the open prize is converting it to *correctness*.

---

## Initiatives, prioritized by leverage × evidence

### P0 — Prove and productize the core thesis

**P0.1 Normalizing compilation.** When Rosetta builds the ADR library (`collect` → distill → `decisions`),
the compile step must:
- **Decode codenames / normalize terminology** — write ADR titles/bodies in the *queryable* vocabulary
  ("EU enterprise billing event-store → managed Postgres (CloudSQL)"), and emit an **alias/glossary
  index** (`Project Meridian = EU enterprise billing`; `managed relational tier = CloudSQL`).
- **Resolve supersession explicitly** — every record carries `Status:` + `Supersedes/Superseded-by`,
  so the *current* answer is a status filter, not a timeline reconstruction.
- **Anchor to code/git** — each decision links the code/commit that makes it true (code-wins).

*Vector:* semantic-evasion + multi-hop (the only mode that breaks models). *Value:* converts the v5/v6
breaks from FAIL → PASS, and lets a **cheap model + the folder** match a frontier model + raw. *Measure:*
re-run the v5/v6 fixtures with a normalized compiled folder; target raw-FAIL → folder-PASS for
Sonnet/Haiku.

**P0.2 The proof experiment (the one we kept predicting, never ran).** Build the normalized compiled
variant of `S3_double_pivot` / `A1_codename` and run raw vs folder×CLI on Haiku/Sonnet/Gemini-Flash.
Expected, and now testable: **raw < 100%, normalized-folder ≈ 100% at a fraction of the cost.** This is
the single highest-credibility artifact — it turns "the folder saves tokens" into "the folder is the
difference between a wrong answer and a right one, on a cheap model." Ship it as the headline benchmark.

### P1 — Freshness (drift) + retrieval ergonomics

**P1.1 Drift / freshness guard.** Rosetta's job isn't one-time compilation — it's keeping the library
*current*. Add: a `decisions validate --staleness` check that flags ADRs whose cited code/commit has
moved on; re-`collect` deltas; auto-`supersede` when a newer decision/commit contradicts an Accepted
record. *Vector:* knowledge drift + supersession. *Measure:* a drift eval scenario (code moved past an
ADR → library must flag/supersede, not silently serve stale).

**P1.2 Retrieval ergonomics in `decisions.py`.** Make the CLI do the multi-hop the model won't:
`search` alias-aware (resolve codenames before matching) and status-filtered by default; add
`get --resolve` that follows Supersedes links to the live record. *Vector:* double-pivot / distractor
density. *Measure:* the v6 S3 double-pivot becomes a single CLI call.

### P2 — Eval program & calibration (make the value continuously provable)

**P2.1 Fold the retrieval-defeating archetypes into the dataset.** Promote v5/v6 (codename pivot,
double-pivot, scope-exception, salient-number, aggregation) into `dataset.json` as first-class
scenarios with gold + the leakage linter. Keep the *negative* archetypes (A2/A3/A4/A5/T1/T3 that models
pass) as **ceiling checks** — they prove the suite isn't just "everything is hard."

**P2.2 Close the eval coverage gaps the research flagged.** (a) **Drift evals** — pinned regression
suite + exact-match-over-time across model versions (the literature's gap *and* ours). (b) **Agentic
evals** — tool-use + error-compounding scenarios for the `decisions`/`collect` CLI agent loop. Both came
back as evidence gaps in the deep-research pass.

**P2.3 Calibration + cost as living gates.** Run the `CALIBRATED: YES/NO` report + the product-value
panel per model tier on every change; require k≥3 samples before quoting numbers; keep `$/correct`
behind the efficacy gate. Wire Tier-A into CI (already done); schedule Tier-B periodically.

---

## Sequencing

1. **P0.1 + P0.2 first** — the normalizing compiler + the proof experiment. This is the thesis; every
   other initiative compounds on a high-quality compiled artifact, and the proof is the credibility
   anchor.
2. **P1** — freshness + retrieval ergonomics (turns a one-shot artifact into a durable, queryable one).
3. **P2** — institutionalize via the eval/calibration program so the value is continuously demonstrated
   and regressions are caught.

## Honest risks (carry these into every claim)

- **Single-sample evidence.** v3–v6 are n=1 per cell; the proof experiment needs k≥3 + a couple of
  distinct fixtures before external quoting.
- **The compiler is itself an LLM step** — normalization can introduce its own errors. It MUST be
  code/git-anchored and validated (`decisions validate`), or it just moves the hallucination upstream.
- **Frontier models keep improving** — the *correctness* gap (folder vs raw) may shrink on the strongest
  models over time; the **cost/efficiency** value (cheap model + folder ≈ frontier) is the more durable
  selling point. Lead with cost-down, support with correctness-on-cheap-models.
- **Compiled libraries go stale** — without P1.1 the folder becomes a confidently-wrong oracle, which is
  worse than raw. Freshness is not optional.

## One-line summary
**Invest in the normalizing, supersession-resolving, code-anchored compiler (P0) and prove it flips the
retrieval-defeating breaks on cheap models — that's where Rosetta turns a model failure into a product
win; then keep it fresh (P1) and continuously calibrated (P2).**

> **Update (2026-06-18):** P0.2 was executed as the kill test — thesis holds at scale (KILLTEST-RESULTS.md). This plan is the pre-proof articulation; retain for sequencing rationale.
