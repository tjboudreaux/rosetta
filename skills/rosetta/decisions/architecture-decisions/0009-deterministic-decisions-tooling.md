# ADR 0009 — Deterministic `decisions.py` (scaffold / index / validate)

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Reviewed: 2026-06-18
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation, requirement #5); code `scripts/decisions.py`
- Related: ADR 0001, ADR 0007, ADR 0008

## Context

Numbering records, regenerating an index, and checking frontmatter are mechanical and error-prone by
hand — and pure waste if an LLM does them. The same "deterministic tools do the heavy lifting" principle
behind the collector (ADR 0001) applies to the decision library.

## Decision

Ship `scripts/decisions.py` (pure stdlib, argparse):
- `new --type --title` → next zero-padded number, render the template, write `NNNN-slug.md`.
- `index` → parse every record's frontmatter and regenerate the timeline table between
  `<!-- ROSETTA:TIMELINE:START/END -->` markers (preserving hand-written prose); idempotent.
- `validate` → required fields present, `Status` in the allowed set, numbers unique, slug matches
  title, and `Supersedes`/`Superseded by` links resolve; nonzero exit on error.

Agents/humans spend tokens only on the decision prose; the mechanics are free and reproducible.

## Consequences

Positive:
- Token-free index regeneration and validation; CI-able (`validate` exits nonzero on a broken library).
- Consistent numbering and format across the whole library.

Negative:
- A bullet-frontmatter parser must track the format; covered by `validate` and the schema doc.

## Alternatives considered

- **Let the agent maintain the index/numbers** — burns tokens and drifts; rejected.
- **Adopt an existing ADR CLI (adr-tools)** — assumes its own format/numbering and shell deps;
  doesn't match the in-house format or the config-driven customization (ADR 0008).

## Related

- `scripts/decisions.py`, `scripts/rosetta` (dispatcher), `references/decision-schema.md`.
