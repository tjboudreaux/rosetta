# Rosetta Decisions Library — index & timeline

This is the catalog of Rosetta's own **architecture decisions** (ADRs, in
[`architecture-decisions/`](architecture-decisions/)), **product decisions** (PDRs, in
[`product-decisions/`](product-decisions/)), and **business decisions** (BDRs, in
[`business-decisions/`](business-decisions/)), reconciled onto one timeline.

It is also the **reference implementation** of the decision-record format Rosetta ships for any team —
Rosetta dogfooding its own output. The format, templates, and customization are in
[`../references/decision-schema.md`](../references/decision-schema.md) and
[`config.json`](config.json); the timeline below is regenerated deterministically by
[`../scripts/decisions.py`](../scripts/decisions.py) (`decisions index`).

## How to read this

- **ADR** = a technical / structural choice (how the system is built).
- **PDR** = a product / strategy choice (what we make and why).
- **BDR** = a business / commercial choice (often made by humans in a meeting or thread).
- Each record cites its evidence as `agent · session-id · date`, a git commit, a code path, or a task id.

**Truth hierarchy** (when sources disagree, later wins, and code arbitrates):
`current code / git state > committed decisions > project docs > latest conversation > older
conversation`. A decision a transcript merely *discussed* is recorded as `Status: Proposed`, not
asserted, until code or an explicit human call confirms it.

## Timeline (by the date the decision was made)

