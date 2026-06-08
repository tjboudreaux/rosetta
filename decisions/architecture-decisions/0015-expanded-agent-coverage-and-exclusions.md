# ADR 0015 — Expanded agent coverage to 18 sources; non-agent exclusion list

- Status: Accepted
- Date: 2026-06-08
- Decided originally: 2026-06-08
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-08` (this conversation; machine reconnaissance + live smoke); code `scripts/collect.py`, `tests/`; supersedes the "no usable transcripts" note in `references/agent-stores.md`
- Related: ADR 0002, ADR 0014

## Context

Rosetta parsed 5 agents and merely *flagged* the rest. Reconnaissance found **13 more** coding
agents installed on this machine — 6 holding real transcripts (Gemini, opencode, Cline, Continue,
Claude Agent-Mode, Aider), 7 installed-but-idle (Qwen, Goose, Crush, Roo, Kilo, Windsurf, Augment).
A prior `agent-stores.md` note wrongly claimed Gemini/Cline/Aider had no usable transcripts; the
recon (Gemini = 115 sessions, Cline = 15 tasks, Aider = per-project markdown) disproves it. Several
look-alike dotdirs are not agents at all.

## Decision

Add resolvers/parsers for all 13 (18 total), tiered by verifiability:
- **P0 (verified vs real data):** Gemini, opencode, Cline, Continue, Claude Agent-Mode, Aider.
- **P1 (implemented from documented formats, fixture-tested, no live data here):** Qwen, Goose,
  Crush, Roo, Kilo, Windsurf, Augment. Crush/Windsurf/Augment ship marked **UNVERIFIED** (`extra`
  flag) since their schemas are inferred, not confirmed.
- **Non-agents → `NON_AGENT_DIRS`** (excluded from the sweep so it stays quiet): `~/.amplify`,
  `~/.cursor-tutor`, `~/.claude-squad`, Warp, `com.apple.AMPLibraryAgent`, app backups.
- **Tested:** `tests/fixtures/build.py` synthesizes a `$HOME` with a store for every agent;
  `tests/test_discovery.py` asserts each resolver+parser finds it; `tests/live_smoke.py` reports
  real-machine counts (non-asserting).

This **supersedes** the agent-stores "no usable transcripts" claim for Gemini/Cline/Aider.

## Consequences

Positive:
- Coverage went from 5 → 18 agents; the sweep is quieter (only genuine gaps like Qoder + desktop
  app containers remain flagged) and honest.

Negative:
- P1 + UNVERIFIED resolvers may need refinement when real data appears (esp. Crush sqlite schema,
  Windsurf/Cascade, Augment). Flagged in code + docs, not hidden.
- Cline-family project scoping is fuzzy (path-mention over task-id dirs) — lower confidence.

## Alternatives considered

- **Only the 6 verified agents now, stub the rest** — narrower but leaves installed agents dark;
  the user chose full coverage with the UNVERIFIED honesty markers.
- **Auto-fingerprint any JSONL under `$HOME`** — powerful but high false-positive risk; a curated
  registry + loud unknown-store sweep (ADR 0002) is safer. Left as a possible future ADR.

## Related

- `scripts/collect.py` (new resolvers/parsers, `NON_AGENT_DIRS`, `AGENTISH_HINTS`); `tests/`;
  `references/agent-stores.md` (additional-agents table + correction note).
