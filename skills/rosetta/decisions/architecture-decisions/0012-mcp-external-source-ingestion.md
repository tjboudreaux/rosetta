# ADR 0012 — External-source ingestion via MCP (Circleback, Slack, …)

- Status: Accepted (scaffolder + workflow shipped 2026-06-08; live-MCP connectors unverified)
- Date: 2026-06-08
- Decided originally: 2026-06-07
- Reviewed: 2026-06-18
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-08` (this conversation, requirement #2); `scripts/ingest.py`; `references/external-sources.md`
- Related: PDR 0004, ADR 0002, ADR 0007

## Context

Many decisions — especially business ones — are made in meetings and chat, never in code or an agent
transcript. Circleback (meeting notes), Slack, Gmail, Calendar, Atlassian/Linear/Notion are reachable
as MCP servers (Circleback/Slack/Gmail/Calendar are in the user's claude.ai marketplace auth cache).
To be the engine for *all* decisions, Rosetta must ingest these too. Unlike transcript collection,
this step is agent-driven and on-demand (it calls MCP tools and needs auth), so it can't be fully
deterministic.

## Decision

Split the work along the deterministic/non-deterministic seam:

- **Shipped (2026-06-08) — the deterministic half:** `scripts/ingest.py` (exposed as `rosetta ingest`)
  takes a JSON array of extracted decisions and writes one reviewable record each, stamped
  `Status: Proposed`, with the external `Sources:` citation and a first-draft body. A human confirms,
  flips to `Accepted`, and runs `decisions.py index` + `validate`.
- **Agent-driven half (documented, live-MCP unverified):** the agent queries the configured MCP
  sources (Circleback/Slack/Gmail/Atlassian/…) for a project/time window, extracts candidate
  decisions, and emits that JSON — normalizing provenance into the `Sources:` format
  (e.g. `circleback · <meeting-id> · <date>`). The workflow lives in SKILL.md; the source→tool→citation
  registry mirrors `agent-stores.md` in `references/external-sources.md`. The connectors are
  **unverified against live MCP servers** in this build (none available headless) — pending real-data validation.

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
