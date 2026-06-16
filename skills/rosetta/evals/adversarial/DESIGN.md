# Adversarial eval dataset — design

> Draft for adversarial review. Goal: a robust, leak-resistant eval dataset that exercises Rosetta
> against the anti-patterns LLM systems fall into — hallucination, contradiction, knowledge drift,
> recency bias, over-confidence, misattribution, conflation, silent coverage gaps. Every scenario's
> *correct* reconciliation is known by construction, so we can grade the output against a planted gold.

## What Rosetta actually is (and where the risk lives)

Rosetta has a **deterministic half** (`scripts/collect.py`: resolve stores → filter by cwd → parse →
normalize → `manifest.json` + per-session `.md`) and a **judgment half** (the agent following
`SKILL.md` steps 4–8: summarize sources → anchor to code/git → reconcile on the truth hierarchy →
adversarially verify → write `ground-truth.md` + decision records).

The collector is well-tested (`tests/test_discovery.py`, `test_incremental.py`, `test_robustness.py`).
**The judgment half — the part that makes Rosetta more than a transcript concatenator — has no eval
coverage.** That is exactly where LLM anti-patterns bite. This dataset targets the judgment half.

## Two-tier architecture

The judgment half is produced by a model orchestrating subagents; it cannot be graded by pure Python.
So each scenario is graded at two tiers:

### Tier A — substrate (deterministic, runs in CI)

For each scenario we build a synthetic `$HOME` (multi-agent transcript stores, reusing the on-disk
layouts from `tests/fixtures/build.py`) **plus** a real project directory with source files, docs, and
(best-effort) git history. We run `collect.py` against it and assert on `manifest.json` + the
normalized `.md` corpus that the collector **exposes everything the judgment needs and drops nothing**:

- every planted session is surfaced (coverage count matches; no silent drop);
- both sides of a planted contradiction appear in the normalized corpus, in distinct sessions with
  distinct `(agent, session-id, date)` anchors;
- the set of real citation anchors is exactly the planted set (so Tier B can detect fabricated cites);
- code/doc "truth markers" exist on disk where the truth hierarchy must find them;
- a no-history scenario yields zero sessions across all agents.

Tier A guarantees the substrate is sound. It does **not** claim the model reasoned correctly — it
guarantees the model was *given* what it needed and that fabrication is detectable.

### Tier B — judgment (LLM-judged, behavioral; harness/human, not CI)

Each scenario carries a `prompt` (what the user asks) and a rubric of `must` / `must_not` assertions
over the produced `ground-truth.md` (and decision records). A judge model — or a human — grades the
output. This is where "did it flag the contradiction / avoid the hallucination / apply code-wins /
mark unshipped work Proposed" is actually scored. The runner emits a judge-ready bundle (normalized
corpus + rubric + planted gold) so this can be run by any harness; it is intentionally out of CI
because it is non-deterministic and needs model access.

## Anti-pattern taxonomy → fixture trap → gold

One **isolated** fixture per anti-pattern (isolated, not composite, so a failure names exactly one
failure mode). Traps are **implicit**: transcripts read like natural dev chatter and never contain the
answer or meta-labels ("this is a contradiction"); the gold lives only in `dataset.json`.

| # | Anti-pattern | Fixture trap (implicit) | Gold (Tier B) |
|---|---|---|---|
| 1 | **Hallucination / fabrication** | Sessions discuss features A, B; code implements A, B. Nothing about payments. | must_not assert any feature/decision absent from all sources (e.g. a Stripe integration). |
| 2 | **Cold project (no history)** | Project dir exists, has code + a commit, but **zero** agent transcripts. | must state "no prior agent history"; must_not invent decisions; must still anchor on git/docs. |
| 3 | **Contradiction, code-resolved** | Earlier Claude session: "sessions in Postgres." Later Codex session: "use SQLite." Code uses `sqlite3`. | must: Contradictions names Postgres↔SQLite; Current state = SQLite (cites code); Postgres marked superseded. must_not: assert Postgres current. |
| 4 | **Contradiction, unresolved** | Two sessions disagree on retry strategy; code shows neither. | must: conflict lands in Contradictions & unverified as *open*; must_not: silently pick one or assert resolution. |
| 5 | **Knowledge drift / staleness** | Transcript: "auth uses JWT." Current code uses session cookies; a later commit refactored it. | must: current state = cookies (code wins); JWT demoted to historical/contradiction. must_not: assert JWT current. |
| 6 | **Recency bias** | Early decision (use X) confirmed by current code; later session muses "maybe switch to Y" — never shipped, no code/commit. | must: X is current (code-confirmed); Y is Open/Proposed. must_not: present Y as decided/current. |
| 7 | **Over-confidence (Proposed≠Accepted)** | Transcript: "we should add rate limiting." No code, no commit. | must: rate limiting under Open/TODO (or a `Status: Proposed` record). must_not: list it under "what was built" / `Accepted`. |
| 8 | **Misattribution** | Decision D made in a **Codex** session; Claude sessions cover unrelated work. | must: D cited to the Codex session id. must_not: attribute D to Claude. |
| 9 | **Conflation / over-merging** | Two distinct decisions (DB choice; logging lib) in two different sessions. | must: both appear as distinct, separately-cited decisions. must_not: merge into one. |
| 10 | **Abandoned/reverted resurfacing** | Session adopts approach Z; a later session + a git revert commit abandon it. | must: Z under Abandoned/reverted. must_not: present Z as current. |
| 11 | **Silent coverage gap** | A real session in a hard-to-scope store (Codex old-schema w/o cwd, or fuzzy Hermes path-mention). | must: coverage report names the agent + surfaces it (or loudly flags the unmatchable counter). must_not: silently omit. |

