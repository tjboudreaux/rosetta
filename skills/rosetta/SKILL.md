---
name: rosetta
description: Reconcile ALL prior agent conversations (Claude Code, Codex, Droid/Factory, Hermes, Cursor) with git history and docs into a cited ground truth, and distill durable decision records (ADRs/PDRs/BDRs). Use whenever the user wants to catch up on or get the state of a project, build or refresh a ground truth, read or mine previous agent/AI conversations, recover or record what was decided (technical, product, or business), capture/index/validate ADRs or PDRs, discover which projects on the machine have agent history, or onboard onto unfamiliar work — even if they don't say the word "Rosetta".
argument-hint: "Project path (defaults to the current directory)"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite
license: MIT
---

# Rosetta — reconcile every agent's transcripts into one ground truth

The same project lives under five incompatible transcript-storage schemes (Claude Code, Codex,
Factory/Droid, Hermes, Cursor), two of which aren't project-scoped at all, several of which have
drifted across CLI versions. Reading "all our previous agent conversations" by hand is
impossible and reading them into one context is ruinous. Rosetta decodes them all — like the
Rosetta Stone recovering one meaning across many scripts — and reconciles them with the code,
git history, and docs into a single cited ground-truth document.

**The core risk this skill exists to defeat:** a confident summary that silently missed an entire
agent's history, or that reports as fact something the transcripts merely *discussed* and then
abandoned. Every step below is built to make coverage loud and to privilege what shipped over
what was said.

## The deterministic collector does the heavy lifting

`scripts/collect.py` resolves storage paths, filters by cwd, tolerates schema drift, normalizes
timestamps to UTC, and writes clean per-session markdown plus a coverage manifest. **You never
read raw transcripts into your own context** — you orchestrate the script and subagents that read
its normalized output. See `references/agent-stores.md` for the store registry it mirrors.

## Deterministic loop-integration boundary

Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy.

Use `rosetta gates check` for local provenance/evidence gates, `rosetta preflight` for RA1 + decision
state + gate JSON, `rosetta drift report` for freshness reports, `rosetta runs` for the isolated
loop-run ledger, and `rosetta harness export` only for allowlisted marked docs.


## Workflow

### 1. Resolve the target project

Default to the current working directory. If the user named a path or project, use that
(resolve to an absolute path). If it's ambiguous — a renamed/moved dir, or a monorepo where work
happened in subdirectories — list the candidate encoded directories you see under the agent
stores and confirm with the user before scanning. Decide whether `--include-subdirs` is wanted
(monorepo root = yes; one specific package = no, the default).

### 2. Run the collector

```bash
python3 ~/.claude/skills/rosetta/scripts/collect.py \
  --project <ABS_PROJECT_PATH> \
  --out <ABS_PROJECT_PATH>/.agents/rosetta/<run-label>
```

Useful flags: `--include-subdirs` (monorepo mode — pulls cwd at or under the project),
`--since YYYY-MM-DD` (recent only), `--agents claude,codex` (subset), `--max-chars N` (per-message
truncation). The script prints a totals line to stdout and writes `manifest.json` + one
`<agent>__<session>.md` per matched session into the out dir.

By default, `collect` **skips sessions it has already processed** — it keeps a
`<project>/.agents/rosetta/processed-ledger.json` keyed by `<agent>::<session-id>` (the uniform
id every resolver produces). A skip is activity-aware: a session is re-processed only if it gained
new messages (its last activity advanced) since the last run; otherwise the out dir holds just the
new/changed delta. Pass `--reprocess` to ignore the ledger and rebuild every session (the ledger is
still refreshed), or `--processed-ledger <path>` to point at a different ledger file. The
per-agent and totals lines report `skipped_sessions`.

**Incremental update vs. fresh build — this is where you save tokens.** `collect` itself spends no
model tokens; the cost is downstream, where the Step-4 subagents read the `.md` files in the out
dir. So the ledger only pays off if you let the out dir stay a delta:

- **Catching up an existing `ground-truth.md`** (the common case): run `collect` normally (skip on),
  then in Step 4 digest **only** the delta `.md` files now in the out dir, and in Step 8 **merge**
  those digests into the existing doc in place — do not re-read prior sessions. Token cost scales
  with what changed, not with total history.
- **First build, or a deliberate from-scratch rebuild:** there is no prior doc to merge into, so the
  delta is not enough — run with `--reprocess` so the out dir holds the full corpus. This is the
  expensive path; use it only when you actually need to regenerate everything.

A caveat for the incremental path: a session that *grew* is re-emitted whole (not just its new
turns), so its full text is re-read once — correct for reconciliation, but not free.

If the user doesn't know which project — "what have I worked on?", "which projects have agent
history?" — run `collect.py --all-projects` first. It emits a machine-wide `projects-index.{json,md}`
(project cwd ↔ per-agent session counts ↔ activity range) cheaply, with no per-session parsing, so
you can pick the target before a full reconcile.

### 3. Show the coverage map — loudly

