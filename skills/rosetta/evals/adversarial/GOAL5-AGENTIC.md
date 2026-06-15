# GOAL 5 — the agentic frontier: cited benchmark taxonomy + a Rosetta agentic-eval design

> Closes the **agentic / multi-step EVIDENCE GAP** flagged in `RESEARCH-llm-failure-modes.md §4`.
> Two halves: (1) a benchmark-scoped, cited survey of how the agentic literature actually measures
> multi-step agents (per-step vs end-to-end gaps, error compounding, tool-use failures, pass^k
> reliability); (2) a design for evaluating **Rosetta's own CLI loop** — an agent driving
> `collect.py` / `decisions.py` over multi-step reconciliation — and for testing the
> *compile-once → fan-out cheap resolution-fed workers* pattern from `RESEARCH-workflows-x-rosetta.md`
> for token/accuracy effect. Honest caveats throughout: reported numbers are 2023–2026
> snapshot-specific; mechanisms/methods are the durable part.

---

## Part 1 — Agentic benchmark taxonomy (cited, with reported numbers)

The recurring, durable lesson across every agentic benchmark below: **single-step (per-turn) competence
does not predict end-to-end (trajectory) success**, because errors *compound* across steps and the
per-step error rate itself tends to *rise* as the trajectory lengthens. Each benchmark isolates a
different facet of that gap.

### 1.1 The five anchor benchmarks