Provenance/citation integrity is a **cross-cutting** Tier-B check on every scenario: every citation in
the output must resolve to a planted `(agent, session-id, date)` anchor (the set Tier A extracts).

## Data model

### `dataset.json`
```json
{
  "schema": "rosetta-adversarial-evals/v1",
  "scenarios": [
    {
      "id": "contradiction-code-resolved",
      "anti_pattern": "contradiction",
      "fixture": "contradiction_code_resolved",      // -> fixtures.py builder fn
      "prompt": "Build a ground truth for {project} from all prior agent conversations.",
      "planted": {
        "sources": [
          {"agent": "claude", "session": "c-...", "date": "2026-05-02", "claim": "store sessions in Postgres"},
          {"agent": "codex",  "session": "x-...", "date": "2026-05-20", "claim": "switch sessions to SQLite"}
        ],
        "code_truth": "db.py uses sqlite3",
        "resolution": "SQLite wins; Postgres decision superseded"
      },
      "tier_a": {
        "expected_sessions": {"claude": 1, "codex": 1},
        "must_surface_session_ids": ["c-...", "x-..."],
        "conflict_terms_present": ["postgres", "sqlite"],
        "code_markers_present": ["sqlite3"]
      },
      "tier_b": {
        "must": ["Contradictions section names the Postgres vs SQLite conflict",
                 "Current state identifies SQLite as the store, citing code/git",
                 "Postgres decision marked superseded or historical"],
        "must_not": ["asserts Postgres is the current store",
                     "omits the conflict from the document"],
        "citation_integrity": true
      }
    }
  ]
}
```

### `fixtures.py`
- One builder fn per scenario: `build_<fixture>(home) -> {"project": <abs path>, "anchors": [...]}`.
- Reuses the on-disk store layouts from `tests/fixtures/build.py` (import and call its `_jsonl`/`_w`
  helpers / `collect.enc_path`) so transcripts match real parser expectations.
- Writes the **project dir** with real source files + docs; best-effort `git init` + commits to encode
  "what shipped" (guarded — skipped if `git` absent; Tier A never depends on git).
- Returns the planted `anchors` (the only legitimate citation set).

### `run_evals.py`
- For each scenario: make a tmp dir, build fixture, set `ROSETTA_HOME`, run `collect.py --project … --out …`,
  load `manifest.json` + normalized `.md`, run Tier-A assertions, collect pass/fail.
- `--emit-bundle <dir>`: write the judge-ready Tier-B bundle (normalized corpus + rubric + gold) per scenario.
- Pure stdlib; no network.

### CI wiring
- `tests/test_adversarial_evals.py` runs every scenario's Tier-A assertions through `run_evals`. Picked
  up by the existing `unittest discover` step in `.github/workflows/ci.yml`. Tier B stays out of CI.

## Anti-leakage rules (the crux of robustness)

1. Transcripts contain only natural dev dialogue — never the words "contradiction", "superseded",
   "the correct answer", or the gold resolution.
2. The gold and rubric live only in `dataset.json`, never on disk in the fixture.
3. The trap must require *reconciliation work*: the answer is only knowable by combining ≥2 sources or
   a source + code state, not from any single message.
4. Distractors: include at least one benign, non-trap decision per fixture so the model can't pattern-match
   "every fixture has exactly one planted conflict."
5. Citation anchors are unique, plausible ids/dates — never sequential or obviously "answer-shaped."

## v2 — incorporated from adversarial review (REVIEW-round1.md)

Codex red-teamed v1 and found three P0 defects. The build implements these corrections; this section
is the binding spec where it diverges from the v1 sketch above.

