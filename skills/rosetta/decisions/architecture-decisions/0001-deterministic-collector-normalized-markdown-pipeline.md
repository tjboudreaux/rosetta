# ADR 0001 — Deterministic collector, normalized-markdown pipeline

- Status: Accepted (retroactive)
- Date: 2026-06-07 (recorded)
- Decided originally: 2026-05-29
- Decider: Travis
- Sources: `claude · bc09f7f6 · 2026-05-29` (design + build); code `scripts/collect.py`
- Related: ADR 0002, ADR 0004; SKILL.md

## Context

Reconciling "all our previous agent conversations" means reading transcripts from five tools with
incompatible storage schemes. Reading them by hand is impossible; reading them into one model
context is ruinously expensive and blows the context window. The hard part — path resolution, cwd
filtering, schema-tolerant parsing, timestamp normalization — is deterministic and does not need an
LLM.

## Decision

Split the work. A pure-stdlib Python collector (`scripts/collect.py`) does the deterministic heavy
lifting once and writes clean per-session markdown plus a coverage `manifest.json`. The orchestrator
and its subagents **never read raw JSONL** — they read only the normalized markdown. Synthesis (the
part that needs judgment) stays with the agent; mechanics stay in code.

## Consequences

Positive:
- Token cost collapses: agents read compact normalized text, not megabytes of raw transcript.
- The parser is testable and reusable across every project on the machine.
- Normalized output under `.agents/rosetta/<run>/` is an auditable, regenerable cache.

Negative:
- A new agent store requires a code change (a resolver) plus a registry entry — accepted as the
  price of correctness (see ADR 0002).

## Alternatives considered

- **Read transcripts directly in-context** — context blowout, high cost, non-reproducible; rejected.
- **A hosted/indexed service** — overkill for local transcripts; adds infra and a trust boundary.

## Related

- `scripts/collect.py` (`collect_session`, `write_session_md`, resolvers), `references/agent-stores.md`.
