# Adversarial review: Rosetta eval dataset, round 2 (implementation)

Codex ran round 2 against the implemented dataset. **Notably, Codex executed in a read-only sandbox
and could not actually read the repo files** — so part of its report confabulated a per-scenario
table referencing scenario ids that do not exist in `dataset.json` (`single-agent-clean`,
`multi-agent-overlap`, `stale-cache`, `session-count-drift`, `crush-sqlite`, `hermes-contamination`).
That is itself the hallucination anti-pattern this dataset targets. Every finding below was therefore
**re-verified against ground truth** (running the runner, emitting bundles, dumping manifests) before
being accepted or rejected — the same code-wins discipline Rosetta enforces.

## Findings accepted (verified real) and fixed

- **P0-A — judge bundle was unjudgeable for code-grounded claims.** `_write_bundle` emitted only the
  prompt, gold, anchors, normalized corpus, and git log — not the project code or `manifest.json`.
  Most scenarios resolve in code/git, so the judge could not verify them. **Fixed:** the bundle now
  includes a `project/` snapshot and `manifest.json`. Verified: `project/cache.py` + `manifest.json`
  present in emitted bundles.

- **P0-B — Tier-A was count-only.** Per-agent counts + `len(files) >= 1` would miss duplicated
  sessions, a session misattributed to the wrong agent, and exact unmatchable counts. **Fixed:** added
  an exact **total** session check, a **misattribution guard** (any agent outside the expected set
  with sessions > 0 fails), exact `len(files) == expected`, an **anchor→source** check (each planted
  session id must resolve to a real source/normalized path), exact `expected_extra` values, and a
  contamination guard (`absent_in_corpus`).

- **P0-C — leakage linter ignored git + filenames.** `git log` is solver-visible (SKILL.md step 5),
  but the linter only scanned transcript text. **Fixed:** the linter now also scans commit
  subjects/bodies and relative filenames. Verified clean across all 20 scenarios.

- **P1 — promised store-classes/anti-patterns missing; `crush`/`request_dump` helpers unused.**
  **Fixed:** added three scenarios — `database-store-crush` (Crush sqlite, unverified), 
  `request-dump-contamination` (Hermes dump excluded; fabricated decision must not surface — verified
  it never reaches the corpus), and `unsupported-store-gap` (`.qoder` flagged in `unknown_stores`).
  Store-class coverage is now: project-encoded (Claude/Factory), date-bucketed (Codex), fuzzy
  path-mention (Hermes), file-location (Aider), database (Crush), unknown (`.qoder`).

- **P1 — `cold-project` rubric assumed a commit** that may not exist without git. **Fixed:** rubric now
  reads "anchors on code/docs, and git history if present."

- **P2 — `fixtures.py` CLI crashed on bad args.** **Fixed:** usage guard + fixture list.

## Findings rejected (confabulated or already satisfied)

- The entire per-scenario table and its scenario ids — **do not exist**; Codex never read
  `dataset.json`. Discarded.
- "No negative-control scenario" — **false**: `negative-control` exists (`"negative_control": true`),
  and `cold-project` is a second control.
- Various `supported_by`/anchor-shape claims tied to the confabulated ids — not applicable.

## Findings deferred (honestly out of scope for v1, noted in DESIGN)

`quantitative-drift`, `positional/order-bias`, and `multi-hop reconciliation` are valuable but not yet
implemented; DESIGN.md marks them **future**, rather than claiming coverage we don't have ("no silent
caps").

## Verdict

After the P0/P1 fixes and ground-truth re-verification, the dataset is trustworthy to ship as the
Tier-A CI gate + Tier-B judge harness: 20 scenarios, 0 leaks, all store-classes covered, exact
substrate assertions, and an enriched judge bundle. The judgment layer (Tier B) remains
model-graded by design.
