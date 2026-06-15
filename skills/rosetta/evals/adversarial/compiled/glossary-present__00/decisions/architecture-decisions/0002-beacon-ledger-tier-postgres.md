# ADR 0002 — Beacon (notification dispatcher) ledger tier migrated to Postgres

- Status: Accepted
- Date: 2026-04-22
- Decided originally: 2026-04-22
- Decider: claude (session glos0c)
- Sources: claude · glos0c · 2026-04-22 (raw/03-migration-decision.md); git commit a1b2c3d 2026-04-20 (raw/git-log.txt); raw/code/notify_svc.py
- Related: 0001-beacon-ledger-tier-mysql.md

## Context

"Beacon" is the notification dispatcher (raw/01-onboarding-glossary.md;
raw/code/notify_svc.py). The "ledger tier" is the strongly-consistent primary
datastore (raw/01-onboarding-glossary.md).

ADR 0001 adopted MySQL for the Beacon ledger tier. MySQL then suffered
hotspotting incidents, prompting a migration review of the notification
dispatcher (raw/03-migration-decision.md).

## Decision

Move the Beacon (notification dispatcher) ledger tier from MySQL to Postgres
for strong consistency. This supersedes the earlier MySQL call (ADR 0001).

Cutover was completed in the prod cluster on 2026-04-20.

This is corroborated by the truth hierarchy (code/git wins):
- git commit a1b2c3d (2026-04-20): "migrate Beacon ledger tier to Postgres;
  disable MySQL writes" (raw/git-log.txt).
- raw/code/notify_svc.py sets `BACKEND = "postgres"` (current backend,
  post-migration) and `LEGACY_MYSQL_ENABLED = False` (legacy MySQL client
  retained temporarily for backfill only).

## Consequences

Positive:
- Strong consistency for the Beacon primary datastore.
- Resolves the MySQL hotspotting incidents that motivated the migration.

Negative:
- A legacy MySQL client is retained temporarily for backfill only
  (`LEGACY_MYSQL_ENABLED = False` in raw/code/notify_svc.py); it must be
  removed once backfill is complete.

## Alternatives considered

- Stay on MySQL (ADR 0001) — rejected due to hotspotting incidents and the
  need for strong consistency.

## Related

- Supersedes ADR 0001 (Beacon ledger tier on MySQL).
- Code path: raw/code/notify_svc.py (`BACKEND = "postgres"`)
- Git: a1b2c3d "migrate Beacon ledger tier to Postgres; disable MySQL writes"
