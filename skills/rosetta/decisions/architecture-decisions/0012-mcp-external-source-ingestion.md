# ADR 0012 — External-source ingestion via MCP (Circleback, Slack, …)

- Status: Proposed
- Date: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation, requirement #2); design `references/external-sources.md`
- Related: PDR 0004, ADR 0002, ADR 0007

## Context

Many decisions — especially business ones — are made in meetings and chat, never in code or an agent
transcript. Circleback (meeting notes), Slack, Gmail, Calendar, Atlassian/Linear/Notion are reachable
as MCP servers (Circleback/Slack/Gmail/Calendar are in the user's claude.ai marketplace auth cache).
To be the engine for *all* decisions, Rosetta must ingest these too. Unlike transcript collection,
this step is agent-driven and on-demand (it calls MCP tools and needs auth), so it can't be fully
deterministic.

## Decision (proposed)

Add an ingestion step (agent-driven, with a deterministic skeleton) that queries configured MCP
sources for a project/time window, extracts candidate decisions, normalizes their provenance into the
same `Sources:` citation format (e.g. `circleback · <meeting-id> · <date>`), and scaffolds BDR/PDR/ADR
drafts via `decisions.py new` for human confirmation. A registry (`references/external-sources.md`)
mirrors `agent-stores.md`: source → MCP tool prefix → how to query and cite it.

## Consequences

Positive:
- Human/meeting decisions stop evaporating; the library spans code, chat, and conversation.

Negative:
- Depends on the user's MCP servers being authed and available (esp. in headless/cron runs); ingestion
  is non-deterministic and must be treated as *Proposed* drafts pending human confirmation, per the
  truth hierarchy (ADR 0004).

## Alternatives considered

- **Per-service exporters (Circleback API, Slack API)** — more control but bespoke auth per service and
  duplicates what MCP already brokers; prefer MCP, fall back to exporters only where no server exists.

## Related

- `references/external-sources.md`; PDR 0004 (the product framing); `decisions.py new`.
