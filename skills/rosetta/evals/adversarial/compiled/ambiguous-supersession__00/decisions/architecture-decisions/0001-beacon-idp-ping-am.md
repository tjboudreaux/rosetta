# ADR 0001 — Beacon IdP: Ping (morning call)

- Status: Superseded by ADR 0003
- Date: 2026-03-04
- Decided originally: 2026-03-04
- Decider: claude (amb0a)
- Sources: claude · amb0a · 2026-03-04T09:12 (raw/01-decision-morning.md)
- Related: ADR 0002 (same-day PM conflicting call), ADR 0003 (Keycloak, supersedes this)

## Context

Beacon (the notification dispatcher) needs an identity provider (IdP). A morning auth review
on 2026-03-04 evaluated options and made a call to settle the IdP question.

## Decision

Adopt Ping as the IdP for Beacon.

## Consequences

Positive:
- Gave Beacon a nominal IdP decision out of the AM auth review.

Negative:
- Conflicted with a separate same-day PM review (ADR 0002) that chose Auth0, leaving the IdP
  unresolved at end of day.
- A later follow-up (ADR 0003) found Ping did not meet Beacon's SCIM requirements, so this
  decision was reversed.

## Alternatives considered

- **Auth0** — chosen instead in the same-day PM review (ADR 0002); also later rejected for SCIM.
- **Keycloak** — not raised until the 2026-04-19 follow-up; ultimately adopted (ADR 0003).

## Related

- Superseded by ADR 0003 (Keycloak), which supersedes BOTH this AM call and the PM call (ADR 0002).
- raw/01-decision-morning.md