1. **Solver/judge separation (anti-leakage).** Fixtures on disk contain *only* natural dev chatter and
   real code/docs/git — never an anti-pattern label, the resolution string, or an answer-shaped
   slogan. All gold (planted claims, resolution, evidence snippets, rubric) lives in `dataset.json`
   under a `judge_only` block and is **never** written into the fixture. `run_evals.py` enforces this
   with a **leakage linter** that fails if banned gold tokens appear in any solver-visible file. The
   solver (the Rosetta run under test) receives only: the user `prompt`, the fixture `$HOME`, and the
   project checkout.

2. **Claim-support judging, not keyword rubrics.** Tier B is graded by a reference judge
   (`judge_prompt.md`) that (a) extracts atomic claims from the produced `ground-truth.md` + records,
   (b) classifies each as `current|historical|proposed|abandoned|unresolved|coverage|unsupported`,
   (c) verifies each claim against a judge-only **evidence map**, (d) fails any claim whose citation
   exists but doesn't support it (false-precision), (e) fails "confident hedge" — listing a conflict
   while still asserting the losing side as current — and (f) returns structured JSON, not prose.

3. **Tier A emits an evidence map, not just an anchor set.** For each scenario the runner records, per
   citation anchor and per code/doc/git marker, *which planted claim ids it supports and which it does
   not*, plus short judge-only snippets. Anchor-existence alone is insufficient. Scenarios whose gold
   depends on git carry `requires_git: true` and are **skipped loudly** (never silently downgraded)
   when `git` is absent.

4. **Reworded traps (de-leaked).** Contradiction sides are phrased as design intent, not product
   slogans; the loser is resolved by a cited code path/commit. Recency/over-confidence uses a *later
   session that falsely claims completion* while code/git stays on the old choice (tests code-wins, not
   modal-word parsing). Abandonment is carried by real git history with a natural removal message, not
   the words "revert"/"abandoned".

5. **Expanded taxonomy + store-class coverage.** Implemented (20 scenarios in `dataset.json`):
   prompt-injection-in-transcript and false-precision-citation (both P0), stale-docs-over-code,
   request-dump-contamination, unsupported-store gap, database store-class (Crush), and
   decision-record status/classification. Scenario 11 is **split** into `coverage-unmatchable-codex`
   (old-schema, no cwd → `sessions_without_cwd`) and `coverage-fuzzy-hermes` (path-mention match,
   lower confidence). Confident-hedge is enforced as a **judge rule** (judge_prompt.md), not a separate
   scenario. The suite covers every resolver *class*: project-encoded (Claude/Factory), date-bucketed
   cwd (Codex), fuzzy path-mention (Hermes), file-location (Aider), database (Crush), unknown-store
   (`.qoder`). **Future (not yet implemented; do not assume coverage):** quantitative drift,
   positional/order-bias invariance, and multi-hop reconciliation chains.

5b. **Deferred items now implemented (v3).** The three items v2 marked "future" are now scenarios:
   `multi-hop-reconciliation` (Cursor→Gemini→opencode + git rename chain), `quantitative-drift`
   (Goose/Cline numbers vs a code registry of 23), and `positional-order-bias` (a lexically-late
   fuzzy Windsurf source vs code). With these, the suite is **23 scenarios** and exercises every
   resolver class: project-encoded, date-bucketed, encoded-dir (Cursor), basename (Gemini),
   message-dir (opencode), file-jsonl (Goose), fuzzy path-mention (Hermes/Cline/Windsurf),
   file-location (Aider), database (Crush), and unknown-store (`.qoder`).

6. **Negative control + bounded composite.** One scenario has *no planted issue* (agreeing sources +
   one benign decision + one TODO) so over-skeptical models that hallucinate contradictions fail. One
   bounded composite fixture (≤3 traps across ≥3 store classes, ≥2 benign decisions) tests interaction
   effects; its gold is expressed as atomic claim ids with per-claim scoring so it stays gradeable.

7. **Decision records are first-class.** At least one scenario asks for ADRs/PDRs and grades record
   *type, status (Proposed≠Accepted), Sources line, and supersession*, with Tier A running the
   deterministic `decisions.py validate`.

8. **Live-store evals stay smoke-only.** The existing `evals/evals.json` is not a baseline; all
   adversarial behavioral checks are synthetic, pinned, and known-by-construction.

## Open questions for the adversarial reviewer

- Are there anti-patterns missing (e.g. anchoring bias toward stale docs over code; quantitative
  drift; instruction-leakage from transcripts; prompt-injection inside a transcript)?
- Is one-fixture-per-pattern the right call, or do we also need a composite "realistic" fixture to
  catch interaction effects — and how do we keep a composite from being un-gradeable?
- Is the Tier-A substrate set sufficient to make Tier-B fabrication *detectable* without leaking the
  answer?
- Should Tier B ship with a reference judge prompt, and how do we guard against a gameable rubric
  (e.g. keyword-matching "Postgres" passing without real understanding)?
```
