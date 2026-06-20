# Rosetta-integrated commands

Slash-command skills that combine common interaction patterns with **Rosetta's decision-resolution
layer** (`scripts/decisions.py resolve/search/get/supersede`, `rosetta gates check`, and
`rosetta preflight`). The point: ground the interaction in *what's already decided and what the code
actually does*, then record durable, code-anchored decision records when humans make a new decision.

Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy.


## Install
These are skill-format markdown files. To make them invocable as `/<name>`, install into a skills or
commands dir your harness loads, e.g.:
```bash
ln -s "$PWD/skills/rosetta/commands/rosetta-grill.md"     ~/.claude/commands/rosetta-grill.md
ln -s "$PWD/skills/rosetta/commands/rosetta-conflicts.md" ~/.claude/commands/rosetta-conflicts.md
```
(Or copy them into `~/.claude/skills/<name>/SKILL.md`.)

## The set

| Command | What it does | Rosetta integration |
|---|---|---|
| **`/rosetta-grill`** ✅ | Grills a plan/decision one question at a time, recommendation-first — then **records the resolution as an ADR/PDR**. | Resolves current state first (no re-litigating settled ADRs); supersedes on change; writes + validates the record. |
| **`/rosetta-conflicts`** ✅ | Audits the library for unresolved conflicts (≥2 current records), code-vs-decision contradictions, and stale records. | Uses `resolve`'s conflict flag + the truth hierarchy (code wins) + drift/staleness checks. |
| **`/rosetta-preflight`** ✅ | Produces the deterministic RA1/decision-state/gates JSON before a loop runner acts. | Wraps `rosetta preflight`; no nested `rosetta loop` namespace and no product execution. |
| `/rosetta-catchup` (planned) | "Get me up to speed on X" — grounded catch-up over a subsystem. | `ground-truth.md` + `resolve` the subsystem's live decisions; cite provenance. |
| `/rosetta-decide` (planned) | Lightweight: capture a decision just made, with code anchors, in one step. | `decisions.py new` + `supersede`, auto-fill Sources from the diff. |
| `/rosetta-premortem` (planned) | Adversarial pre-mortem on a proposed change, grounded in past abandoned/reverted approaches. | Pulls Abandoned/reverted records so the same mistake isn't re-attempted. |

## Design principle (why this is "deep" integration, not a wrapper)
Each command **resolves before it reasons** and **records after it concludes**. Resolving first means it
operates on the *open* questions, never re-deriving settled state — which the eval work
(`PHASE0.5-RESULTS.md`) showed is both more accurate and cheaper (a resolved layer lets even a cheap
model reach the right current state). Recording after means every interaction compounds the library,
making the next one cheaper and more accurate still. That compounding loop is the product.
