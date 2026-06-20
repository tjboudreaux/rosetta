# Decision-record schema & customization

Rosetta emits three kinds of durable decision records, all sharing one format:

| Type | Name | Captures | Default dir |
|---|---|---|---|
| **ADR** | Architecture Decision Record | *how* the system is built (technical/structural) | `architecture-decisions/` |
| **PDR** | Product Decision Record | *what* we make and why (product/content/strategy) | `product-decisions/` |
| **BDR** | Business Decision Record | business/commercial calls — often made by humans in a meeting or thread | `business-decisions/` |

A library lives under a **decisions root** (rosetta's own is `decisions/`) containing the three
record dirs, an `index` file (`README.md`), and an optional `config.json`. Records are authored from
`templates/{adr,pdr,bdr}-template.md` and managed by the deterministic `scripts/decisions.py`.

## Record format (locked to the canonical "rosetta format")

Heading + a **bullet-list frontmatter** (not YAML), then fixed body sections:

```markdown
# ADR NNNN — <short title>

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-05-29    (optional — when the call was actually made, if backdated)
- Reviewed: 2026-06-18             (optional — last date a human/agent confirmed this against its cited code; see below)
- Decider: Travis
- Sources: `claude · <session-id> · <date>` (verified); `git <sha> · <date>`
- Related: ADR NNNN; scripts/path.py function_name

## Context
## Decision
## Consequences      (Positive: / Negative:)
## Open questions    (optional)
## Alternatives considered
## Related
```

### Frontmatter fields

- **Required:** `Status`, `Date`, `Decider`.
- **Recommended:** `Sources` — provenance, the thing that makes a record trustworthy. Cite as
  `` `agent · session-id · date` `` (Rosetta's transcript citation), a git commit, a code path, a
  meeting note, or a task id. Multiple sources are comma-separated.
- **Optional:** `Decided originally` (when the call was actually made, if the record is backdated),
  `Reviewed` (freshness acknowledgment — see below), `Related`, `Supersedes`, `Aliases`
  (codenames/synonyms for the concept — see below), plus loop-gate fields `Human gated paths`,
  `Human approval for`, `Evidence for`, and `Evidence artifacts`.

### Loop-gate fields

`rosetta gates check` reads these parseable fields; it never infers approval or evidence from prose:

- **`Human gated paths`** — on an Accepted ADR/PDR, semicolon-separated repo-relative `fnmatch`
  patterns such as `src/payments/**; docs/MOBILE.md`. A changed matching path requires an explicit
  `--change-id` and an Accepted approval record.
- **`Human approval for`** — on an Accepted ADR/PDR/BDR, exact change id approved by the human
  decider. A matching record must also have non-empty `Sources` and the normal required `Decider`.
- **`Evidence for`** — on an Accepted ADR/PDR/BDR, exact change id covered by a local UI evidence
  artifact.
- **`Evidence artifacts`** — semicolon-separated local artifact refs of the form
  `screenshot:<repo-path>` or `video:<repo-path>`. The gate checks only that the referenced local
  file exists under the project; it does not inspect screenshots/videos or assert behavioral proof.

### Signal ingest fields

`rosetta ingest --schema auto|signals` maps validated product signals to `Status: Proposed` records.
Signal ids appear in `Sources:` as ``signal:<id>``; public/internal raw refs are added as additional
backticked sources. `pii` and `sensitive` signals are refused unless `--allow-sensitive` and
`redacted: true` are both present; redacted records store `[redacted: <privacy_class> signal]` and no
raw refs beyond the signal id.

### Harness export contract

`rosetta harness export` consumes only `rosetta-harness-export/v1` JSON and writes only between
`<!-- ROSETTA:HARNESS:START -->` / `<!-- ROSETTA:HARNESS:END -->` markers in allowlisted docs:
`ARCHITECTURE.md`, `docs/MOBILE.md`, and `domains/<single-kebab-slug>/README.md`.

### Status lifecycle

`Proposed → Accepted → Superseded by <ID>` (or `Deprecated` / `Rejected`). **Every reversal is
recorded**: when a new record overturns an old one, the old record's `Status` becomes
`Superseded by <ID>` and the new one names it under `## Related` / `Supersedes`. The library never
silently oscillates — this is the same "no silent contradictions" discipline as `ground-truth.md`.

### Provenance & the truth hierarchy

Records inherit Rosetta's truth hierarchy: **current code / git > committed decisions > docs >
latest conversation > older conversation.** A decision a transcript merely *discussed* is recorded
as `Status: Proposed` (or noted "discussed/intended"), not asserted as Accepted, until code or an
explicit human call confirms it.

### `Reviewed:` — freshness acknowledgment

The optional **`Reviewed:`** field records the last date a human or agent confirmed an Accepted
decision is still current against its cited code. It is the adjudication step the staleness guard
(`decisions.py staleness`) was missing: without it, a record whose cited code changed in git is
re-flagged stale on every run, even after someone reviewed and confirmed it.

```markdown
- Reviewed: 2026-06-18
```

- **Format** — a single `YYYY-MM-DD` date, ≤ today. Malformed or future values are ignored by the
  staleness check (which falls back to the effective date) and surfaced as a warning by `validate`.
  A `Reviewed:` date before the decision's effective date is also a warning (nonsensical).
- **Semantics — a baseline, not a permanent override.** The staleness comparison uses `Reviewed:` as
  the baseline when present: a cited code path whose last git commit is *after* the `Reviewed:` date
  is stale again. So a review is only good until the code moves once more — it does not exempt a
  record from future drift, it just records that the last change was reviewed and found
  non-contradicting.
- **What it does not change** — `Date`, `Decided originally`, `Status`, and supersession are
  untouched. The decision timeline is preserved; `Reviewed:` is a freshness-layer annotation only.
- **Surfaces** — `staleness`, `validate --staleness`, and `resolve`'s stale flag all honor
  `Reviewed:` via the shared `staleness_for_record` baseline. The JSON output carries `reviewed` and
  `baseline_date` on each assessed entry so a consumer can see which date drove the comparison.

### Aliases & the glossary (codename resolution)

Real teams refer to a decision by a **codename** ("Project Meridian", "the new pipeline", "Zephyr"),
not its ADR number. The optional **`Aliases:`** field captures those names so a codename query
resolves to the live decision instead of silently missing it:

```markdown
- Aliases: Project Meridian; the new pipeline; Zephyr
```

- **Format** — a single line, `;`-separated. Blank or separator-only segments are ignored, so the
  empty template line contributes nothing.
- **Normalization** — case-insensitive; runs of whitespace, `-`, `_`, `/`, `\` collapse to one
  space. Everything else is preserved, so `Project-Meridian` == `project_meridian` while `C++`, `C#`,
  and `.NET` stay distinct (no false collisions).
- **Resolution (`resolve`)** — an alias in the query adds its target under `via_alias` (following
  supersession to the current record). The literal `conflict` flag is unchanged (literal-text matches
  only); a separate **`resolved_unique`** flag is `true` only when the whole query — literal hits
  *and* alias targets — points to exactly one current decision. An alias mapping to two different
  current decisions is reported under `alias_conflict`, never silently merged. `--no-alias-expand`
  turns the layer off (literal matching only).
- **Uniqueness is enforced** — `validate` is a **hard error** (fails CI even without `--strict`) when
  one normalized alias maps to two or more distinct current decisions, or when an aliased record sits
  on a forked/contradictory supersession chain. An ambiguous codename is a defect, not a warning.
- **Generic single words are suppressed** — a one-word alias on the `alias_stoplist`
  (`api app web auth prod test db data core service` by default; override wholesale in `config.json`)
  will not match, so a query for "api" is not hijacked. Multi-word aliases are never suppressed.
- **The glossary** — `index` writes `GLOSSARY.md` (human) and `GLOSSARY.json` (machine): the derived
  codename → decision map, plus any ambiguous codenames printed loudly. Both are regenerated from the
  records on every run — never a cache.

### Library health (`coverage`)

`decisions.py coverage` prints a deterministic JSON health report so a library's *trustworthiness* is
measurable, not assumed (ADR 0026). It reads only the records on disk and never mutates them.

- **`anchoring` (primary, gateable)** — the share of **Accepted** records whose `Sources:` cite at
  least one real code path (matched by **exact relative path**, file or directory, under the repo
  boundary — never by basename, so a citation can't anchor to an unrelated sibling file). `rate` is the
  rounded headline; `rate_raw` is the exact value the gate compares; `unanchored` lists the gaps. This
  is the closest deterministic proxy for "does this decision point at the code it governs?"
- **`supersession`** — status distribution plus active/retired counts and chain depth (how deeply
  decisions have been revised); a reported signal, not a gate.
- **`retrieval.ambiguous_topics`** — a non-gated **diagnostic**: each Accepted record's own title is
  resolved; any that don't resolve to a unique record (a literal or alias collision) are listed with
  the ids they `collides_with`, so a human can disambiguate or add an alias.
- **`orphans`, `staleness`, `alias_coverage`** — supporting structural signals (unlinked records;
  git-detected drift, skipped cleanly when git is absent; share of records carrying a codename).
- **Gate** — report-only by default. `--min-coverage FLOAT` (in `[0,1]`) fails with a nonzero exit if
  `anchoring.rate_raw` is below the floor; a null rate (no Accepted records) is skipped, never an error.

## Customize for your team

Drop a `config.json` in your decisions root (see `decisions/config.json` for the annotated default).
Everything is overridable; omit `config.json` entirely to take the rosetta defaults.

- `record_types` — add/rename types (e.g. a `gov` Governance record), point each at a `dir` and a
  `template`. `label` is the ID prefix shown in files (`ADR`, `PDR`, …).
- `number_width` — zero-padding for IDs (default 4 → `0007`).
- `statuses` — the allowed `Status` values `validate` enforces.
- `required_fields` / `recommended_fields` / `optional_fields` — your frontmatter contract.
- `index.path` + `index.columns` — where the timeline index is written and its columns.
- `alias_stoplist` — single-word aliases to ignore during codename resolution (your override
  *replaces* the default list wholesale).
- `template` paths resolve relative to the decisions root; if absent, `decisions.py` falls back to
  the rosetta skill's `templates/<type>-template.md`, so a team can adopt the format with zero files
  copied, then override a template only when they want to diverge.

Teams keep their existing ADR conventions by editing this one file — the tooling and the Rosetta
workflow adapt to it, not the other way around.
