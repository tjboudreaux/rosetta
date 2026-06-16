# GOAL 1 — Central-thesis experiment: does provenance recover recall?

**Thesis under test.** Rosetta's distinctive bet (per `RESEARCH-workflows-x-rosetta.md`) is that a
*code-anchored, supersession-resolved decision graph* recovers the **factual-recall loss
(~33–35 pts on memory benchmarks at high compression)** that flat compression / flat-RAG / summary
incurs. The decisive question is **accuracy, not cost**: does the resolved graph beat **both** raw
long-context **and** a generic flat summary on getting the *current* answer right?

**Verdict: INCONCLUSIVE** (this fixture). All conditions scored **3/3** on Haiku. The graph won on
per-query tokens and produced a single pre-resolved, conflict-free record, but it showed **no
accuracy advantage**, because flat compression **did not actually lose recall here** — so there was
nothing for provenance to recover. See "Why inconclusive" and "What a decisive test needs."

---

## Design (focused, fair, k=3)

**Model under test:** Haiku — the cheap model we want to lift. **k=3 per condition. Grading:
read-verified claim-check** against a written rubric (`goal1-outputs/GOLD.md`), never grep-grading.

**Fixture** (`goal1_fixture_gen.py` → `goal1-outputs/corpus.md`): one recall-heavy decision history,
32 records, ~1.1k tokens, mixing eng-logs, code snapshots, dashboards, runbooks, incidents, org
notes, and a doc. The correct *current* answer requires resolving three traps at once:

1. **Implicit codename** — "Project Halifax" is **never** glossed as "Halifax is the checkout
   service"; it is inferable only from scattered co-occurrence (pod roster, `halifax-prod`
   dashboard, runbook → `services/checkout`, cost report namespace).
2. **Supersession chain** — auth evolves **JWT(HS256) → opaque Redis sessions → PASETO v4**; only
   the last is current.
3. **Distractors** — (a) a **stale-but-Accepted-looking** architecture doc (R18) that still calls
   Redis "current," and (b) an **adjacent service** (billing / "Sterling") that uses **JWT RS256**
   in recent, confident language.

**The one question (identical for all conditions):**
> "What is the CURRENT session-token mechanism for Project Halifax, and what mechanism did it
> replace? Be specific about the current choice and the immediately prior one."

**Gold:** current = **PASETO v4** (v4.local, paseto-py); replaced = **opaque Redis-backed sessions**;
codename = checkout; must NOT answer JWT / Redis / billing-RS256 as current.

**Conditions** (same question, k=3 each, fresh Haiku agents, no shared context):

| | Condition | Context the Haiku answerer sees | Built by |
|---|---|---|---|
| **A** | raw long-context | the full raw `corpus.md` | — |
| **B** | flat RAG / summary | a naive flat summary of the corpus (no supersession structure; conflicts left flat) | **Opus** subagent |
| **C** | Rosetta resolved graph | `decisions.py resolve "checkout session token"` → the single CURRENT ADR it returns | **Opus** compiler subagent → `decisions.py` |

The flat summarizer was explicitly instructed **not** to resolve conflicts or build a current-state
section (that would make B secretly a graph). The Opus compiler decoded the codename from scattered
evidence, wrote **9 validated ADRs**, built the supersession chain with `decisions.py supersede`,
gave the stale doc **no** phantom current record, kept billing separate, and confirmed
`resolve` returns a single current ADR (`conflict: false`). `validate` passes clean (0 errors).

---

## Read-verified results

| Condition | Correctness (Haiku, k=3) | Per-query input tokens (est) | One-time compile (est) |
|---|---|---|---|
| **A** raw long-context | **3/3** | ~1,097 | 0 |
| **B** flat RAG/summary (68% compress) | **3/3** | ~736 | ~33k (Opus summary) |
| **B2** flat RAG/summary (20% compress, stress) | **3/3** | ~224 | ~31k (Opus summary) |
| **C** Rosetta resolved graph | **3/3** | ~690 | ~76k (Opus compile, 9 ADRs) |

Every one of the 12 graded runs named **PASETO v4** as current and **opaque Redis sessions** as the
thing it replaced, tied the codename to checkout, and avoided the billing-RS256 and stale-Redis
distractors. (One C run first mis-ran `resolve` against the wrong `--root` and found nothing; a
re-run with the correct absolute path resolved cleanly — an operator path-discipline note, not a
library failure.) Detail in `goal1-outputs/results.json`; raw answers were inspected inline.

