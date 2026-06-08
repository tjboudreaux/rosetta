# ADR 0014 — Pluggable per-agent parsers + agent registry + ROSETTA_HOME injection

- Status: Accepted
- Date: 2026-06-08
- Decided originally: 2026-06-08
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-08` (this conversation); code `scripts/collect.py` (AGENTS registry, `home()`, parsers)
- Related: ADR 0001, ADR 0002, ADR 0015

## Context

The original collector assumed one storage shape: a resolver returns a list of JSONL files, and one
`collect_session` parses them all. Expanding past the first five agents broke that assumption —
real stores use one-JSON-per-message directories (opencode), nested JSON trees (Continue), markdown
(Aider), sqlite (Crush), and a `$set.messages` JSONL wrapper (Gemini). A single parser can't handle
them, and the import-time store-root constants made the whole thing impossible to unit-test without
touching the real `$HOME`.

## Decision

Two structural changes:
- **Agent registry + pluggable parsers.** Replace the `RESOLVERS` dict with `AGENTS = {name:
  {resolver, parser, root}}`. A resolver returns `{match_mode, units, extra}` where a *unit* is a
  file, a session-dir, or a sqlite `(db, session)` pair; the agent's *parser* turns one unit into
  normalized messages. `collect_session` stays the default parser (JSONL / whole-object / bare-list);
  exotic formats supply `parse_gemini` / `parse_opencode` / `parse_continue` / `parse_aider` /
  `parse_crush`. `main()` loops the registry uniformly.
- **`home()` injection.** Store roots derive from `home()` → `$ROSETTA_HOME or Path.home()`, computed
  at call time, so a test (or another machine) can sandbox the entire store layout by setting one env
  var.

## Consequences

Positive:
- Adding an agent is a registry row + (maybe) a parser + a fixture — no surgery on the core loop.
- The whole machine is sandboxable → deterministic unit tests (ADR 0015) with zero real-data deps.
- Shared parsers collapse work: Cline/Roo/Kilo share one resolver; Gemini/Qwen share one parser.

Negative:
- The unit/parser indirection is a little more abstract than "list of files"; documented and tested.

## Alternatives considered

- **One mega-parser with format sniffing** — becomes an unmaintainable if-ladder; per-agent parsers
  keep each format's quirks isolated and testable.
- **Keep import-time roots, monkeypatch in tests** — brittle and order-dependent; an env-var seam is
  explicit and also useful operationally.

## Related

- `scripts/collect.py` (`AGENTS`, `home()`, `parse_*`); `tests/` (ADR 0015); `references/agent-stores.md`.
