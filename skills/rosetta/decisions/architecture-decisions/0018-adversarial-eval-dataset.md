# ADR 0018 — Adversarial eval dataset for the judgment half

- Status: Accepted
- Date: 2026-06-13
- Decider: Travis Boudreaux
- Sources: evals/adversarial/ (DESIGN.md, fixtures.py, dataset.json, run_evals.py, judge_prompt.md), tests/test_adversarial_evals.py, REVIEW-round1.md, REVIEW-round2.md
- Related: ADR 0002 (coverage manifest surfaces gaps loudly), ADR 0004 (truth hierarchy: code wins), ADR 0017 (test-enforced resilience)

## Context

Rosetta has a deterministic **collector** (well-tested) and an LLM-driven **judgment** half (steps
4–8 of SKILL.md: summarize → anchor to code/git → reconcile on the truth hierarchy → adversarially
verify → write `ground-truth.md`). The judgment half is where the product's value lives and where LLM
anti-patterns bite — hallucination, contradiction, knowledge drift, recency bias, over-confidence,
misattribution, conflation, prompt-injection, false-precision citations, silent coverage gaps. It had
**no eval coverage**: the only behavioral evals (`evals/evals.json`) are machine-bound, manual, and
LLM-judged, and CI only exercised the collector. A regression in the workflow that degraded
ground-truth quality would have been invisible.

## Decision

Add a synthetic, **known-by-construction** adversarial eval dataset under `evals/adversarial/`, graded
at two tiers:

- **Tier A (deterministic, in CI):** 20 scenarios, each materializing a synthetic `$HOME`
  (multi-agent transcript stores in their real on-disk shapes) + a project checkout with real
  code/docs/git. The runner asserts the collector surfaced exactly the planted sessions, anchors and
  code/doc/git markers exist, nothing was misattributed or dropped, excluded sources (Hermes request
  dumps) and unknown stores are handled, and — critically — a **leakage linter** proves no gold token
  (anti-pattern label, scenario id, resolution slogan, rubric phrasing) appears in any solver-visible
  file (project tree, normalized corpus, filenames, or git log). Wired into CI via
  `tests/test_adversarial_evals.py`; pure stdlib.
- **Tier B (LLM-judged, harness/human):** each scenario's `judge_only` gold + a reference
  **claim-support** judge (`judge_prompt.md`) grade the produced `ground-truth.md` — extract atomic
  claims, classify, verify each against a code/manifest/git bundle, and fail false-precision
  citations, confident hedges, and invented contradictions. Out of CI by design (non-deterministic,
  needs model access).

Hard rule: **solver inputs are separated from judge-only gold.** Fixtures contain only natural dev
chatter; all gold lives in `dataset.json` and the emitted bundle, never on disk in the fixture.

The dataset was **adversarially reviewed by an independent model (Codex) in two rounds** before
acceptance; findings are recorded in `REVIEW-round1.md` / `REVIEW-round2.md` and every finding was
re-verified against ground truth (the round-2 reviewer itself hallucinated non-existent scenarios — a
live reminder of why code-wins verification is the discipline).

## Consequences

Positive:
- The judgment half now has a leak-resistant regression gate (Tier A) and a gameable-resistant grading
  protocol (Tier B). Store-class coverage is complete (project-encoded, date-bucketed, fuzzy,
  file-location, database, unknown-store).
- Anti-leakage and claim-support judging are enforced mechanically, not by reviewer goodwill.

Negative:
- Tier B is not automated in CI (needs a model); it is a documented harness. A model regression in
  judgment is caught only when Tier B is run, not on every push.
- Three taxonomy items (quantitative drift, positional-bias invariance, multi-hop reconciliation) are
  deferred and explicitly marked future in DESIGN.md to avoid overstating coverage.

## Alternatives considered

- **Keep only the live-store behavioral evals** — drift with local history, can't supply stable gold,
  can't test absence. Rejected; kept as smoke tests only.
- **Fully deterministic CI eval of the judgment** — impossible without running a model; the synthesis
  is model-driven. Chosen the Tier-A-substrate + Tier-B-judge split instead.
- **Keyword/`must`-`must_not` rubrics** (the existing eval style) — gameable by emitting the right
  section headers and terms. Rejected for claim-support judging after the round-1 review.