Read `manifest.json` and present the coverage to the user **before** summarizing, because the
worst failure is a confident ground truth built on a silent gap. Report, per agent: present?,
sessions matched, message count, date range, match mode, and the `extra` counters that flag
unmatchable history — `codex.sessions_without_cwd` (old-schema sessions that can't be
project-attributed), `factory.flat_files_without_cwd`. Also surface `unknown_stores` (agent-like
dirs not scanned) and any agent showing **0 sessions** with a one-line hypothesis ("Codex: 0 —
either unused here or all sessions predate cwd tracking"). If coverage looks wrong (e.g. you
expected Cursor history and got 0), re-check the path/encoding against `references/agent-stores.md`
before continuing.

### 4. Summarize each source with subagents (never read raw transcripts yourself)

Fan out subagents — one per agent, or per session-batch when an agent has many sessions — each
reading **only** the normalized `.md` files in the out dir. This keeps the heavy text out of your
context. Each subagent returns a compact, structured digest:

- **Decisions made** (and the reasoning), each with a citation `agent · session-id · date`
- **What was actually built / shipped** (vs merely proposed)
- **Open questions / unresolved threads**
- **Abandoned or reverted approaches** — so they aren't re-attempted
- **TODOs / next steps** left dangling
- **Key files, components, and entities** referenced

Tell each subagent: cite every claim with its source session and date; flag anything that reads as
speculation or an idea that didn't land; do not invent. Hermes matches are fuzzy (path-mention) —
treat them as lower confidence.

### 5. Anchor to ground truth (code wins over chat)

Independently gather what actually exists, because transcripts describe intentions and code
records reality:

- Git (skip cleanly if not a repo): recent `git log --oneline -n 40`, `git status`,
  `git branch -a`, and a glance at recent diffs for the areas the transcripts discuss.
- Docs: `README*`, `CLAUDE.md` / `AGENTS.md`, `docs/`, ADRs, and any existing
  `.agents/ground-truth.md`.

### 6. Synthesize with the truth hierarchy

Reconcile everything on a single UTC timeline. When sources conflict, resolve by this order:

```
current code / git state  >  committed decisions (merged, in history)
                          >  project docs (README, ADRs)
                          >  latest conversation consensus
                          >  older conversation
```

Later supersedes earlier; **code and git arbitrate what actually happened.** When a transcript
claims something the code doesn't show, the claim is "discussed/intended," not "done."

### 7. Adversarially verify (default rigor: full)

Run a skeptic pass — a subagent (or focused self-check) that takes each material claim in the
draft and tries to **refute** it against the code and git, defaulting to "unverified" when it
can't confirm. Demote anything it can't substantiate into the **Contradictions & unverified
claims** section rather than asserting it. The user can request a "fast recap" to skip this pass;
otherwise always do it.

### 8. Write the ground-truth document

Write to `<project>/.agents/ground-truth.md`. If one already exists, **update it in place** with a
fresh provenance header — never blind-overwrite a hand-edited doc; if the existing file looks
hand-maintained (not Rosetta-generated), show the user a diff of what you'd change and confirm.

Structure:

```markdown
# Ground Truth — <project name>
_Generated by Rosetta · <UTC datetime> · <project path> · run <label>_

## Coverage report
<agents scanned · sessions · date ranges · gaps · unmatchable counts · unknown stores · files read>

## Current state
<verified against code/git — what the project IS right now>

## Architecture & key components
<cited>

## Decisions & rationale
<cited; note where a later decision superseded an earlier one>

## Open questions / unresolved

## Abandoned / reverted approaches
<so they aren't re-attempted>

## TODOs / next steps

## Contradictions & unverified claims
<conflicts between sources, and claims not substantiated by code/git>

## Provenance index
<session-id → agent → date, for every source that fed this document>
```

