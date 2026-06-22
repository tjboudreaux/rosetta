# AGENTS.md

Briefing for AI agents working in this repository. Keep it high-signal.

Rosetta is an open-source **agent skill** that reconciles every coding agent's local conversation
history (18 transcript stores) with git history and docs into one cited **ground truth**, plus
durable **decision records** (ADR / PDR / BDR). The shipped collector and decision CLI are
**pure-stdlib Python with zero runtime dependencies** (ADR 0013). The skill itself lives under
`skills/rosetta/`; the repo root holds the README, `llms.txt`, `assets/`, and `LICENSE`.

## Build & Test

No build step — pure stdlib. From the repo root (mirrors `.github/workflows/ci.yml`):

```bash
# Syntax check (no deps)
python -m py_compile skills/rosetta/scripts/collect.py skills/rosetta/scripts/decisions.py \
  skills/rosetta/scripts/ingest.py skills/rosetta/rosetta_cli.py

# Unit tests — every agent resolver/parser, gates, preflight, ingest, decisions
python -m unittest discover -s skills/rosetta/tests -v

# Decision library must stay well-formed (anti-hallucination integrity gate)
python skills/rosetta/scripts/decisions.py --root skills/rosetta/decisions validate --integrity
```

Coverage runs as a separate CI job (kept out of the test job so that stays zero-dep): from
`skills/rosetta/`, `coverage run -m unittest discover -s tests && coverage report` — `fail_under = 90`
is enforced via `.coveragerc`. CI runs the suite on Python **3.9 and 3.12**; keep both green.
Optional: `pip install -e skills/rosetta` puts `rosetta` on PATH; `python3 skills/rosetta/tests/live_smoke.py`
runs non-asserting counts against your real machine.

## Architecture

`skills/rosetta/rosetta_cli.py` is a thin dispatcher that shells each subcommand to a deterministic
script under `skills/rosetta/scripts/`:

- `collect.py` — resolve + normalize transcripts for one project: 18 per-agent resolvers + parsers,
  a discovery sweep, crash-safe atomic writes, and a processed-session ledger. `--all-projects` emits
  a machine-wide discovery index.
- `decisions.py` — ADR/PDR/BDR records: `new | index | validate | integrity | staleness | search |
  get | supersede | resolve | coverage`. Owns numbering, the index, and validation.
- `ingest.py` — external decisions/signals → `Status: Proposed` drafts (never auto-accepted).
- `gates.py` / `preflight.py` — local provenance/evidence gates; `preflight` also embeds RA1's
  structural readiness report. `runs.py` — isolated loop-run ledger under `loop-runs/`.
  `harness.py` — allowlisted harness-doc export. `drift.py` — decision-freshness JSON.

Boundary (see `skills/rosetta/docs/PLAN-loop-integration.md`): **Rosetta** owns local memory,
provenance, decision state, evidence/gates, drift, and run ledgers; **RA1** owns structural readiness
(embedded only in the `preflight` RA1 section); **loop runners** own execution and product-behavior
proof. Rosetta's CLI makes no external network calls except `preflight --allow-ra1-github`.

## Conventions & Patterns

- **Pure stdlib, zero runtime deps.** Keep `collect.py` schema-tolerant: count-and-skip a malformed
  line, never crash on one.
- **Loud coverage, not silent gaps.** Every collect run writes `manifest.json` with per-agent `extra`
  counters for history it could not attribute; unrecognized stores are flagged, never dropped.
- **Crash-safe writes.** Use `atomic_write_text` (temp file + `os.replace`) for ledgers/manifests so a
  killed process never leaves a truncated file.
- **Truth hierarchy** when sources conflict: `current code / git > committed decisions > docs >
  latest conversation > older conversation`. A transcript claim the code does not show is *intended*,
  not *done*.
- **Decisions are records, not loose prose.** Capture with `decisions.py new`; fill `Sources:` with
  `agent · session-id · date`, a commit, or a code path. `validate` runs in CI.

## Security

- **Read-only by default** against transcript stores and product source. Default writes are limited to
  `.agents/**`, `decisions/**`, and `loop-runs/**`, plus allowlisted harness docs only under explicit
  `harness export --apply`.
- **`.agents/` is gitignored** — normalized transcripts can contain secrets, so never commit it. Never
  commit `.env` files or credentials.
- Rosetta never runs product builds/tests/deploys, asserts behavior, or pushes/merges on its own.

## Git Workflow

- Work on a feature branch (e.g. `readiness/*` for agent-readiness fixes); never commit to `main`.
- End agent-authored commits with a `Co-authored-by:` trailer — repo convention:
  `Co-authored-by: Claude Opus 4.8 <noreply@anthropic.com>`.
- Record material technical/product/business decisions as ADR/PDR/BDR via `decisions.py`, and keep the
  library `validate --integrity` clean. Do not commit regenerable caches
  (`skills/rosetta/decisions/INDEX.json`, `.counter.json` — both gitignored).
