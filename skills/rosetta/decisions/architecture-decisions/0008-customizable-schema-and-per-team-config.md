# ADR 0008 — Customizable frontmatter schema + per-team config

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Reviewed: 2026-06-18
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation, requirement #3); code `decisions/config.json`, `references/decision-schema.md`
- Related: ADR 0007, ADR 0009, PDR 0003

## Context

Every team already has ADR habits — different directories, numbering, statuses, required fields, and
templates. For Rosetta to be the decision engine for *any* team, the format must bend to the team, not
the reverse.

## Decision

Drive the record contract from an optional `config.json` at the decisions root: `record_types`
(label/name/dir/template), `number_width`, `statuses`, `required`/`recommended`/`optional` fields, and
`index` (path + columns). Tooling reads it; absent ⇒ rosetta defaults apply. `template` paths resolve
relative to the root, falling back to the skill's `templates/`, so a team can adopt the format with
zero files copied and override only what they want. Config is JSON (pure stdlib — no PyYAML); decision
files keep the bullet-list frontmatter.

## Consequences

Positive:
- Teams adopt Rosetta with their own conventions by editing one file.
- New record types (e.g. a Governance `gov` record) need no code change.

Negative:
- Wholesale `record_types` override (not deep-merge) means a team redefining types restates all of
  them — kept intentionally simple and predictable.

## Alternatives considered

- **Hardcode ADR/PDR/BDR** — blocks team adoption; rejected.
- **YAML config** — adds a dependency; JSON stays stdlib and is enough.

## Related

- `decisions/config.json` (annotated default), `references/decision-schema.md`, `scripts/decisions.py` (`load_config`).
