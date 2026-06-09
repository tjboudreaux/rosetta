# ADR 0013 — Installable CLI packaging

- Status: Accepted (editable install shipped 2026-06-08; portable wheel/PyPI publish deferred)
- Date: 2026-06-08
- Decided originally: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-08` (this conversation, requirement #6); `pyproject.toml`, `rosetta_cli.py`
- Related: ADR 0011

## Context

The thin dispatcher (ADR 0011) requires running `python3 …/scripts/rosetta` or setting an alias. Once
the command surface stabilizes, putting `rosetta` on `PATH` is a better experience and makes the tool
shareable beyond this machine.

## Decision

Ship `skills/rosetta/pyproject.toml` + an importable `rosetta_cli.py` with a `[project.scripts]`
entry point (`rosetta = rosetta_cli:main`), pure-stdlib, `requires-python >=3.8`. The command surface
(collect / discover / decisions / ingest) carries over from the thin dispatcher unchanged.

```bash
pip install -e skills/rosetta   # → `rosetta` on PATH; edits to the scripts take effect live
```

## Consequences

Positive:
- `pip install -e` gives `rosetta` on PATH for local/dev use without abandoning the
  run-the-scripts-directly path (ADR 0011) — both work.

Negative / open question:
- **A portable wheel / PyPI / `pipx install` is deferred.** It additionally requires bundling
  `scripts/` and `templates/` as package data and making `decisions.py`'s `SKILL_ROOT` resolution
  install-aware — a packaging refactor that trades against the zero-install, direct-run design this
  skill values. Editable install covers the realistic local case; revisit a published wheel when there
  is demand to install Rosetta on machines that won't clone the repo.

## Alternatives considered

- **Stay alias-only (ADR 0011)** — fine for one machine; doesn't scale to other users/CI.
- **A single-file zipapp** — distributable without an index, but loses `pip`/`pipx` discoverability.

## Related

- ADR 0011 (thin dispatcher shipped now); `scripts/rosetta`.
