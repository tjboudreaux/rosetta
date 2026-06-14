# Product value — three things the evals can prove

Token counts in the results are **not** a record of what running the evals costs. They exist so the
suite can demonstrate that product value is multi-dimensional. Three lenses, all rendered in the
**Product value** panel of `REPORT.md`:

1. **Correctness** — does the model produce the right, code-anchored ground truth? (pass-rate)
2. **Correctness at token savings** — same correctness for fewer tokens / lower cost.
3. **Bringing SoTA performance to cheaper / distilled models** — does Rosetta's scaffolding lift a
   cheap model to a strong model's correctness, and at what cost?

Each run is tagged with `model_tier` (opus/sonnet/haiku), `condition` (baseline / rosetta / naive /
notools), and `scenario_set` (base / hard). The panel groups by set and computes the lenses; cost is
solver tokens, and **$/correct** = cost per *passed* scenario (failing cheap looks expensive, not
free) and is **withheld below an 80% efficacy gate** so "cheap but wrong" never reads as a win. Dollar
figures are estimated from total tokens × a blended rate in the versioned `pricing.json` (exact
input/output pricing is used when a run carries a split).

## Measured result (hard suite, model × condition grid, blind-judged)

Each cell is a tool-enabled solver on the 3 hard scenarios, graded by an independent Sonnet judge.

| Condition | Correctness | Est. $/correct |
|---|---|---|
| **Opus, no scaffolding** (SoTA baseline) | **3/3 (100%)** | ~$1.14 |
| Haiku, no scaffolding | 1/3 (33%) | withheld (<80%) |
| **Haiku + Rosetta** (cheap + product) | **3/3 (100%)** | **~$0.047** |
| Opus + Rosetta | 3/3 (100%) | ~$1.18 |

**The three lenses, from one experiment:**

1. **Correctness:** Opus-baseline sets the bar at 3/3 on scenarios built to defeat grep-and-pattern-match.
2. **Correctness at token savings:** on the base suite, Rosetta guidance holds 100% for ~3% fewer
   tokens than the naive prompt; on the hard suite, Haiku+Rosetta reaches the same 100% as Opus for
   **~25× less per correct answer**.
3. **SoTA on a cheaper model:** unaided Haiku scores **33%** on the hard suite; **Haiku + Rosetta
   scaffolding scores 100% — matching the Opus baseline — at ~24× lower estimated cost per correct
   answer.** The product is the difference between the 33% and the 100% column. The two Haiku failures
   without scaffolding were a confident-hedge (citing a "Redis shipped" chat claim as current) and a
   dropped gold claim — exactly the failure modes the truth-hierarchy + skeptic pass prevent.

This is the core product argument made measurable: **Rosetta's scaffolding transfers a frontier
model's reconciliation correctness onto a distilled model an order of magnitude cheaper.**

## Honest limits

- **Single sample per cell.** No k≥3 yet; treat the grid as directional. The earlier Codex/Gemini
  reviews asked for k≥3 + median before quoting cost numbers externally — do that before publishing.
- **$ is estimated** from total tokens × a blended 70/30 rate, because the subagent harness reports a
  total, not an input/output split. The *ratio* between tiers (~19× per token) is robust; the absolute
  dollars are illustrative. Capture an input/output split to get exact `$`.
- **Small N (3 hard scenarios).** Widen the hard suite before treating the 33%→100% lift as a precise
  effect size; the direction is clear and blind-judged.
- Same model family (Sonnet) judged all cells — guards against in-context bias, not a shared blind spot.
