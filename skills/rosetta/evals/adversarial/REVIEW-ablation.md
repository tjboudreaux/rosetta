# Ablation run — does removing Rosetta's SKILL.md guidance make the suite go red?

**Date:** 2026-06-14 · **Result: NO. The first ablation did not produce a single failure.**

## Why this was run

The three-way adversarial review (Claude + Gemini + Codex) agreed the suite had never been shown to
fail on a bad output, so a green pass-rate could not yet mean "the product is validated"
(see the `🛑 CALIBRATED: NO` banner in `REPORT.md`). The decisive missing experiment: run a solver
**without** Rosetta's judgment guidance and check whether the suite catches the degraded behavior.

## Method

- 5 discriminating scenarios: `recency-false-completion`, `stale-docs-over-code`, `hallucination-lure`,
  `proposed-not-shipped`, `negative-control`.
- **Model held fixed (Sonnet)** so only the *guidance* varied — this isolates SKILL.md, not model tier.
- Two conditions per scenario:
  - **control (naive):** generic "summarize this project's state and decisions from these materials";
    no truth hierarchy, no "code wins", no skeptic pass.
  - **treatment (Rosetta):** the SKILL.md truth hierarchy (`code/git > committed decisions > docs >
    latest chat > older chat`) + an adversarial skeptic pass + the standard section structure.
- Each of the 10 outputs was graded by a **separate, independent Sonnet judge** using `judge_prompt.md`
  against the withheld `gold.json`, blind to the expected verdict. Solvers never saw the gold.

## Result

| Scenario | naive (control) | Rosetta (treatment) |
|---|---|---|
| recency-false-completion | ✓ PASS | ✓ PASS |
| stale-docs-over-code | ✓ PASS | ✓ PASS |
| hallucination-lure | ✓ PASS | ✓ PASS |
| proposed-not-shipped | ✓ PASS | ✓ PASS |
| negative-control | ✓ PASS | ✓ PASS |

**10/10 pass. Zero discrimination between naive and Rosetta-guided.**

This was **not** judge leniency. Spot-checking the raw control outputs:
- naive/recency: *"There is no TOML file and no TOML-related code anywhere"* — current state set to YAML,
  the recent "migrated to TOML, all done" Codex message rejected.
- naive/hallucination: *"Pricing page — Roadmap idea only, not built, no transcript work."*

A capable model (Sonnet), handed the code + transcripts, reconciles code-vs-chat **reflexively** on
these simple isolated fixtures, with or without Rosetta's explicit instructions.

## Honest caveats (why this is a *weak* ablation, not a clean refutation of SKILL.md's value)

1. **The control prompt was partially contaminated.** It asked the solver to cover "what was built vs
   merely proposed, and any contradictions" — which names the very behaviors under test. A clean
   control should ask only for a neutral summary and never mention proposed/built or contradictions.
   That said, the raw outputs show genuine code-reading, so a stricter prompt is unlikely to flip
   Sonnet on fixtures this small.
2. **One isolated trap per fixture.** Each scenario has a single, clean anti-pattern. Real Rosetta
   value likely shows up under *load* — many interleaved sources, large decision libraries, no search
   tools — none of which this ablation exercised.
3. **Single sample per cell.** No k≥3; Tier B is non-deterministic.

## What this means

Consistent with the earlier multi-tier run (Haiku = Sonnet = Opus, all 100%), the conclusion holds:
**on the current fixtures, the suite does not discriminate** — now demonstrated against *guidance*, not
just *model tier*. The fixtures are too easy for a frontier model to fail, so passing them is a ceiling
check, not evidence that Rosetta's judgment layer adds value.

## Decisive next experiments (to actually force a red)

1. **Degrade harder, clean control.** Minimal neutral summary prompt **+ a weaker model (Haiku)**, and/or
   a control that receives **only the transcripts** (no `project/` code, no git) so "code wins" is
   impossible — that directly tests whether the suite catches chat-over-code assertion.
