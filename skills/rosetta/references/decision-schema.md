# Decision-record schema & customization

Rosetta emits three kinds of durable decision records, all sharing one format:

| Type | Name | Captures | Default dir |
|---|---|---|---|
| **ADR** | Architecture Decision Record | *how* the system is built (technical/structural) | `architecture-decisions/` |
| **PDR** | Product Decision Record | *what* we make and why (product/content/strategy) | `product-decisions/` |
| **BDR** | Business Decision Record | business/commercial calls — often made by humans in a meeting or thread | `business-decisions/` |

A library lives under a **decisions root** (rosetta's own is `decisions/`) containing the three
record dirs, an `index` file (`README.md`), and an optional `config.json`. Records are authored from
`templates/{adr,pdr,bdr}-template.md` and managed by the deterministic `scripts/decisions.py`.

## Record format (locked to the canonical "rosetta format")

Heading + a **bullet-list frontmatter** (not YAML), then fixed body sections:

```markdown
# ADR 0005 — Path encoding: every non-alphanumeric → dash

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-05-29
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (verified); supersedes `claude · bc09f7f6 · 2026-05-29`
- Related: ADR 0002; scripts/collect.py enc_path

## Context
## Decision
## Consequences      (Positive: / Negative:)
## Open questions    (optional)
## Alternatives considered
## Related
```

### Frontmatter fields

- **Required:** `Status`, `Date`, `Decider`.
- **Recommended:** `Sources` — provenance, the thing that makes a record trustworthy. Cite as
  `` `agent · session-id · date` `` (Rosetta's transcript citation), a git commit, a code path, a
  meeting note, or a task id. Multiple sources are comma-separated.
- **Optional:** `Decided originally` (when the call was actually made, if the record is backdated),
  `Related`, `Supersedes`.

### Status lifecycle

`Proposed → Accepted → Superseded by <ID>` (or `Deprecated` / `Rejected`). **Every reversal is
recorded**: when a new record overturns an old one, the old record's `Status` becomes
`Superseded by <ID>` and the new one names it under `## Related` / `Supersedes`. The library never
silently oscillates — this is the same "no silent contradictions" discipline as `ground-truth.md`.

### Provenance & the truth hierarchy

Records inherit Rosetta's truth hierarchy: **current code / git > committed decisions > docs >
latest conversation > older conversation.** A decision a transcript merely *discussed* is recorded
as `Status: Proposed` (or noted "discussed/intended"), not asserted as Accepted, until code or an
explicit human call confirms it.

## Customize for your team

Drop a `config.json` in your decisions root (see `decisions/config.json` for the annotated default).
Everything is overridable; omit `config.json` entirely to take the rosetta defaults.

- `record_types` — add/rename types (e.g. a `gov` Governance record), point each at a `dir` and a
  `template`. `label` is the ID prefix shown in files (`ADR`, `PDR`, …).
- `number_width` — zero-padding for IDs (default 4 → `0007`).
- `statuses` — the allowed `Status` values `validate` enforces.
- `required_fields` / `recommended_fields` / `optional_fields` — your frontmatter contract.
- `index.path` + `index.columns` — where the timeline index is written and its columns.
- `template` paths resolve relative to the decisions root; if absent, `decisions.py` falls back to
  the rosetta skill's `templates/<type>-template.md`, so a team can adopt the format with zero files
  copied, then override a template only when they want to diverge.

Teams keep their existing ADR conventions by editing this one file — the tooling and the Rosetta
workflow adapt to it, not the other way around.
