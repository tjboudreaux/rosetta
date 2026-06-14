# Adversarial review round 3 — scale / hardening / evals (post-fix)

Codex re-reviewed the three goals after the Phase 1–4 fixes. Codex ran read-only (couldn't write this
file), so its findings are transcribed here **with a verification column** — each was checked against
the actual code before being accepted (Codex has confabulated specifics in prior rounds, and did again
here on one item).

## Verdicts (Codex): all three PARTIALLY MET — fair.

- **Goal 1 (scale):** O(1) counter hot path, `search`/`get`/`supersede`, INDEX.json, and the
  "query, don't slurp" SKILL protocol are confirmed present. Residual: `search` is unbounded; no
  10k–50k perf test (largest is 3k); `index` full-rebuild each call (acceptable, deliberate).
- **Goal 2 (hardening):** atomic writes, cycle detection, `--strict`, slug cap confirmed. **But real
  residual race/robustness bugs remain (below).**
- **Goal 3 (evals):** structured-verdict scoring, no-tools `library.txt`, gates, report all confirmed.
  Calibration *infrastructure* is met; tier *discrimination* is not (already documented honestly).

## Findings — verified

| # | Pri | Finding | Verified? | Where |
|---|-----|---------|-----------|-------|
| 1 | P1 | **Race protects filename, not number.** Two concurrent `new` with *different* titles read the same counter → same number, different slugs → both O_EXCL-succeed → duplicate number. "Race-safe numbering" is overclaimed (only same-title collisions are handled). | **REAL** | `decisions.py` cmd_new counter→reserve |
| 2 | P1 | **0-byte tombstone.** O_EXCL creates a 0-byte file, content is written separately; a crash between leaves a 0-byte `NNNN-slug.md` occupying the number (collect logs "no H1", skips — loud-ish, but a turd). | **REAL** | `decisions.py` cmd_new |
| 3 | P1 | **ingest.py bypasses the counter** (globs for next number) and isn't race-safe. | **REAL** | `ingest.py:37-43` |
| 4 | P1 | **`supersede` silent no-op** if the old record has no `- Status:` line — `_set_frontmatter_line` returns text unchanged, but supersede prints success. | **REAL** | `decisions.py` `_set_frontmatter_line` / cmd_supersede |
| 5 | P1 | **Verdict-block gaming:** `bool(v.get("near_miss_untouched"))` — a JSON string `"false"` is truthy → passes. Booleans must be `is True`; extra keys should be rejected. | **REAL** | `score.py:110-111` |
| 6 | P2 | "ADR 0022 title 'Eval Calibration Achieved' is an overclaim." | **HALLUCINATED** — file is `0022-eval-calibration-across-model-tiers.md`, title has no "Achieved"; body already says calibration is *not* met. Rejected. | — |
| 7 | P2 | `search` returns unbounded results at 50k; add `--limit`. | **REAL (minor)** | `decisions.py` cmd_search |

## Fair overclaim catch

ADR 0021 / SKILL call numbering "race-safe" — true only for same-title collisions, **not** for
concurrent `new` with different titles (finding #1). The claim must be scoped down or the race fixed.

## Disposition — RESOLVED (ADR 0023)

All real findings fixed and tested; #6 rejected (hallucinated).

- **#1 + #2 — FIXED:** `counter_lock` + `allocate_and_write` (portable O_EXCL lock file with stale
  reclaim) serialize read-counter→write-record; record written via `atomic_write_text`. No
  duplicate-number race, no 0-byte tombstone. Tests: `test_new_never_reuses_a_number_even_with_stale_counter`,
  `test_counter_lock_is_released`.
- **#3 — FIXED:** `ingest.py` routes through `allocate_and_write`. Test:
  `test_ingest_uses_counter_and_continues_numbering`.
- **#4 — FIXED:** `_set_frontmatter_line` raises; `supersede` exits loudly. Test:
  `test_supersede_raises_on_record_without_status_line`.
- **#5 — FIXED:** verdict booleans require `is True`/`is False`. Test:
  `test_truthy_string_does_not_game_booleans`.
- **#7 — FIXED:** `search --limit` (default 50) + loud truncation. Test:
  `test_search_limit_surfaces_truncation`.
- **Overclaim — CORRECTED:** numbering is now genuinely lock-serialized; ADR 0023 records the fix and
  corrects the over-scoped "race-safe" claim in ADR 0020/0021.
- **#6 — REJECTED:** the cited ADR 0022 title/filename do not exist (hallucinated).
