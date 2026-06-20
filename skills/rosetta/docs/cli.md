# CLI reference

The `rosetta` CLI is a thin, zero-install dispatcher over the deterministic tools. Run it directly or
alias it:

```bash
alias rosetta="python3 ~/.claude/skills/rosetta/scripts/rosetta"
```

The heavy synthesis (reading transcripts, writing `ground-truth.md`, drafting decision prose) is done
by the **agent** via the skill; the CLI is only the deterministic, token-free mechanics.

## Deterministic boundary

Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy.


## `rosetta collect` — gather + normalize a project's transcripts

```bash
rosetta collect --project <path> --out <dir> [flags]
```

| Flag | Meaning |
|---|---|
| `--project <path>` | Project to scope to (default: cwd). |
| `--out <dir>` | Where to write `manifest.json` + one `<agent>__<session>.md` per session. |
| `--agents a,b,c` | Subset of agents (default: all 18). |
| `--since YYYY-MM-DD` | Only sessions active on/after this date. |
| `--include-subdirs` | Monorepo mode: also include sessions whose cwd is *under* the project. |
| `--max-chars N` | Truncate each message to N chars (default 4000). |
| `--reprocess` | Rebuild every session, ignoring the processed-session ledger (the ledger is still refreshed). |
| `--processed-ledger <path>` | Override the ledger location (default: `<project>/.agents/rosetta/processed-ledger.json`). |

By default `collect` skips sessions it has already processed, keyed by `<agent>::<session-id>` in
the processed-session ledger. The skip is activity-aware: a session is re-processed only if it
gained new messages since the last run, so the out dir holds the new/changed delta. Use
`--reprocess` for a full rebuild.

The `manifest.json` reports, per agent: sessions, messages, `skipped_sessions`, date range, match
mode, and `extra` counters for unmatchable history (`sessions_without_cwd`, `flat_files_without_cwd`,
`request_dumps_excluded`) plus `unknown_stores`.

## `rosetta discover` — machine-wide project index

```bash
rosetta discover [--out <dir>]
```

Enumerates every project with agent history across all stores → `projects-index.{json,md}`
(project cwd ↔ per-agent session counts ↔ last activity). Cheap: globs + file mtimes, no transcript
parsing.

## `rosetta decisions` — the decision library (10 subcommands)

```bash
rosetta decisions new --type adr|pdr|bdr --title "…" [--status Proposed] [--decider <name>] [--root <dir>]
rosetta decisions index    [--root <dir>]
rosetta decisions validate [--root <dir>] [--integrity] [--staleness]
rosetta decisions integrity  [--root <dir>]
rosetta decisions staleness  [--root <dir>] [--strict]
rosetta decisions search     [--root <dir>] --text "<topic>" [--type adr|pdr|bdr] [--status Accepted] [--limit N]
rosetta decisions get        [--root <dir>] "ADR 0042" [--resolve]
rosetta decisions supersede  [--root <dir>] "ADR 0042" --by "ADR 0098"
rosetta decisions resolve    [--root <dir>] --text "<topic-or-codename>" [--no-alias-expand] [--no-stale-check]
rosetta decisions coverage   [--root <dir>] [--min-coverage 0.8]
```

- **new** — allocates the next zero-padded number, renders the template, writes `NNNN-slug.md`.
- **index** — regenerates the timeline table inside the index file's `<!-- ROSETTA:TIMELINE -->`
  markers (preserves your prose). Idempotent.
- **validate** — checks required frontmatter, allowed `Status` values, unique numbering, and that
  `Supersedes`/`Superseded by` links resolve. **Exit code is nonzero on failure → CI-friendly.**
  Add `--integrity` to also fail on **fabricated provenance** (ADR 0024), `--staleness` to flag
  records whose cited code moved in git (ADR 0027).
- **integrity** — standalone JSON check for fabricated provenance (ghost citations, dangling refs).
- **staleness** — standalone JSON check for code drift; `--strict` exits nonzero if any record is
  stale (the CI-gate form). Honors the `Reviewed:` field as a re-flaggable baseline.
- **search** — returns matching records as JSON (by text, type, status, limit).
- **get** — reads one record in full; `--resolve` follows the supersession chain to the current record.
- **supersede** — flips an old record's Status to `Superseded by <new>` and sets the new record's
  `Supersedes` line. Don't hand-edit status; let the tool do it.
