# Contributing to Rosetta

Thanks for helping make Rosetta read more of the world's agent history. It's pure-stdlib Python — no
build step, no dependencies.

## Run the tests

```bash
python3 -m unittest discover -s tests   # unit tests (synthetic fixtures, every agent)
python3 tests/live_smoke.py             # non-asserting counts against your real machine
python3 scripts/decisions.py --root decisions validate   # decision library is well-formed
```

## Add support for a new agent

Most additions are a registry row + a resolver; reuse a parser if the format matches an existing one.

1. **Document the store** — add a row to [`references/agent-stores.md`](references/agent-stores.md):
   root path, format, how a session is scoped to a project, and the per-message schema.
2. **Add a resolver** in `scripts/collect.py` returning `{match_mode, units, extra}` (a *unit* is a
   file, a session-dir, or a sqlite `(db, session)` pair). Reuse `probe_cwd`, `file_mentions_path`,
   `cwd_matches`, `enc_path`.
3. **Pick a parser** — if it's JSONL / a single JSON object / a bare message array, use the default
   `parse_default`. Otherwise add a `parse_<agent>` returning a session dict via `_session_dict(...)`.
4. **Register it** in the `AGENTS` dict: `{"resolver": ..., "parser": ..., "root": ...}`.
5. **Add a fixture** in `tests/fixtures/build.py` mirroring the real on-disk layout, and the test in
   `tests/test_discovery.py` picks it up automatically. Run the suite.
6. If it's installed but you have no real data, mark it UNVERIFIED via `extra={"unverified": True}`.

Store roots derive from `home()` → `$ROSETTA_HOME`, so tests sandbox the whole machine.

## Record a decision

Use the deterministic tool (it does numbering, indexing, and validation — you write the prose):

```bash
python3 scripts/decisions.py new --type adr --title "Your decision" --decider <you>
# edit the file, fill Sources with citations…
python3 scripts/decisions.py index --root decisions
python3 scripts/decisions.py validate --root decisions
```

## Conventions

- Pure stdlib; no third-party runtime deps. Keep `collect.py` schema-tolerant (count-and-skip, never
  crash on a malformed line).
- Surface gaps loudly (manifest `extra` counters); never silently drop unmatchable history.
- Don't commit `.agents/` (it holds normalized transcripts that can contain secrets — it's gitignored).
