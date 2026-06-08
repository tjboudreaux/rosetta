# PDR 0001 — Rosetta as the universal decision context engine

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation — explicit direction)
- Related: PDR 0002, PDR 0003, PDR 0004, ADR 0007, BDR 0001

## Context

Rosetta began as a transcript reconciler producing one `ground-truth.md`. But the durable value isn't
the transcripts — it's the **decisions** inside them, plus the decisions made in code, meetings, and
chat. Decisions today are scattered and evaporate: across five agents, multiple repos, Slack, and
Circleback meetings, with no single place that records what was decided, by whom, and why.

## Decision

Reposition Rosetta as **the context engine for all decisions** — technical (ADRs), product (PDRs),
and business (BDRs) — made by **agents or humans**, sourced from agent conversations, the codebase and
git, and external systems (Circleback, Slack, …). Ground-truth reconciliation becomes one capability
feeding a broader goal: a cited, reconciled, queryable decision record for any project or team.

## Consequences

Positive:
- One north-star ties the roadmap together: machine-wide discovery (ADR 0010), decision records
  (ADR 0007), customization (ADR 0008), external ingestion (ADR 0012).
- Institutional memory and onboarding stop depending on who remembers the meeting (see BDR 0001).

Negative:
- Larger surface area than a single skill; managed by shipping deterministic mechanics first and
  capturing heavier capabilities as Proposed ADRs rather than building everything at once.

## Open questions

- How far to go toward a queryable interface (search/ask over the decision corpus) vs. plain markdown +
  index — open; start with markdown + the generated index.

## Alternatives considered

- **Keep Rosetta as a transcript→ground-truth tool** — leaves the decision corpus unbuilt and the
  human/meeting decisions uncaptured; rejected.
- **A separate new product for decisions** — duplicates Rosetta's collection + provenance machinery;
  fold it into Rosetta instead.

## Related

- ADR 0007 (records as first-class output), PDR 0004 (human-source decisions), BDR 0001 (business case).