---

## Why inconclusive (the honest read)

The thesis predicts B (flat compression) should **lose the superseding fact** and answer "Redis" or
"JWT," while C recovers it. That did not happen — **B never lost it.** Two reasons:

1. **The corpus is small (~1.1k tokens).** Raw long-context (A) trivially retains everything, and
   even an aggressive 20%-compression summary (B2) had room to keep the auth chain. The 33–35-pt
   recall-loss figure is a **high-compression-of-large-context** phenomenon; a 1.1k-token corpus
   never enters that regime.
2. **A competent (Opus) summarizer ordered the chain.** Even under a hard 900-char budget, B2 wrote
   "JWT → *then* Redis → *then* PASETO," preserving recency. A faithful summary that keeps temporal
   order is *already* answerable; flat ≠ lossy when the summarizer is good and the input is small.

So this fixture tested the traps (codename, supersession, distractors) but **not the compression
pressure** that the thesis is actually about. C's real, measured wins here are narrower than the
thesis: **fewer per-query tokens** (690 vs 1,097 raw, −37%) and a **single pre-resolved,
conflict-flagged record** instead of leaving the cheap model to adjudicate the stale-doc conflict
itself — a robustness margin that this easy fixture didn't force any model to spend.

## Honest caveats

- **Single fixture, k=3, one cheap tier (Haiku).** Not a preregistered suite; no Sonnet/Gemini-Flash
  tiers; no `$/correct` accounting beyond rough token counts. Consistent with Phase 0.5's own
  "not fully met by single fixtures" caveat.
- **Compile cost is real and large** (~76k tokens for C's 9 ADRs; ~31–33k for B's summary). These
  amortize over many queries but are not free; break-even was not measured here.
- **The compiler tuned ADR phrasing so the substring matcher resolves cleanly** (it added
  resolution-anchor phrases and removed "Halifax" from the billing ADR). That is legitimate
  compilation work, but it means C's clean single-record resolve is partly an artifact of the
  matcher being literal substring, not semantic. A broad single word (`"billing"`) still returns a
  conflict — correct behavior, but a reminder the retriever is primitive.
- **Token-per-query numbers are answerer-self-reported estimates**, cross-checked against file sizes
  (corpus 4,389 / flat 2,944 / ADR 0003 2,758 chars), not metered API counts.

## What a decisive test needs (the falsifier, sharpened)

To actually move this from INCONCLUSIVE to SUPPORTED/REFUTED, force flat compression into its
lossy regime so B *can* fail while C holds:

1. **Large corpus** (tens of k tokens) so the summary **must** drop detail — the documented
   high-compression regime.
2. **Adversarial summarizer / cheaper summarizer** (or a summary that, realistically, keeps the
   stale doc's "Redis is current" claim while dropping the late migration line) so the superseding
   fact is genuinely lost or scrambled.
3. **Multiple questions per fixture** (not just the one the summarizer might happen to preserve) and
   **≥20 generated fixtures** across glossary present/absent/scattered × ambiguous-supersession ×
   code-vs-decision conflict, per the Phase-0b gate.
4. **Report `$/correct`** including compile + retrieval + retry, across tiers {Haiku, Sonnet,
   Gemini-Flash}.

**Falsifier (unchanged):** if a faithful flat summary keeps matching the resolved graph on accuracy
across *large, lossy* fixtures, the accuracy half of the thesis is refuted and Rosetta should be
positioned as the **token-reduction / single-pre-resolved-record** lever (which it demonstrably is
here: −37% tokens vs raw, conflict-free single record) rather than a recall-recovery lever.

## Verdict

**INCONCLUSIVE on recall recovery.** On this fixture the decision graph did **not** beat flat
summary on accuracy (3/3 vs 3/3) because flat compression incurred **no** recall loss to recover —
the corpus was too small and the summarizer too faithful to enter the lossy regime the thesis
targets. The graph's demonstrated advantages were **cost (−37% tokens/query vs raw)** and a
**single pre-resolved, conflict-free answer**, not accuracy. Do **not** claim "provenance recovers
recall" on this evidence. The next experiment must force the compression pressure.
