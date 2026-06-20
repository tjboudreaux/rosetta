---
name: rosetta-preflight
description: Produce Rosetta's deterministic preflight JSON for a scoped change: optional RA1 structural report, decision-state resolution, and local Rosetta gates. Use before handing execution to a loop runner.
argument-hint: "--project-root <project> --decisions-root <decisions> --scope <query> --min-coverage <0-1> [change flags]"
user-invocable: true
allowed-tools: Bash, Read
license: MIT
---

# /rosetta-preflight — deterministic preflight JSON

Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy.

## Workflow

Run the canonical top-level command; do not use a nested `rosetta loop` namespace:

```bash
rosetta preflight \
  --project-root <project> \
  --decisions-root <decisions-root> \
  --scope "<decision-query>" \
  --min-coverage 0.8 \
  [--changed-path <path> ... | --diff-file <path-or-> | --base <rev> --head <rev>] \
  [--change-id <stable-id>] \
  [--allow-ra1-github]
```

Interpret the output sections by owner:

- `ra1_structural` (`owner: ra1`) — structural readiness JSON from RA1, or `skip` when RA1 is absent.
- `decision_state` (`owner: rosetta`) — current decision resolution for `--scope`; fails on conflict,
  ambiguous alias, stale current records, or non-unique matches.
- `gates` (`owner: rosetta`) — the same pure gate report as `rosetta gates check`.

Exit 1 means at least one section failed. Exit 0 means the deterministic preflight report was generated
with no failing sections; execution policy remains outside Rosetta.
