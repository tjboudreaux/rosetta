# Adversarial eval dataset

A leak-resistant, known-by-construction eval suite for Rosetta's **judgment half** — the part that
reconciles transcripts, code, git, and docs into a cited `ground-truth.md`. It targets the
anti-patterns LLM systems fall into: hallucination, contradiction, knowledge drift, recency bias,
over-confidence, misattribution, conflation, prompt-injection, false-precision citation, and silent
coverage gaps. (The collector half is covered by `tests/test_discovery.py`,
`test_incremental.py`, `test_robustness.py`.)

It was designed and then **adversarially reviewed by an independent model (Codex)** in two rounds —
see `DESIGN.md`, `REVIEW-round1.md`, `REVIEW-round2.md`. (Round 2 is also a live demonstration of why
the dataset exists: the reviewer hallucinated scenarios that didn't exist, so every finding was
re-verified against ground truth before being applied.)

## Two tiers

| Tier | What it grades | Determinism | Runs in CI |
|------|----------------|-------------|------------|
| **A — substrate** | The collector surfaced exactly the planted sessions, anchors and code/doc/git markers exist, nothing was misattributed or dropped, and **no gold leaked** into any solver-visible file. | Deterministic (pure Python) | **Yes** — `tests/test_adversarial_evals.py` |
| **B — judgment** | Did the produced `ground-truth.md` flag the contradiction, avoid the hallucination, apply code-wins, mark unshipped work Proposed, cite truthfully? | LLM-judged (claim-support) | No (needs a model) |

Tier A proves the model was *given* what it needs and that fabrication is *detectable*. Tier B grades
whether it reasoned correctly.

## Files

- `dataset.json` — 32 scenarios. 23 test the reconcile→ground-truth path across every resolver/store
  class (project-encoded, date-bucketed, Cursor encoded-dir, Gemini basename, opencode message-dir,
  Goose file-jsonl, fuzzy path-mention, Aider file, Crush database, unknown-store). 6 test the
  decision-library half of the workflow: `decision-supersession-lookup-{5,25,100,250}` (a
  **size-parameterized** family that seeds an N-ADR library with a buried needle + near-miss
  distractor, to measure judgment drift with library size), `decision-already-recorded` (dedup), and
  `incremental-ground-truth-merge` (update a prior doc in place). **3 are the v2 hard suite**
  (`silent-revert-refactor`, `semantic-evasion-cache`, `release-gate-composite`) — built to break the
  grep-and-pattern-match strategy that lets a tool-enabled SoTA solver ceiling the base suite; see
  `HARD-SUITE.md`. Each has a solver-visible `prompt` and a `judge_only` block (gold claims + rubric).
  **`judge_only` is never written to a fixture and never given to the solver.** See `RESULTS.md` and
  `REVIEW-ablation.md` for runs; `HARD-SUITE.md` for the difficulty contract.
- `fixtures.py` — one builder per scenario: writes a synthetic `$HOME` (multi-agent transcript stores
  in their real on-disk shapes) + a project checkout with real code/docs and best-effort git history.
  Returns the planted facts (expected sessions, anchors, markers, banned tokens).
- `run_evals.py` — Tier-A runner: builds each fixture, runs `collect.py`, executes the substrate
  checks + leakage linter, and (with `--emit-bundle`) writes judge-ready Tier-B bundles.
- `judge_prompt.md` — the reference Tier-B judge protocol (claim extraction → classification →
  claim-support verification → structured JSON verdict). Resists keyword-gaming and confident hedges.
- `report.py` — pure-stdlib renderer: turns one or more `rosetta-eval-results/v1` JSON files into a
  visual report — a computed **CALIBRATED: YES/NO/UNKNOWN** verdict (applies CALIBRATION.md's gates),
  scorecard with per-run scoring provenance, scenario×run matrix, drift curve (Tier-A excluded),
  discrimination panel, and a **cost-efficiency** panel (`REPORT.md` + optional `REPORT.html`).
- `pricing.json` — versioned price sheet (USD per 1M tokens). The cost panel computes `$/pass` from it
  when a run carries an input/output token split, so rates never get hardcoded into `report.py`.
- **Product-value dimension** (`VALUE.md`): runs carry `tokens` + tags (`model_tier`, `condition`,
  `scenario_set`). The report's **Product value** panel proves value is multi-dimensional — (1)
  correctness, (2) correctness at token savings, (3) bringing SoTA correctness to a cheaper/distilled
  model. **$/correct** = cost per *passed* scenario, **withheld below an 80% efficacy gate** so "cheap
  but wrong" can't look good; $ comes from the versioned `pricing.json` (blended estimate from totals,
  exact when an input/output split is present). Measured result: Haiku + Rosetta matches the Opus
  baseline's correctness on the hard suite at ~24× lower est cost (see `VALUE.md`). Metric design
  hardened against Codex/Gemini red-team review. A full **14-model cross-harness sweep** (Claude,
  Codex, Gemini, Droid) is in `SWEEP.md` + `results-tierb-sweep.json`, with model IDs probed live and
  prices verified against the 2026-06 sheet.

