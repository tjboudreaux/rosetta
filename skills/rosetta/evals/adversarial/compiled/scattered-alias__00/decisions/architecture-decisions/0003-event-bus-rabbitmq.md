# ADR 0003 — svc-flags_api event bus: RabbitMQ (early architecture)

- Status: Superseded by ADR 0002
- Date: 2025-11-02
- Decided originally: 2025-11-02
- Decider: Platform team
- Sources: `claude · sca0a · 2025-11-02` (raw/01-arch-note.md); git commit `11bb22c 2025-11-02 flags_api: publish to RabbitMQ`; `codex · sca0b · 2026-02-10` (raw/02-ops-runbook.md)
- Related: ADR 0001, ADR 0002

## Context

In the early architecture, the Drift pipeline — i.e. svc-flags_api / the feature-flag service (see
ADR 0001) — published events to RabbitMQ. This was the operating assumption for the ops runbook,
which directed draining the RabbitMQ consumer group on incident (`raw/02-ops-runbook.md`).

## Decision

svc-flags_api publishes events to **RabbitMQ**.

## Consequences

Positive:
- Established a working event pipeline for the early architecture.

Negative:
- Lacked the ordering guarantees later required, prompting the migration to Pub/Sub.

## Alternatives considered

- (Recorded historically; this was the initial choice.)

## Related

- This decision is **superseded by ADR 0002** (migration to Pub/Sub, cutover 2026-05-17,
  commit `77aa88b`).
- ADR 0001 (canonical service identity)
- Source: `claude · sca0a · 2025-11-02`; commit `11bb22c`
