# ADR 0006 — Hermes multi-shape ingestion

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Reviewed: 2026-06-18
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (found + fixed + verified); `claude · 43c9e0f6 · 2026-06-07` (surfaced during a downstream-project run); code `scripts/collect.py` (`resolve_hermes`, `collect_session`)
- Related: ADR 0002

## Context

`~/.hermes/sessions/` mixes four file shapes; only two are conversations. The original resolver
globbed `*.jsonl` only and so saw ~2 of ~65 files — roughly 97% of Hermes history was invisible. The
bulk live in `session_*.json` (a single JSON object with a top-level `messages` list), and 40
`request_dump_*.json` files are HTTP request/error dumps that merely embed a `role`, so a naive
`"role"` grep would wrongly pull them in.

## Decision

`resolve_hermes` globs `*.jsonl` **and** `session_*.json`, excluding `request_dump_*.json` (counted as
`request_dumps_excluded` in the manifest) and `sessions.json` (an index). `collect_session` detects a
single-object file with a top-level `messages` list and iterates it, falling back to JSONL otherwise;
when per-message timestamps are absent it uses the doc's `session_start`/`last_updated` for the date
range. `references/agent-stores.md` documents all four shapes.

## Consequences

Positive:
- Hermes coverage jumped from ~2 files to the full set (e.g. on one real project: 1 → 8 sessions / 257
  messages, verified). Excluded dumps are surfaced, not silently dropped (ADR 0002 discipline).

Negative:
- One more on-disk shape for `collect_session` to handle; mitigated by detecting it via a whole-file
  JSON parse that JSONL files fail cleanly.

## Alternatives considered

- **Glob all `*.json`** — would ingest the request/error dumps as if they were transcripts; rejected.
- **A separate Hermes-only normalizer** — duplicates `collect_session`; folded in instead.

## Related

- `resolve_hermes()`, `collect_session()`; `references/agent-stores.md` "Hermes".
