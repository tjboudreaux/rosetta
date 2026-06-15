# ADR 0001 — Canonical service identity: svc-flags_api (feature-flag service, fka "Drift")

- Status: Accepted
- Date: 2026-06-14
- Decided originally: 2026-05-18
- Decider: Platform team
- Sources: `claude · sca0c · 2026-05-18` (raw/03-platform-decision.md); `claude · sca0a · 2025-11-02` (raw/01-arch-note.md); `codex · sca0b · 2026-02-10` (raw/02-ops-runbook.md); code path `raw/code/flags_api.py`
- Related: ADR 0002

## Context

One single service is referred to by three different names scattered across the corpus, which makes
its decision history impossible to follow without unification:

- **"Drift"** — old codename, used in the early architecture note (`raw/01-arch-note.md`,
  `claude · sca0a · 2025-11-02`).
- **"the feature-flag service"** — descriptive name, used in the ops runbook
  (`raw/02-ops-runbook.md`, `codex · sca0b · 2026-02-10`).
- **"svc-flags_api"** — the svc- id, used in the platform decision
  (`raw/03-platform-decision.md`, `claude · sca0c · 2026-05-18`) and backed by the code path
  `raw/code/flags_api.py`.

The platform decision states explicitly: "svc-flags_api, the feature-flag service, and what older
docs call 'Drift' are the SAME service." The code file header confirms it:
`# flags_api.py — also known as Drift / feature-flag service`.

## Decision

Treat all three names as aliases of one canonical entity. The canonical identifier is
**svc-flags_api** (matching the code path `flags_api.py`, since code/git wins). Record the alias map
explicitly:

| Alias | Type | Source |
|-------|------|--------|
| svc-flags_api | svc- id (canonical) | `raw/code/flags_api.py`, `claude · sca0c · 2026-05-18` |
| feature-flag service | descriptive name | `codex · sca0b · 2026-02-10` |
| Drift | old codename | `claude · sca0a · 2025-11-02` |

All decision records about this service resolve to svc-flags_api.

## Consequences

Positive:
- Decision history for the service can be traced across documents written years and tools apart.
- Downstream queries on any of the three names resolve to one entity.

Negative:
- Older "Drift" references remain in archived docs; mitigated by recording the alias map here so they
  are never read as a separate service.

## Alternatives considered

- **Keep "Drift" as canonical** — rejected; it is a stale codename with no code backing.
- **Keep "feature-flag service" as canonical** — rejected; descriptive, not an identifier, and not
  what the code uses.

## Related

- ADR 0002 (message bus / event queue for this service)
- Code path: `raw/code/flags_api.py`
