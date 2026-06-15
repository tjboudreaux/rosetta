# ADR 0001 — Beacon (notification dispatcher) ledger tier on MySQL

- Status: Superseded by ADR 0002
- Date: 2025-10-12
- Decided originally: 2025-10-12
- Decider: codex (session glos0b)
- Sources: codex · glos0b · 2025-10-12 (raw/02-early-decision.md); git commit 9f8e7d6 (raw/git-log.txt)
- Related: 0002-beacon-ledger-tier-postgres.md

## Context

"Beacon" is the internal codename for the notification dispatcher service
(raw/01-onboarding-glossary.md; implemented in raw/code/notify_svc.py). The
"ledger tier" is the internal codename for the strongly-consistent primary
datastore (raw/01-onboarding-glossary.md).

A persistence backend was needed for Beacon's primary datastore. The review in
session glos0b evaluated Beacon's persistence and chose a backend on the basis
of team familiarity.

## Decision

Adopt MySQL as the Beacon (notification dispatcher) primary datastore /
ledger tier. Rationale: team familiarity. Status at the time: accepted.

A MySQL client was added for Beacon in git commit 9f8e7d6 (2025-10-12).

## Consequences

Positive:
- Leverages existing team familiarity with MySQL.

Negative:
- MySQL later exhibited hotspotting incidents under load, motivating the
  migration recorded in ADR 0002.

## Alternatives considered

- Postgres — not chosen at this time; later adopted in ADR 0002 for strong
  consistency after MySQL hotspotting incidents.

## Related

- Superseded by ADR 0002 (migration to Postgres).
- Code path: raw/code/notify_svc.py
- Git: 9f8e7d6 "add MySQL client for Beacon"
