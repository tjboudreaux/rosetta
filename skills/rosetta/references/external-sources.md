# External decision-source registry (backs ADR 0012)

Parallel to `agent-stores.md` (which maps *agent transcript* stores), this maps *external* systems
where decisions are made by humans — meetings, chat, trackers — reachable via MCP.

**Status:** the deterministic half is **shipped** — `scripts/ingest.py` (`rosetta ingest`) turns a JSON
array of extracted decisions or validated product signals into reviewable `Status: Proposed` records.
Agent-run external-source collection remains outside the deterministic CLI.

Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy.

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

Signal ingest uses the same draft discipline. `pii`/`sensitive` signals are refused unless the caller
passes `--allow-sensitive` and the item says `redacted: true`; redacted records keep only
``signal:<id>`` as a raw reference.

## Adding a source

Add a row here + the MCP tool prefix and a citation format, mirroring how `agent-stores.md` + a
`collect.py` resolver work together. No new source is ingested silently — unconfigured sources are
reported, not skipped.
