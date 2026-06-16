# LLM failure & drift — cited research reference (two deep-research passes)

Synthesized from two adversarially-verified deep-research passes (each: fan-out search → fetch →
3-vote refute verification → cited synthesis). Pass 1 covered inference-time + retrieval/long-context;
pass 2 closed the model-drift gap. **Agentic/multi-step remains an evidence gap in both passes.** Every
claim below survived ≥2/3 reviewers failing to refute it; confidence + refuted claims are shown honestly.

The cross-cutting eval pattern: **isolate one variable in a fixture and pair it with a metric tuned to
the specific failure** (exact-match-retrieval vs task-accuracy; ECE; reliable@k; faithfulness =
supported-ratio; exact-match-over-time; n-gram contamination). Generic accuracy hides these.

---

## 1. Inference-time failure modes  *(well supported)*

- **Hallucination — the central mode.** Two-axis taxonomy: **factuality** (diverges from real-world
  facts) vs **faithfulness** (drifts from the user input/context; sub-split instruction/context/logical)
  [Huang et al., **arXiv:2311.05232**; Alansari & Luqman, **arXiv:2510.06265**]. Causes span the
  lifecycle — data, training (shortcut learning, exposure bias, MLE not penalizing factual error),
  architecture (attention/positional limits, softmax bottleneck), **inference** (stochastic top-k/nucleus
  decoding, over-confidence, reasoning failure).
  - *Evals:* detection matched to type — factuality → retrieval fact-check + uncertainty; faithfulness →
    fact/classifier/QA/LLM-judge; 5-family scheme (retrieval/uncertainty/embedding/learning/
    self-consistency) using **sequence log-prob**, **semantic entropy**, multi-response self-consistency.
    Benchmarks split evaluation (TruthfulQA, HalluQA, HaluEval-2.0) vs detection (SelfCheckGPT, HaluEval,
    FELM). *(high)*
- **Instruction-following lapses.** **IFEval** [Zhou et al., **arXiv:2311.07911**]: ~25 *verifiable*
  instruction types over ~500 prompts, programmatically checkable (no biased human/LLM judge). *(high)*
- **Prompt brittleness.** Instruction-following drops **up to 61.8% (relative)** under
  semantically-equivalent rephrasings — frontier included (GPT-5 −18.3%, o3 −21.3%, Gemini-2.5-Pro
  −23.0%). Metric: **reliable@k** (pass *all k* "cousin" prompts) / IFEval++ [Dong et al.,
  **arXiv:2512.14754**]. *(high)*
- **Miscalibration / overconfidence.** Measured by **ECE** on contamination-free post-cutoff questions;
  KalshiBench found systematic overconfidence, ECE 0.120–0.395 across 5 frontier models
  [**arXiv:2512.16030**]. *(medium — single preprint; its "90%+ confidence wrong 15–32%" sub-claim was
  refuted 1-2)*

## 2. Retrieval & long-context failures  *(well supported, large effects)*

