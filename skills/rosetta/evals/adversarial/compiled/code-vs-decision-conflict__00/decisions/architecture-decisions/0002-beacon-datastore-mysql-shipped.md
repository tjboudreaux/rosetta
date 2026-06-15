# ADR 0002 — Beacon notification dispatcher datastore: MySQL (shipped to production)

- Status: Accepted
- Date: 2026-05-25
- Decided originally: 2026-05-24
- Decider: core-svc lead
- Supersedes: ADR 0001
- Sources: code path `notify_svc.py` (`DATASTORE = "mysql"  # what actually shipped`); git 55dd66e (2026-05-24 notify_svc: provision MySQL (prod), retire Postgres POC); claude · cvd0b · 2026-05-25 (raw/02-impl-note.md)
- Related: ADR 0001 (Beacon datastore: Postgres — stale, superseded)

## Context

ADR 0001 recorded Postgres as Beacon's datastore (Accepted, 2026-02-01) but was never
amended after implementation. During the build the team hit a **licensing blocker on
Postgres** and shipped on **MySQL** instead (claude session cvd0b, 2026-05-25).

Per the Rosetta truth hierarchy, **code and git history win** over an un-amended decision
record. The production code and the git log both confirm MySQL is the live datastore:

- `notify_svc.py`: `DATASTORE = "mysql"  # what actually shipped` (comment: "ADR says
  Postgres but licensing blocked it; see impl note").
- git 55dd66e (2026-05-24): "notify_svc: provision MySQL (prod), retire Postgres POC".

Prod has been on MySQL since cutover. This ADR records that reality and supersedes the
stale Postgres record.

## Decision

Beacon (notification dispatcher) uses **MySQL** as its datastore in production. The
current-state claim is anchored to the code path `notify_svc.py` (`DATASTORE = "mysql"`)
and git commit 55dd66e, which provisioned MySQL in prod and retired the Postgres POC.

## Consequences

Positive:
- The decision library now matches production. A downstream model querying Beacon's
  datastore resolves to MySQL, not the stale Postgres claim.
- The Postgres licensing blocker is no longer on the critical path.

Negative:
- The original Postgres ADR sat un-amended from cutover (2026-05-24) until this
  reconciliation — a documentation gap. Mitigated by superseding ADR 0001 and anchoring
  this record to code + git so the divergence cannot recur silently.

## Alternatives considered

- **Postgres** (ADR 0001) — blocked by a licensing issue during the build; retired at
  cutover (git 55dd66e). Not viable.
- **Keep ADR 0001 as the source of truth** — rejected: it contradicts shipped code and
  git history, which take precedence under the truth hierarchy.

## Related

- Supersedes ADR 0001 (Beacon datastore: Postgres).
- Code: `notify_svc.py` (`DATASTORE = "mysql"`). Git: 55dd66e (MySQL prod), 88ff99a
  (retired Postgres POC). Impl note: raw/02-impl-note.md.
