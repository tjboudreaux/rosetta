# ADR 0023 — Round-3 hardening fixes (true lock-based allocation; loud failures)

- Status: Accepted
- Date: 2026-06-13
- Decider: Travis Boudreaux
- Sources: scripts/decisions.py (counter_lock, allocate_and_write, _set_frontmatter_line, cmd_search), scripts/ingest.py, evals/adversarial/score.py, evals/adversarial/REVIEW-round3.md, tests/test_decisions_cli.py, tests/test_score.py, tests/test_ingest_cli.py
- Related: ADR 0020 (library hardening), ADR 0021 (scalable store), ADR 0022 (eval calibration)

## Context

An independent adversarial re-review (REVIEW-round3.md) verified the ADR 0020–0022 fixes and found
genuine residual gaps — most importantly that the numbering "race-safety" claimed in ADR 0020/0021 was
**over-scoped**: the `O_EXCL` reserve protected the *filename* (`NNNN-slug.md`), not the *number*, so
two concurrent `new` calls with different titles could both succeed at the same number → a duplicate
ADR. It also flagged a 0-byte tombstone on crash, `ingest.py` bypassing the counter, a silent no-op in
`supersede`, and a truthy-string gaming hole in the eval verdict scorer. (One finding — an "ADR 0022
title overclaim" — was a hallucination: no such title exists; rejected after verification.)

## Decision

- **True lock-based allocation.** Replace the O_EXCL-reserve dance with `counter_lock` (a portable
  O_EXCL lock *file* with stale-lock reclaim) wrapping the read-counter → choose-number → write-record
  → save-counter critical section (`allocate_and_write`). The lock serializes allocation, so concurrent
  `new` can no longer collide on a number; a targeted glob guards against counter drift. The record is
  written via `atomic_write_text`, so a crash leaves **no 0-byte tombstone**. This makes the
  "race-safe" claim actually true; it **corrects the over-scoped claim in ADR 0020/0021**.
- **`ingest.py` shares the allocation** — routed through `allocate_and_write`, so it is O(1) and
  race-safe too (no glob, no duplicate-number race).
- **Loud failures, not silent no-ops.** `_set_frontmatter_line` raises (and `supersede` exits with a
  clear message) when a record has no `Status` line to flip, instead of printing success having done
  nothing.
- **Verdict scorer can't be gamed by string booleans.** `score.py` requires the verdict block's
  boolean fields to be real `True`/`False` (`is True` / `is False`), since a JSON string `"false"` is
  truthy in Python.
- **`search --limit`** (default 50) bounds results and surfaces truncation loudly (`truncated`,
  `total_matches`) rather than silently returning everything at 50k.

## Consequences

Positive:
- Numbering is genuinely race-safe and crash-safe across `new` and `ingest`; the claim now matches the
  code.
- `supersede` and the verdict scorer fail loudly on malformed/gamed input.

Negative:
- `counter_lock` adds a lock file and a stale-reclaim window (30s); on a hard crash mid-critical-section
  the next caller waits up to that window. Acceptable for a local CLI; documented.
- `ingest.next_number` is now unused by `main()` (retained only for its unit test); minor dead code.

## Alternatives considered

- **`fcntl.flock`** — POSIX-only; breaks the zero-dependency cross-platform goal. The O_EXCL lock file
  with stale reclaim is portable. Rejected.
- **Leave numbering as O_EXCL + scope the claim down in docs** — cheaper, but leaves a real
  duplicate-number race. Rejected in favor of fixing it.
