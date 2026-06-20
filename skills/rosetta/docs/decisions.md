# Decision records (ADR / PDR / BDR)

A ground truth is a *snapshot*; decisions deserve durable, individually-addressable records with
provenance and a status lifecycle. Rosetta distills three kinds, all in one format:

| Type | Name | Captures | Default dir |
|---|---|---|---|
| **ADR** | Architecture Decision Record | *how* the system is built (technical/structural) | `architecture-decisions/` |
| **PDR** | Product Decision Record | *what* we make and why (product/strategy) | `product-decisions/` |
| **BDR** | Business Decision Record | business/commercial calls — often made by humans in a meeting | `business-decisions/` |

Rosetta's own decisions live in [`/decisions`](../decisions) and are the **reference implementation**
of the format — Rosetta dogfooding its own output.

## Format

A `# <LABEL> NNNN — title` heading, a bullet-list frontmatter, then fixed body sections:

```markdown
# ADR 0005 — Path encoding: every non-alphanumeric → dash

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-05-29
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (verified); supersedes the `/`-only encoding
- Related: ADR 0002; scripts/collect.py enc_path

## Context
## Decision
## Consequences      (Positive: / Negative:)
## Open questions    (optional)
## Alternatives considered
## Related
```

- **Required:** `Status`, `Date`, `Decider`.
- **Recommended:** `Sources` — the provenance that makes a record trustworthy: `` `agent · session-id ·
  date` ``, a git commit, a code path, a meeting note, or a task id.
- **Status lifecycle:** `Proposed → Accepted → Superseded by <ID>` (or `Deprecated` / `Rejected`).
  Every reversal supersedes the prior record — the library never silently oscillates.
- A decision the transcripts only *discussed* stays `Proposed` until code or an explicit human call
  confirms it (the truth hierarchy, again).
- Loop-gate fields are parseable frontmatter, not prose inference: `Human gated paths`,
  `Human approval for`, `Evidence for`, and `Evidence artifacts`.

Full spec: [`references/decision-schema.md`](../references/decision-schema.md).

## The deterministic tool

`scripts/decisions.py` does the mechanical work so you (or the agent) spend effort only on prose:

```bash
rosetta decisions new --type adr --title "Adopt SQLite for the cache" --decider you
rosetta decisions index    --root decisions    # regenerate the timeline table (idempotent)
rosetta decisions validate --root decisions    # CI-friendly: nonzero exit on a broken library
```

`index` rewrites only the table between `<!-- ROSETTA:TIMELINE:START/END -->` markers, preserving any
prose you add around it. `validate` enforces the frontmatter contract, unique numbering, allowed
statuses, and resolvable supersede links.

For integration gates, `rosetta gates check` treats validation warnings as failures, runs integrity and
staleness checks, gates `coverage.anchoring.rate_raw` against `--min-coverage`, and joins the parseable
human-approval/evidence fields. It emits JSON; it does not inspect screenshots/videos or assert product
behavior.

## Use your own templates (any team)

Drop a `config.json` at your decisions root; omit it for Rosetta's defaults. Everything is overridable:

```json
{
  "number_width": 4,
  "statuses": ["Proposed", "Accepted", "Superseded", "Deprecated", "Rejected"],
  "required_fields": ["Status", "Date", "Decider"],
  "record_types": {
    "adr": {"label": "ADR", "dir": "architecture-decisions", "template": "templates/adr-template.md"},
    "gov": {"label": "GOV", "dir": "governance-decisions", "template": "templates/gov-template.md"}
  },
  "index": {"path": "README.md", "columns": ["Date", "ID", "Type", "Decision", "Status"]}
}
```

Add a record type (e.g. a `gov` Governance record) with **no code change**. Template paths resolve
relative to the root and fall back to the skill's `templates/`, so a team can adopt the format with
zero files copied and override only what they want. The format bends to your team — not the reverse.

## Beyond code and chat

Many decisions — pricing, partnerships, hiring — happen in meetings (Circleback) or Slack, never in
code. `rosetta ingest --schema auto|decisions|signals` also accepts normalized product signals;
`pii`/`sensitive` signals require `--allow-sensitive` plus `redacted: true`.

Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy.
