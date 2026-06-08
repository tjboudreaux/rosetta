# PDR 0004 — Ingest decisions made outside code and agent chat

- Status: Proposed
- Date: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation, requirement #2)
- Related: PDR 0001, ADR 0012, BDR 0001

## Context

The most consequential decisions — pricing, partnerships, hiring, strategy — are often made by humans
in a Circleback-recorded meeting or a Slack thread, never touching code or an agent transcript. A
decision engine that only sees code and agent chat misses exactly the decisions that matter most to the
business.

## Decision (proposed)

Make external, human-made decisions a first-class input: ingest from Circleback, Slack, Gmail, Calendar,
and trackers via MCP, normalize their provenance into the same citation format, and scaffold
BDR/PDR/ADR drafts for human confirmation. (Technical design: ADR 0012.)

## Consequences

Positive:
- Business and product decisions get the same durable, cited treatment as technical ones.
- Closes the gap between "what the team decided in the room" and "what the repo knows."

Negative:
- Depends on MCP availability/auth and is non-deterministic; ingested items stay `Proposed` until a
  human confirms (ADR 0004). Privacy: external content may carry sensitive material — kept in the
  gitignored `.agents/` cache.

## Open questions

- Which source to pilot first — Circleback meeting notes are the highest-signal for business decisions
  and already in the user's MCP auth cache; likely the first connector.

## Alternatives considered

- **Manual entry only** — humans rarely write the record; ingestion + confirm is far more likely to
  capture reality.

## Related

- ADR 0012 (MCP ingestion), `references/external-sources.md`, BDR 0001.
