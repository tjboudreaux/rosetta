# ADR 0016 — Incremental collect via processed-session ledger

- Status: Accepted
- Date: 2026-06-13
- Decider: Travis Boudreaux
- Sources: scripts/collect.py (ledger helpers + per-unit loop), tests/test_incremental.py
- Related: ADR 0001 (normalized output as regenerable cache)

## Context

`collect` re-parses and re-emits a normalized `.md` for every matching session on every run. For a
project with months of history across many agents, the downstream reconciliation step then re-reads
sessions it has already folded into `ground-truth.md`. We want `collect` to ignore sessions it has
already processed — uniformly across all supported agents, where the session id lives variously in a
folder name, a filename stem, or inside the chat (e.g. Crush's `{db}-{session_id}`, Cline's
`{editor}-{task_id}`).

The key enabler: every agent's resolver already normalizes its identifier into a single uniform
`unit['id']`, so a skip can key on `<agent>::<unit['id']>` with zero per-agent code.

## Decision

`collect` keeps a per-project **processed-session ledger** at
`<project>/.agents/rosetta/processed-ledger.json` (overridable with `--processed-ledger`), keyed by
`<agent>::<session-id>` with the session's last-activity timestamp. By default it skips sessions
already in the ledger. The skip is **activity-aware**: a session is re-processed only if its
`last_ts` advanced since the recorded run (sessions with no timestamps degrade to id-only skip). The
out dir therefore holds only the new/changed delta. `--reprocess` ignores the ledger for skip
decisions and rebuilds everything, while still refreshing the ledger. `manifest.json` reports
`skipped_sessions` per agent and in totals.

## Consequences

Positive:
- Re-runs are cheap; the downstream reconciliation reads only new/changed sessions.
- Uniform across all 18 agents — no per-agent logic, since the ledger keys on the already-normalized
  `unit['id']`.
- Ledger lives above the per-run `--out` dir, so it survives differently-labeled runs; it is itself
  regenerable and `.gitignore`-safe (consistent with ADR 0001).

Negative:
- Sessions are still parsed before the skip decision (we compare the parser's `last_ts`); the saving
  is in normalization + downstream read, not parse. A pre-parse mtime fast-path is a possible future
  optimization but is messy across non-file units (SQLite rows, message-dir agents), so it was
  deferred in favor of one uniform code path.

## Alternatives considered

- **Id-only skip (skip forever once seen)** — simpler, but goes stale on active/ongoing sessions
  that keep gaining messages. Rejected in favor of activity-aware skip.
- **Reuse a prior run's `manifest.json` via `--from-manifest`** — no new state file, but the per-run
  out dir is not a stable ledger across differently-labeled runs. Rejected for a dedicated
  fixed-path ledger.
- **Opt-in flag, off by default** — preserves today's full-regeneration, but the common case is
  incremental catch-up. Chosen the inverse: on by default with `--reprocess` to force a rebuild.
