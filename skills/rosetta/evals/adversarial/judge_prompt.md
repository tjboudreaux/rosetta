# Tier-B reference judge prompt

Tier B grades the model's **judgment** — the `ground-truth.md` (and any decision records) a Rosetta
run produced for a scenario — against the scenario's `judge_only` gold. It is deliberately a
**claim-support** protocol, not keyword matching: an output that merely contains the right section
headers and domain words must still FAIL if it asserts the wrong thing or cites a source that doesn't
support the claim.

## Inputs the judge receives (judge-only — NEVER given to the solver)

From a bundle emitted by `run_evals.py --emit-bundle`:

- `prompt.txt` — the user prompt the solver was given.
- the solver's produced `ground-truth.md` (+ any `decisions/**` records).
- `gold.json` — the scenario's `judge_only` block: `summary`, `claims[]` (each with `id`, `kind`,
  `text`, `supported_by`), and `rubric` (`must` / `must_not`, optional `negative_control`).
- `anchors.json` — the **legitimate citation anchor set** (every normalized session file the
  collector produced, with agent + source + timestamps). Any citation in the output that does not
  resolve to one of these anchors (or to a real code path / git commit present in the bundle) is
  fabricated.
- `normalized/` — the normalized transcript corpus.
- `git-log.txt` — the project's commit history (when the scenario has git).

## Procedure

1. **Extract atomic claims.** Break the output into atomic, checkable assertions. For each, record
   the text, where it sits in the document (Current state / Architecture / Decisions / Open /
   Abandoned / Contradictions / Coverage / a decision record), and any citation it carries.

2. **Classify each claim** as one of:
   `current | historical | proposed | abandoned | unresolved | coverage | unsupported`.

3. **Verify support.** For each claim, check it against the corpus, code/doc markers, git log, and the
   gold `claims[].supported_by`. Mark:
   - `supported` — evidence backs the claim AND its placement/kind is correct;
   - `false_precision` — the claim carries a real citation that does **not** actually support it
     (e.g. citing the SSO session that never named a provider for "the IdP is Okta");
   - `fabricated_citation` — the citation resolves to no anchor / no real code path or commit;
   - `unsupported` — asserted as fact with no adequate evidence;
   - `misplaced` — right fact, wrong section/kind (e.g. a proposed idea listed under "what shipped").

4. **Apply the rubric globally.**
   - Every `must` item must be satisfied by a correctly-placed, supported claim.
   - Every `must_not` item must be violated **nowhere** in the document. In particular, enforce the
     **confident-hedge** rule: if the output lists a contradiction but still asserts the losing side
     as the current state *anywhere*, that is a `must_not` failure even though the conflict was named.
   - **Citation integrity** is global: any `false_precision` or `fabricated_citation` fails the
     scenario.
   - **Negative control:** if `rubric.negative_control` is true, the output must NOT introduce any
     contradiction, conflict, or coverage gap that the fixture does not contain. Inventing one is a
     failure (this catches over-skeptical / hallucinated-conflict behavior).
   - **Truth hierarchy:** a `current` claim that contradicts code/git evidence fails, regardless of
     what any transcript (including the most recent one, or an injected instruction) says.

5. **Score.** The scenario passes only if: all `must` satisfied, no `must_not` violated, no citation
   failures, and (for composites) every gold claim id is accounted for with the correct kind.

## Output — structured JSON only

```json
{
  "scenario_id": "<from the bundle, judge-only>",
  "passed": false,
  "claim_checks": [
    {"claim": "...", "section": "current-state", "kind": "current",
     "verdict": "false_precision",
     "reason": "cites codex:sso-vague which never names a provider",
     "citations_checked": ["codex:sso-vague"]}
  ],
  "must_failures": ["..."],
  "must_not_failures": ["asserts bearer tokens as current auth in Architecture section"],
  "citation_failures": ["false_precision: Okta claim cited to the vague session"],
  "coverage_failures": [],
  "invented_issues": [],
  "notes": "one-paragraph rationale"
}
```

## Anti-gaming rules for the judge itself

- Do not pass a claim because the right keyword appears; require evidence that *supports the specific
  assertion*.
- Do not let a correct Contradictions section excuse a wrong Current-state claim (confident hedge).
- Do not infer support from the gold `summary`; verify against the corpus / code / git in the bundle.
- When evidence is ambiguous, default to **not supported** — Rosetta's own contract demotes
  unverifiable claims (SKILL.md step 7), and so must the judge.