- **Long-context degradation / "context rot."** Non-uniform accuracy across length, even on simple
  tasks. **NoLiMa** [**arXiv:2502.05167**, Adobe, ICML'25]: removing literal lexical overlap → **10/12
  models ≤50% of short-context score at 32K** (GPT-4o 99.3%→69.7%); advertised 128K windows show
  **effective ~2K — up to 64× gap.** Corroborated by Chroma "Context Rot" (18 models) and "Lost in the
  Middle" [**arXiv:2307.03172**]. *(high)*
- **Length is an independent cause, separate from retrieval.** Even with *perfect* retrieval, task
  accuracy degrades **13.9%–85%** as input grows [Du, Tian, Ronanki et al., **arXiv:2510.05381**,
  EMNLP'25]. *(high)*
- **Distractor sensitivity** — a single distractor measurably hurts; impact amplifies with length; lower
  question↔needle semantic similarity accelerates decay [Chroma Context Rot]. *(high)*
- **RAG grounding/retrieval quality.** **RAGAS** [Es et al., **arXiv:2309.15217**]: faithfulness =
  |supported statements| / |all statements|; answer relevance; context relevance = crucial / total
  retrieved. *(high)*

## 3. Model drift over time  *(filled in pass 2)*

- **Silent provider drift is real and fast.** Fixed-API behavior changed substantially in ~3 months
  [Chen, Zaharia & Zou, **arXiv:2307.09009**]; **decreased instruction-following** was a common cause.
  *(durable claim: high; specific magnitudes: disputed — see below)*
  - ⚠️ **CITATION DISPUTE (flagged by adversarial review).** The exact prime-identification figures are
    **contested across paper versions and reviewers**: the original v1 headline was reported as
    **~97.6%→2.4%**, while later analysis attributes most of the apparent drop to a **prime-only test set
    (flipped yes/no bias)** and **output-format artifacts**, not reasoning loss. An earlier draft of this
    doc asserted "84.0%→51.1%" as settled — that is **not reliable**; do not quote a specific pair.
  - ⚠️ *Behavior change, not proven capability loss* (Narayanan & Kapoor). The "executable code
    52%→10%" drop was a **markdown-formatting artifact**, not correctness. **Refuted (do not cite):** a
    bogus "instruction fidelity 99.5%→0.5%" figure (0-3). **The durable, uncontested takeaway:** a fixed
    API name can change behavior substantially within months — *that* survives every critique.
- **Hard to catch:** silent updates/deprecations behind fixed names; standard regression testing doesn't
  transfer (different correctness, brittleness, **non-determinism even at temp=0**) [Ma, Yang & Kästner,
  CMU FSE'24, **arXiv:2311.11123**]; silent updates *largely unmonitored* due to audit cost
  [**arXiv:2512.03816**]. *(high)*
- *Evals/detectors:* **exact-match / answer-mismatch over time** (12.2% of GPT-4 USMLE answers differed
  Mar→Jun; 27.9% GPT-3.5); **cheap logprob tracking** (~1,000× cheaper, detects one fine-tuning step)
  [2512.03816, *medium*]; pinned longitudinal regression over data slices.
- **Benchmark contamination = parallel drift.** Eval scores inflate via leakage; canonical detection =
  **13-gram overlap** [**arXiv:2406.04244** survey]; caught by training-cutoff natural experiments
  [**arXiv:2310.10628**] and time-windowed refreshed benchmarks (LiveCodeBench, **arXiv:2403.07974**).
  *(high)* — ⚠️ the specific "**1.1%–45.8%** measured contamination" range could **not** be confirmed in
  2406.04244 by review; treat as **unsourced** pending the real citation.

## 4. Agentic / multi-step failures  *(SOURCING ARTIFACT, not a real gap — corrected per review)*

Both deep-research passes produced **zero surviving claims** here — but Codex **and** Gemini agree this
is a **methodology failure of our search, not a literature gap.** The passes fetched the older static
AgentBench (**arXiv:2308.03688**) and stopped before the reproducible, environment-grounded agentic
frontier. The agentic literature is in fact robust and reproducible; must-add anchors:
- **SWE-bench** [Jimenez et al., 2023] — multi-step codebase navigation/editing; large per-step→
  end-to-end compounding gap.
- **WebArena** [Zhou et al., 2023] — multi-step browser tasks with **catastrophic end-to-end success
  rates (often <15%)**.
- **τ-bench / ToolBench** — tool-use hallucination and error-recovery as verifiable, reproducible modes.
- Metrics: **per-step vs end-to-end (outcome) success gap**, trajectory-level grading, **pass^k**
  reliability.
This is the eval dimension Rosetta itself is *least* covered on; it needs a dedicated, benchmark-scoped
research pass + fixtures (see plan Phase 3).

---

## Durable takeaways (mechanisms & methods outlast the 2023–2025 magnitudes)
1. On our baseline fixtures, agents break on **retrieval-defeated** queries (semantic mismatch,
   distractors, length) more than on scale (v3–v6, n=1/cell) — a robust local finding, **not** a proven
   universal law, and **not** proof that pre-compilation is the only fix (inference-time tooling may
   match it; that head-to-head is untested).
2. Drift is **silent and under-monitored**; cheap detectors (logprob, exact-match-over-time, pinned
   regression) exist and are borrowable.
3. **Contamination** inflates static benchmarks → synthetic, code-anchored, periodically-regenerated
   fixtures (what this repo builds) are the contamination-resistant answer.
4. The agentic frontier is under-measured in the literature *and* here.

## Adversarial review (Codex + Gemini) — corrections & additions applied

Both reviewers independently flagged the same core problems; corrections applied above, plus:

**Missing failure modes to add (with sources):**
- **Sycophancy** — agreeing with a false premise in the prompt even when context has the truth [Sharma
  et al. **2310.13548**; Perez et al. **2308.03958**; **2502.08177**]. *Directly relevant to Rosetta:* a
  user asserting "we use X" can override correct retrieved evidence.
- **Multi-document / conflicting-context failure** — RAG degrades predictably given contradictory
  retrieved docs with no explicit supersession. **This is exactly Rosetta's problem space** and was
  missing from the synthesis.
- **Jailbreak / safety-training failures** [**2307.02483**]; **tokenization/counting brittleness**
  (BPE-level, e.g. character/exact counting — note our A3 "counting passes" conclusion ignored this)
  [**2405.17067**]; **multilingual/low-resource degradation** [**2412.12499**]; **repetition/
  degeneration** [Holtzman nucleus sampling **1904.09751**; **1908.04319**]; **position/order bias beyond
  lost-in-middle** [**2401.01989**]; **RAG retrieval-vs-generation decomposition** via RAGAS + **ARES
  (2311.09476)**.

**Overclaim downgrades (applied to interpretation, not deleted):**
- "**Only** semantic evasion breaks models" → "Semantic evasion **reliably breaks our baseline
  tool-calling agents** (n=1 per cell, base prompt)." It is not a universal law; it's a robust finding on
  our fixtures.
- **Rosetta-as-antidote is a HYPOTHESIS, not a result.** It has not been tested with a normalized
  compiled folder; the PRODUCT-VALUE-PLAN labels it accordingly.

**The falsification both reviewers raised (load-bearing for product strategy):** the compilation thesis
**collapses if inference-time tooling matches it** — e.g. giving the agent a `resolve_codename` /
`search_glossary` tool, or a better retriever, lets it pass the "unfindable" trap *without* any
pre-compiled folder. Our own v5 data shows scaffolded-Sonnet and raw-Opus/Flash already pass. So
**compilation must be benchmarked head-to-head against inference-time tooling**, not assumed superior.
A fair falsification suite: (a) normalized folder doesn't beat raw on v5/v6; (b) raw + better retriever
≈ folder; (c) the compiler introduces stale/hallucinated aliases; (d) non-retrieval failures dominate at
k≥3; (e) cheap-model+folder doesn't approach frontier-raw.

## Source quality notes
- Concentration: 8/12 drift findings trace to 2307.09009 (robust figures, contested interpretation —
  scoped here to "behavior change").
- Single recent preprints: 2512.03816 (logprob), 2512.16030 (KalshiBench) — author-reported, not yet
  replicated; medium weight.
- Practitioner source: Chroma Context Rot (vector-DB vendor; mild COI, externally replicated).
- All magnitudes are 2023–2025 snapshot-specific and time-sensitive; mechanisms/methods are the durable
  part. Full per-claim vote tallies are in the workflow run outputs.
