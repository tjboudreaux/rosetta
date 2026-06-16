# ADR 0002 — Beacon IdP: Auth0 (afternoon call)

- Status: Superseded by ADR 0003
- Date: 2026-03-04
- Decided originally: 2026-03-04
- Decider: codex (amb0b)
- Sources: codex · amb0b · 2026-03-04T16:40 (raw/02-decision-afternoon.md)
- Related: ADR 0001 (same-day AM conflicting call), ADR 0003 (Keycloak, supersedes this)

## Context

A separate afternoon auth review on 2026-03-04 revisited Beacon's IdP question, apparently
unaware of (or in disagreement with) the morning call (ADR 0001) that had chosen Ping.

## Decision

Adopt Auth0 as the IdP for Beacon.

## Consequences

Positive:
- Captured the PM review's preferred IdP.

Negative:
- Directly conflicted with the same-day AM call (Ping, ADR 0001); the transcript itself notes the
  conflict was unresolved at end of day. A naive "latest-same-day-wins" rule would wrongly treat
  this PM choice as final.
- A later follow-up (ADR 0003) found Auth0 did not meet Beacon's SCIM requirements, so this
  decision was reversed.

## Alternatives considered

- **Ping** — chosen in the same-day AM review (ADR 0001); also later rejected for SCIM.
- **Keycloak** — not raised until the 2026-04-19 follow-up; ultimately adopted (ADR 0003).

## Related

- Superseded by ADR 0003 (Keycloak), which supersedes BOTH this PM call and the AM call (ADR 0001).
- raw/02-decision-afternoon.md
