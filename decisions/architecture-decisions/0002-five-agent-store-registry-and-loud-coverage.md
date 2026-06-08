# ADR 0002 — Five-agent store registry + loud coverage manifest

- Status: Accepted (retroactive)
- Date: 2026-06-07 (recorded)
- Decided originally: 2026-05-29
- Decider: Travis
- Sources: `claude · bc09f7f6 · 2026-05-29`; code `scripts/collect.py` (RESOLVERS), `references/agent-stores.md`
- Related: ADR 0001, ADR 0006, ADR 0010

## Context

The same project lives under five storage schemes — Claude Code (path-encoded), Codex (date-bucketed),
Factory/Droid (path-encoded + flat files), Hermes (timestamped, unscoped), Cursor (own encoding) —
several of which have drifted across CLI versions. The worst failure mode is a confident ground truth
that **silently missed an entire agent's history**.

## Decision

Maintain an explicit store registry (`references/agent-stores.md`) mirrored by one resolver per agent
in `collect.py`. Every run emits a coverage `manifest.json` that reports, per agent: present?,
sessions, messages, date range, match mode, and `extra` counters for unmatchable history
(`sessions_without_cwd`, `flat_files_without_cwd`, `request_dumps_excluded`). A discovery sweep flags
agent-looking dotdirs not in the registry under `unknown_stores`. Coverage is shown to the user
**before** any synthesis.

## Consequences

Positive:
- Gaps are loud, not silent — the core risk the skill exists to defeat.
- Adding an agent = one registry entry + one resolver; unknown stores surface themselves.

Negative:
- The registry must be re-verified when CLIs change their on-disk layout (accepted; the sweep makes
  drift visible).

## Alternatives considered

- **Best-effort glob with no manifest** — hides misses; rejected.
- **Hard-fail on unknown stores** — brittle; better to report and continue.

## Related

- `references/agent-stores.md`, `discovery_sweep()`, the `manifest.json` `extra` counters.
