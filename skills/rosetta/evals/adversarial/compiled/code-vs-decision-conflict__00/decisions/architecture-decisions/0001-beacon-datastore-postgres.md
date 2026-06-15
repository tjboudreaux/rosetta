# ADR 0001 — Beacon notification dispatcher datastore: Postgres

- Status: Superseded by ADR 0002
- Date: 2026-02-01
- Decided originally: 2026-02-01
- Decider: core-svc lead
- Sources: codex · cvd0a · 2026-02-01 (raw/01-adr-record.md); git 88ff99a (2026-02-01 notify_svc: scaffold against Postgres POC)
- Related: ADR 0002 (Beacon datastore: MySQL — what actually shipped)

## Context

Beacon, the notification dispatcher, needed a persistent datastore. The original ADR
(codex session cvd0a, 2026-02-01) recorded the choice as Postgres, Status Accepted.

**This record is STALE.** It was never amended after implementation. Per the truth
hierarchy (code and git history win over an un-amended decision record), the production
reality diverged: Postgres hit a licensing blocker during the build and was retired at
cutover in favor of MySQL. See ADR 0002.

## Decision

(As originally recorded — now superseded.) Beacon will use Postgres as its datastore.

This decision was Accepted on paper but never reached production. The Postgres path
existed only as a POC scaffold (git 88ff99a) and was retired (git 55dd66e).

## Consequences

Positive:
- (Intended) Single mature relational store for the dispatcher.

Negative:
- A Postgres licensing blocker stopped this from shipping. The team pivoted to MySQL
  but never amended this record, leaving the decision library out of sync with prod —
  the exact staleness this ADR is now marked to correct.

## Alternatives considered

- **MySQL** — at decision time, not chosen. It later became the shipped datastore once
  the Postgres licensing blocker surfaced (see ADR 0002).

## Related

- Superseded by ADR 0002 (Beacon datastore: MySQL).
- raw/01-adr-record.md (original Accepted record), git 88ff99a (Postgres POC scaffold).
