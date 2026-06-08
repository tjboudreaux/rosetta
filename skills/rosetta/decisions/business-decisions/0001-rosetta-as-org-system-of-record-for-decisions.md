# BDR 0001 — Rosetta as the org system-of-record for decisions

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation — explicit goal)
- Related: PDR 0001, PDR 0004, ADR 0012

## Context

Organizational knowledge of *why* things were decided lives in people's heads, scattered chats, and
recorded meetings. When someone leaves or a quarter passes, the rationale is gone — decisions get
re-litigated, contradicted, or silently reversed. This is a business risk (wasted cycles, repeated
mistakes, weak audit trail), not just a documentation nicety.

## Decision

Adopt Rosetta as the **system-of-record for decisions across the org** — technical, product, and
business — so every significant decision has one cited, durable, supersedable record, reconciled from
agents, code, and human conversations.

## Business impact

- **Institutional memory:** the "why" outlives the people and the quarter.
- **Faster onboarding:** a new hire (or agent) reads the decision library instead of interviewing
  everyone.
- **Decision audit:** a clear trail of what was decided, by whom, when, and what superseded it.
- **Less rework:** fewer silently-contradicted or re-litigated decisions.
- Judged in hindsight by: decisions captured vs. decisions made, and reduction in "why did we do this?"
  archaeology.

## Consequences

Positive:
- A single, queryable source of organizational decision context for humans and agents alike.

Negative:
- Requires habit + light process to keep current; mitigated by automated ingestion (ADR 0012) and
  deterministic tooling (ADR 0009) so capture is cheap.

## Alternatives considered

- **Wiki / Confluence pages** — drift from reality, lack provenance and a supersede lifecycle, and
  aren't agent-readable as structured records; Rosetta records are cited, validated, and reconciled.
- **Do nothing (status quo)** — the risk above persists; rejected.

## Related

- PDR 0001 (engine vision), PDR 0004 (human-source ingestion), ADR 0012 (MCP ingestion).
