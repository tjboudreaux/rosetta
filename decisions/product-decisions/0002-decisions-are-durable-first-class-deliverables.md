# PDR 0002 — Decisions are durable, first-class deliverables

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation)
- Related: PDR 0001, ADR 0004, ADR 0007

## Context

A reconciled `ground-truth.md` answers "what is true now," but a decision needs to persist on its own:
addressable by ID, carrying its rationale, provenance, and a status that can later be superseded. Prose
buried in a state document can't do that.

## Decision

Treat each decision as a standalone, durable record (ADR/PDR/BDR) with citations and a status
lifecycle (`Proposed → Accepted → Superseded`). A decision a transcript merely discussed is `Proposed`,
not asserted, until code or an explicit human call confirms it (truth hierarchy, ADR 0004). Reversals
are always recorded by superseding the prior record — the library never silently oscillates.

## Consequences

Positive:
- The "why" behind the system survives long after the conversation scrolls away.
- Auditable history: you can see when and why a decision changed.

Negative:
- Discipline cost: someone (agent or human) must write and supersede records; eased by deterministic
  scaffolding/validation (ADR 0009).

## Alternatives considered

- **Decisions live only in commit messages / chat** — unaddressable, no status, no provenance hierarchy;
  rejected.

## Related

- ADR 0007 (format), ADR 0009 (tooling), `references/decision-schema.md` (status lifecycle).
