# ADR 0026 — Decision-coverage library-health metric

- Status: Accepted
- Date: 2026-06-16
- Decider: Travis Boudreaux
- Sources: scripts/decisions.py, tests/test_coverage.py, specs/SPEC-03-decision-coverage.md
- Related: ADR 0024 (anti-hallucination integrity gate), ADR 0021 (scalable decision store / `resolve`), ADR 0025 (alias/glossary resolution layer), ADR 0020 (decision-library hardening), ADR 0019 (test-coverage gate)
- Aliases: coverage metric; library health; decision coverage

## Context

A decision library's value rests on a claim the tooling never actually measured: that its records are
*trustworthy* — anchored to the code they govern, uniquely retrievable, and not silently stale. ADR
0024 made fabricated provenance falsifiable per-record; ADR 0019 covers *test* coverage of the tooling.
Neither answers the *product/library-health* question a team needs before relying on the oracle: across
the whole library, what fraction of live decisions are anchored, how many topics fail to resolve
uniquely, and is any of it drifting? Without a number, "the library is good" is an assertion, not a
fact, and there is nothing to gate in CI.

The design was hardened across three adversarial-review rounds (codex + gemini) recorded in
`specs/SPEC-03-decision-coverage.md`. One reviewer-split decision — whether full-title self-retrieval
should be a headline *rate* — was escalated and resolved by the maintainer: self-retrieval is a
non-gated **diagnostic**, and only anchoring is gated (a title-collision rate punishes legitimate
cross-references and manufactures false failures).

## Decision

Add a deterministic `decisions.py coverage` command that prints a JSON health report and never mutates
the library. The denominator for the gated signal is **Accepted** records (the ones a library serves).

1. **Provenance/code-anchoring (primary, gateable)** — a record is anchored iff its `Sources:` cite at
   least one path that resolves by **exact relative path** (file *or* directory) under a repo-bounded
   set of source roots, plus a directory addendum for bare dir tokens. Matching is never by basename,
   and resolved paths must stay inside the git repo boundary when git is present, so a citation cannot
   anchor to an unrelated sibling project. Output carries the rounded `rate`, the exact `rate_raw` the
   gate compares, and the `unanchored` gaps.
2. **Reported signals (not gated)** — supersession stats (status distribution, active/retired, chain
   depth via the existing resolver's chain length), `orphans` (records with no in/out links),
   git-optional `staleness` (skipped cleanly when git is absent), and `alias_coverage`.
3. **Agent-retrieval diagnostic (not gated)** — each Accepted record's own title is resolved; any that
   do not resolve to a unique record are listed under `retrieval.ambiguous_topics` with the ids they
   `collides_with` (defined as `sorted((endpoints ∪ alias-conflict candidates) − self)`), so a human
   can disambiguate or add an alias. It is a diagnostic, not a rate, by explicit review decision.
4. **Gate** — report-only by default; `--min-coverage FLOAT` (validated to `[0,1]`) exits nonzero when
   `anchoring.rate_raw` is below the floor. A null rate (no Accepted records) is skipped, never a crash.
5. **Shared core** — the resolution logic is extracted into a pure `resolve_query(...)` reused by both
   `resolve` and the coverage retrieval diagnostic, so the two can never diverge; `cmd_resolve`'s JSON
   output is unchanged byte-for-byte.

## Consequences

Positive:
- Library trustworthiness is now a single deterministic number that can gate CI (`--min-coverage`),
  turning "is this library good?" into a measurable, falsifiable check.
- Reuses the existing resolver/staleness/integrity machinery; pure stdlib, no new dependencies.
- Fully additive: `resolve` output is byte-identical; the full suite passes (214 tests, 21 new,
  including a full-JSON parity guard on the refactor).

Negative:
- The anchoring rate is a *proxy* — a record can cite a real path that is the wrong one; the metric
  measures the presence of trustworthy provenance, not its semantic correctness.
- The retrieval diagnostic runs one resolution per Accepted record (each builds the alias map), so it
  is O(n) resolves; acceptable for an occasional health command, not a hot path.

## Alternatives considered

- **A headline self-retrievability rate** — rejected after escalation: full-title self-resolution
  collisions are dominated by legitimate cross-references, so a rate manufactures false failures. Kept
  as a non-gated diagnostic instead.
- **Gating supersession or staleness** — rejected for v1: both are healthy/contextual signals (a mature
  library *should* have superseded records), so they are reported, not gated.
- **A `--status` flag to change the denominator** — deferred: the `accepted_*` field names imply a fixed
  denominator; revisit with neutral field names if a team needs to gate a different lifecycle stage.

## Related

- `scripts/decisions.py` (`resolve_query`, `_anchor_roots`, `_record_code_anchored`, `assess_coverage`,
  `cmd_coverage`; `coverage` subcommand + dispatch), `tests/test_coverage.py`,
  `specs/SPEC-03-decision-coverage.md` (3-round adversarial review), `references/decision-schema.md`
  (the authored contract), `SKILL.md` (operator guidance).
