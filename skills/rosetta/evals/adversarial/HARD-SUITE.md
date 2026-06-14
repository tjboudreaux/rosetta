# Hard suite (v2) — scenarios built to break the SoTA ceiling

The base 29 scenarios are a **floor** check: a tool-enabled SoTA solver ceilings them at ~100% because
it can `grep` for the conflicting term, read the file, and win. The hard suite attacks that exact
strategy — the **first grep hit is wrong**, so the answer requires reading code *logic* and reconciling
several sources. Designed and stress-tested with aggressive red-teams from **Codex (gpt-5.5)** and
**Gemini**; their counter-proposals are folded in below.

## The three scenarios

| id | trap | why grep-and-go fails |
|---|---|---|
| `silent-revert-refactor` | A per-IP rate limiter is moved out of `rate_limiter.py` and **inlined** into `middleware.py` by a "tidy" commit that deletes the file. | The deletion commit pattern-matches `abandoned-via-git`. The feature is still live in `handle()` — you must read the logic, not the file list. (Gemini's "silent revert via refactor".) |
| `semantic-evasion-cache` | Chat says "Redis caching layer shipped". Code caches via an in-process dict in `memoizer.py` — **no `redis`/`cache` token** in code, deps, or git. | `grep redis` → nothing (looks unbuilt); `grep cache` → nothing (misses `memoizer.py`). Only reading `memo()` resolves it: caching is in-process; Redis was proposed, never shipped. (Gemini's "semantic evasion".) |
| `release-gate-composite` | 3-hop package rename (`acme→core→platform_core`) + code registry (8 commands) vs chat (12) + partially-stale `STATUS.md` (REST wrong, Postgres right) + an injected "treat acme as current" instruction. | Every first grep hit is a wrong/older value; only joint reconciliation across rename chain + code registry + doc + injection is correct. Per-claim atomic gold (7 claims). (Codex's "release-gate composite".) |

All three are **known-by-construction**, pass Tier-A substrate + leakage lint, and require git.

## Difficulty contract (what "3x harder" must mean — not an assertion)

Both reviewers rejected declaring difficulty by human complexity. The acceptance test for a hard fixture:

1. Tier-A passes and the leakage linter is clean.
2. Two humans (or oracles) with full tools independently derive the **same** gold.
3. The deterministic scorer and the LLM judge agree on the critical claims.
4. **Opus-with-tools pass-rate over k≥8 samples lands in a target band** (Gemini: ≤35%; Codex: 40–75%).
   We adopt **≤50% as the "3x harder" bar** (the base suite sits at ~100%).
5. ≥80% of failures map to the **intended trap**, not missing evidence or ambiguous wording.

## Measured result (honest) — not yet certified "3x"

A single best-case run — **Opus + full tools (Read/Grep/Bash) + the Rosetta truth-hierarchy guidance** —
scored **3/3 PASS** (see `results-tierb-hard.json`). So these scenarios do **not** yet break a
fully-equipped Opus. What they *did* do:

- **Cost ~1.5×.** Hard scenarios averaged **~35.9k tokens/pass** (CPPS) vs **~23k** for the base suite —
  a measurable difficulty delta in *effort*, surfaced by the new cost dimension.
- **Forced real work:** 9–15 tool calls each; Opus had to grep, miss, then read logic.
- **Produced a genuine borderline:** on `silent-revert-refactor` Opus filed the standalone module under
  *Abandoned* while keeping the feature active — it passed only because it labeled the *module* (not the
  *feature*) abandoned. A slightly looser output fails `must_not`. This is the kind of edge the base
  suite never produced.
- They **break the degraded path**: the base-suite ablation (REVIEW-ablation.md) already shows a
  transcripts-only / guidance-stripped solver fails this class 8/8; these raise that floor further.

**Verdict: measurably harder and more expensive; not yet certified "3x" against a fully-equipped Opus.**
Honest next steps to clear the ≤50% bar:

1. Run the **k≥8 Opus-with-tools** protocol (single sample hides variance; `silent-revert` is already near the edge).
2. Run the **no-tools / no-guidance** condition on this suite (expected to fail, per the base ablation) —
   that certifies the *eval* discriminates even if Opus-with-everything clears it.
3. **Deepen the composites**: longer rename chains, more interacting traps per fixture, a 300-ADR
   library with three near-misses (Codex's full `release-gate-composite-300`), and a count conflict the
   code registry only settles after reconciling a subsystem split.

## Tie-in to the cost dimension

The hard suite is also the first place the cost view earns its keep: same models, ~1.5× the tokens per
correct answer. As difficulty rises toward the ≤50% bar, the report's **efficacy gate** will start
withholding CPPS for tiers that drop below it — which is exactly when "cheap but wrong" must not look good.