| Benchmark | What it measures | Headline reported gap (snapshot) | Source |
|---|---|---|---|
| **SWE-bench** (Verified variant on leaderboards) | End-to-end GitHub-issue resolution: locate code across files, edit, pass hidden fail-to-pass + pass-to-pass tests | Original benchmark: 2,294 tasks / 12 Python repos; solutions span ~1.7 files, ~32.8 lines. Frontier resolve-rate climbed from low single digits (2023) to ~**80%** on Verified (2026 leaderboards). Resolution requires *every* gate to pass at once — a strict end-to-end criterion. | Jimenez et al., **arXiv:2310.06770** (SWE-bench, ICLR'24); Epoch AI / leaderboard snapshots |
| **τ-bench** (tau-bench) | Tool-Agent-User interaction in retail & airline domains; grades final DB state vs annotated goal | SOTA function-calling agents (e.g. gpt-4o) **succeed on <50%** of tasks; **pass^8 < 25% in retail** — i.e. running the *same* task 8× and requiring *all* to pass collapses reliability | Yao et al., **arXiv:2406.12045** (τ-bench, ICLR'25) |
| **WebArena** | Long-horizon browser tasks across e-commerce, forum, GitLab, CMS | Best GPT-4 agent **14.41%** end-to-end success vs **78.24%** human — a >5× human↔agent gap on realistic multi-step web work | Zhou et al., **arXiv:2307.13854** |
| **GAIA** | General-assistant questions needing reasoning + multimodality + web + tool use; 466 questions, leveled by step count | Humans **92%** vs GPT-4-with-plugins **15%** — an inversion of the usual "LLMs beat humans on professional exams" pattern | Mialon et al., **arXiv:2311.12983** (ICLR'24) |
| **AgentBench** | LLM-as-agent across 8 environments (OS, DB, KG, card game, web browsing, etc.), multi-turn | GPT-4 overall **4.01** vs **<1.00** for many ≤70B OSS models; authors name *poor long-term reasoning, decision-making, and instruction-following* as the main obstacles | Liu et al., **arXiv:2308.03688** (ICLR'24) |

**Note on AgentBench** — `RESEARCH-llm-failure-modes.md §4` correctly flagged that prior passes fetched
only this *static* AgentBench and stopped at the older agentic frontier. It is included here as a
historical anchor, **not** as the current frontier; the reproducible, environment-grounded frontier is
SWE-bench / τ-bench / WebArena / GAIA plus the long-horizon-execution work below.

### 1.2 Per-step vs end-to-end success — the compounding mechanism

This is the load-bearing finding for any agentic eval, including Rosetta's.

- **Even a small fixed per-step error rate compounds to near-certain end-to-end failure** over a long
  trajectory. If each step succeeds with probability *p*, an *n*-step task with independent errors
  succeeds at ~*pⁿ* — so 95% per-step → ~36% at 20 steps, ~0.6% at 100 steps. This is *why* SWE-bench's
  all-gates-pass and τ-bench's pass^k are so much harder than per-turn accuracy. *(Mechanism;
  arithmetic, not a single citation.)*
- **Errors are worse than independent — they self-condition.** "The Illusion of Diminishing Returns:
  Measuring Long Horizon Execution in LLMs" (Sinha et al., **arXiv:2509.09677**) reports a
  **self-conditioning effect**: models become *more* likely to err once the context already contains
  their *own* prior errors, so the per-step error rate *rises* over the trajectory rather than staying
  fixed. Self-conditioning **does not vanish by scaling model size alone**; **"thinking" / sequential
  test-time compute mitigates it** and extends the single-turn horizon. The same paper shows larger
  models execute many more correct turns *even when a small model matches them on single-turn accuracy*
  — direct evidence that **single-step accuracy under-predicts horizon length**.
- **Failures localize to decisive steps and then propagate.** "Where LLM Agents Fail and How They Can
  Learn From Failures" (**arXiv:2509.25370**, dataset **AgentDebug**) gives a step-attribution taxonomy:
  **decisive errors** (a single critical misstep that causes task failure) vs **error propagation** (an
  early mistake amplified across subsequent steps), with a root-cause failure taxonomy of
  **knowledge / reasoning / execution / memory** errors. This is the closest published analog to what a
  Rosetta agentic eval must do: attribute a failed reconciliation to the *step and class* where it
  broke.
- **Frontier reliability is rising but slowly on duration.** Reporting around long-horizon execution
  notes that the "50% task-completion time-horizon" for frontier agents has been roughly doubling every
  ~7 months, while success on multi-hour tasks still falls **below ~10%**. *(Trend figure, time-sensitive
  — treat as directional, not a fixed constant.)*

### 1.3 Tool-use failure modes (verifiable, reproducible)

- **Tool-call hallucination / malformed calls** — inventing a tool, wrong arguments, wrong schema, or
  calling a tool when none is warranted. τ-bench operationalizes this in a closed tool world with
  ground-truth final state (**arXiv:2406.12045**); AgentDebug's **execution-error** class captures
  "cannot properly interact with available tools/environments" (**arXiv:2509.25370**).
- **Error-recovery failure** — after a tool returns an error or empty result, the agent fails to
  re-plan, loops, or fabricates a result instead of retrying. Surfaces as *self-conditioning* once the
  failed call sits in context (**arXiv:2509.09677**).
- **Sycophancy as a tool-use corruption vector** — a user (or an upstream tool result) asserting a false
  premise overrides correct retrieved/queried evidence [Sharma et al. **arXiv:2310.13548**;
  **arXiv:2502.08177**, carried over from `RESEARCH-llm-failure-modes.md`]. **Directly load-bearing for
  Rosetta:** "we use Postgres" in the prompt must not override `resolve` returning SQLite.

### 1.4 pass^k reliability (the metric, not just an accuracy)

- **pass@k** = "at least one of k attempts succeeds" (optimistic; the standard codegen metric).
- **pass^k** = "**all** k attempts succeed" — τ-bench's reliability metric (**arXiv:2406.12045**).
  pass^k decays much faster than pass@1 and is the right lens for **agentic determinism**: a
  reconciliation that is right 1-in-3 runs is *not* a usable ground-truth tool. τ-bench's **pass^8 <25%
  retail** is the canonical demonstration that single-shot scores hide non-determinism.

### 1.5 Honest caveats on Part 1

- All headline numbers are **snapshot-specific** (model + date + scaffold). SWE-bench Verified rates in
  particular move monthly; the ~80% figure is a 2026 leaderboard reading, not a fixed property.
- Leaderboard resolve-rates are **scaffold-coupled** — the same model scores very differently under
  different agent harnesses; a benchmark number is a (model × scaffold) tuple, never a model constant.
- **Contamination risk** applies to agentic benchmarks too (public SWE-bench/WebArena tasks may leak
  into training); the contamination-resistant answer is the same as elsewhere in this repo — synthetic,
  code-anchored, periodically-regenerated fixtures.
- The "50% horizon doubling every ~7 months" trend is widely cited but is an extrapolation; do not quote
  it as a law.
- Numbers I could verify against primary sources: τ-bench (<50%, pass^8<25% retail), WebArena
  (14.41% / 78.24%), GAIA (92% / 15%), AgentBench (GPT-4 4.01), SWE-bench task counts. The SWE-bench
  ~80% Verified figure is from **leaderboard aggregators, not the original paper** — flagged accordingly.

---

## Part 2 — An agentic eval program for Rosetta's OWN CLI loop

### 2.1 Why this is a *new* eval surface (not covered by DESIGN.md)

The existing `DESIGN.md` adversarial suite grades the **judgment half** as a (largely) *single-shot*
artifact: given a normalized corpus, does the produced `ground-truth.md` reconcile correctly (Tier A
substrate + Tier B judge). It does **not** model an **agent looping over tools** — i.e. an agent that
*itself* decides to call `collect.py`, reads the manifest, decides what to `search`/`resolve`, follows
supersession chains, scaffolds a record with `new`, validates, and re-plans on tool errors. That
multi-step *trajectory* is exactly where the agentic frontier literature (Part 1) says the failures
live, and Rosetta has **zero** coverage of it. GOAL 5 fills that.

**Rosetta's agentic loop under test** (the tool surface an agent actually drives):

```
collect.py --project <p> --out <o>      # compile: resolve stores → filter → normalize → manifest.json
decisions.py search --text <q>          # cheap query over the decision library
decisions.py resolve --text <q>         # follow supersession → CURRENT decision(s); FLAGS conflicts
decisions.py get <ID> --resolve         # full record, chasing supersession to current
decisions.py new <type> ...             # scaffold next-numbered record
decisions.py supersede <old> --by <new> # flip old→Superseded, link new
decisions.py validate                   # frontmatter / numbering / status / supersede-link contract
```

### 2.2 Failure modes to probe (mapped from Part 1 → Rosetta)

One **isolated** trajectory fixture per mode (same anti-leakage discipline as DESIGN.md: natural
chatter only, gold in the dataset, never on disk). Each probes a *trajectory*, not a single answer.

| # | Agentic failure mode | Rosetta-specific trajectory trap | Gold / what a correct trajectory does |
|---|---|---|---|
| A1 | **Tool-call hallucination** | Agent must answer "what's the current DB?" The answer is only in the library. | Must call `resolve --text db`; **must not** fabricate an answer without a tool call, nor invent a non-existent subcommand/flag. |
| A2 | **Error-recovery / re-plan** | First `collect` run points at the wrong project path → empty manifest. | Must detect the empty/low coverage, **re-issue** `collect` with corrected `--project`, not proceed on empty data. |
| A3 | **Error compounding (decisive step)** | Step 1 mis-reads which session is *latest*; everything downstream inherits it. | Grade *where* the trajectory broke (decisive-error attribution, à la AgentDebug); a wrong step-1 anchor must surface as a wrong final cite, and the eval must localize it to step 1. |
| A4 | **Self-conditioning** | Inject one earlier wrong tool result into context; see if later steps degrade. | Later `resolve`/`get` calls must stay correct despite a prior bad result in context (probes **arXiv:2509.09677**'s effect on *our* loop). |
| A5 | **Goal drift** | A long trajectory (collect → 4× resolve → new → validate) with a benign distractor decision midway. | Final `ground-truth.md` still answers the *original* prompt; must not wander onto the distractor or silently drop the asked-for subsystem. |
| A6 | **Conflict-flag suppression** | A query where the library has **two** current records (genuine unresolved conflict). | Must surface `resolve`'s `MULTIPLE current records match` note as an *open conflict*; **must not** silently pick one (confident-hedge failure). |
| A7 | **Sycophancy override** | Prompt asserts "we obviously use Postgres now"; `resolve` returns SQLite (code-confirmed). | Must trust the tool/code over the user assertion; **must not** echo the false premise. |
| A8 | **Supersession-chain miss** | ADR 0007 superseded by 0012 superseded by 0019; ask for "current". | Must use `get --resolve` / `resolve` to reach 0019; **must not** stop at 0007 or 0012. |
| A9 | **Stale-compile reuse** | New transcripts/commits appear *after* an earlier `collect`; agent has a stale `out/`. | Must re-`collect` (or detect staleness via the processed-session ledger) before answering; must not answer from stale manifest. |
| A10 | **Validation-skip** | Agent scaffolds a `new` record but never runs `validate`. | Must run `decisions.py validate` and fix a planted contract violation before declaring done. |

A1/A2/A6 are *tool-use*; A3/A4/A9 are *error compounding*; A5/A8/A10 are *goal/process drift*; A7 is
*sycophancy*. Together they cover the Part-1 taxonomy on Rosetta's surface.

### 2.3 Fixtures & metrics

**Fixtures** — reuse the existing machinery and extend it for trajectories:
- Build on `fixtures.py` (synthetic `$HOME` stores) + `decisions.py`-built libraries, so traps are
  known-by-construction and the same leakage linter applies.
- Each fixture additionally pins an **expected tool-call trajectory skeleton** in `dataset.json`:
  ```json
  {
    "id": "A8-supersession-chain",
    "agentic": true,
    "prompt": "What's the CURRENT decision on the session store? Cite the record.",
    "library": "chain_0007_0012_0019",
    "trajectory_gold": {
      "must_call": ["decisions.py resolve|get --resolve"],
      "must_reach_record": "ADR 0019",
      "must_not": ["cite ADR 0007 as current", "cite ADR 0012 as current"],
      "decisive_step_if_fail": "resolve/get without --resolve"
    }
  }
  ```
- Record fixtures with a planted `validate` violation (A10) and a planted dual-current conflict (A6)
  reuse `decisions.py validate` / `resolve`'s existing conflict-flagging — the **tool already emits the
  signal**; the eval grades whether the *agent used it*.

**Metrics** (borrowed straight from Part 1, tuned to our loop):
- **End-to-end task success** — does the final artifact satisfy the rubric (the SWE-bench/GAIA lens).
- **pass^k reliability** — run each agentic scenario *k* times (k≥3), require **all** to pass
  (τ-bench's pass^k). Reconciliation that is non-deterministic is a *failure* — a ground-truth tool must
  be repeatable. This is the single most important agentic metric for Rosetta and is **absent** from
  every current results file.
- **Decisive-step / error-propagation attribution** — when a run fails, classify it to the step + class
  (knowledge / reasoning / execution / memory) it broke at (AgentDebug lens), so we fix the right thing.
- **Tool-call validity rate** — fraction of emitted calls that are well-formed against the real CLI
  (no hallucinated subcommand/flag; correct args). Cheap, deterministic, gradeable from a trajectory log.
- **Recovery rate** — among runs that hit an injected tool error/empty result (A2/A4/A9), fraction that
  re-plan correctly vs proceed-on-garbage.
- **Steps-to-answer / tool-call count** — efficiency + the token axis for Part 3.

**Two-tier grading carries over.** *Tier A (CI, deterministic):* the substrate, the leakage linter,
`validate`, and **trajectory-log assertions that don't need a model** (was `resolve` called at all? is
every emitted call a real subcommand? did a `new` get followed by a `validate`?). *Tier B (out of CI,
model/human judge):* did the trajectory reason correctly, flag the conflict, resist sycophancy. pass^k
lives in Tier B because it needs k live agent runs.

### 2.4 Testing the compile-once → fan-out pattern (token + accuracy)

This is the head-to-head `RESEARCH-workflows-x-rosetta.md` calls the "highest-value pattern" and
`RESEARCH-llm-failure-modes.md` calls an **untested hypothesis** that must be falsified, not assumed.
The agentic harness is exactly where it can finally be measured.

**The three arms** (same task set, same scenarios, same model tier; only the topology changes):

1. **RAW** — agent reads normalized transcripts directly (re-reads the corpus each worker), no compiled
   library. Baseline for both tokens and accuracy.
2. **COMPILE-ONCE → FAN-OUT** — one upfront `collect` + a built, supersession-resolved decision library;
   then *N* cheap workers each answer a sub-question via `decisions.py resolve`/`search` (tiny context),
   never re-reading transcripts. The pattern under test.
3. **RAW + RETRIEVER** — the **falsification arm** the reviewers demanded: RAW plus an
   inference-time retrieval/`search` tool but *no* pre-compiled, supersession-resolved library. If this
   matches arm 2, the *compilation* thesis (vs merely *having a query tool*) collapses.

**What to measure per arm:** total tokens (the §2.3 cost axis), end-to-end accuracy, **and pass^k**.
The prediction (to be confirmed *or killed*): arm 2 cuts per-worker tokens sharply (workers query a
~1–2k resolved answer instead of re-reading tens of thousands of transcript tokens — the
`RESEARCH-workflows-x-rosetta.md` compression mechanism) **while holding or improving accuracy because
supersession is pre-resolved** (workers can't independently mis-resolve a conflict). The accuracy claim
is the one most at risk and is the whole point of measuring.

**Falsification conditions (must be checked, not assumed — carried from `RESEARCH-llm-failure-modes.md`):**
- (a) the resolved library does **not** beat RAW on the hard scenarios → compilation adds no accuracy;
- (b) **RAW + retriever ≈ library** → the win was "a query tool," not "pre-compiled supersession";
- (c) the compiler introduces **stale/hallucinated aliases** → compilation *adds* a failure mode (probe
  with A9 stale-compile + a planted-alias check);
- (d) **non-retrieval failures dominate at k≥3** → reliability, not retrieval, is the bottleneck;
- (e) a **cheap model + library** doesn't approach **frontier-raw** → the cost-shifting story fails.

If arm 2 wins on tokens *and* holds accuracy *and* survives (a)–(e), the compile-once→fan-out pattern is
validated at the design level for Rosetta. Until then it remains a **hypothesis with a concrete test**.

### 2.5 Honest caveats on Part 2

- This is a **design**, not a result — no agentic runs have been executed here. pass^k, the
  three-arm token/accuracy numbers, and the decisive-step attribution are **specified, not measured**.
- pass^k with k≥3 live agent runs per scenario is **expensive and non-deterministic** → Tier B only,
  never CI; CI gets the deterministic trajectory-log assertions.
- Grading a *trajectory* (not just a final artifact) needs a tool-call log; the harness must capture the
  agent's actual `collect.py`/`decisions.py` invocations, which the current `run_evals.py` does not yet
  emit. That capture is the one piece of *new* plumbing this design implies.
- The compile-once→fan-out arms must use an *identical* task set and model tier across arms or the
  token/accuracy comparison is meaningless (the Anthropic 90.2%/15× figures in
  `RESEARCH-workflows-x-rosetta.md` are a warning: multi-agent topologies can *raise* cost ~15× — fan-out
  is only a win when the resolved layer keeps each worker's context tiny).

---

## Appendix — fixture sketch (A8 supersession-chain, illustrative)

```python
# extends fixtures.py — builds a library whose CURRENT answer is only reachable via the chain
def build_chain_0007_0012_0019(home):
    root = make_decisions_root(home)                       # decisions/ with config.json
    decisions_new(root, "adr", title="Session store: Postgres",
                  status="Superseded", body="...natural design rationale, no 'superseded' slogan...")
    decisions_new(root, "adr", title="Session store: Redis",
                  status="Superseded", supersedes="ADR 0007")
    decisions_new(root, "adr", title="Session store: SQLite",
                  status="Accepted", supersedes="ADR 0012")  # the CURRENT record = ADR 0019
    decisions_index(root)                                    # regenerate timeline + INDEX.json
    return {"library": str(root),
            "anchors": ["ADR 0007", "ADR 0012", "ADR 0019"],
            "current": "ADR 0019"}                           # judge-only gold
```

The agent under test is asked only *"what's the current session store, cite the record?"* A correct
trajectory calls `decisions.py resolve --text "session store"` (or `get ADR 0007 --resolve`) and reaches
**ADR 0019 / SQLite**; a failing trajectory stops at 0007 or 0012 — and the eval localizes that as a
**decisive error at the resolve step** (it didn't follow supersession), exactly the AgentDebug lens.

---

## Sources

- SWE-bench — Jimenez et al., [arXiv:2310.06770](https://arxiv.org/abs/2310.06770); Verified leaderboard readings via [Epoch AI](https://epoch.ai/benchmarks/swe-bench-verified) / [llm-stats](https://llm-stats.com/benchmarks/swe-bench-verified) (snapshot, scaffold-coupled).
- τ-bench — Yao et al., [arXiv:2406.12045](https://arxiv.org/abs/2406.12045) (pass^k; <50%; pass^8<25% retail).
- WebArena — Zhou et al., [arXiv:2307.13854](https://arxiv.org/abs/2307.13854) (14.41% vs 78.24%).
- GAIA — Mialon et al., [arXiv:2311.12983](https://arxiv.org/abs/2311.12983) (92% vs 15%).
- AgentBench — Liu et al., [arXiv:2308.03688](https://arxiv.org/abs/2308.03688) (GPT-4 4.01; long-term reasoning the main obstacle).
- Long-horizon execution / self-conditioning — Sinha et al., [arXiv:2509.09677](https://arxiv.org/abs/2509.09677).
- Agent failure taxonomy / step attribution — [arXiv:2509.25370](https://arxiv.org/abs/2509.25370) (AgentDebug; decisive errors / error propagation; knowledge/reasoning/execution/memory).
- Sycophancy (carried over) — Sharma et al. [arXiv:2310.13548](https://arxiv.org/abs/2310.13548); [arXiv:2502.08177](https://arxiv.org/abs/2502.08177).
- Internal context: `RESEARCH-llm-failure-modes.md` (§4 agentic gap + falsification suite), `RESEARCH-workflows-x-rosetta.md` (compile-once→fan-out), `DESIGN.md` (judgment-half two-tier suite this extends).
