# Loop Integration Plan

This is the hardened implementation contract for Rosetta loop integration.

## Boundary

Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy.

## Ownership split

- **Rosetta** owns local memory, provenance, decision state, evidence presence checks, drift reports, and run ledgers.
- **RA1** owns structural readiness reports. Rosetta embeds RA1 output only in the RA1-owned preflight section.
- **Loop runners** own execution, scheduling, product behavior proof, and policy for autonomous operation.

## Commands

### `rosetta gates check`

```bash
rosetta gates check \
  --project-root <repo-or-project-root> \
  --decisions-root <decisions-root> \
  --min-coverage <float in [0,1]> \
  [--changed-path <repo-relative-path> ... | --diff-file <path-or-> | --base <rev> --head <rev>] \
  [--change-id <stable-id>] \
  [--out -|<json-path>]
```

- `--project-root` defaults to cwd.
- `--decisions-root` defaults to `<project-root>/decisions` if it exists, else `<project-root>`.
- `--min-coverage` is required; omission is argparse exit 2.
- Exactly one change source may be supplied; no source is allowed and skips changed-path joins.
- `--base/--head` uses local `git diff --name-only --diff-filter=ACMRTUXB <base>...<head>` only.
- Exit 1 when any gate fails, else 0.

Gate JSON schema is `rosetta-gates/v1` and contains `validation`, `integrity`, `staleness`, `anchoring`, `denylist`, and `evidence_presence` gates. Every gate is owned by Rosetta and every `evidence` value is an array.

Parseable fields:

- `Human gated paths`: semicolon-separated repo-relative `fnmatch` patterns on Accepted ADR/PDR records.
- `Human approval for`: exact change id on an Accepted ADR/PDR/BDR with non-empty `Sources` and `Decider`.
- `Evidence for`: exact change id on an Accepted ADR/PDR/BDR.
- `Evidence artifacts`: semicolon-separated `screenshot:<repo-path>` or `video:<repo-path>` local refs.

`denylist` fails when a touched path matches `Human gated paths` without a matching `Human approval for`. `evidence_presence` applies only to UI file extensions and checks only that a cited local screenshot/video artifact exists.

### `rosetta ingest`

`rosetta ingest` preserves legacy decision JSON and adds `--schema auto|decisions|signals` plus `--allow-sensitive`.

Signal items require `id`, `source`, `product_area`, `platform`, `app_version`, `device_os`, `content_summary`, `raw_refs`, `customer_impact`, `actionability`, `privacy_class`, `suggested_owner`, and `created_at`. Signal records are always written as `Status: Proposed`. For `privacy_class: pii|sensitive`, default behavior is a hard error before writes. With `--allow-sensitive`, `redacted: true` is required; the record stores a redacted summary and no raw refs beyond ``signal:<id>``.

### `rosetta harness export`

```bash
rosetta harness export --project-root <repo-or-project-root> \
  [--from-json <path>] [--patch | --apply]
```

The input is only `rosetta-harness-export/v1` JSON. It does not scrape `.agents/ground-truth.md` prose. Targets are allowlisted exactly: `ARCHITECTURE.md`, `docs/MOBILE.md`, and `domains/<single-kebab-slug>/README.md`. Dry-run prints JSON and writes nothing; `--patch` prints a unified diff and writes nothing; `--apply` updates only existing files containing `<!-- ROSETTA:HARNESS:START -->` and `<!-- ROSETTA:HARNESS:END -->`, otherwise exits 3 with a patch.

### `rosetta runs`

`rosetta runs` writes an isolated ledger under `<project-root>/loop-runs/` and is not part of the decision library.

```bash
rosetta runs new --project-root <project> --title <title> --runner <id> --trigger manual|ci|goal|loop|other --scope <text> [--budget <text>] [--artifact <path> ...]
rosetta runs append --project-root <project> "RUN 0001" --note <text> [--artifact <path> ...] [--checker-result pass|fail|skip|unknown] [--outcome pending|success|failure|stopped] [--harness-improvement <text>]
rosetta runs close --project-root <project> "RUN 0001" --stop-reason <text> [--outcome success|failure|stopped] [--checker-result pass|fail|skip|unknown]
rosetta runs index --project-root <project>
rosetta runs validate --project-root <project>
```

Closed runs must have a nonblank `Stop reason`. `decisions.py validate/search/coverage` do not scan `loop-runs/`.

### `rosetta drift report`

```bash
rosetta drift report --project-root <project> --decisions-root <decisions-root> [--status Accepted] [--out -|<json-path>]
```

Emits `rosetta-drift/v1` JSON and exits 0 when the report is generated, even when records are stale. Non-git projects return `status: skip`.

### `rosetta preflight`

```bash
rosetta preflight \
  --project-root <project> \
  --decisions-root <decisions-root> \
  --scope <decision-query> \
  --min-coverage <float in [0,1]> \
  [same change-source flags as gates check] \
  [--change-id <id>] \
  [--allow-ra1-github] \
  [--ra1-timeout <seconds default 30>] \
  [--out -|<json-path>]
```

Output schema is `rosetta-preflight/v1` with three sections: `ra1_structural` (owner `ra1`), `decision_state` (owner `rosetta`), and `gates` (owner `rosetta`). Missing RA1 is a structured skip. RA1 timeout, nonzero exit, invalid JSON, or stderr-only failure is a structured failure. Default RA1 argv is `ra1 report --format json --no-github`; `--allow-ra1-github` omits `--no-github`.

No nested `rosetta loop preflight` namespace exists; unknown `loop` continues to exit 2.

## Verification contract

- Targeted command tests cover dispatch parity, gate joins, signal privacy, harness write limits, run ledger isolation, drift JSON, and preflight RA1 handling.
- Legacy tests must remain green.
- Manual smoke for `gates check` and `preflight` should print valid JSON and write no files unless `--out` or `harness export --apply` is supplied.