<!-- ROSETTA:TIMELINE:START -->
| Date | ID | Type | Decision | Status |
|---|---|---|---|---|
| 2026-05-29 | [ADR 0001](architecture-decisions/0001-deterministic-collector-normalized-markdown-pipeline.md) | adr | Deterministic collector, normalized-markdown pipeline | Accepted (retroactive) |
| 2026-05-29 | [ADR 0002](architecture-decisions/0002-five-agent-store-registry-and-loud-coverage.md) | adr | Five-agent store registry + loud coverage manifest | Accepted (retroactive) |
| 2026-05-29 | [ADR 0003](architecture-decisions/0003-exact-cwd-scoping-default.md) | adr | Exact-cwd scoping by default; `--include-subdirs` opt-in | Accepted (retroactive) |
| 2026-05-29 | [ADR 0004](architecture-decisions/0004-truth-hierarchy-and-adversarial-verification.md) | adr | Truth hierarchy + adversarial verification | Accepted (retroactive) |
| 2026-06-07 | [ADR 0005](architecture-decisions/0005-path-encoding-non-alphanumeric-to-dash.md) | adr | Path encoding: every non-alphanumeric → dash | Accepted |
| 2026-06-07 | [ADR 0006](architecture-decisions/0006-hermes-multi-shape-ingestion.md) | adr | Hermes multi-shape ingestion | Accepted |
| 2026-06-07 | [ADR 0007](architecture-decisions/0007-decision-records-as-first-class-output.md) | adr | Decision records as a first-class Rosetta output | Accepted |
| 2026-06-07 | [ADR 0008](architecture-decisions/0008-customizable-schema-and-per-team-config.md) | adr | Customizable frontmatter schema + per-team config | Accepted |
| 2026-06-07 | [ADR 0009](architecture-decisions/0009-deterministic-decisions-tooling.md) | adr | Deterministic `decisions.py` (scaffold / index / validate) | Accepted |
| 2026-06-07 | [ADR 0010](architecture-decisions/0010-machine-wide-project-discovery.md) | adr | Machine-wide agent-conversation discovery | Accepted |
| 2026-06-07 | [ADR 0011](architecture-decisions/0011-thin-rosetta-cli-dispatcher.md) | adr | Thin Rosetta CLI dispatcher | Accepted |
| 2026-06-07 | [ADR 0012](architecture-decisions/0012-mcp-external-source-ingestion.md) | adr | External-source ingestion via MCP (Circleback, Slack, …) | Accepted (scaffolder + workflow shipped 2026-06-08; live-MCP connectors unverified) |
| 2026-06-07 | [ADR 0013](architecture-decisions/0013-installable-cli-packaging.md) | adr | Installable CLI packaging | Accepted (editable install shipped 2026-06-08; portable wheel/PyPI publish deferred) |
| 2026-06-07 | [BDR 0001](business-decisions/0001-rosetta-as-org-system-of-record-for-decisions.md) | bdr | Rosetta as the org system-of-record for decisions | Accepted |
| 2026-06-07 | [PDR 0001](product-decisions/0001-rosetta-as-universal-decision-context-engine.md) | pdr | Rosetta as the universal decision context engine | Accepted |
| 2026-06-07 | [PDR 0002](product-decisions/0002-decisions-are-durable-first-class-deliverables.md) | pdr | Decisions are durable, first-class deliverables | Accepted |
| 2026-06-07 | [PDR 0003](product-decisions/0003-team-customizable-so-any-team-adopts-it.md) | pdr | Team-customizable so any team can adopt it | Accepted |
| 2026-06-07 | [PDR 0004](product-decisions/0004-ingest-decisions-made-outside-code-and-chat.md) | pdr | Ingest decisions made outside code and agent chat | Proposed |
| 2026-06-08 | [ADR 0014](architecture-decisions/0014-pluggable-per-agent-parsers-and-registry.md) | adr | Pluggable per-agent parsers + agent registry + ROSETTA_HOME injection | Accepted |
| 2026-06-08 | [ADR 0015](architecture-decisions/0015-expanded-agent-coverage-and-exclusions.md) | adr | Expanded agent coverage to 18 sources; non-agent exclusion list | Accepted |
| 2026-06-13 | [ADR 0016](architecture-decisions/0016-incremental-collect-via-processed-session-ledger.md) | adr | Incremental collect via processed-session ledger | Accepted |
| 2026-06-13 | [ADR 0017](architecture-decisions/0017-crash-safe-writes-and-resilience.md) | adr | Crash-safe writes and parse resilience | Accepted |
| 2026-06-13 | [ADR 0018](architecture-decisions/0018-adversarial-eval-dataset.md) | adr | Adversarial eval dataset for the judgment half | Accepted |
| 2026-06-13 | [ADR 0019](architecture-decisions/0019-coverage-gate.md) | adr | CI coverage gate (fail under 90%) | Accepted |
| 2026-06-13 | [ADR 0020](architecture-decisions/0020-decision-library-hardening.md) | adr | Decision-library hardening (atomic writes, race-safe numbering, cycle detection) | Accepted |
| 2026-06-13 | [ADR 0021](architecture-decisions/0021-scalable-decision-store.md) | adr | Scalable decision store (O(1) numbering, query subcommands, query-don't-slurp) | Accepted |
| 2026-06-13 | [ADR 0022](architecture-decisions/0022-eval-calibration-across-model-tiers.md) | adr | Eval calibration across model tiers (judge-independent scoring, no-tools variant, gates) | Accepted |
| 2026-06-13 | [ADR 0023](architecture-decisions/0023-round3-hardening-fixes.md) | adr | Round-3 hardening fixes (true lock-based allocation; loud failures) | Accepted |
| 2026-06-14 | [ADR 0024](architecture-decisions/0024-compiler-anti-hallucination-integrity-gate.md) | adr | Compiler anti-hallucination integrity gate | Accepted |
| 2026-06-16 | [ADR 0025](architecture-decisions/0025-alias-glossary-resolution-layer.md) | adr | Alias/glossary codename-resolution layer | Accepted |
<!-- ROSETTA:TIMELINE:END -->

## Notable supersessions & nuances

- **ADR 0005 (path encoding)** overturns the original `/`-only `enc_path`: the real Claude/Factory
  scheme collapses *every* non-alphanumeric to `-`, so Rosetta had been blind to any project under a
  dotdir — including its own home. Found and fixed via the ADR 0004 adversarial pass.
- **ADRs 0001–0004** are retroactive audits of choices made on 2026-05-29 (`claude · bc09f7f6`); they
  carry `Date: 2026-06-07 (recorded)` with `Decided originally: 2026-05-29`.
- **ADRs 0012–0013 and PDR 0004 are `Proposed`** — the roadmap (external MCP ingestion, installable CLI
  packaging, human-source decisions), captured as designs, not yet built.

## Where the rest lives

- Reconciliation, coverage, contradictions, provenance: written to `../.agents/ground-truth.md` at
  runtime (gitignored). See the [example ground truth](../docs/examples/ground-truth.example.md).
- Record format, schema & customization: [`../references/decision-schema.md`](../references/decision-schema.md)
- External-source ingestion design (Proposed): [`../references/external-sources.md`](../references/external-sources.md)
- Agent transcript store registry: [`../references/agent-stores.md`](../references/agent-stores.md)
