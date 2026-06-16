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
  `Related`, `Supersedes`, `Aliases` (codenames/synonyms for the concept — see below).

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

### Aliases & the glossary (codename resolution)

Real teams refer to a decision by a **codename** ("Project Meridian", "the new pipeline", "Zephyr"),
not its ADR number. The optional **`Aliases:`** field captures those names so a codename query
resolves to the live decision instead of silently missing it:

```markdown
- Aliases: Project Meridian; the new pipeline; Zephyr
```

- **Format** — a single line, `;`-separated. Blank or separator-only segments are ignored, so the
  empty template line contributes nothing.
- **Normalization** — case-insensitive; runs of whitespace, `-`, `_`, `/`, `\` collapse to one
  space. Everything else is preserved, so `Project-Meridian` == `project_meridian` while `C++`, `C#`,
  and `.NET` stay distinct (no false collisions).
- **Resolution (`resolve`)** — an alias in the query adds its target under `via_alias` (following
  supersession to the current record). The literal `conflict` flag is unchanged (literal-text matches
  only); a separate **`resolved_unique`** flag is `true` only when the whole query — literal hits
  *and* alias targets — points to exactly one current decision. An alias mapping to two different
  current decisions is reported under `alias_conflict`, never silently merged. `--no-alias-expand`
  turns the layer off (literal matching only).
- **Uniqueness is enforced** — `validate` is a **hard error** (fails CI even without `--strict`) when
  one normalized alias maps to two or more distinct current decisions, or when an aliased record sits
  on a forked/contradictory supersession chain. An ambiguous codename is a defect, not a warning.
- **Generic single words are suppressed** — a one-word alias on the `alias_stoplist`
  (`api app web auth prod test db data core service` by default; override wholesale in `config.json`)
  will not match, so a query for "api" is not hijacked. Multi-word aliases are never suppressed.
- **The glossary** — `index` writes `GLOSSARY.md` (human) and `GLOSSARY.json` (machine): the derived
  codename → decision map, plus any ambiguous codenames printed loudly. Both are regenerated from the
  records on every run — never a cache.

## Customize for your team

Drop a `config.json` in your decisions root (see `decisions/config.json` for the annotated default).
Everything is overridable; omit `config.json` entirely to take the rosetta defaults.

- `record_types` — add/rename types (e.g. a `gov` Governance record), point each at a `dir` and a
  `template`. `label` is the ID prefix shown in files (`ADR`, `PDR`, …).
- `number_width` — zero-padding for IDs (default 4 → `0007`).
- `statuses` — the allowed `Status` values `validate` enforces.
- `required_fields` / `recommended_fields` / `optional_fields` — your frontmatter contract.
- `index.path` + `index.columns` — where the timeline index is written and its columns.
- `alias_stoplist` — single-word aliases to ignore during codename resolution (your override
  *replaces* the default list wholesale).
- `template` paths resolve relative to the decisions root; if absent, `decisions.py` falls back to
  the rosetta skill's `templates/<type>-template.md`, so a team can adopt the format with zero files
  copied, then override a template only when they want to diverge.

Teams keep their existing ADR conventions by editing this one file — the tooling and the Rosetta
workflow adapt to it, not the other way around.
