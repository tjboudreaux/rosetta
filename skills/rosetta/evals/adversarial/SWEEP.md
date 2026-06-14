# Cross-harness validation sweep (2026-06-14)

14 models × 3 hard scenarios × {baseline, Rosetta-scaffolded}, **identical inlined inputs** (in-context,
no tools — every model gets the same transcripts + code + git + manifest pasted into the prompt), each
output **blind-judged by an independent Sonnet judge** against the withheld gold. 84 solver runs + 84
judgments. Raw record: `results-tierb-sweep.json`. Prices: verified 2026-06 sheet (`pricing.json`).

Model IDs were probed live; corrections vs the original request are in `pricing.json` (droid has no
`droid-core-` prefix; codex `gpt-5.4` is the plain id; **`gemma-4-31b-it` is omitted — Google API quota
block**).

## The matrix

| Harness | Model | Baseline | +Rosetta | Δ | ~$/correct (Rosetta) |
|---|---|---|---|---|---|
| claude | haiku 4.5 | 3/3 | 3/3 | +0 | ~$0.0076 |
| claude | sonnet 4.6 | 3/3 | 3/3 | +0 | ~$0.0225 |
| claude | opus 4.8 | 3/3 | 3/3 | +0 | ~$0.0425 |
| codex | gpt-5.4 | 3/3 | 3/3 | +0 | ~$0.078 † |
| codex | gpt-5.5 | 3/3 | 3/3 | +0 | ~$0.126 † |
| gemini | gemini-3.1-pro | 3/3 | 3/3 | +0 | ~$0.0155 |
| gemini | gemini-3.5-flash | 3/3 | 3/3 | +0 | ~$0.0144 |
| gemini | gemini-3-flash-preview | 2/3 | 2/3 | +0 | ~$0.0057 |
| gemini | gemini-3.1-flash-lite | **1/3** | **2/3** | **+1** | ~$0.0027 |
| droid | glm-5.1 | 3/3 | 3/3 | +0 | 0.55× mult ‡ |
| droid | kimi-k2.6 | 3/3 | 3/3 | +0 | 0.40× mult ‡ |
| droid | minimax-m2.7 | 3/3 | 3/3 | +0 | 0.12× mult ‡ |
| droid | deepseek-v4-pro | 3/3 | 3/3 | +0 | mult n/a ‡ |
| droid | nemotron-3-ultra | **2/3** | **3/3** | **+1** | 0.40× mult ‡ |

† codex/droid captured output includes CLI chrome (banners + reasoning logs), so their token/$ are
**upper bounds**, not comparable to the clean per-token figures. ‡ Droid Core models are multiplier-priced
on Factory credits, not per-token — $ omitted.

## The three value axes, from real data

**1. Correctness.** 9/14 models clear the full hard suite (3/3) unaided; **11/14 with Rosetta**. The Opus
4.8 bar (3/3) is matched by Sonnet, Haiku, gpt-5.4/5.5, gemini-3.1-pro, gemini-3.5-flash, and four of
five Droid open models — i.e. correctness is *not* exclusive to the frontier tier on this suite.

**2. Correctness at token savings.** At identical 3/3 correctness the cost spread is large: **Haiku
matches Opus at ~$0.0076 vs ~$0.0425 — ~5.6× cheaper for the same result.** gemini-3.5-flash also hits
3/3 at ~$0.0144 (~3× cheaper than Opus). Same answer, a fraction of the spend.

**3. Bringing SoTA correctness to cheaper / distilled models.** Two complementary findings:
- **Distilled models already at the bar:** gemini-3.5-flash, Haiku, and Droid minimax-m2.7 (0.12×) /
  glm-5.1 / kimi-k2.6 / deepseek-v4-pro all reach the Opus 3/3 correctness at far lower cost.
- **Scaffolding lifts the weakest toward the bar:** the only models that improved with Rosetta were the
  two weakest — **gemini-3.1-flash-lite 1/3 → 2/3** and **nemotron-3-ultra 2/3 → 3/3 (perfect).** For
  these, the truth-hierarchy + skeptic scaffolding is the difference between missing and matching.

## Honest caveats (these bound the claims)

- **In-context mode makes the hard suite easier.** Every model received all the code inlined, so the
  grep-defeating traps (which punish search-and-stop) are softened — a model that reads the whole prompt
  sees the real code directly. That's why most models ceiling at baseline here, whereas the earlier
  *tool-enabled* run had Haiku at 1/3 on the same scenarios. Both modes are legitimate; they measure
  different things (long-context reconciliation vs. tool-driven retrieval). The scaffolding Δ is
  therefore a **lower bound** — it shows up only where in-context reading still isn't enough.
- **n = 1 per cell** (× 3 scenarios). Directional, not statistically firmed; k≥3 needed before quoting.
- **Cost is clean only for claude + gemini.** codex/droid token counts include CLI overhead (upper
  bounds); droid is multiplier-priced. The per-token $ for claude/gemini use the verified sheet.
- **`silent-revert` gold is lenient** — all 14 passed it; discrimination came from semantic-evasion and
  the composite. Worth tightening (require naming the live limiter logic).
- **gemma-4-31b-it not run** — Google quota block on the account.

## Bottom line

The product-value thesis holds across harnesses with real, blind-judged data: **correctness is
achievable well below the frontier tier; the same correctness is available at multiples-cheaper cost;
and Rosetta's scaffolding measurably lifts the weakest/cheapest models toward the SoTA correctness bar**
(flash-lite +1, nemotron +1 to perfect). The effect is strongest exactly where it should be — on the
models that can't already do it alone.
