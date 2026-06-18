# ADR 0010 — Machine-wide agent-conversation discovery

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Reviewed: 2026-06-18
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation, requirement #1); code `scripts/collect.py` (`discover_all_projects`, `--all-projects`)
- Related: ADR 0002, ADR 0005

## Context

Rosetta scoped to one project at a time. To be a context engine you must first *find* the context —
"which projects on this machine even have agent history?" — without parsing every transcript.

## Decision

Add `collect.py --all-projects`: enumerate every project with history across all stores and emit
`projects-index.json` + `projects-index.md` (project cwd ↔ per-agent session counts ↔ activity range).
It is **discovery-only** — counts come from globs and last-activity from file mtime, so there is no
per-session parse and no token cost. Real cwds come from probing one representative session per dir
(`enc_path` is lossy per ADR 0005, so dir names can't be decoded); Codex is grouped by its line-1
`session_meta.cwd`; Cursor dirs are listed unresolved (no per-line cwd); Hermes is noted as
not-project-scoped.

## Consequences

Positive:
- A single command maps the machine (verified: 89 projects found, including Rosetta itself).
- Cheap enough to run routinely; feeds a "pick a project to reconcile" step.

Negative:
- Cursor projects can't be mapped to a real path (encoding-only) — surfaced as `cursor_unresolved`
  rather than guessed.

## Alternatives considered

- **Normalize every session to discover** — far too expensive for a "what exists?" question; rejected.
- **Decode directory names back to paths** — impossible after the lossy encoding (ADR 0005); probe a
  session's cwd instead.

## Related

- `discover_all_projects()`, `codex_cwd_fast()`, `probe_cwd()`; `rosetta discover`.