- **resolve** — follows supersession to the current decision(s), flags unresolved conflicts, returns
  whether the query resolved uniquely. `--no-alias-expand` for literal-only, `--no-stale-check` to
  skip git freshness annotations.
- **coverage** — library health report (JSON): `anchoring.rate` (share of Accepted records with real
  code provenance), supersession stats, ambiguous topics, orphans, staleness, alias coverage.
  `--min-coverage 0.8` turns the anchoring rate into a CI gate (ADR 0026).

`--root` defaults to `./decisions` if present, else the current directory. Drop a `config.json` in the
root to use your own record types, directories, numbering, statuses, fields, and templates (see
[decisions.md](decisions.md)).

## `rosetta ingest` — external decisions and signals

```bash
rosetta ingest --root ./decisions --from input.json [--schema auto|decisions|signals] [--allow-sensitive]
```

Legacy decision JSON is unchanged. `--schema auto` treats objects with all signal discriminator keys as
signals; signal records are written as `Status: Proposed`. `pii`/`sensitive` signals are refused unless
`--allow-sensitive` and `redacted: true` are both present; redacted records store no raw refs beyond
``signal:<id>``.

## `rosetta gates check` — local decision/evidence gates

```bash
rosetta gates check --project-root <project> --decisions-root <decisions-root> --min-coverage 0.8 \
  [--changed-path <path> ... | --diff-file <path-or-> | --base <rev> --head <rev>] \
  [--change-id <id>] [--out -|report.json]
```

Emits `rosetta-gates/v1` JSON and exits 1 when any gate fails. Gates: strict validation,
integrity, staleness, anchoring, `Human gated paths` approval, and UI `Evidence artifacts` presence.
With no changed paths, the approval/evidence joins skip with `no_changed_paths`.

## `rosetta harness export` — deterministic harness docs

```bash
rosetta harness export --project-root <project> [--from-json .agents/rosetta/harness-export.json] [--patch | --apply]
```

Consumes only `rosetta-harness-export/v1` JSON. Targets are allowlisted exactly:
`ARCHITECTURE.md`, `docs/MOBILE.md`, and `domains/<single-kebab-slug>/README.md`. Dry-run prints JSON
and writes nothing; `--patch` prints a diff and writes nothing; `--apply` updates only existing files
with `<!-- ROSETTA:HARNESS:START -->` / `<!-- ROSETTA:HARNESS:END -->` markers.

## `rosetta runs` — isolated loop-run ledger

```bash
rosetta runs new --project-root <project> --title <title> --runner <id> --trigger manual|ci|goal|loop|other --scope <text>
rosetta runs append --project-root <project> "RUN 0001" --note <text>
rosetta runs close --project-root <project> "RUN 0001" --stop-reason <text>
rosetta runs index --project-root <project>
rosetta runs validate --project-root <project>
```

Writes only under `loop-runs/`; decision-library commands do not scan those files.

## `rosetta drift report` — freshness JSON

```bash
rosetta drift report --project-root <project> --decisions-root <decisions-root> [--status Accepted] [--out -|report.json]
```

Emits `rosetta-drift/v1` JSON and exits 0 when the report is generated, even if stale records exist.

## `rosetta preflight` — RA1 + decision state + gates

```bash
rosetta preflight --project-root <project> --decisions-root <decisions-root> --scope <query> --min-coverage 0.8 \
  [same change-source flags as gates check] [--change-id <id>] [--allow-ra1-github] [--ra1-timeout 30] [--out -|report.json]
```

Emits `rosetta-preflight/v1` JSON. Missing RA1 is a structured skip; RA1 timeout, nonzero exit,
stderr-only failure, or invalid JSON is a structured `ra1_structural` failure. There is no
`rosetta loop preflight` alias.

## Testing the installation

```bash
python3 -m unittest discover -s ~/.claude/skills/rosetta/tests   # all agents, synthetic fixtures
python3 ~/.claude/skills/rosetta/tests/live_smoke.py             # counts against your real machine
```

## Environment

- `ROSETTA_HOME` — override the machine home all store roots derive from (used by the test suite to
  sandbox a fake `$HOME`; also handy for analyzing a mounted/another user's home).
