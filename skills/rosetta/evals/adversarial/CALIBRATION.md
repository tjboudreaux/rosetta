# Eval calibration — Haiku → Opus

A suite that everything passes (or everything fails) measures nothing. This file defines what it means
for the Rosetta evals to *work across model tiers*, and the machinery that makes that measurable.

## The problem with "100% on Opus"

The headline result in `RESULTS.md` (29/29 Tier-A, 23/23 + drift on Opus) is a **ceiling check on one
strong, tool-enabled model**. It proves the suite is *passable* and leak-free; it does **not** prove
the suite *discriminates* model quality. Two things were missing and are addressed here:

1. **Judge dependence.** Tier B is graded by an LLM judge. If the judge is itself weak, the grade is
   noise. → We move the *objective* judgments out of the LLM judge (below).
2. **Tool-assisted ≠ long-context.** The decision-history drift family gave the solver `grep`/`Bash`,
   so it measured retrieval-*with-tools*, not long-context recall. → We add a no-tools variant.

## Judge-independent objective scoring (`score.py`)

For the decision-history scenarios the load-bearing judgments are objective and regex-checkable, with
the correct answer re-derived from the deterministic fixture:

- **supersession:** did the output supersede the *correct* needle ADR, leave the near-miss untouched,
  and report the columnar store (not Postgres) as current?
- **dedup:** did it recognize the decision is already recorded and cite the existing ADR instead of
  duplicating?

`score.py` computes these deterministically (`passed` + per-check booleans), so a Haiku-class **judge**
cannot corrupt them — only the **solver's** answer is under test. The LLM judge (`judge_prompt.md`)
remains the backstop for the subjective claims and for phrasings the regex misses.

## Tools vs no-tools (long-context recall)

`run_evals.py --emit-bundle` writes, for every decision-library scenario, a `library.txt` that
concatenates the entire ADR library into one blob. Two solver conditions:

- **tools** — solver gets `Read`/`Grep`/`Bash` and the project tree; it *searches* the library. This
  is the realistic Rosetta condition (the CLI even has `decisions.py search`). Measures whether the
  model reliably queries.
- **no-tools** — solver gets only `library.txt` inline and must recall from context. Measures
  long-context retrieval; this is where smaller models and large N bend. Run this to find the curve's
  knee.

## Calibration gates (what "works across tiers" means)

Run the suite (or the discriminating subset) per tier, score with `score.py` + the judge, and emit one
`results-tierb-<model>.json` per tier; `report.py` renders the scenario×tier matrix + drift curve +
discrimination panel. The suite is considered **calibrated** when:

| Requirement | Gate |
|---|---|
| Opus-class pass-rate | ≥ 95% |
| Sonnet-class pass-rate | ≥ 80% |
| Haiku-class pass-rate | ≥ 50% |
| **Monotonic ordering** | Opus ≥ Sonnet ≥ Haiku (no inversion) |
| **Discrimination** | ≥ 1/4 of scenarios separate at least two tiers |
| Drift (no-tools) | pass-rate is non-increasing as N grows for the weaker tiers |

If the ordering inverts or nothing discriminates, the suite is mis-calibrated (too easy, too hard, or
leaky) and must be revised — that check is the point, not the absolute numbers.

## How to run a multi-tier pass

```bash
# per tier: run each solver bundle through a model of that tier, save its ground-truth.md, then:
python3 score.py --scenario decision-supersession-lookup-100 --solver-output <tier>/gt.md
# assemble per-tier results-tierb-<model>.json (schema rosetta-eval-results/v1), then render:
python3 report.py results-tier-a.json results-tierb-opus.json results-tierb-sonnet.json \
        results-tierb-haiku.json --out REPORT.md --html REPORT.html
```

## Status

- Built & tested: deterministic scorer, no-tools bundle, multi-tier-capable report, gates above.
- A representative multi-tier run (Haiku/Sonnet/Opus over the discriminating supersession family) is
  recorded in `RESULTS.md` when executed; absent that, the gates are the contract, not yet a measured
  curve. Variance: take k≥3 solver samples per (scenario, tier) and report pass-*rate*, not a single
  pass/fail, since Tier-B is non-deterministic.
