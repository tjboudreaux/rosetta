# SPEC-03 — Decision-library coverage / health metric

Status: v4 (post-R3 — review gate SATISFIED: both reviewers APPROVE WITH CHANGES, all changes folded,
no split). Reviewers: codex + gemini (adversarial gauntlet, same protocol as SPEC-04).
Scope: Part-D recommendation #3 — a **decision-coverage / library-health metric**. Confirmed with the
maintainer: library-health *proxies* computed from the records + git, no external gold set. Headline
**gated** metric is **ADR-coverage (provenance-anchoring)**; **supersession-rate** is a reported signal;
**agent-retrieval** ships as a **diagnostic** (ambiguous-topics list), not a gated rate. Report-only
JSON by default, with an **optional** `--min-coverage` threshold that exits nonzero (a CI gate,
mirroring ADR 0019's test-coverage gate but for decisions).

> NOTE TO REVIEWERS: this is a **pre-implementation DESIGN spec**. The `coverage` command and
> `resolve_query`/`assess_coverage`/`cmd_coverage` do **not** exist in `decisions.py` yet — that is
> expected. Review the **design's soundness**, not whether it is already implemented.

## Review history

- **R1** codex APWC / gemini APWC (strong convergence). Agreed fixes folded into v2: `resolve_query`
  returns `current_recs`/`invalid_note`/`matched_records` and does not reorder `current`; anchoring by
  **exact relative path** (file or dir), no basename/`rglob`; null-rate + raw-vs-rounded gate defined;
  `code_areas_*` cut. Both rejected full-title self-retrievability as a headline rate → **escalated**;
  maintainer chose **Option A** (ship agent-retrieval as a non-gated diagnostic; gate only anchoring).
- **R2** gemini APWC (3 refinements, folded into v3): (1) anchoring must **not** reuse `_source_roots`
  (it adds `root.parent` unconditionally → outside git a citation could anchor to an unrelated sibling
  project); scope anchor roots to the repo boundary. (2) bare directory citations without a slash
  (`Sources: scripts`) are dropped by the path heuristic → false-unanchored; add a directory addendum.
  (3) supersession-depth must be defined **per-origin-record** via `resolve_current` (not "at"
  intermediate nodes, which needs a reverse DAG). codex R2 misfired (reviewed for code presence rather
  than design) → re-reviewed on v3 with the note above.
- **R3** codex APWC / gemini APWC (both confirm anchoring, depth, the non-gated diagnostic, and the
  refactor are sound; remaining items folded into v4): gemini — `resolve_query` must take `root`
  (needed for `path: cur["path"].relative_to(root)`). codex — (1) expose the **raw** gated rate, not
  just the rounded display; (2) **drop `--status`** for v1 (the `accepted_*` field names imply a fixed
  denominator); (3) define retrieval `collides_with` precisely for alias-conflict ambiguity; (4)
  strengthen the parity test to compare **full** `cmd_resolve` JSON. No reviewer split → gate satisfied.

## 1. Problem

`decisions.py` can validate structural integrity (ADR 0024), flag staleness (Goal-4), and resolve
queries (ADR 0021 + the alias layer, ADR 0025), but it cannot answer **"is this decision library
healthy and trustworthy as an oracle?"** A library can pass `validate` yet be a poor oracle: decisions
with no code/git provenance (floating claims), runaway supersession churn, or topics whose text
overlaps so an agent's query can't land uniquely. There is no single deterministic health read, and
nothing CI can gate decision-library quality on (the existing coverage gate is *test* coverage,
ADR 0019 — a different thing).

## 2. Non-goals

- No external "gold set" of decisions-that-should-exist; no LLM scoring. Deterministic, pure-stdlib
  (subprocess to git only, ADR 0013), degrading cleanly when git is absent.
- Not a replacement for `validate`/`integrity`/`staleness`; `coverage` *reuses* them. It never mutates
  records.
- No trend/history storage. One library → one report.

## 3. Design

New subcommand `decisions.py coverage` → deterministic JSON. The denominator for the headline rate is
**Accepted records** (the live oracle); overall counts are also reported. Every record set is listed by
id (sorted) so a human/CI can act, not just see a number.

### 3.1 ADR-coverage = provenance / code-anchoring (PRIMARY, gated)

A decision with no verifiable code/git provenance is a floating claim. A record is `code_anchored` iff
its `Sources:` cites ≥1 path that resolves by **exact relative path** under an **anchor root** — file
or directory — and the resolved real path is **inside the repo boundary**.

**Anchor roots (R2 fix — repo-bounded, deterministic, not `_source_roots`):**
- `repo_root = _git_repo_root(root)` (may be None).
- candidate roots, in order, de-duped: `root`, then `root.parent`.
- a candidate is kept iff `repo_root is None` **or** the candidate is inside `repo_root`. When git is
  present, additionally every *resolved citation path* must be inside `repo_root` (blocks `../` escapes
  and the sibling-project leak). When git is absent, anchor roots are `[root, root.parent]` (best-effort,
  same posture as integrity's git-absent fallback; documented limitation).
  *(Rationale: a decisions library commonly sits at `<project>/decisions`, so code citations are
  relative to `<project>` = `root.parent`; this is rosetta's own layout. The repo-boundary clamp keeps
  that working while preventing resolution outside the project.)*

**Candidate path tokens** from `Sources:` = the union of:
- `extract_source_paths(Sources)` (handles backticked + slashed/extensioned paths; already ignores
  transcript citations like `claude · id · date`), and
- **directory addendum (R2 fix):** any comma/semicolon/whitespace-split token from `Sources` that, as
  written, resolves to an **existing directory** by exact relative path under an anchor root. This
  catches a bare `Sources: scripts` (no slash) that the path heuristic otherwise drops. Tokens that are
  not existing dirs are ignored (so prose words can't false-anchor).

Output:
- `anchoring.accepted_anchored` / `accepted_total`; `anchoring.rate` (displayed, rounded 3dp) **and**
  `anchoring.rate_raw` (full precision — the value the gate compares, so the gate decision is always
  transparent and reproducible from the JSON; R3 codex fix).
- `anchoring.unanchored` — sorted Accepted ids citing no resolvable path (records sourced only to
  transcripts/commits are not *code*-anchored by design and appear here).
- `anchoring.all_anchored` / `all_total` — whole-library counts, informational.

`code_areas_*` from v1 is **cut** (both reviewers: ungated noise; no sound definition of "code dir").

### 3.2 supersession-rate (reported signal, NOT gated)

Pure frontmatter + supersession-graph stats:

- `status_distribution` — count per normalized bucket: `accepted`, `proposed`, `superseded`,
  `deprecated`, `rejected`, `other`. A Status starting with "superseded by" → `superseded`.
- `supersession.active` = accepted; `supersession.retired` = superseded+deprecated+rejected;
  `supersession.rate` = retired / records_total (`null` if 0 records).
- **chain depth (R2 fix — per-origin-record, computable via `resolve_current`):** for each record `r`,
  forward-walk its `Status: Superseded by …` chain to the endpoint; `depth(r)` = number of hops =
  `len(chain)` returned by `resolve_current(records, r, cfg)` (already cycle-safe). `max_chain_depth` =
  `max(depth(r))` over all records (0 if nothing is superseded). `mean_chain_depth` = mean of `depth(r)`
  over records with `depth(r) ≥ 1` (the superseded ones); `null` if none. Example A→B→C: depth(A)=2,
  depth(B)=1, depth(C)=0 → `max=2`, `mean=1.5`.

Never gated (both high and low churn can be healthy) — a signal for humans.

### 3.3 agent-retrieval = ambiguous-topics DIAGNOSTIC (NOT a rate, NOT gated)

Maintainer-selected Option A after both reviewers rejected a full-title *rate*. For each **Accepted**
record, query `resolve_query` with that record's own **title**; if the result is not `resolved_unique`,
or its single endpoint is not that record, add it to `retrieval.ambiguous_topics` as
`{id, title, collides_with:[ids]}`. **`collides_with` is defined precisely (R3 codex) as**
`sorted((endpoints ∪ {each alias_conflict candidate id}) − {self})` — so an ambiguity arising from an
`alias_conflict` (where the title text is itself a colliding alias, and the candidates are NOT in
`endpoints`) is still reported with its colliding ids. This surfaces decisions whose topic *text
overlaps* others (a benign cross-reference, or a genuine duplicate/conflict) so a human can disambiguate.

- Explicitly a **diagnostic**, not a quality percentage: honestly noisy (a record whose title another
  live record quotes will appear), so **never** a headline rate and **never** gated.
- `retrieval.ambiguous_count` = len(list); `retrieval.checked` = Accepted count. No rate field.
- Reuses `resolve_query` verbatim, so the diagnostic and real `resolve` can never diverge; supersession
  collapse is whatever `resolved_unique` already does (no separate claim).

### 3.4 Refactor: extract a reusable `resolve_query` core (DRY, byte-identical `resolve`)

Extract the pure resolution out of `cmd_resolve` (no git/freshness, no printing):

```python
def resolve_query(records, cfg, root, text, type_filter=None, no_alias=False):
    """Pure resolution. `root` is needed to build each entry's `path` (relative_to(root)). Returns:
       {current: {id: entry},        # dict, INSERTION ORDER preserved (cmd_resolve depends on it)
        current_recs: {id: rec},      # live record objects, for cmd_resolve's freshness pass
        conflict: bool,               # len(current) > 1 (literal-only)
        via_alias: [...], alias_conflict: [...],
        resolved_unique: bool,
        invalid_note: str|None,
        matched_records: int,
        endpoints: set(ids)}          # current ∪ via_alias target ids (for coverage)
    """
```

`cmd_resolve` becomes: call `resolve_query`, then run the existing freshness annotation over
`current_recs`, assemble notes (using `conflict`/`alias_conflict`/`invalid_note`) and the JSON in the
**current order**, and print. Output **byte-for-byte unchanged** — the SPEC-04 resolve tests and the
existing resolve tests must pass untouched. `resolve_query` sorts nothing in `current`; `coverage`
sorts its own derived id lists.

### 3.5 Structural / supporting fields (informational, not gated)

- `orphans` — Accepted record ids with no outbound link (`Related`/`Supersedes` naming a real record)
  **and** no inbound link (named by no other record's `Status`/`Supersedes`/`Related`).
- `staleness` — when git is available, reuse `assess_staleness` over Accepted records: `{git:true,
  checked, stale, unknown, stale_ids:[...]}`; `{git:false, skipped:true}` when git is absent (never a
  false "0 stale").
- `alias_coverage` — Accepted records with a non-empty `Aliases:` / total (ties to ADR 0025).

### 3.6 Output shape + the optional gate

```jsonc
{
  "root": "decisions",
  "records_total": 30,
  "accepted_total": 27,
  "anchoring": { "accepted_anchored": 25, "accepted_total": 27, "rate": 0.926, "rate_raw": 0.9259259259,
                 "unanchored": ["BDR 0001","PDR 0003"], "all_anchored": 26, "all_total": 30 },
  "supersession": { "active": 27, "retired": 3, "rate": 0.1, "max_chain_depth": 2, "mean_chain_depth": 1.5 },
  "status_distribution": { "accepted": 27, "superseded": 2, "deprecated": 0, "rejected": 1, "proposed": 0, "other": 0 },
  "retrieval": { "checked": 27, "ambiguous_count": 1,
                 "ambiguous_topics": [ {"id":"ADR 0024","title":"…","collides_with":["ADR 0025"]} ] },
  "orphans": ["BDR 0001"],
  "staleness": { "git": true, "checked": 27, "stale": 0, "unknown": 1, "stale_ids": [] },
  "alias_coverage": { "with_aliases": 1, "accepted_total": 27, "rate": 0.037 },
  "thresholds": { "min_coverage": null },
  "failures": [],
  "ok": true
}
```

- `--min-coverage FLOAT` gates **`anchoring.rate`** only. argparse-validated to `[0,1]`.
- Gate compares the **raw** (unrounded) rate; only displayed rates are rounded to 3dp (so a printed
  `0.950` can't disagree with a raw `0.9496` comparison).
- If `anchoring.rate` is `null` (no Accepted records), any `--min-coverage` is **skipped** (vacuously
  satisfied — no `None < float` crash), with a note.
- A supplied-and-violated threshold appends a human-readable string to `failures`; `ok = (failures ==
  [])`. **Exit 1 iff `failures` non-empty**; with no `--min-coverage` the command is informational
  (exit 0).
- `--root` like every subcommand. (`--status` override is **out of scope for v1** — the denominator is
  always Accepted, matching the `accepted_*` field names; R3 codex. Revisit with neutral field names if
  a team needs to gate a different lifecycle stage.)
- Determinism: all id arrays sorted; displayed floats rounded to 3dp (raw kept in `rate_raw`); two runs
  byte-identical.

## 4. Files

- `scripts/decisions.py`: `resolve_query` extraction (3.4); `_anchor_roots(root)` + an
  `assess_coverage(records, cfg, root)` → report dict; `cmd_coverage`; argparse `coverage`
  subparser (`--root`, `--min-coverage`). Reuse existing helpers; no new module-level deps.
- `tests/test_coverage.py`: section-6 cases.
- `references/decision-schema.md` + `SKILL.md`: document `coverage` (one paragraph each).
- `decisions/architecture-decisions/0026-decision-coverage-metric.md`: the ADR.
- Regenerate `decisions/README.md` + `INDEX.json` (+ `GLOSSARY.*`).

## 5. Compatibility / safety

Purely additive: a new read-only subcommand + an internal refactor that preserves `resolve` output
byte-for-byte. No record mutated. Pure stdlib; anchoring is git-independent (exact-path, repo-bounded
when git is present); staleness is git-optional with explicit `skipped` (never a false pass). Default
invocation exits 0; only an explicit, violated `--min-coverage` exits nonzero.

## 6. Test plan (tests/test_coverage.py)

1. **resolve_query parity (full JSON, R3 codex)** — for several fixture libraries/queries (single hit;
   literal conflict; alias hit; alias_conflict; superseded chain with `replaced`/`superseded_from`),
   capture `cmd_resolve`'s **entire** JSON object and assert it is unchanged by the refactor — every
   key: `current` (and its order), `via_alias`, `alias_conflict`, `resolved_unique`, `matched_records`,
   `conflict`, notes, and freshness fields. The existing SPEC-04 + resolve tests must also pass
   unmodified.
2. **anchoring (exact path, file)** — a record citing `scripts/x.py` that exists is anchored.
3. **anchoring (exact path, directory with slash)** — citing `scripts/` (real dir) is anchored.
4. **anchoring (bare directory, no slash)** — `Sources: scripts` (real dir, no slash) is anchored
   (R2 directory addendum).
5. **anchoring negatives** — citing only a transcript, only a non-existent bare basename, or a ghost
   path → `unanchored`; a prose word that isn't a real dir does not false-anchor.
6. **anchor-root boundary** — a citation that would only resolve OUTSIDE the git repo boundary (e.g.
   `../sibling/x.py`) is NOT counted as anchored.
7. **anchoring denominator is Accepted-only** — a Proposed unanchored record does not lower the rate.
8. **supersession** — A→B→C reports `retired`=2, `active`=1, `max_chain_depth`=2, `mean_chain_depth`=1.5;
   `status_distribution` buckets a `Superseded by` Status as `superseded`.
9. **retrieval diagnostic** — a record with a unique title is NOT in `ambiguous_topics`; two Accepted
   records sharing a literal title phrase both appear with each other under `collides_with`.
10. **orphans** — a linked pair are not orphans; a record with no in/out links is.
11. **alias_coverage** — reflects the fraction of Accepted records with a non-empty `Aliases:`.
12. **gate** — `--min-coverage` above the actual rate ⇒ `failures` non-empty + exit 1; below ⇒ exit 0;
    no flag ⇒ exit 0 regardless of rate.
13. **threshold validation** — `--min-coverage 1.5` is an argparse error.
14. **null-rate gate** — empty library (or zero Accepted) with `--min-coverage 0.8` does NOT crash and
    does NOT fail (rate `null`, threshold skipped, `ok=true`).
15. **no-git degradation** — outside a git work tree: `staleness` is `{git:false, skipped:true}`,
    anchoring still works by exact-path, no crash.
16. **determinism** — all listed id arrays sorted; floats rounded to 3dp; two runs identical output.

## 7. Resolved questions

- *Headline agent-retrieval proxy* (R1, both reviewers): resolved → **Option A**, a non-gated
  ambiguous-topics diagnostic. No keyphrase heuristic, no dubious percentage.
- *Anchor-root scope* (R2 gemini): resolved → repo-bounded `_anchor_roots`, not `_source_roots`.
- *Bare directory citations* (R2 gemini): resolved → directory addendum to candidate tokens.
- *Supersession depth* (R2 gemini): resolved → per-origin-record via `resolve_current`.
