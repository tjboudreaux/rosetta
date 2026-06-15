# ADR 0022 — Eval calibration across model tiers (judge-independent scoring, no-tools variant, gates)

- Status: Accepted
- Date: 2026-06-13
- Decider: Travis Boudreaux
- Sources: evals/adversarial/score.py, evals/adversarial/run_evals.py, evals/adversarial/report.py, evals/adversarial/CALIBRATION.md, evals/adversarial/RESULTS.md, tests/test_score.py
- Related: ADR 0018 (adversarial eval dataset), ADR 0021 (decision query/supersede the evals exercise)

## Context

The eval suite scored 100% on Opus, which proves it is *passable* and leak-free but not that it
*discriminates* model quality (Haiku→Opus). Two specific weaknesses: (1) Tier B is graded by an LLM
judge, so a weak judge corrupts the grade; (2) the decision-history drift family gave the solver
`grep`/`Bash`, measuring retrieval-*with-tools*, not long-context recall. A flat 100% gives no curve.

## Decision

- **Judge-independent objective scoring with a structured-output contract.** `score.py` scores the
  objective parts of the decision-history scenarios (which ADR was superseded, near-miss untouched,
  current store) from a structured `rosetta-verdict` JSON block the solver emits, checked exactly
  against the fixture-derived answer. Absent the block it returns `scorable: false` and routes to the
  LLM judge — it does **not** guess from prose.
- **No-tools long-context variant.** `run_evals.py --emit-bundle` writes `library.txt` (the whole ADR
  library concatenated) so a solver can be tested without search tools — measuring recall, the
  condition where smaller models bend.
- **Calibration gates** (`CALIBRATION.md`): per-tier pass-rate bands, monotonic ordering
  (Opus≥Sonnet≥Haiku), a discrimination requirement, and non-increasing no-tools drift. The suite is
  "calibrated" only if ordering holds and ≥¼ of scenarios separate tiers; otherwise it is too easy,
  too hard, or leaky and must be revised. `report.py` renders the scenario×tier matrix + drift curve.

## Consequences

Positive:
- The objective core no longer depends on judge capability — a Haiku-class *judge* can't corrupt it.
- The harness can now *measure* tier separation, not just pass/fail one model; the report visualizes
  it.

Negative / honest findings:
- **Regex-grading free-form prose is unreliable** — the first scorer produced false negatives
  (newline-spanning "ADR N → Superseded by") and false positives ("migrated FROM Postgres" → "Postgres
  current") on real Haiku/Sonnet output. Hence the structured-block contract; the prose heuristic is
  retained only as explicitly non-authoritative triage (`--heuristic`).
- **The tools-enabled supersession family does not discriminate** — a multi-tier run (RESULTS.md)
  showed Haiku, Sonnet, and Opus all pass every size. It is a ceiling check; discrimination needs the
  no-tools variant or harder traps. That variant is built but not yet run at scale, and multi-tier
  scoring should use k≥3 samples per (scenario,tier) for a pass-*rate*. These are documented as
  pending rather than claimed.

## Alternatives considered

- **Keep regex-on-prose scoring** — proven to invert results; rejected for the structured contract.
- **Fully LLM-judged, no deterministic layer** — leaves the objective core hostage to judge quality;
  rejected.
- **Adaptive per-tier pass thresholds baked into CI** — overfits; the gates are a calibration contract
  for manual multi-tier runs, not a CI gate (Tier B is non-deterministic and out of CI by design).
