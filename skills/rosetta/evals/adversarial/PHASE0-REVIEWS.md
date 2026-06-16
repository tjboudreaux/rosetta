# Gemini P0 review
Here is the adversarial review. The Phase 0 results are built on falsified data and rigged methodology. If you pivot the product based on this document, you are building a trap.

### 1. The Smoking Gun: Data Falsification / Mis-grading
Your headline conclusion relies on the claim that Arm 4 (Rosetta compiled folder) scored **6/6**. This is completely false. 
- A review of the raw outputs reveals that `arm4comp__sonnet__k1.txt` and `arm4comp__sonnet__k3.txt` both explicitly name **"Postgres"** as the datastore, completely missing the 2026-06-08 migration to Cloud Spanner (ADR 0651).
- **Arm 4 actually scored 4/6.** 
- Grading "unified ledger tier" as a MISS is entirely fair (an opaque codename is useless to a developer). Under your own rules, the hand-tuned retriever (Arm 3) actually *beat* the compiled folder (6/6 vs 4/6).

### 2. Methodology: A "Fake vs. Fake" Head-to-Head
The experiment claims to compare "pre-compilation" against "inference-time tooling." In reality, it compared a **human** against a **regex script**, proving nothing about LLM capabilities.
- **Arm 3 (The Retriever) is rigged:** `phase0_alias_retriever.py` is ridiculously overfitted. It uses highly specific regexes (e.g., `r"'([^']+)'\s*(?:=|is)\s*([A-Za-z0-9 .()/-]+?)[.;]"`) tuned exactly to the synthetic glossary's syntax. Real-world glossaries are messy, unstructured, and distributed; an LLM tool would be much lossier than this regex.
- **Arm 4 (The Compiler) is a human:** You explicitly note the compiled folder was hand-normalized. There is zero evidence an LLM compiler could actually perform this normalization safely without hallucination or missing supersessions.
- **Conclusion:** The finding that "inference-time tooling ties compilation" is invalid. You cannot make architecture decisions based on two mechanisms that didn't actually use the intended production technology (LLM automation).

### 3. The Value Proposition is Dishonest
> *"Rosetta's value is... via an alias-aware, supersession-resolving retrieval layer."*

This is taking credit for the base model's native reasoning. `alias_retriever.py` does absolutely **zero** supersession resolution. It blindly expands aliases and dumps grepped text into the context window. It was Haiku/Sonnet that read the raw logs and figured out the timeline. Claiming your retrieval layer is "supersession-resolving" is dishonest product framing. 

Where this fails in reality: Any repo where aliases are implied rather than explicitly defined as `X is internally 'Y'`, or where decisions overlap conceptually without explicitly citing `Supersedes: Z`. The moment the regex breaks, the tool's value drops to zero.

### 4. Roadmap Pivot: What to actually do next
Do **not** execute Phase 1 as planned. Building `decisions.py` around an overfitted regex script is a dead end. 

**The highest-value next experiment (Phase 0.5):**
Run a true **LLM vs. LLM** test on a messy corpus.
1. Build a bare-minimum LLM compiler (to see if it hallucinates or drops supersessions).
2. Build a bare-minimum LLM inference-time tool (e.g., giving the model a `resolve_codename` search tool, not a regex script).
3. Test against a corpus where the glossary is distributed and implicit (e.g., mentioned off-hand in PR descriptions or slack-like dumps), not nicely formatted in a single file.

**What falsifies the redirect:** If the inference-time LLM tool is too expensive (requires multiple tool-calling hops per query) or fails to reliably find scattered aliases, then **amortized compilation is still the moat**, and the Phase 0 conclusion was wrong. Prove the LLM can do it before pivoting the entire company toward retrieval.

# Codex P0 review (re-run)
**Verdict: NO-GO on the product redirect as written. GO on a Phase 0b.**

1. **The Phase 0 gate was not actually met.** The roadmap required `{Haiku, Sonnet, Gemini-Flash}`, real inference-time tooling, and `$ / correct` measurement, but the result only covers Haiku/Sonnet, swaps arm 2 into prompt scaffolding, and reports mean tokens only. Compare [EVAL-AND-PRODUCT-ROADMAP.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/EVAL-AND-PRODUCT-ROADMAP.md:22) with [PHASE0-RESULTS.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/PHASE0-RESULTS.md:21) and [PHASE0-RESULTS.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/PHASE0-RESULTS.md:29). This is a smoke test, not the decision gate the roadmap defines.

