---
name: rosetta-conflicts
description: Surface decisions the library cannot uniquely resolve — unresolved conflicts (≥2 current records), code that contradicts an Accepted ADR, and stale records whose cited code moved on. Use to audit a decision library's health before trusting it, or when the user asks "what's contradictory / unresolved / stale in our decisions".
argument-hint: "Optional topic to scope to; defaults to the whole library"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep, Agent, TodoWrite
license: MIT
---

# /rosetta-conflicts — audit the decision library for unresolved/stale/contradicted decisions

A decision library is only trustworthy if it *uniquely resolves* each question. This command finds where
it doesn't — the exact failure that silently produced wrong answers in Rosetta's Phase-0 evals (two
`Accepted` records for the same thing).

## Workflow

### 1. Conflicts — multiple current records for one query
For each major subsystem/topic (or the user's `$ARGUMENTS` scope), run the resolver and report any
`conflict: true`:
```bash
python3 scripts/decisions.py resolve --root decisions --text "<topic>"   # conflict=true => unresolved
```
List each conflict with its competing current record ids and recommend the fix (disambiguate by
scope, or `supersede` the losing side). These are the highest-priority items — a conflicted library
will hand an agent the wrong answer.

### 2. Code-vs-decision contradictions (truth hierarchy: code wins)
For each Accepted decision, check whether the code it cites still supports it:
- `decisions.py search --root decisions --status Accepted` to enumerate live records,
- read each record's `Sources:` paths and `git log -1 -- <path>`,
- flag any where the current code contradicts the decision (e.g., ADR says Postgres, code imports a
  cloudsql client) — recommend either updating the code or superseding the ADR.

### 3. Staleness — cited code moved on
Flag Accepted records whose cited code/commit has changed materially since the record's date (the drift
failure mode from the research: silent updates leave a confidently-wrong oracle). Two resolution paths:
- **Code moved but the decision still holds** → add `Reviewed: <YYYY-MM-DD>` to the record (ADR 0027).
  This acknowledges the code change without corrupting the decision timeline — the staleness guard
  treats `Reviewed:` as a re-flaggable baseline, not a permanent override, so any *future* change
  re-flags it. Run `decisions.py staleness --root decisions` to see which records need review.
- **Code moved and the decision is now wrong** → `supersede` the ADR with a new one that reflects
  the current code, or re-run `rosetta` to refresh the library.

### 4. Report
Output a prioritized table: **Conflicts** (must-fix) → **Code-contradictions** → **Stale**. Close with
the single most dangerous item (the one most likely to mislead an agent) and the exact `supersede` /
re-collect command to fix it. Run `decisions.py validate --root decisions` at the end to confirm
frontmatter/numbering/supersede-link integrity.
