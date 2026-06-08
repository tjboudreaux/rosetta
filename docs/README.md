# Rosetta documentation

Rosetta reconciles every AI coding agent's local conversation history — plus git and docs — into one
**cited ground truth**, and distills durable **decision records** (ADR / PDR / BDR).

## Contents

- [Getting started](getting-started.md) — install, first ground truth, first decision.
- [Agents & discovery](agents.md) — the 18 supported stores, how scoping works, adding your own.
- [Decision records](decisions.md) — the ADR/PDR/BDR format, the `decisions.py` tool, team customization.
- [CLI reference](cli.md) — `rosetta collect | discover | decisions`, all flags.
- **Examples**
  - [End-to-end walkthrough](examples/end-to-end.md) — discover → reconcile → distill decisions.
  - [Example ground truth](examples/ground-truth.example.md) — what Rosetta writes.

## The two ideas that make Rosetta trustworthy

1. **Coverage is loud.** Every run shows what was found *and what was missed* (unmatchable sessions,
   unknown stores) before it summarizes — the worst failure is a confident summary built on a silent gap.
2. **Code wins over chat.** Sources are reconciled on one truth hierarchy —
   `current code / git > committed decisions > docs > latest conversation > older conversation` — so a
   thing a transcript merely *discussed* is recorded as proposed/intended, never asserted as done.

Everything heavy and mechanical (resolving stores, parsing schemas, numbering/indexing/validating
decisions) is **deterministic Python**, so the agent spends tokens only on judgment.
