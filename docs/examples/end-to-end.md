# End-to-end walkthrough

A complete pass on a fictional `~/code/example-app`: discover → reconcile → distill decisions. Outputs
are illustrative.

## 0. Install + alias

```bash
npx skills add tjboudreaux/rosetta
alias rosetta="python3 ~/.claude/skills/rosetta/scripts/rosetta"
```

## 1. What do I even have?

```bash
$ rosetta discover --out /tmp/disc
{"projects": 37}

$ grep example-app /tmp/disc/projects-index.md
| /Users/you/code/example-app | 18 | 9 | — | 7 | — | — | 2026-06-07 |
```

37 projects on the machine have agent history; `example-app` has Claude + Codex + Gemini sessions.

## 2. Reconcile into normalized transcripts + a coverage map

```bash
$ rosetta collect --project ~/code/example-app --out ~/code/example-app/.agents/rosetta/full
[rosetta] claude: 18 sessions, 402 messages (path-encoded project dir)
[rosetta] codex: 9 sessions, 121 messages (scan + cwd filter); extra={'sessions_without_cwd': 3}
[rosetta] gemini: 7 sessions, 54 messages (tmp/<project>/chats + projects.json map)
[rosetta] aider: 5 sessions, 31 messages (per-project .aider.chat.history.md)
[rosetta] hermes: 2 sessions, 4 messages (fuzzy: project path mentioned)
{"sessions": 41, "messages": 612, "skipped_lines": 188}
```

That wrote one normalized `<agent>__<session>.md` per session plus `manifest.json`. **The coverage map
is shown before any summary** — note the 3 unattributable Codex sessions are surfaced, not hidden.

## 3. Build the ground truth (in your agent)

In Claude Code (or any skills-compatible agent), ask:

> "Use Rosetta to build a ground truth for ~/code/example-app."

The agent reads only the normalized `.md` files (never raw transcripts), reconciles them against
`git log`/`git status` and the README under the truth hierarchy, runs an adversarial verification
pass, and writes [`.agents/ground-truth.md`](ground-truth.example.md). It closes with the headline
("5 agents, 41 sessions, Feb–Jun; Cursor had none") and the top contradictions.

## 4. Distill the decisions

> "Capture the decisions from that ground truth as ADRs and PDRs."

Or scaffold deterministically:

```bash
$ rosetta decisions new --type adr --title "Postgres-backed job queue, not Redis" --decider you
/Users/you/code/example-app/decisions/architecture-decisions/0001-postgres-backed-job-queue-not-redis.md
```

Fill the body + `Sources` (the agent does this with citations like `claude · 7f3a… · 2026-04-22`),
then:

```bash
$ rosetta decisions index    --root decisions
indexed 3 records → /Users/you/code/example-app/decisions/README.md
$ rosetta decisions validate --root decisions
validated 3 records: 0 errors, 0 warnings
```

A thing the transcripts only *discussed* (e.g. usage billing) is recorded `Status: Proposed`, not
asserted — and the reverted Redis prototype becomes an "Abandoned" note so nobody re-attempts it.

## Result

```
example-app/
├── .agents/ground-truth.md            # reconciled, cited state (gitignore .agents/)
└── decisions/
    ├── architecture-decisions/0001-…  # ADRs
    ├── product-decisions/0001-…       # PDRs
    └── README.md                      # generated timeline index
```

You now have a cited, queryable record of *what is true* and *why* — for humans and for the next agent.
