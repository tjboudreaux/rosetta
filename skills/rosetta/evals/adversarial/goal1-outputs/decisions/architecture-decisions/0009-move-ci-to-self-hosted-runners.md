# ADR 0009 — Move CI to self-hosted runners

- Status: Accepted
- Date: 2026-01-15
- Decided originally: 2026-01-15
- Decider: Eng
- Sources: corpus R16 (eng-log · 2026-01-15)

## Context

CI needed more control over capacity/cost. R16 notes this is unrelated to auth.

## Decision

Move CI to **self-hosted runners** (R16).

## Consequences

Positive:
- Control over runner capacity and cost.

Negative:
- The org now operates and secures its own runner fleet.

## Alternatives considered

- **Hosted CI runners** — rejected for cost/capacity control.

## Related

- corpus R16.
