# ADR 0020 — Decision-library hardening (atomic writes, race-safe numbering, cycle detection)

- Status: Accepted
- Date: 2026-06-13
- Decider: Travis Boudreaux
- Sources: scripts/decisions.py (atomic_write_text, cmd_new, cmd_validate), scripts/ingest.py, tests/test_decisions_cli.py (DecisionsHardening)
- Related: ADR 0017 (crash-safe writes in collect.py), ADR 0019 (coverage gate)

## Context

ADR 0017 made `collect.py`'s durability-critical writes atomic, but the **decision-library** writes
were left in-place: `cmd_new`, `cmd_index`, and `ingest.py` all used bare `path.write_text(...)`. A
process killed mid-write could leave a half-written record or a truncated `README.md` index — and for
a tool whose whole point is a durable, auditable decision history, a corrupt record is a silent
data-loss path. `cmd_new` also picked the next number by globbing every file and taking `max+1`, with
a `refusing to overwrite` hard-stop: under concurrency two `new` calls could pick the same number and
one would crash. `validate` resolved dangling supersede links but did not detect supersede **cycles**
(A superseded-by B, B superseded-by A) — the exact "silent oscillation" the project forbids — and had
no way to fail on warnings. An adversarial review flagged the writes/validation as data-loss paths.

## Decision

- **Atomic writes everywhere in the library.** `decisions.py` gets an `atomic_write_text` (temp file +
  `os.replace`, mirroring `collect.py`); `cmd_new`, `cmd_index`, and `ingest.py`'s record write all
  route through it.
- **Race-safe numbering.** `cmd_new` reserves the numbered filename with `os.open(..., O_CREAT |
  O_EXCL)` and, on collision (a concurrent `new` or a slug clash at that number), bumps the number and
  retries instead of crashing. The zero-pad width auto-expands past 9999 so numbering stays correct at
  scale.
- **Cycle detection + `--strict`.** `validate` builds a supersede graph and reports any cycle
  (oscillation) as an error via an iterative DFS (no recursion-limit risk on long chains). `validate
  --strict` makes warnings fail the run (nonzero exit) for CI use. Slugs are length-capped.

## Consequences

Positive:
- An interrupted `new`/`index`/`ingest` can no longer corrupt a record or the index.
- Concurrent record creation no longer crashes or collides; numbering self-heals by bumping.
- Oscillating supersessions are caught deterministically; `--strict` gives CI a hard quality gate.

Negative:
- `cmd_new` still globs to seed the starting number (O(n) per insert). ADR 0021 removes that with a
  counter file; this ADR deliberately scopes to correctness/durability, not the O(n²) scale fix.
- The `O_EXCL` reserve leaves a 0-byte file for the instant before `os.replace` fills it; a concurrent
  `new` correctly treats it as taken and bumps, so this is benign.

## Alternatives considered

- **`fcntl.flock` for concurrency** — POSIX-only; would break the zero-dep cross-platform goal. The
  `O_EXCL` reserve is portable and sufficient. Rejected.
- **Keep `refusing to overwrite`** — surfaces collisions but makes concurrent use fragile. Replaced
  with auto-bump (the library tolerates gaps in numbering, not duplicates).
- **Recursive cycle DFS** — simpler, but a long supersede chain could hit the recursion limit; used an
  iterative coloring DFS instead.
