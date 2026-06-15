# ADR 0002 — Cobalt's datastore is MySQL on cluster mysql-prod-eu

- Status: Accepted
- Date: 2026-06-14
- Decided originally: 2026-03-15
- Decider: infra (per git commit author / dashboard export)
- Sources: git commit `44ee55f · 2026-03-15` "point Cobalt at mysql-prod-eu" (raw/git-log.txt); `raw/code/billing_core.py` (`DSN = "mysql://mysql-prod-eu/profiles"`); `droid · abs0b · 2026-03-15` (raw/02-dashboard-export.md); `claude · abs0d · 2026-05-01` (raw/04-incident.md)
- Related: ADR 0001 (Cobalt scope), ADR 0003 (rejected Spanner TODO)

## Context

Cobalt (the user-profile service, see ADR 0001) needs a persistent datastore. The datastore must be
determined from code, git history, and operational evidence rather than from any explicit "X uses Y"
statement, since the corpus has no glossary. Per compiler rules, code and git WIN over speculation.

## Decision

Cobalt's datastore is **MySQL**, hosted on the cluster **`mysql-prod-eu`**.

Evidence (code/git authoritative, ops corroborating):
- Code (billing_core.py): `DSN = "mysql://mysql-prod-eu/profiles"` — a `mysql://` DSN pointing at the
  `mysql-prod-eu` cluster, database `profiles`.
- Git (44ee55f, 2026-03-15): commit "point Cobalt at mysql-prod-eu" — explicit, dated wiring of
  Cobalt to the MySQL cluster.
- Dashboard export (droid abs0b, 2026-03-15): "Cluster mysql-prod-eu hosts the Cobalt workloads.
  Backend engine reported by the cluster: MySQL."
- Incident review (claude abs0d, 2026-05-01): "latency spike on mysql-prod-eu. The MySQL read
  replicas lagged ... Root cause: replica failover. No datastore change." — confirms MySQL remained
  the datastore through the latest dated event.

## Consequences

Positive:
- Cobalt's persistence layer is unambiguously MySQL on `mysql-prod-eu`, corroborated by four
  independent signals across code, git, dashboards, and incident review.

Negative:
- MySQL read-replica lag has already caused at least one latency incident (abs0d); replica failover
  is a known risk to Cobalt's profile reads. This is an operational concern, not a datastore change.

## Alternatives considered

- **Cloud Spanner** — rejected. The only mention of Spanner is an unresolved TODO scratch question
  (see ADR 0003). It was never confirmed and is contradicted by code, git, and ops evidence.

## Related

- raw/code/billing_core.py, raw/git-log.txt, raw/02-dashboard-export.md, raw/04-incident.md
- ADR 0001 — Cobalt scope.
- ADR 0003 — the rejected Spanner TODO distractor.
