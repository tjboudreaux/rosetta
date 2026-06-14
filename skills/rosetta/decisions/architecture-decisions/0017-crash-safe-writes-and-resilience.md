# ADR 0017 — Crash-safe writes and parse resilience

- Status: Accepted
- Date: 2026-06-13
- Decider: Travis Boudreaux
- Sources: scripts/collect.py (`atomic_write_text`, `load_ledger`, `save_ledger`, manifest write), tests/test_robustness.py
- Related: ADR 0016 (processed-session ledger), ADR 0002 (coverage manifest surfaces gaps loudly)

## Context

Rosetta's promise is that nothing disappears. Two write paths broke that promise on an interrupted
run. `save_ledger` and the manifest write went straight to the destination file
(`path.write_text(...)` / `json.dump(fh, ...)`), so a process killed mid-write left a truncated
file. For the ledger this failed silently in the worst way: `load_ledger` caught every error and
returned an empty ledger, so a half-written ledger quietly made the next run reprocess **every**
session (ADR 0016's incremental skip silently degraded to a full rebuild) with no signal to the
user. Separately, the parsers' count-and-skip resilience on malformed transcript lines was asserted
nowhere, so a regression that turned a skip into a crash would have shipped uncaught.

## Decision

Durability-critical files are written atomically via a single `atomic_write_text(path, text)` helper
— write to a temp file in the same directory, then `os.replace()` (atomic on POSIX and Windows). The
ledger, `manifest.json`, and the `--all-projects` index files all route through it; per-run session
`.md` files do not (they are regenerated every run, so a partial one is harmless).

`load_ledger` now distinguishes a missing ledger (silent — normal first run) from a present-but-
corrupt one: corruption still recovers to an empty ledger (never crashes) but is reported loudly on
stderr (`ledger at <path> was unreadable; reprocessing all sessions`), consistent with ADR 0002's
"surface gaps loudly" principle. `tests/test_robustness.py` asserts atomic-write behavior, the
manifest schema, corrupt-ledger recovery, and that a malformed transcript line is skipped (counted
in `skipped_lines`) rather than fatal.

## Consequences

Positive:
- An interrupted `collect` can no longer corrupt the ledger or manifest; readers see the old file or
  the new one, never a partial one.
- The rare remaining corruption (e.g. a pre-existing bad ledger) self-heals with a visible warning
  instead of silently discarding the incremental cache.
- The count-and-skip guarantee is now test-enforced, locking in resilience against future parser
  changes.

Negative:
- `atomic_write_text` needs write permission on the target's parent directory for the temp file (the
  same directory we already write to), so no new requirement in practice.

## Alternatives considered

- **`fsync` before replace** — guarantees durability against power loss, not just process kill. Adds
  cost and platform nuance for a local, regenerable cache; the `os.replace` atomicity that prevents
  *torn* files is the property that matters here. Deferred.
- **Crash on a corrupt ledger** — surfaces the problem maximally, but breaks a routine catch-up run
  over a stale state file. Rejected for recover-and-warn, matching count-and-skip elsewhere.
- **Leave session `.md` writes non-atomic** (chosen) vs. routing them through the helper too — they
  are fully regenerated each run, so the added temp-file churn buys nothing.
