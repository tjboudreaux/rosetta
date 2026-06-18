# ADR 0027 — Reviewed freshness-acknowledgment field

- Status: Accepted
- Date: 2026-06-18
- Decided originally: 2026-06-18
- Reviewed:
- Decider: Travis Boudreaux
- Sources: `scripts/decisions.py` (`parse_reviewed`, `staleness_baseline`, `staleness_for_record`), `tests/test_staleness.py`, `references/decision-schema.md`
- Related: ADR 0026 (decision-coverage health metric), the GOAL4 freshness guard (`evals/adversarial/GOAL4-FRESHNESS.md`), ADR 0004 (truth hierarchy)
- Aliases: Reviewed field; freshness acknowledgment; staleness escape hatch

## Context

The staleness guard (`decisions.py staleness`, shipped as GOAL4) flags Accepted records whose cited
`Sources:` code paths changed in git after the record's `Date`. GOAL4 §Limitations explicitly states
"Changed ≠ contradicts … this layer raises the flag a human/agent then adjudicates." But there was
**no mechanism to record that adjudication** — a record that was reviewed and confirmed still-current
got re-flagged stale on every run. This makes `staleness` unusable as a CI gate on any actively
developed repo: it can never go green, because every code change re-flags every citing record, even
ones already reviewed and found non-contradicting.

A live sanity run on Rosetta's own library confirmed the problem: 12 of 30 Accepted records were
flagged stale, all citing core files (`collect.py`, `decisions.py`, `SKILL.md`) that change
routinely. Without an acknowledgment mechanism, those 12 records are either permanently noisy in CI
or permanently ignored — neither is correct.

## Decision

Add an optional **`Reviewed:`** frontmatter field that records the last date a human or agent
confirmed an Accepted decision is still current against its cited code. The staleness comparison
uses it as the **baseline** when present and valid:

```
baseline_date = Reviewed   if present, valid (YYYY-MM-DD), ≤ today, and ≥ effective_date
              = effective_date(rec)   otherwise
```

1. **`parse_reviewed(rec)`** — returns the `Reviewed:` value only when it is a valid `YYYY-MM-DD`
   calendar date ≤ today; returns `None` for absent, malformed, or future values. A future date
   would mask all drift, so it is rejected identically to a malformed one.
2. **`staleness_baseline(rec)`** — returns `Reviewed:` when valid *and* on/after the decision's
   effective date; otherwise falls back to `effective_date(rec)`. A `Reviewed:` before the
   decision's effective date is nonsensical and ignored (validate warns separately).
3. **`staleness_for_record`** — uses `staleness_baseline` as the comparison date; the result dict
   carries `date` (effective date, unchanged), `baseline_date` (whichever was used), and `reviewed`
   (the honored value, or `None`). An ignored `Reviewed:` is never reported as honored.
4. **`validate`** — warns (not errors) on malformed, future, or before-effective-date `Reviewed:`
   values, so a bad field doesn't silently mask drift. The warning appears on plain `validate`,
   not only under `--staleness`.
5. **Surfaces** — `staleness`, `validate --staleness`, and `resolve`'s stale flag all honor
   `Reviewed:` via the shared `staleness_for_record` baseline. The JSON output carries `reviewed`
   and `baseline_date` on each assessed entry so a consumer can see which date drove the comparison.

**Semantics — a baseline, not a permanent override.** A cited code path whose last git commit is
*after* the `Reviewed:` date is stale again. So a review is only good until the code moves once more.
`Reviewed:` does not touch `Date`, `Decided originally`, `Status`, or supersession — the decision
timeline is preserved.

## Consequences

Positive:
- The freshness guard becomes usable as a CI gate: a reviewed-and-confirmed record reports fresh
  until the code moves again, so the gate can go green and re-flag only on genuine new drift.
- Rosetta's own 12 stale records can now be triaged — reviewed and acknowledged — without
  corrupting the decision timeline (no re-dating or superseding).
- Fully additive: records without `Reviewed:` keep the same staleness semantics (the baseline
  falls back to the effective date); JSON output gains additive `reviewed`/`baseline_date` fields.
  223 tests pass (9 new).

Negative:
- `Reviewed:` must be authored and maintained — an unpopulated field adds nothing until someone
  fills it; mitigated by the template seeding the field and `validate` surfacing malformed values.
- The staleness baseline is a *proxy* — a review confirms the cited code was checked, not that the
  decision is semantically correct (same limitation as the anchoring rate in ADR 0026).

## Alternatives considered

- **Re-date the record on review** — rejected: corrupts the decision timeline. `Date` records when
  the decision was made; `Reviewed` records when it was last confirmed, a distinct fact.
- **A permanent `Stale: false` override** — rejected: masks all future drift. A review is only valid
  until the next code change, so the baseline must re-flag on new commits.
- **Auto-supersede when code changes** — rejected (GOAL4 scope): "Changed ≠ contradicts." A code
  change touching a cited file does not prove the decision is wrong; `Reviewed:` records the
  human/agent adjudication, not an automatic one.

## Related

- `scripts/decisions.py` (`parse_reviewed`, `reviewed_problem`, `_reviewed_value_and_problem`,
  `staleness_baseline`, `staleness_for_record`), `tests/test_staleness.py` (`StalenessReviewedField`),
  `references/decision-schema.md` (the `Reviewed:` contract), `decisions/config.json` (`optional_fields`),
  `templates/{adr,pdr,bdr}-template.md`.
