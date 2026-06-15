# Rosetta — phased roadmap for evals + product (post adversarial review)

**Reframe forced by the Codex+Gemini reviews:** our headline ("retrieval-defeat breaks models; Rosetta's
compiled library is the antidote") is a **hypothesis on n=1 fixtures**, not a result — and it is
**falsifiable** by inference-time tooling (a `resolve_codename`/glossary tool, or a better retriever)
matching the compiled folder with no pre-compilation. So Phase 0 is *prove-or-kill*, cheaply, before
building. Every phase has an **Eval track** and a **Product track**; each ends in a **decision gate**.

Guiding principles: (1) label hypotheses as hypotheses; (2) **k≥3** before quoting any number;
(3) the compiler is itself an LLM step → **code/git-anchor everything or it just moves hallucination
upstream**; (4) lead the pitch with **cost-down** (durable) over the correctness gap (frontier-sensitive);
(5) synthetic, code-anchored, periodically-regenerated fixtures (contamination-resistant by construction).

---

## Phase 0 — De-risk the thesis (≈1–2 weeks). Cheap, decisive.

**Question:** does pre-compilation actually beat the cheaper inference-time alternatives?

**Eval track**
- Re-run the v5/v6 breakers at **k≥3** to confirm the breaks are real (not n=1 noise). Report pass-rate, not pass/fail.
- Build the **4-arm head-to-head** on the same breaker fixtures × {Haiku, Sonnet, Gemini-Flash}:
  1. raw (base)  2. raw + inference-time `resolve_codename`/glossary tool  3. raw + a stronger retriever (embeddings/alias-expansion)  4. **Rosetta normalized compiled folder**.
  Measure correctness **and** $/correct for each arm.
- Run **Codex's falsification checklist** explicitly: (a) folder doesn't beat raw on v5/v6; (b) raw+retriever ≈ folder; (c) compiler emits stale/hallucinated aliases; (d) non-retrieval failures dominate at k≥3; (e) cheap+folder doesn't approach frontier-raw.

**Product track**
- Build a *minimal* normalizing compiler (decode codenames → queryable titles, resolve supersession into `Status:`/`Supersedes`, code-anchor) — only enough to run arm 4.
- Build a *minimal* `resolve_codename`/glossary lookup tool — to run arm 2.

**Decision gate.** If the compiled folder clearly wins on correctness **and** $/correct → build it for real (Phase 1). If inference-time tooling matches it → **pivot**: ship the glossary/retriever tooling (cheaper, no compile/freshness burden) and reposition compilation as an *optimization*, not the core value. Either outcome is a win; we stop guessing.

---

## Phase 1 — Build the winner + make it durable (≈2–6 weeks)

**Product track**
- Build out whichever arm won (likely a **hybrid**: compiler emits the normalized, supersession-resolved, code-anchored library *and* exposes a resolve/alias tool so a cheap model gets the multi-hop for free).
- **Freshness / drift guard** (evidence-backed by the drift research — silent updates, code moving past an ADR): `decisions validate --staleness` flags ADRs whose cited code/commit moved; re-`collect` deltas; auto-`supersede` on contradiction. *Without this the folder becomes a confidently-wrong oracle — worse than raw.*
- **CLI ergonomics:** alias-aware, status-filtered `search`; `get --resolve` follows supersedes to the live record.

**Eval track**
- **Drift evals:** pinned regression suite + exact-match-over-time; a scenario where code moved past an ADR (library must flag/supersede, not serve stale); borrow the cheap logprob/exact-match drift detectors.
- **Multi-document / conflicting-context** scenario — Rosetta's *core* problem space, missing until the review flagged it: contradictory sources with no explicit supersession → must reconcile via code-wins.

**Decision gate.** Freshness guard catches a planted stale-ADR regression; compiler passes `decisions validate` with zero hallucinated aliases (code-anchored).

---

## Phase 2 — Broaden eval coverage to the real failure surface (≈4–8 weeks)

**Eval track** — add the failure modes the review named as missing, each as a code-anchored archetype:
- **Sycophancy** — user asserts a false premise ("we use X") vs. correct retrieved/code evidence; Rosetta must hold code-wins. [Sharma 2310.13548; Perez 2308.03958]
- **Tokenization/counting** — real char/exact-count tasks (our A3 "counting passes" ignored BPE-level failure). [2405.17067]
- **Order/position bias** beyond lost-in-middle [2401.01989]; **RAG retrieval-vs-generation decomposition** [RAGAS 2309.15217 + ARES 2311.09476]; (optionally) jailbreak/safety-drift, multilingual, repetition.
- Keep the **negative/ceiling archetypes** (the ones models pass) so the suite proves it isn't "everything is hard."
- **Calibration as a living gate:** `CALIBRATED: YES/NO` + the product-value (correctness / $-savings / SoTA-on-cheap) panel run per model tier on every change; **k≥3** mandatory; Tier-A in CI, Tier-B scheduled.

**Product track**
- Harden the compiler against these modes (sycophancy → code-wins over user assertion; conflict → explicit supersession + provenance).

**Decision gate.** Suite discriminates ≥1/4 of co-tested scenarios across tiers (CALIBRATION.md gate); cost panel shows the cheap-model+folder value holds at k≥3.

---

## Phase 3 — Agentic coverage + scale (≈8+ weeks)

**Research:** the benchmark-scoped agentic pass the synthesis still lacks — SWE-bench, WebArena (<15% end-to-end), τ-bench, GAIA; per-step-vs-end-to-end gap, pass^k.

**Eval track:** agentic eval program for the Rosetta CLI agent loop itself — tool-use errors on `collect`/`decisions`, error-compounding over multi-step reconciliation, pass^k reliability.

**Product track:** scale to large **real** multi-agent-store decision libraries; ship the **cost/value dashboard** as the live, customer-facing proof artifact (per-tier correctness + $/correct, refreshed to fight contamination/drift).

**Decision gate.** Agentic suite reproduces a known per-step→end-to-end compounding gap; dashboard runs on a real repo, not just synthetic fixtures.

---

## Success metrics (what "better" means)
- **Evals:** discriminates by tier (not flat 100%); covers ≥8 failure modes incl. the review's additions; every headline number is k≥3 with the CALIBRATED gate; contamination-resistant (regenerated).
- **Product:** on the head-to-head, the shipped approach delivers SoTA-level correctness on a cheaper model at lower $/correct than raw; freshness guard prevents stale-oracle regressions; value proven on a real library.

## Risks (carried from the reviews)
- **Inference-time tooling cannibalizes compilation** — *the* strategic risk; Phase 0 exists to face it head-on.
- **Compiler-as-LLM** hallucinates aliases/normalizations — must be code-anchored + validated.
- **Frontier models keep improving** → correctness gap shrinks; cost-down is the durable value.
- **Stale libraries** are worse than none → freshness is mandatory, not optional.
- **n=1** everywhere today → k≥3 gates every quoted result.