2. **The conclusion is still too motivated.** The corrected doc honestly retracts compiler-vs-retriever ordering, but then still says to “lead with the retrieval capability” and build alias retrieval first. That does not follow from a hand-tuned regex retriever versus a hand-normalized, buggy compiled folder. The retriever is not a general product capability; it parses two exact glossary phrasings and greps `history/*.md` only: [phase0_alias_retriever.py](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/phase0_alias_retriever.py:8), [phase0_alias_retriever.py](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/phase0_alias_retriever.py:10), [phase0_alias_retriever.py](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/phase0_alias_retriever.py:24). It proves “this glossary was easy to exploit,” not “retrieval is the moat.”

3. **The artifact set is not clean enough to audit.** The setup says 4 arms x 2 models x k=3, which implies 24 files, but `p0-outputs/` has 30 files because both `arm1_raw__*` and `arm1iso__*` exist. If the intended baseline is `arm1iso`, 0/6 is correct. If someone reads `arm1_raw`, the baseline is not 0/6: [arm1_raw__haiku__k1.txt](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/p0-outputs/arm1_raw__haiku__k1.txt:1) and [arm1_raw__sonnet__k1.txt](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/p0-outputs/arm1_raw__sonnet__k1.txt:1) both answer Cloud Spanner. Mark the non-isolated files excluded or move them out of the scored corpus.

4. **The grading is fair on “Cloud Spanner,” but lenient on evidence.** Counting undecoded “unified ledger tier” as a miss is fair because the trap is alias decoding: [PHASE0-RESULTS.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/PHASE0-RESULTS.md:21). But if the product claim is “supersession-resolving retrieval,” then merely naming Cloud Spanner is too low a bar. Some passing arm-3 answers do not explicitly reject the Postgres distractor or show the supersession chain, e.g. [arm3ret__haiku__k1.txt](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/p0-outputs/arm3ret__haiku__k1.txt:1). Grade two axes: decoded answer and supported resolution.

5. **“Cheap models reach frontier correctness” is an overclaim.** The table shows Haiku beating Sonnet in the compiled arm because Sonnet followed a poisoned compiled record: [PHASE0-RESULTS.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/PHASE0-RESULTS.md:34), [arm4comp__sonnet__k1.txt](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/p0-outputs/arm4comp__sonnet__k1.txt:1). That says more about artifact quality than model tier. Safer framing: “On this one alias/supersession fixture, cheap models can be lifted when the missing resolution evidence is exposed.”

**Better framing:** Rosetta is not “an alias-aware retriever.” The stronger product is a **decision-resolution layer**: build and serve a provenance graph that maps aliases, supersession, scope, code evidence, and stale/conflicting records. Retrieval is the interface. Compilation is the cache/materialization strategy. The moat, if one exists, is verified resolution plus freshness, not search.

**Highest-value next experiment:** Run Phase 0b as a preregistered 2x2 on 20+ generated fixtures across glossary-present, glossary-absent, scattered alias, ambiguous supersession, and code-vs-decision conflict cases.

Arms: raw; prompt scaffold; production query-time resolver over raw corpus; production compiler-generated decision graph plus the same resolver. No hand-normalization, no fixture-specific regex, same token budget rules, include compile cost amortized over multiple queries, and report `$ / correct`.

**Falsifies the redirect:** raw plus general query-time retrieval fails when the glossary is absent/scattered, or requires query-specific tuning, while compiled resolution wins on correctness or amortized cost. Conversely, if the real retriever matches compiled output across messy fixtures and real repos, then lead with retrieval.

**Roadmap changes:** add Phase 0b before Phase 1; make Phase 1 build the shared resolver/evidence graph, not just `decisions.py search`; pull messy alias and code-conflict tests forward from Phase 2; do not claim cost-down until `$ / correct` includes compile, retrieval, and retry costs.


tokens used
93,921
**Verdict: NO-GO on the product redirect as written. GO on a Phase 0b.**

