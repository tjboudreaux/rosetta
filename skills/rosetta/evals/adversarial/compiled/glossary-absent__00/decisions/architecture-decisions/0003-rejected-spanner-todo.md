# ADR 0003 — "Cloud Spanner for profiles" was an open TODO, never adopted (not a decision)

- Status: Rejected
- Date: 2026-06-14
- Decided originally: 2026-01-09
- Decider: n/a — this records a NON-decision
- Sources: `cursor · abs0c · 2026-01-09` (raw/03-stray-distractor.md)
- Related: ADR 0002 (the actual MySQL datastore decision)

## Context

During planning, a scratch note raised whether Cobalt's profile datastore should be Cloud Spanner.
This must NOT be mistaken for a decision: an open question is not a resolution. This record exists to
explicitly capture and quarantine the distractor so downstream models do not treat it as the answer.

## Decision

Cloud Spanner is **NOT** Cobalt's datastore. The Spanner reference is an unresolved open question,
not an adopted decision.

Evidence:
- cursor abs0c (2026-01-09): 'Random scratch note: "profile datastore: Cloud Spanner?" — someone's
  open question during planning, never confirmed. Marked TODO, never resolved.'

The note is dated 2026-01-09, before the MySQL wiring (git 44ee55f, 2026-03-15). It is phrased as a
question ("Cloud Spanner?"), explicitly marked TODO, and explicitly "never confirmed / never
resolved." No later source revisits or adopts it. The authoritative code/git/ops evidence points to
MySQL (see ADR 0002).

## Consequences

Positive:
- The Spanner distractor is recorded as a rejected non-decision, preventing it from being surfaced
  as Cobalt's datastore.

Negative:
- None. This is a clarifying record.

## Alternatives considered

- **Record Spanner as the datastore** — rejected. It was an unconfirmed TODO and is contradicted by
  code, git, and operational evidence (ADR 0002).

## Related

- raw/03-stray-distractor.md
- ADR 0002 — the confirmed MySQL datastore decision.
