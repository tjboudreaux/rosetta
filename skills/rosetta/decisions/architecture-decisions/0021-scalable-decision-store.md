# ADR 0021 — Scalable decision store (O(1) numbering, query subcommands, query-don't-slurp)

- Status: Accepted
- Date: 2026-06-13
- Decider: Travis Boudreaux
- Sources: scripts/decisions.py (load_counter/save_counter, cmd_new, cmd_index, cmd_search/get/supersede), SKILL.md (step 9), tests/test_decisions_cli.py (DecisionsScale)
- Related: ADR 0020 (library hardening), ADR 0002 (coverage manifest / no silent gaps)

## Context

The decision library must support tens of thousands of records (10k–50k). Two limits blocked that. (1)
**Deterministic CLI:** `new` globbed every file and took `max+1` to pick the next number — O(n) per
insert, **O(n²)** to build a library; `index` re-read everything to regenerate a flat n-row markdown
table. (2) **The agent ceiling (the bigger problem):** SKILL.md told the model to *read* the decision
library to find/supersede records — at tens of thousands of ADRs that exceeds any context window, and
the size-drift evals exist precisely because "find the right prior ADR among N" is where judgment
fails. The library had no way for the agent to *query* instead of *slurp*.

## Decision

Turn the library into a **queryable store**, and teach the agent to query it:

- **O(1) numbering** via a per-type counter file `decisions/.counter.json`. `new` reads the counter
  (falling back to a single O(n) glob only to initialize on an existing library), reserves the number
  race-safely (ADR 0020), then persists the counter atomically. `index` recomputes the counter from
  disk, self-healing any drift.
- **`INDEX.json`** — `index` emits a machine-readable index (id · type · number · title · status ·
  date · path) alongside the human `README.md`, so tools and the agent can orient from one small file
  instead of N records.
- **Query subcommands** (all deterministic, token-free):
  - `search --text/--type/--status` → returns only matching records as JSON;
  - `get <id>` → prints one record in full;
  - `supersede <old> --by <new>` → deterministically flips the old `Status` to `Superseded by <new>`
    and sets the new record's `Supersedes`, removing the most error-prone manual edit.
- **SKILL.md step 9 rewrite:** an explicit "operating over a LARGE decision library — query, never
  slurp" protocol: `search` before recording (dedupe), `get` to read one, `supersede` to reverse.

## Consequences

Positive:
- Building a library is now O(n) total (O(1) per `new`), not O(n²).
- The agent spends tokens only on *which* record matters, never on scanning the corpus — the real
  fix for the 10k–50k-ADR ceiling. `supersede`/dedup become deterministic, which also de-risks the
  judgment the size-drift evals probe.

Negative:
- `search`/`get` still scan record frontmatter on disk (O(n) Python, token-free) for correctness/
  freshness rather than trusting `INDEX.json`; at 50k that's seconds of CPU, acceptable for an
  occasional query. A `--fast` INDEX.json-backed path is a future optimization.
- Records still live as one-file-per-decision in a single directory; filesystem glob is O(n). Optional
  thousand-bucket sharding (`architecture-decisions/0NNxx/`) is deferred until a real library proves it
  necessary — flagged here rather than silently assumed away.

## Alternatives considered

- **Trust INDEX.json for search/get** — faster but can go stale within a session after a `new`;
  chose scan-for-correctness with INDEX.json as an orientation/optimization artifact.
- **Keep telling the agent to read the library** — does not scale and is the exact failure the evals
  target. Rejected for the query protocol.
- **SQLite-backed store** — fast queries, but breaks the plain-text, git-diffable,
  zero-dependency record model that is core to the project. Rejected.
