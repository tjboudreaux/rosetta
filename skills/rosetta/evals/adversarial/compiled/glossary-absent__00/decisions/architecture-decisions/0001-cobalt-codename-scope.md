# ADR 0001 — "Cobalt" codename refers to the user-profile service (squad + workload)

- Status: Accepted
- Date: 2026-06-14
- Decided originally: 2025-12-03
- Decider: infra org (per org roster note)
- Sources: `hermes · abs0a · 2025-12-03` (raw/01-org-notes.md); corroborated by `droid · abs0b · 2026-03-15` (raw/02-dashboard-export.md) and `claude · abs0d · 2026-05-01` (raw/04-incident.md)
- Related: ADR 0002 (Cobalt datastore), raw/code/billing_core.py, git commit 44ee55f

## Context

The corpus has NO explicit glossary entry — "Cobalt" is never defined with an "X is Y" statement.
The meaning of the codename must be INFERRED from scattered co-occurrence across org notes,
a dashboard export, and an incident review.

## Decision

INFERRED (no explicit definition found): "Cobalt" denotes the **user-profile service** — the squad
and the workload responsible for user-profile functionality.

Evidence supporting the inference:
- Org roster (hermes abs0a): "the Cobalt squad owns everything user-profile related — sign-up,
  profile reads, avatar storage. They report into infra."
- Dashboard export (droid abs0b): "Cluster mysql-prod-eu hosts the Cobalt workloads."
- Incident review (claude abs0d): "Cobalt's profile reads degraded" during a latency spike.

All three independent sources tie "Cobalt" to user-profile / profile-read functionality. No source
contradicts this.

## Consequences

Positive:
- Downstream queries about "Cobalt" can be answered as the user-profile service without re-deriving
  it from raw co-occurrence.

Negative:
- This is an inference, not an explicit definition. It is flagged as INFERRED; if an authoritative
  glossary later appears, this record should be reconciled against it.

## Alternatives considered

- **Treat "Cobalt" as undefined / unknown** — rejected. Three independent sources consistently
  associate it with user-profile work, which is sufficient to infer the scope with high confidence.

## Related

- raw/01-org-notes.md, raw/02-dashboard-export.md, raw/04-incident.md
- ADR 0002 — Cobalt's datastore.
