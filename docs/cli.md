# CLI reference

The `rosetta` CLI is a thin, zero-install dispatcher over the deterministic tools. Run it directly or
alias it:

```bash
alias rosetta="python3 ~/.claude/skills/rosetta/scripts/rosetta"
```

The heavy synthesis (reading transcripts, writing `ground-truth.md`, drafting decision prose) is done
by the **agent** via the skill; the CLI is only the deterministic, token-free mechanics.

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

The `manifest.json` reports, per agent: sessions, messages, date range, match mode, and `extra`
counters for unmatchable history (`sessions_without_cwd`, `flat_files_without_cwd`,
`request_dumps_excluded`) plus `unknown_stores`.

## `rosetta discover` — machine-wide project index

```bash
rosetta discover [--out <dir>]
```

Enumerates every project with agent history across all stores → `projects-index.{json,md}`
(project cwd ↔ per-agent session counts ↔ last activity). Cheap: globs + file mtimes, no transcript
parsing.

## `rosetta decisions` — scaffold / index / validate the decision library

```bash
rosetta decisions new --type adr|pdr|bdr --title "…" [--status Proposed] [--decider <name>] [--root <dir>]
rosetta decisions index    [--root <dir>]
rosetta decisions validate [--root <dir>]
```

- **new** — allocates the next zero-padded number, renders the template, writes `NNNN-slug.md`.
- **index** — regenerates the timeline table inside the index file's `<!-- ROSETTA:TIMELINE -->`
  markers (preserves your prose). Idempotent.
- **validate** — checks required frontmatter, allowed `Status` values, unique numbering, and that
  `Supersedes`/`Superseded by` links resolve. **Exit code is nonzero on failure → CI-friendly.**

`--root` defaults to `./decisions` if present, else the current directory. Drop a `config.json` in the
root to use your own record types, directories, numbering, statuses, fields, and templates (see
[decisions.md](decisions.md)).

## Testing the installation

```bash
python3 -m unittest discover -s ~/.claude/skills/rosetta/tests   # all agents, synthetic fixtures
python3 ~/.claude/skills/rosetta/tests/live_smoke.py             # counts against your real machine
```

## Environment

- `ROSETTA_HOME` — override the machine home all store roots derive from (used by the test suite to
  sandbox a fake `$HOME`; also handy for analyzing a mounted/another user's home).