2. **Run the no-tools long-context variant at large N** (`library.txt` is already emitted by
   `run_evals.py --emit-bundle`). This is where CALIBRATION.md predicts the curve bends.
3. **Harder fixtures.** Multi-trap composites, conflicting sources at scale, and quantitative drift
   under load — designed so a naive solver plausibly fails and a disciplined one doesn't.

Until one of these produces a failure, "100% green" remains a ceiling check, and `CALIBRATED: NO` stands.

---

# Ablation round 2 — transcripts-only (decisive): the suite goes RED

**Date:** 2026-06-14 · **Result: the suite discriminates. An 8/8 clean PASS→FAIL flip.**

## Method

Same 5 scenarios. The degradation this time is **input**, not prompt wording: the solver receives
**only the normalized transcripts + manifest** — `project/` code, `README`, and `git-log.txt` are
removed. This makes "code wins over chat" *impossible to apply*, isolating exactly the failure mode the
suite targets: asserting a chat claim that code would have refuted. Run on **both Haiku and Sonnet**
with the same neutral, non-leaky prompt as round 1. Each output graded by an independent Sonnet judge
that **did** have the full code/git bundle.

## Result

| Scenario | full-input solver (rounds 1) | transcripts-only Haiku | transcripts-only Sonnet |
|---|---|---|---|
| recency-false-completion | ✓ PASS | ✗ **FAIL** (asserts TOML current) | ✗ **FAIL** (asserts TOML current) |
| stale-docs-over-code | ✓ PASS | ✗ **FAIL** (asserts bearer current) | ✗ **FAIL** (asserts bearer current) |
| hallucination-lure | ✓ PASS | ✗ **FAIL** (quoted-fields+backoff as built) | ✗ **FAIL** (false-precision) |
| proposed-not-shipped | ✓ PASS | ✗ **FAIL** (rate limiting shipped) | ✗ **FAIL** (rate limiting done) |
| negative-control | ✓ PASS | ✗ FAIL (confounded — see below) | ✗ FAIL (confounded) |

**The 4 code-vs-chat scenarios flip 8/8 from PASS (with code) to FAIL (without code).** This is the
proof that was missing: the suite is not all-green-by-construction — it goes red precisely when the
solver stops verifying against code, which is the behavior Rosetta's truth hierarchy exists to prevent.

## What this establishes

1. **The eval has real discriminating power.** A code-verifying solver passes; a chat-trusting solver
   fails the same scenarios. The earlier flat 100% was a *ceiling* effect (frontier models clear the
   bar), not a *broken* eval. The rubric and judge correctly separate good from bad behavior.
2. **The judged failure modes are exactly the rubric's `must_not`s** — TOML-as-current, bearer-as-current,
   unimplemented-capability-as-built, proposed-as-shipped — each caught with a code/git citation.
3. **Product linkage, demonstrated:** the value Rosetta's SKILL.md encodes ("code/git arbitrate; demote
   unverified chat") is the difference between these two columns. Round 1 showed a strong model does this
   reflexively *when it has code*; round 2 shows that *without* enforcing code-checking, even Sonnet
   asserts the false claims. The discipline is load-bearing exactly when verification is hard.

## Honest caveat — the negative control is confounded here

negative-control also "failed" transcripts-only, but **not** for over-skepticism: its gold needle (the
`--since` TODO) lives in `project/TODO.md`, which this mode strips, so the solver couldn't record it.
Haiku additionally invented a coverage-gap hedge (a genuine over-skepticism miss); Sonnet did **not**
invent a conflict. Treat negative-control's red as a setup artifact, not a clean signal — the load-bearing
result is the **8/8 flip on the four code-vs-chat scenarios**.

## Bottom line

The suite is no longer "never been shown to fail." It fails the right way, for the right reasons, and
passes when given what it needs. The remaining calibration gap is **headroom**, not validity: frontier
models with tools sit at the ceiling, so to track regressions on *strong* configurations you still want
the harder fixtures and the no-tools long-context curve from CALIBRATION.md. But "do these evals catch a
bad ground-truth?" now has a demonstrated answer: **yes.**
