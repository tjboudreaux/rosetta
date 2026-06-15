---
name: rosetta-grill
description: Grill the user about a plan or design — but grounded in Rosetta's resolved decision state — then RECORD the outcome as an ADR/PDR. Use when the user wants to stress-test a decision, says "grill me on this", or wants a decision interrogated and captured. Integrates grill-me-style interrogation with Rosetta's decision-resolution layer and decision-record tooling.
argument-hint: "What you're deciding (or a path/topic); defaults to the current change"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite
license: MIT
---

# /rosetta-grill — grounded interrogation that produces a decision record

`grill-me` interrogates a plan from scratch. **rosetta-grill** does it *grounded in what's already
decided and what the code actually does*, and **closes the loop by writing the resolved decision into
the library** — so the conversation produces a durable, code-anchored ADR/PDR instead of evaporating.

## Workflow

### 1. Ground in the resolved decision state (don't re-litigate settled decisions)
Before asking anything, resolve the current state for the topic so questions are informed, not naive:
- Locate the decision library (`./decisions` or run `rosetta` first if none exists).
- For the topic terms, run the resolver — this returns the **current** decision(s), follows
  supersession, and flags conflicts:
  ```bash
  python3 scripts/decisions.py resolve --root decisions --text "<topic terms>"
  python3 scripts/decisions.py search  --root decisions --text "<topic terms>" --status Accepted
  ```
- Read any existing `.agents/ground-truth.md` for the verified current state.
- `git log --oneline -20` + read the code the topic touches — **code/git is the truth hierarchy's top
  authority** (SKILL.md step 6). A plan that contradicts current code must justify the change.

Open by stating what's already settled: *"ADR 0042 (Accepted) makes X the current approach, and
`foo.py` confirms it. Are you changing that? If so this will supersede 0042."* If `resolve` returns a
**conflict** (≥2 current records), surface it first — that's the highest-value thing to resolve.

### 2. Grill — one question at a time, recommendation-first, grounded
Walk the decision tree, resolving dependencies one-by-one (the grill-me discipline). For each question:
- Give your **recommended answer** and the reasoning.
- Anchor it to the resolved state: cite the ADR/code it agrees-with or would-supersede.
- If a question is answerable from the codebase or the decision library, **answer it yourself** (Read/
  Grep/`decisions.py get`) instead of asking.
- Push on: unstated assumptions, what it supersedes, scope (subsystem/region/tier — Rosetta evals show
  decisions are often conditional), reversibility, and how you'd verify it in code/git later.

### 3. Record the outcome (the integration that matters)
When a decision settles, **write it into the library** so it survives:
- Scaffold the record (ADR for technical, PDR for product, BDR for business):
  ```bash
  python3 scripts/decisions.py new --root decisions --type adr --title "<decision>" --decider "<name>"
  ```
- Fill Context / Decision / Sources (cite the code paths + this conversation), set Status
  (`Accepted` if decided now, `Proposed` if not yet committed — never mark Proposed as Accepted).
- If it changes a prior decision, **supersede** it (don't silently contradict):
  ```bash
  python3 scripts/decisions.py supersede <old-id> --by <new-id> --root decisions
  ```
- Regenerate the index and validate:
  ```bash
  python3 scripts/decisions.py index --root decisions && python3 scripts/decisions.py validate --root decisions
  ```
- Close by telling the user the record id, what it superseded (if anything), and the top 1–2 open
  questions still unresolved.

## Why grounded grilling is better (and cheaper)
Rosetta's eval work (PHASE0.5-RESULTS) showed a resolved decision layer lets even a cheap model reach
the right current state without re-reading the whole history. The same applies here: resolving first
means you grill on what's *actually open*, never waste turns re-deriving settled state, and leave behind
a record that makes the next grilling cheaper still. Use a cheap model for the resolve/read steps and a
strong model only for the interrogation if you want to minimize cost.
