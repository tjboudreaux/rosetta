# External decision-source registry (backs ADR 0012)

Parallel to `agent-stores.md` (which maps *agent transcript* stores), this maps *external* systems
where decisions are made by humans — meetings, chat, trackers — reachable via MCP.

**Status:** the deterministic half is **shipped** — `scripts/ingest.py` (`rosetta ingest`) turns a JSON
array of extracted decisions into reviewable `Status: Proposed` records. The agent-driven half (the
actual MCP queries that produce that JSON) is documented below and in SKILL.md but **unverified against
live MCP servers** in this build. Unlike transcript collection (deterministic, local files), external
ingestion is **agent-driven and on-demand**: it calls MCP tools, needs auth, and may be unavailable in
headless/cron runs. Everything it surfaces is a **Proposed** draft pending human confirmation (truth
hierarchy, ADR 0004).

## Sources

| Source | Reach | Decision kind | Citation format |
|---|---|---|---|
| Circleback | claude.ai MCP (meeting notes / AI notetaker) | business, product | `circleback · <meeting-id> · <date>` |
| Slack | claude.ai MCP | business, product, technical | `slack · <channel>/<ts> · <date>` |
| Gmail | claude.ai MCP / `gws gmail` | business | `gmail · <thread-id> · <date>` |
| Google Calendar | claude.ai MCP / `gws calendar` | business (commitments) | `gcal · <event-id> · <date>` |
| Atlassian (Jira/Confluence) | project MCP (SSE) | technical, product | `jira · <KEY-123> · <date>` |
| Linear / Notion | MCP (where configured) | product, technical | `linear · <id>` / `notion · <page-id>` |

Verify what's actually authed with the collector's discovery sweep and the user's
`~/.claude/mcp-needs-auth-cache.json`; the user's `CLAUDE.md` also documents a `gws` Google Workspace
CLI and Circleback usage.

## Ingestion flow

1. **Select** sources + a project/time window.
2. **Query** each via its MCP tools (a deterministic skeleton lists tools + windows; the agent runs the
   calls).
3. **Extract** candidate decisions (what was decided, by whom, why).
4. **Normalize** provenance into the `Sources:` citation format above.
5. **Scaffold**: emit the extracted decisions as a JSON array and pipe it to `rosetta ingest`
   (`scripts/ingest.py`), which writes one `Status: Proposed` record each (numbering, provenance, body draft).
6. **Confirm** with a human before any draft becomes `Accepted` (ADR 0004).

## Adding a source

Add a row here + the MCP tool prefix and a citation format, mirroring how `agent-stores.md` + a
`collect.py` resolver work together. No new source is ingested silently — unconfigured sources are
reported, not skipped.
