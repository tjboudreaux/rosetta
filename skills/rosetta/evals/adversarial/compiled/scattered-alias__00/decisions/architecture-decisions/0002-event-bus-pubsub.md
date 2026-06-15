# ADR 0002 — svc-flags_api event bus: Pub/Sub (migrated off RabbitMQ)

- Status: Accepted
- Date: 2026-06-14
- Decided originally: 2026-05-18
- Decider: Platform team
- Sources: `claude · sca0c · 2026-05-18` (raw/03-platform-decision.md); code path `raw/code/flags_api.py` (`EVENT_BUS = "pub/sub"`); git commit `77aa88b 2026-05-17 flags_api: switch event bus to Pub/Sub`
- Related: ADR 0001, ADR 0003 (superseded)

## Context

svc-flags_api (the feature-flag service, fka "Drift" — see ADR 0001) originally published events to
RabbitMQ (see ADR 0003, the early architecture). The platform team decided to migrate off RabbitMQ
onto Pub/Sub for ordering guarantees. Cutover completed 2026-05-17.

Code and git are the authoritative tie-breaker and both confirm the migration:
- `raw/code/flags_api.py`: `EVENT_BUS = "pub/sub"  # migrated from rabbitmq`
- git: `77aa88b 2026-05-17 flags_api: switch event bus to Pub/Sub` (supersedes
  `11bb22c 2025-11-02 flags_api: publish to RabbitMQ`)

## Decision

The current message bus / event queue for svc-flags_api is **Pub/Sub**. RabbitMQ is retired for this
service. This supersedes ADR 0003.

## Consequences

Positive:
- Ordering guarantees the platform decision required.
- A single current answer for "what bus does the feature-flag service use?" — Pub/Sub.

Negative:
- The ops runbook (`raw/02-ops-runbook.md`, 2026-02-10) still instructs draining the RabbitMQ
  consumer group on incident; that guidance is stale post-cutover and must be updated. Mitigated by
  marking ADR 0003 superseded.

## Alternatives considered

- **Stay on RabbitMQ** — rejected; lacked the ordering guarantees needed (see ADR 0003).

## Related

- ADR 0001 (canonical service identity)
- ADR 0003 (RabbitMQ — superseded by this ADR)
- Code path: `raw/code/flags_api.py`; commit `77aa88b`
