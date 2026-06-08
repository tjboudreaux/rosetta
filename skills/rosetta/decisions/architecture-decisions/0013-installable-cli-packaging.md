# ADR 0013 — Installable CLI packaging

- Status: Proposed
- Date: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation, requirement #6)
- Related: ADR 0011

## Context

The thin dispatcher (ADR 0011) requires running `python3 …/scripts/rosetta` or setting an alias. Once
the command surface stabilizes, putting `rosetta` on `PATH` is a better experience and makes the tool
shareable beyond this machine.

## Decision (proposed)

Add a `pyproject.toml` with a `console_scripts` entry point (`rosetta = rosetta.cli:main`), keep the
runtime pure-stdlib, and publish to PyPI or a private index. Pin a minimum Python version. The thin
dispatcher's command surface (collect / discover / decisions) carries over unchanged.

## Consequences

Positive:
- `pipx install rosetta` (or similar) → `rosetta` on PATH for any user/CI.

Negative:
- Packaging, versioning, and release overhead; only worth it once the surface is stable (hence Proposed,
  after ADR 0011 ships the thin version).

## Alternatives considered

- **Stay alias-only (ADR 0011)** — fine for one machine; doesn't scale to other users/CI.
- **A single-file zipapp** — distributable without an index, but loses `pip`/`pipx` discoverability.

## Related

- ADR 0011 (thin dispatcher shipped now); `scripts/rosetta`.
