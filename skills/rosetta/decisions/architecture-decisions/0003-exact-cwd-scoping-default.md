# ADR 0003 — Exact-cwd scoping by default; `--include-subdirs` opt-in

- Status: Accepted (retroactive)
- Date: 2026-06-07 (recorded)
- Decided originally: 2026-05-29
- Reviewed: 2026-06-18
- Decider: Travis
- Sources: `claude · bc09f7f6 · 2026-05-29` (tested live); code `scripts/collect.py` (`cwd_matches`, `matching_dirs`)
- Related: ADR 0002

## Context

A project path can be a single package or a monorepo root. Pulling every session whose cwd is *under*
a path is right for a monorepo but catastrophic for a sibling-heavy parent: tested live, scanning
`~/Sandbox` with subdirs included exploded Factory from ~5 to ~2,936 sessions.

## Decision

Scope to **exact cwd match by default**. A project means that directory, not its children.
`--include-subdirs` opts into monorepo mode (cwd at or under the project). The skill explains the
flag exists rather than guessing the user's intent.

## Consequences

Positive:
- Safe, predictable default; no accidental cross-project contamination of a ground truth.
- Monorepos are still a one-flag away.

Negative:
- A user who expected recursive behavior must pass the flag (documented in SKILL.md).

## Alternatives considered

- **Recursive by default** — the 5→2,936 blowup proves this is unsafe; rejected.
- **Always prompt** — adds friction; a sane default + an opt-in flag is better.

## Related

- `cwd_matches()`, `matching_dirs()`, the `--include-subdirs` flag.
