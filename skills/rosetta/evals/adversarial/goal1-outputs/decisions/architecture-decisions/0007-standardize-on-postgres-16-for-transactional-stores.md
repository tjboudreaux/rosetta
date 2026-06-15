# ADR 0007 — Standardize on Postgres 16 for transactional stores

- Status: Accepted
- Date: 2025-07-10
- Decided originally: 2025-07-10
- Decider: Eng
- Sources: corpus R09 (eng-log · 2025-07-10)

## Context

The org wanted a single supported version for transactional datastores.

## Decision

Standardize on **Postgres 16** for transactional stores (R09).

## Consequences

Positive:
- One supported version simplifies ops, tooling, and upgrades.

Negative:
- Services on older versions must upgrade.

## Alternatives considered

- **Mixed versions / other engines** — rejected for operational consistency.

## Related

- corpus R09.
