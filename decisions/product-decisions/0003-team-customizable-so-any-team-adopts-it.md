# PDR 0003 — Team-customizable so any team can adopt it

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation, requirement #3)
- Related: PDR 0001, ADR 0008

## Context

Adoption dies if a tool forces its own ADR conventions on a team that already has theirs. For Rosetta
to be *the* decision engine across many teams, the format must be the team's, with Rosetta supplying
the mechanics.

## Decision

Make the record format, types, numbering, statuses, fields, and templates **team-configurable** via a
single `config.json`, with sensible rosetta defaults when it's absent (the technical design is ADR
0008). Ship the format as reusable templates + a schema doc + customization guide so a team adopts it
in minutes and overrides only what they care about.

## Consequences

Positive:
- Teams keep their existing ADR habits; Rosetta adapts to them.
- Lower adoption friction → the decision corpus actually gets built.

Negative:
- More configuration surface to document and validate (handled by `decisions.py validate` and
  `references/decision-schema.md`).

## Alternatives considered

- **One fixed house format for everyone** — simplest to build, worst for adoption; rejected.

## Related

- ADR 0008 (config mechanism), `references/decision-schema.md` ("Customize for your team"),
  `templates/`.