## Reporting

```bash
# 1. emit the deterministic Tier-A results
python3 run_evals.py --report results-tier-a.json
# 2. render the report (merge Tier-A with any Tier-B / multi-model result files)
python3 report.py results-tier-a.json results-tierb-opus.json --out REPORT.md --html REPORT.html
```

`REPORT.md` + `REPORT.drift.svg` are committed as a rendered example (dark theme; the SVG carries its
own dark background so it reads correctly on GitHub too). The drift curve plots pass-rate vs
decision-library size (one series per model tier); with multiple tiers it shows where judgment bends
(the discrimination signal). `results-tierb-{opus,sonnet,haiku}.json` and `results-detail-opus.json`
are captured Tier-B runs; `results-tier-a.json` and `REPORT.html` are regenerable build artifacts
(gitignored).

**Per-test detail.** A results file may carry, per scenario, `expected` (from the gold), `actual` (the
solver's output excerpt or its `rosetta-verdict` block), and `judge: {decision, reasoning}` (the
LLM-as-judge's trace). When present, `report.py` renders a **Per-test detail** section — each test with
its expected result, the model's actual result, and the judge's decision + reasoning trace
(collapsible in the HTML dashboard). `results-detail-opus.json` is a captured example over six
representative scenarios (real solver→independent-judge run).

## Running

```bash
# Tier A — all scenarios (also runs in CI via unittest)
python3 run_evals.py
python3 run_evals.py --scenario contradiction-code-resolved      # one scenario

# Emit Tier-B judge bundles (contain gold — judge-only, never give to the solver)
python3 run_evals.py --emit-bundle /tmp/rosetta-bundles

# Materialize one fixture to inspect on disk
python3 fixtures.py build_contradiction_code_resolved /tmp/inspect-home
```

Tier A is pure stdlib. Scenarios whose gold depends on git carry `requires_git` and are **skipped
loudly** (never silently downgraded) when `git` is unavailable.

## Running Tier B (judgment)

1. `python3 run_evals.py --emit-bundle <dir>` — one folder per scenario with `prompt.txt`, the
   normalized corpus, a `project/` code snapshot, `manifest.json`, `git-log.txt`, `anchors.json`, and
   `gold.json`.
2. Have the **solver** (a Rosetta run under test) produce `ground-truth.md` from only the `prompt` +
   the fixture `$HOME` + the project checkout — *not* the bundle (the bundle contains gold).
3. Grade the output. **Deterministic-scoring-first (default for scorable scenarios):** run `score.py`
   FIRST; only fall back to the LLM judge when it can't score deterministically. This is the H2 lever
   from `TOKEN-REDUCTION-HYPOTHESES.md` — a scorable scenario costs **zero judge tokens**:

   ```bash
   # default grading path: try the deterministic scorer first
   python3 score.py --scenario decision-supersession-lookup-100 --solver-output ground-truth.md
   # exit 0 = pass, 1 = fail (judge-independent), 2 = scorable:false → route to the LLM judge below
   ```

   `score.py` is authoritative when the solver emits a ```` ```rosetta-verdict {…}``` ```` block (it
   re-derives the needle/near-miss from the deterministic fixture and checks the block exactly — no
   prose parsing, no model call). The scorable set is `score.SCORERS` (the decision-supersession-*
   and decision-already-recorded families). On `scorable: false` (exit 2), and for all free-form
   scenarios, fall through to:
4. Have a **judge** model grade the output using `judge_prompt.md` against `gold.json`, returning the
   structured verdict. The solver and judge must be isolated; the judge sees gold, the solver never.

See `GOAL3-TOKEN-REDUCTION-RESULTS.md` for the measured before/after token accounting of this path
(`measure_tokens.py` is the harness).

## Adding a scenario

1. Write a `build_<name>(home)` in `fixtures.py` returning the planted manifest. Keep transcripts as
   natural dev chatter — **no anti-pattern labels, resolution slogans, or rubric phrasing on disk**.
2. Register it in `REGISTRY`.
3. Add a `dataset.json` entry: `id`, `anti_pattern`, `fixture`, solver-visible `prompt`, and the
   `judge_only` gold + rubric. List the leak-guard tokens in the fixture's `banned_in_fixture`.
4. `python3 run_evals.py --scenario <id>` until Tier A is green (the leakage linter will catch any
   gold that slipped onto disk).
