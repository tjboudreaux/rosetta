# ADR 0011 — Thin Rosetta CLI dispatcher

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Reviewed: 2026-06-18
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation, requirement #6); code `scripts/rosetta`
- Related: ADR 0009, ADR 0010, ADR 0013

## Context

The deterministic mechanics now span two scripts (`collect.py`, `decisions.py`). A single entry point
makes them discoverable and ergonomic — but a full installable package is a heavier commitment that
shouldn't block having a usable CLI today.

## Decision

Ship `scripts/rosetta`: a thin, zero-install dispatcher that forwards subcommands to the underlying
scripts unchanged — `rosetta collect …`, `rosetta discover …` (`collect.py --all-projects`),
`rosetta decisions new|index|validate …`. Run via `python3 …/scripts/rosetta` or an alias. Full
PATH packaging (`pyproject.toml` + `console_scripts`) is deferred to ADR 0013.

## Consequences

Positive:
- One memorable command surface over all deterministic tools; no install, no new deps.
- Adding a subcommand is a few lines of passthrough.

Negative:
- Not on `PATH` by default — needs an alias. `pip install -e skills/rosetta` (ADR 0013) puts `rosetta`
  on PATH; the portable wheel / PyPI publish remains deferred.

## Alternatives considered

- **Jump straight to a packaged console_scripts CLI** — more moving parts (packaging, versioning,
  install) before the surface has settled; a thin dispatcher first, package later (ADR 0013).
- **No CLI, call scripts directly** — workable but poor ergonomics for the unified engine.

## Related

- `scripts/rosetta`; ADR 0013 (installable packaging); README.md "CLI".
