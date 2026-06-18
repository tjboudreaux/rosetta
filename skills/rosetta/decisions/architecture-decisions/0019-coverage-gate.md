# ADR 0019 — CI coverage gate (fail under 90%)

- Status: Accepted
- Date: 2026-06-13
- Reviewed: 2026-06-18
- Decider: Travis Boudreaux
- Sources: .github/workflows/ci.yml (coverage job), skills/rosetta/.coveragerc, tests/
- Related: ADR 0013 (pure-stdlib, zero runtime deps), ADR 0017 (test-enforced resilience), ADR 0018 (adversarial eval dataset)

## Context

Coverage had drifted: the collector was well-tested but `decisions.py`/`ingest.py` and the
`--all-projects` discovery path were thinly covered (≈68% line+branch overall, with two scripts under
60%). Nothing stopped coverage from silently regressing. We want a hard floor enforced in CI. The
tension is ADR 0013: the shipped skill is pure stdlib with zero runtime dependencies, and the main
test job is intentionally dependency-free.

## Decision

Enforce **≥90% line+branch coverage** in CI, configured in `skills/rosetta/.coveragerc`
(`fail_under = 90`, `branch = True`, `source = scripts, evals/adversarial`, with `__main__`/pragma
exclusions). The gate runs as a **separate CI job** that `pip install`s `coverage` — so the existing
matrix unit-test job stays pure-stdlib and dependency-free. `coverage.py` is a **CI/dev-only tool**,
explicitly **not** a runtime dependency of the skill; ADR 0013's zero-runtime-dep guarantee is intact.

To reach and hold the floor, in-process tests were added for the previously subprocess-only/uncovered
paths: `collect.py` `--all-projects`/`discover_all_projects`, resolver no-match branches, and parser
count-and-skip branches; `decisions.py` `new`/`index`/`validate` (incl. error paths); `ingest.py`
happy + error paths; and the eval runner's `main()`/bundle/skip paths. Current coverage: 92% total,
every measured file ≥90%.

## Consequences

Positive:
- Coverage can no longer silently regress; a drop below 90% fails CI.
- The added tests materially exercise the judgment-adjacent code paths (discovery, decision library),
  not just the collector.

Negative:
- CI now has one job with a third-party dev dependency (`coverage`). Mitigated by isolating it to its
  own job; the core tests still run with zero deps on the 3.9/3.12 matrix.
- The 90% threshold is line+branch combined; pushing higher would require testing more defensive
  error branches with diminishing value, so 90% was chosen as the floor, not a target ceiling.

## Alternatives considered

- **stdlib `trace` module instead of coverage.py** — avoids the dev dependency but has no branch
  coverage and no `--fail-under`; building an equivalent gate by hand is brittle. Rejected.
- **Add coverage to the existing matrix job** — simpler YAML, but pollutes the deliberately
  dependency-free test job and runs the gate redundantly on two Python versions. Rejected for a
  dedicated single-version job.
- **No gate, just measure** — fails the explicit requirement that CI block coverage regressions.
