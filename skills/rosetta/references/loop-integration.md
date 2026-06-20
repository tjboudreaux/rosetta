# Loop integration boundary

Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy.

## Local gates

`rosetta gates check` emits `rosetta-gates/v1` JSON and exits 1 on any failing gate. It checks:

- decision validation warnings/errors;
- fabricated references and ghost sources;
- git staleness when git is available;
- code-anchoring coverage against `--min-coverage`;
- `Human gated paths` joined to exact `Human approval for: <change-id>`;
- UI file changes joined to `Evidence for: <change-id>` plus an existing local `Evidence artifacts` screenshot/video ref.

The evidence gate checks local artifact presence only.

## Preflight

`rosetta preflight` emits `rosetta-preflight/v1` JSON with three sections:

1. `ra1_structural` (`owner: ra1`) — `ra1 report --format json --no-github` by default, or GitHub-enabled RA1 when `--allow-ra1-github` is present.
2. `decision_state` (`owner: rosetta`) — shared `decisions build_resolve_report` semantics, including stale current records.
3. `gates` (`owner: rosetta`) — the same pure gate report used by `rosetta gates check`.

Missing RA1 is a skip. RA1 timeout, nonzero exit, invalid JSON, or stderr-only failure is a structured failure. There is no `rosetta loop preflight` alias.

## Run ledger

`rosetta runs` records local run lifecycle notes under `loop-runs/`. It is intentionally outside the decision library: `RUN` is not a decision record type and decision validation/search/coverage do not scan `loop-runs/`.

## Harness export

`rosetta harness export` consumes `rosetta-harness-export/v1` JSON only. It writes only between `<!-- ROSETTA:HARNESS:START -->` and `<!-- ROSETTA:HARNESS:END -->` markers in `ARCHITECTURE.md`, `docs/MOBILE.md`, and `domains/<single-kebab-slug>/README.md`, and only with explicit `--apply`.
