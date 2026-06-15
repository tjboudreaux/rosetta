# ADR 0008 — Nightly DB backups to S3 with 30-day retention

- Status: Accepted
- Date: 2025-11-03
- Decided originally: 2025-11-03
- Decider: Eng
- Sources: corpus R15 (eng-log · 2025-11-03)

## Context

The org needed a durable, retained backup policy for databases.

## Decision

Take **nightly DB backups to S3 with 30-day retention** (R15).

## Consequences

Positive:
- Durable off-host backups with a defined recovery window.

Negative:
- S3 storage cost; 30-day window bounds point-in-time recovery.

## Alternatives considered

- **No off-host backups / shorter retention** — rejected for durability/recovery needs.

## Related

- corpus R15.