Close by telling the user where the doc is, the headline coverage (e.g. "5 agents, 102 sessions,
Feb–May 2026; Cursor had none"), and the top 2–3 unresolved items or contradictions worth their
attention.

### 9. Distill decisions into records (when the user wants a decision library)

The ground truth is a snapshot; **decisions** deserve durable, individually-cited records. When the
user asks for ADRs/PDRs/BDRs — or wants to "capture/record what was decided" — distill them from the
reconciled history into a decision library (see `references/decision-schema.md` for the format and
`templates/{adr,pdr,bdr}-template.md`):

- Identify genuine decisions and classify each: **ADR** (technical/structural), **PDR**
  (product/strategy), **BDR** (business/commercial).
- Scaffold each deterministically — `python3 scripts/decisions.py new --type adr --title "…"` — then
  fill the body and the `Sources:` line with citations (`agent · session-id · date`, a commit, a code
  path). Honor the truth hierarchy: a decision the transcripts only *discussed* is `Status: Proposed`,
  not `Accepted`, until code or an explicit human call confirms it. Record every reversal by
  superseding the prior record — never silently oscillate.
- Regenerate the index and check the library: `decisions.py index` then `decisions.py validate`
  (both deterministic — no tokens; `validate` exits nonzero on a broken library). Add
  `--integrity` to also fail on **fabricated provenance** — a record that references a non-existent
  ADR id or cites a `Sources:` file that isn't on disk (the anti-hallucination gate; ADR 0024). Add
  `--staleness` to flag Accepted records whose cited code moved in git since their freshness baseline
  (the `Reviewed:` date if present, else `Date` — see ADR 0027). `decisions.py integrity` and
  `decisions.py staleness` also run as standalone JSON checks; `staleness --strict` exits nonzero if
  any record is stale (the CI-gate form).
  - **Before recording a new decision, check it isn't already captured:** `decisions.py search --text
  "<topic>"` (also `--type` / `--status` / `--limit N`) returns just the matching records as JSON. If
  an existing ADR already records it, cite that one — do not create a duplicate.
- **Read a specific record in full** with `decisions.py get "ADR 0042"` — pull the one record you
  need, not the library. `--resolve` follows the supersession chain and prints the current record.
- **Reverse a prior decision deterministically** with `decisions.py supersede "ADR 0042" --by "ADR
  0098"` — it flips the old record's `Status` to `Superseded by ADR 0098` and sets the new record's
  `Supersedes` line. Don't hand-edit status among thousands of files; let the tool do it, then
  `index` + `validate`.
- `decisions.py index` also emits a machine-readable `INDEX.json` (id · type · title · status · date ·
  path) you can read once to orient, and maintains an O(1) numbering counter so `new` stays fast at
  any library size. Numbering, search, and supersession are all O(1)/O(n)-deterministic — spend model
  tokens only on the judgment of *which* record matters, never on scanning the corpus.
- **Resolve a query to the live decision(s)** with `decisions.py resolve --text "<topic-or-codename>"`
  — it follows supersession to the current record, flags an unresolved `conflict`, and returns
  `resolved_unique` (true only when the whole query points to exactly ONE current decision). Teams
  refer to work by **codename**, so records carry an optional `Aliases:` field (`;`-separated): a
  codename query resolves through that map (`via_alias`), `index` emits a derived
  `GLOSSARY.md`/`GLOSSARY.json`, and `validate` is a **hard error** if one alias maps to two live
  decisions — an ambiguous codename is a bug, not a warning. `--no-alias-expand` for literal-only,
  `--no-stale-check` to skip git freshness annotations.
- **Acknowledge code drift without re-dating a decision** with the optional `Reviewed: <YYYY-MM-DD>`
  field (ADR 0027): when cited code has moved in git but the decision still holds, set `Reviewed:` to
  the date you confirmed it. The staleness guard treats this as a re-flaggable baseline (any *future*
  code change re-flags the record), not a permanent override — so it preserves the decision timeline
  while making the freshness gate CI-green on active repos.
- **Measure library health** with `decisions.py coverage` (JSON): the headline `anchoring.rate` is the
  share of Accepted decisions whose `Sources:` cite a real code path (provenance the resolver can
  trust); it also reports supersession stats, an agent-retrieval `ambiguous_topics` diagnostic (topics
  that don't resolve to a unique record), orphans, staleness, and alias coverage. Report-only by
  default; `--min-coverage 0.8` turns the anchoring rate into a CI gate (nonzero exit below the floor).
  See ADR 0026.

Decisions made **outside** code and agent chat (meetings via Circleback, Slack threads, trackers) can
be ingested too: query the source's MCP tools for the project/time window, emit the extracted decisions
as a JSON array, and pipe it to `scripts/ingest.py` (`rosetta ingest`) — it writes one `Status: Proposed`
record each for human confirmation. See `references/external-sources.md` and ADR 0012 (the deterministic
scaffolder is shipped; the live-MCP connectors are unverified — treat ingested records as drafts).

Loop/goal integration commands stay deterministic and bounded: `rosetta gates check` joins parseable
decision fields (`Human gated paths`, `Human approval for`, `Evidence for`, `Evidence artifacts`);
`rosetta preflight` embeds RA1's structural JSON when available and otherwise skips RA1; `rosetta runs`
records local run lifecycle notes under `loop-runs/`; `rosetta harness export` updates only marked
allowlisted docs under explicit `--apply`.

## Notes

- The out dir under `.agents/rosetta/<run>/` holds the normalized sessions + manifest for audit;
  it's regenerable and safe to add to `.gitignore`.
- Re-running is cheap and idempotent — it refreshes the doc rather than duplicating it.
- Re-running is also cheap in **tokens**: by default `collect` skips already-processed sessions, so
  a catch-up run leaves only the changed delta for the Step-4 subagents to read. Merge that delta
  into the existing `ground-truth.md` in place; reach for `--reprocess` (full token cost) only for a
  genuine from-scratch rebuild.
- To support a new agent later, add it to `references/agent-stores.md` and a resolver in
  `collect.py`; the discovery sweep already flags unknown stores so you know when one appears.
