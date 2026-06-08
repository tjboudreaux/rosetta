# Getting started

## Install

Rosetta is an [Agent Skill](https://agentskills.io) — a folder with a `SKILL.md`. Install it into any
skills-compatible agent:

```bash
# skills.sh (works for Claude Code, Codex, Gemini CLI, Cursor, opencode, and more)
npx skills add tjboudreaux/rosetta

# or GitHub CLI
gh skill install tjboudreaux/rosetta

# or clone the repo and copy the skill folder into your skills dir
git clone https://github.com/tjboudreaux/rosetta /tmp/rosetta && cp -r /tmp/rosetta/skills/rosetta ~/.claude/skills/rosetta
```

Rosetta is pure-Python **stdlib** — no `pip install`, no dependencies. You need Python 3.8+.

Optional: add a CLI alias.

```bash
alias rosetta="python3 ~/.claude/skills/rosetta/scripts/rosetta"
```

## 1. Discover what's on your machine

```bash
rosetta discover --out /tmp/disc
cat /tmp/disc/projects-index.md
```

This lists every project that has agent history across all supported stores, with per-agent session
counts and last activity — cheaply (no transcript parsing).

## 2. Build a ground truth for a project

In an agent (Claude Code, etc.), just ask — the skill triggers on intent:

> "Build a ground truth for this project from all our previous agent conversations."

Under the hood the agent runs the deterministic collector, shows you a coverage map, fans out
sub-readers over the normalized transcripts (never raw), reconciles against git + docs, runs an
adversarial verification pass, and writes `<project>/.agents/ground-truth.md`.

To run just the collector yourself:

```bash
rosetta collect --project ~/code/your-project --out ~/code/your-project/.agents/rosetta/full
```

## 3. Distill decisions

Ask the agent to "capture the decisions as ADRs and PDRs," or scaffold them deterministically:

```bash
rosetta decisions new --type adr --title "Adopt SQLite for the cache" --decider you
# fill in the body + Sources, then:
rosetta decisions index    --root decisions
rosetta decisions validate --root decisions
```

See the [end-to-end walkthrough](examples/end-to-end.md) for the whole flow on a real project.

## Where output goes

- `<project>/.agents/ground-truth.md` — the reconciled, cited state snapshot.
- `<project>/decisions/` — the ADR/PDR/BDR library + a generated index.
- `<project>/.agents/rosetta/<run>/` — normalized transcripts + a coverage `manifest.json` (cache;
  add `.agents/` to `.gitignore` — it can contain secrets).