1. **The Phase 0 gate was not actually met.** The roadmap required `{Haiku, Sonnet, Gemini-Flash}`, real inference-time tooling, and `$ / correct` measurement, but the result only covers Haiku/Sonnet, swaps arm 2 into prompt scaffolding, and reports mean tokens only. Compare [EVAL-AND-PRODUCT-ROADMAP.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/EVAL-AND-PRODUCT-ROADMAP.md:22) with [PHASE0-RESULTS.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/PHASE0-RESULTS.md:21) and [PHASE0-RESULTS.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/PHASE0-RESULTS.md:29). This is a smoke test, not the decision gate the roadmap defines.

2. **The conclusion is still too motivated.** The corrected doc honestly retracts compiler-vs-retriever ordering, but then still says to “lead with the retrieval capability” and build alias retrieval first. That does not follow from a hand-tuned regex retriever versus a hand-normalized, buggy compiled folder. The retriever is not a general product capability; it parses two exact glossary phrasings and greps `history/*.md` only: [phase0_alias_retriever.py](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/phase0_alias_retriever.py:8), [phase0_alias_retriever.py](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/phase0_alias_retriever.py:10), [phase0_alias_retriever.py](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/phase0_alias_retriever.py:24). It proves “this glossary was easy to exploit,” not “retrieval is the moat.”

3. **The artifact set is not clean enough to audit.** The setup says 4 arms x 2 models x k=3, which implies 24 files, but `p0-outputs/` has 30 files because both `arm1_raw__*` and `arm1iso__*` exist. If the intended baseline is `arm1iso`, 0/6 is correct. If someone reads `arm1_raw`, the baseline is not 0/6: [arm1_raw__haiku__k1.txt](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/p0-outputs/arm1_raw__haiku__k1.txt:1) and [arm1_raw__sonnet__k1.txt](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/p0-outputs/arm1_raw__sonnet__k1.txt:1) both answer Cloud Spanner. Mark the non-isolated files excluded or move them out of the scored corpus.

4. **The grading is fair on “Cloud Spanner,” but lenient on evidence.** Counting undecoded “unified ledger tier” as a miss is fair because the trap is alias decoding: [PHASE0-RESULTS.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/PHASE0-RESULTS.md:21). But if the product claim is “supersession-resolving retrieval,” then merely naming Cloud Spanner is too low a bar. Some passing arm-3 answers do not explicitly reject the Postgres distractor or show the supersession chain, e.g. [arm3ret__haiku__k1.txt](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/p0-outputs/arm3ret__haiku__k1.txt:1). Grade two axes: decoded answer and supported resolution.

5. **“Cheap models reach frontier correctness” is an overclaim.** The table shows Haiku beating Sonnet in the compiled arm because Sonnet followed a poisoned compiled record: [PHASE0-RESULTS.md](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/PHASE0-RESULTS.md:34), [arm4comp__sonnet__k1.txt](/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/evals/adversarial/p0-outputs/arm4comp__sonnet__k1.txt:1). That says more about artifact quality than model tier. Safer framing: “On this one alias/supersession fixture, cheap models can be lifted when the missing resolution evidence is exposed.”

**Better framing:** Rosetta is not “an alias-aware retriever.” The stronger product is a **decision-resolution layer**: build and serve a provenance graph that maps aliases, supersession, scope, code evidence, and stale/conflicting records. Retrieval is the interface. Compilation is the cache/materialization strategy. The moat, if one exists, is verified resolution plus freshness, not search.

**Highest-value next experiment:** Run Phase 0b as a preregistered 2x2 on 20+ generated fixtures across glossary-present, glossary-absent, scattered alias, ambiguous supersession, and code-vs-decision conflict cases.

Arms: raw; prompt scaffold; production query-time resolver over raw corpus; production compiler-generated decision graph plus the same resolver. No hand-normalization, no fixture-specific regex, same token budget rules, include compile cost amortized over multiple queries, and report `$ / correct`.

**Falsifies the redirect:** raw plus general query-time retrieval fails when the glossary is absent/scattered, or requires query-specific tuning, while compiled resolution wins on correctness or amortized cost. Conversely, if the real retriever matches compiled output across messy fixtures and real repos, then lead with retrieval.

**Roadmap changes:** add Phase 0b before Phase 1; make Phase 1 build the shared resolver/evidence graph, not just `decisions.py search`; pull messy alias and code-conflict tests forward from Phase 2; do not claim cost-down until `$ / correct` includes compile, retrieval, and retry costs.


