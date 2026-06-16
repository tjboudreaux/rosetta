# GOAL 4 — Phase-1 resolver/freshness layer

The durable product piece from `EVAL-AND-PRODUCT-ROADMAP.md` Phase 1: *"Freshness / drift guard …
`decisions validate --staleness` flags ADRs whose cited code/commit moved … Without this the folder
becomes a confidently-wrong oracle — worse than raw."* This document records what was built, how
staleness is detected, the test results, and the limitations.

## What was built (`scripts/decisions.py`)

1. **`decisions.py staleness`** (new subcommand) — flags **Accepted** records whose cited `Sources:`
   code paths changed in git **after** the record's `Date`. Prints compact JSON:
   `{git, checked_records, stale[], unknown[], fresh_count, note}`.
   - `--status <prefix>` checks a different status set (default: `Accepted` — the records a library
     actively serves).
   - `--strict` exits non-zero when any stale record is found (CI-gateable).

2. **`decisions.py validate --staleness`** — runs the same freshness pass inside `validate`, surfacing
   each stale record as a warning (and, under `--strict`, a failure). So one `validate --staleness`
   invocation is the combined contract + freshness gate.

3. **`decisions.py resolve` freshness annotation** — the resolver now annotates each returned current
   record with a `stale` flag (`true` / `false` / `null`=unknown) and, when stale, the offending
   `stale_paths`. Top-level `freshness_checked` says whether git was consulted; top-level `stale: true`
   appears if any resolved record is stale. `--no-stale-check` opts out (skips git). This is the moat
   piece: a resolved Accepted record whose code has moved is a *stale oracle*, and the resolver now
   says so instead of presenting it as authoritative.

All pure stdlib — only `subprocess` to the `git` binary was added (ADR 0013). No new dependencies.

## How staleness is detected

For each in-scope record:

1. **Extract code paths from `Sources:`** (`extract_source_paths`). The `Sources:` field mixes Rosetta
   transcript citations (`` `agent · session · date` ``), prose, and code paths. The extractor:
   - strips ``` `… · … · …` ``` transcript citations wholesale (the ` · ` separator identifies them),
   - keeps tokens that are slash-paths (`scripts/decisions.py`, `tests/`) or dotted filenames with a
     short extension (`ci.yml`, `pyproject.toml`),
   - drops bare prose words (no slash, no extension), and de-dupes preserving order.
2. **Locate the git work tree** (`_git_repo_root`) containing the decisions root. If there is none, or
   git is unavailable, the whole check **skips cleanly** (reports `git: false, skipped: true`) — it
   never reports a false all-fresh.
3. **Per cited path**, run `git -C <repo> log -1 --format=%cI -- <path>` to get the last commit date.
   The path is resolved decisions-root-relative first, then verbatim (repo-relative). The day-level
   commit date is compared against the record's `Date`:
   - last commit **strictly after** `Date` → **stale** (the code moved past the decision),
   - last commit on/before `Date` → **fresh**,
   - git knows no history for any cited path → **unknown** (`stale: null`).

The three-state result (`true` / `false` / `null`) is deliberate: a consumer must treat "unknown" as
*unknown*, never silently as "fresh".

## Test results

New file `tests/test_staleness.py` (15 tests): pure-unit coverage of the path extractor (citations,
prose, dedupe, backticked/bare paths, trailing-slash dirs) plus integration tests that stand up a real
throwaway git repo with explicit commit dates and assert:

- a record whose code committed **after** its Date is flagged stale (with the offending path),
- a record whose code predates its Date is reported fresh,
- only Accepted records are checked by default,
- a path git doesn't track is reported unknown (not stale),
- `--strict` exits non-zero on stale,
- `validate --staleness` warns and (with `--strict`) fails,
- `resolve` surfaces the `stale` flag, and `--no-stale-check` skips it,
- a decisions-root-relative cited path resolves to the tracked file,
- with no git repo the check skips cleanly.

```
$ python3 -m unittest discover -s tests -p test_staleness.py
Ran 15 tests — OK

$ python3 -m unittest discover -s tests          # full suite
Ran 149 tests — OK
```

Sanity check on the real library in this repo:

```
$ decisions.py staleness --root skills/rosetta/decisions
git: True  checked: 27  stale: 12  unknown: 8  fresh: 7
```

i.e. of 27 Accepted records, 12 cite code that has moved since their Date (expected in an
actively-developed repo), 8 cite only non-code/unresolvable sources, 7 are fresh.

## Limitations

- **Best-effort, git-only.** No git, a detached/unavailable binary, or a non-repo root → the check
  skips. It is a *guard*, not a proof of freshness.
- **Day-resolution dates.** `Date:` is a `YYYY-MM-DD` string, so comparison is at day granularity; a
  same-day commit-after-decision is treated as not-stale (conservative — avoids false positives).
- **Heuristic path extraction.** A code path written in prose with spaces, or an unusual extension
  (>5 chars), may be missed; a non-path token that happens to look like `name.ext` could be picked up.
  Real `Sources:` lines in this repo extract cleanly. Records whose evidence is a commit hash or a
  transcript citation only (no code path) are reported **unknown**, not stale.
- **"Changed" ≠ "contradicts".** A commit touching a cited file flags the record for *review*; it does
  not prove the decision is wrong. Auto-supersede-on-contradiction (the roadmap's stretch goal) is out
  of scope here — this layer raises the flag a human/agent then adjudicates.
- **Renames/moves.** A cited path that was renamed in git will read as "unknown" once the old path has
  no history at HEAD; `git log --follow` was not used (it complicates the strictly-after-Date compare).
