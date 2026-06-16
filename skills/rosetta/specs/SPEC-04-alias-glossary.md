# SPEC 04 — Promote alias/entity glossary from eval prototype to shipped resolution layer

Status: DRAFT v4 (revised after adversarial review rounds 1-3; core-signal decided by owner)
Owner: Rosetta
Scope: highest-value item from the product-gap analysis ("the stated moat")

## Review history
- **R1** codex REJECT / gemini AWC: free-text query expansion manufactured false conflicts → adopted
  Direct Record Mapping.
- **R2** codex REJECT / gemini AWC: `Aliases:` text leaked into the LITERAL haystack (via
  `fields.values()` + raw file text); reviewers split on the core signal → exclude alias text from
  literal matching; **owner decided Option A** (literal `conflict` + new `resolved_unique`).
- **R3** codex AWC / gemini AWC: bounded fixes only — (a) normalization that tokenized on *all*
  non-alphanumerics collapsed `C++`/`C#` to one token and would fire a *false* hard collision; (b)
  tighten 3.2 wording (only the `Aliases:` field is excluded; body prose stays literal); (c) specify
  `--type`-scoped and invalid-chain `resolve` behavior; (d) deterministic output ordering; (e) extra
  tests. All applied below; see section 9.

## 1. Why (value)
Rosetta's own evidence (Goal-2 / PHASE0.5): a findable codename↔canonical glossary moved a weak model
(Haiku) from ~33% to ~100% on retrieval-defeating queries; `EVAL-AND-PRODUCT-ROADMAP` P0.1 names a
materialized alias index as core to the moat. Today it is only an eval prototype
(`evals/adversarial/phase0_alias_retriever.py`) plus a latent, undocumented `Aliases:` field. This ships
it deterministically without weakening resolve precision.

## 2. Current state (verified in code)
`cmd_resolve` matches `q in (title + " ".join(fields.values()))` **and** `q in raw_file_text` (the
substring path). An authored `Aliases:` value would therefore leak into the literal haystack. The
deterministic resolution + loud ambiguity flag is the core value and must not regress.

## 3. Design (v4)

### 3.1 First-class `Aliases:` field (optional, additive)
Document in `references/decision-schema.md`; add an empty optional `- Aliases:` line to the three
templates. Value is `;`-separated codenames/synonyms for the concept this record decides. No new
*required* field. v1 treats it as a **single-line** frontmatter field (multi-line not supported).
- **Alias ingestion (R4 guard):** split the field on `;`, trim each segment, **ignore blank segments**
  (`foo;;bar` → `foo`,`bar`), and **reject any non-blank segment whose normalized token list is empty**
  (e.g. `-`, `/`, `___`). A blank/absent `Aliases:` line (as in the template) contributes nothing. No
  empty normalized alias can ever enter `alias_map` or query matching.

### 3.2 Exclude the `Aliases:` FIELD from the literal haystack (R2 fix; R3 wording)
- Define `literal_haystack(rec)` = `title` + values of all fields **except `Aliases`** + the record
  **body** (raw file text with the `- Aliases: …` frontmatter line removed).
- Therefore the **`Aliases:` field text never participates** in literal matching. **Body-prose mentions
  of a codename remain legitimate literal content and DO match** (by design — that is real authored
  text, not metadata). `--no-alias-expand` then disables *all* alias influence with no field leak.

### 3.3 One shared normalization + matching rule (R3 fix)
- `normalize(s)`: casefold; replace any run of separator characters `[whitespace, '-', '_', '/', '\\']`
  with a single space; strip leading/trailing spaces. **All other characters are preserved verbatim.**
  Tokens = the normalized string split on spaces.
  - Guarantees distinct technical terms stay distinct: `C++`→`[c++]`, `C#`→`[c#]`, `.NET`→`[.net]`,
    `Node.js`→`[node.js]`, `A.1`→`[a.1]` vs `A-1`→`[a, 1]`. Equates separators: `Project-Meridian`,
    `project_meridian`, `project meridian` all →`[project, meridian]`.
  - **Documented v1 limitation (precision-safe):** sentence punctuation *adjacent* to an alias in a
    query (e.g. `meridian,` `c++.`) becomes part of the token and may prevent the alias match (an
    under-match, never a false match). Literal matching still covers such body text independently.
- **No length floor** (preserves `S3`, `CI`, `QA`, `UX`). A small **configurable `alias_stoplist`**
  (default: `api app web auth prod test db data core service`) suppresses *single-token* aliases from
  query matching only (still listed in the glossary, flagged `too_generic`); multi-token aliases are
  never stoplisted. Config `alias_stoplist` **replaces** the default wholesale (consistent with how
  `load_config` overrides top-level keys).
- **Phrase-boundary match:** an alias matches only as a contiguous run of whole tokens in the query.
- **Longest-then-leftmost greedy:** longest alias wins overlapping spans; ties break leftmost; a
  consumed span is not reused.

### 3.4 Alias-aware `resolve` — Direct Record Mapping, NO query rewriting (R2/owner decision)
- The literal matcher (alias-free per 3.2) runs unchanged. Detect alias phrases in the normalized query
  (map built from records at query time, 3.6). For each **unambiguous** alias eligible under the active
  `--type` filter: union its target **current record id** into `via_alias` with `{alias, target_id}`
  provenance. The query string is never modified; no canonical terms injected.
- For each **ambiguous** alias in the query (collision per 3.5, evaluated **within the `--type` scope**):
  inject nothing; report `alias_conflict: [{alias, candidates:[ids]}]`.
- If alias-map construction finds an **invalid chain** (3.5) for an alias present in the query, do not
  crash and do not inject; force `resolved_unique=false` and add a `note`. (`validate` is the hard gate.)
- **Output contract:**
  - `current`: literal-matched current endpoints — **byte-stable** with today's shape (no `match` tag).
  - `conflict` (bool): **literal-only**, unchanged (>=2 distinct current endpoints among literal
    matches). Computed from literal `current` **before** any `via_alias` union. Alias logic never flips it.
  - `via_alias`: unambiguous-alias endpoints (+provenance), **deduped against `current`** (a record
    matched both ways appears once, in `current`), **sorted by record id** (deterministic).
  - `alias_conflict`: present only on a queried ambiguous alias; entries **sorted by alias then id**.
  - `resolved_unique` (bool, owner-decided safety signal): **true iff** exactly one distinct current
    endpoint across `current ∪ via_alias` **and** no `alias_conflict` **and** no invalid-chain note.
    False on any ambiguity (0 matches, disjoint literal+alias, multiple unambiguous aliases to different
    records, ambiguous alias, invalid chain). The single authoritative "did this uniquely resolve?"
    check; it does not change `conflict`.
- `--no-alias-expand` fully disables alias logic: no `via_alias`/`alias_conflict`; `resolved_unique`
  reflects literal matches only; `current`/`conflict` byte-identical to pre-feature output.

### 3.5 Collision = HARD ERROR, on collapsed chains (R2; R3 scope)
- Build `alias_map: normalize(alias) -> set(current endpoint ids)`, each declaring record's alias mapped
  to its **current endpoint** via `resolve_current` (aliases along one chain collapse to the single live
  endpoint; converging chains `A→C`,`B→C` = one endpoint = NOT a collision).
- **Collision = one normalized alias → >=2 DISTINCT current Accepted endpoints** after collapse.
- **Invalid-chain guard:** if `resolve_current` cannot reach exactly one Accepted endpoint (forked
  successors, or contradictory `Status: Superseded by X` vs successor `Supersedes: Y`), do not silently
  collapse — surface a **validate error**.
- **Scope:** `validate` collision/invalid-chain checks are **global** (type-agnostic) and a **hard
  error** (`validate` exits non-zero even without `--strict`). `resolve` evaluates ambiguity **within
  its `--type` scope** (an alias that spans types is unambiguous when `--type` narrows it to one).

### 3.6 Emission, freshness, CLI surface (R2 cut)
- **No standalone `glossary` subcommand.** `cmd_index` emits two derived artifacts via the shared
  builder: `GLOSSARY.md` (human table: Alias | Canonical concept | Record id | Status) and
  `GLOSSARY.json` (machine map + top-level `_alias_conflicts`, both deterministically sorted).
- `index` is a generator (exit 0) but prints any collision/invalid-chain **loudly to stderr** (never
  silent), pointing to `validate` as the gate. `validate`/`resolve` build the alias map **from records**
  each run; **no one reads `GLOSSARY.json` as a cache** (derived-only; cannot drift).

### 3.7 Moat claim, honestly scoped
v1 ships **field-authored** aliases as the deterministic primitive. Reading a *prose* glossary and
deciding the codename→concept mapping is the **collector/ingest** step's job (it isolates non-determinism
to the agent) and materializes codenames into `Aliases:`. We do not claim automatic prose extraction here.

### 3.8 Non-goals / cut for v1
Prose-glossary parsing; multi-line `Aliases:`; stable `entity_id`; merge/split CLI; scoped/team aliases;
bridged-conflict promotion (covered by `resolved_unique`); `match` tag on `current`; standalone `glossary`.

## 4. File-level changes
- `scripts/decisions.py`: add `normalize`, `literal_haystack(rec)`, `build_alias_map(records,cfg) ->
  (map, collisions, invalid_chains)`, `find_query_aliases(query, alias_map, stoplist)`; wire into
  `cmd_resolve` (Direct Record Mapping + `resolved_unique`, `--type` scope, invalid-chain note),
  `cmd_validate` (hard-error collisions + invalid chains, global), `cmd_index` (emit `GLOSSARY.*`, loud
  warnings); add `--no-alias-expand`; read optional `alias_stoplist`. ~220-260 LOC, pure stdlib.
- `references/decision-schema.md`: document `Aliases:` + normalization limitation + stoplist semantics.
- `templates/{adr,pdr,bdr}-template.md`: optional `- Aliases:` line.
- `decisions/config.json`: document optional `alias_stoplist` (replaces default; absent ⇒ default).
- `tests/test_glossary.py` (new): section 6.
- `decisions/architecture-decisions/00NN-alias-glossary-resolution-layer.md`: the ADR.
- `SKILL.md`: one workflow line; note `index` emits `GLOSSARY.*`.
- Regenerate `decisions/README.md` + `INDEX.json` (+ new `GLOSSARY.*`).

## 5. Backward compatibility
Additive: `Aliases:` optional; alias logic default-on but disable-able; `current`/`conflict` byte-stable
(new keys `via_alias`/`alias_conflict`/`resolved_unique` additive); no standalone command; no format
break; no new dependencies.

## 6. Test plan (`tests/test_glossary.py`)
Core-value / regression:
- **Golden regression:** previously-precise queries return identical `current` and `conflict` with the
  feature on vs `--no-alias-expand`.
- **Haystack exclusion:** `--no-alias-expand` + a query equal to an alias does NOT match the declaring
  record via fields OR raw text; **body-prose** fixture — same codename in `Aliases:` AND in body — still
  literal-matches via the body (and via field only when alias logic is on).
- Stoplisted single-token alias ignored for matching; 2-letter acronym (`S3`,`CI`) preserved + matches.
- **Normalization:** `-`/`_`/`/` variants equal; **`C++` vs `C#` vs `.NET` do NOT collapse**; `A.1` vs
  `A-1` do NOT false-collide; longest-then-leftmost (`Project Meridian` beats `Meridian`; `A B` vs `B C`
  in `A B C`); alias not matched inside a larger token (`Meridians`).
Mapping / collision / chains:
- **empty/separator-only aliases** (blank `Aliases:`, `foo;;bar`, a `-`-only segment) contribute no
  aliases, never enter `alias_map`, and never collide (R4 guard);
- duplicate alias on same record idempotent; same alias along ONE chain → one endpoint (no collision);
  same alias on TWO live endpoints → `_alias_conflicts` + `validate` exit 1 without `--strict`;
  **forked successors** and **mismatched `Superseded by`/`Supersedes`** → validate error (no silent
  collapse); alias only on `Superseded` record → maps to live successor (or "no current endpoint").
- **`--type`-scoped collision:** same alias across ADR and PDR → global `validate` collision, but
  `resolve --type adr` resolves it unambiguously to the ADR endpoint.
resolve behavior:
- unambiguous alias → `via_alias` populated, `conflict` unchanged, `resolved_unique` per union;
- **disjoint** literal + alias to different records → `conflict` literal-only; `resolved_unique=false`;
- **multiple unambiguous aliases → different records** → `resolved_unique=false` (union>1);
- ambiguous alias → `alias_conflict` populated, nothing injected, `resolved_unique=false`;
- same record literal+alias → deduped, `resolved_unique=true`;
- **deterministic ordering** of `via_alias`/`alias_conflict`; missing/malformed `GLOSSARY.json` does not
  affect `resolve`.
Then full suite + `validate --integrity --staleness` on the repo's own library; no regressions.

## 7. Open questions for round-4 reviewers
1. Is the v4 normalization rule (`[\s\-_/\\]` separators, preserve all else) + documented
   adjacent-punctuation under-match acceptable, or any remaining false-collision/over-match path?
2. Any remaining path by which alias logic can weaken `conflict` or resolve precision?
3. Is the `--type` scoping (global `validate` collision, scoped `resolve`) the right split?

## 8. (reserved)

## 9. Round-3 issue → resolution map
- *normalize collapsed `C++`/`C#` → false hard collision* → 3.3 preserves all non-separator chars; tests
  lock `C++`≠`C#`≠`.NET`, `A.1`≠`A-1`.
- *3.2 wording overclaimed ("alias text")* → now "the `Aliases:` FIELD text"; body prose stays literal.
- *unspecified `--type`/invalid-chain resolve behavior* → 3.4/3.5 specify scoped resolve, global hard-gate
  validate, invalid-chain → no inject + `resolved_unique=false` + note.
- *nondeterministic output* → `via_alias`/`alias_conflict`/glossary deterministically sorted (3.4/3.6).
- *missing tests* → section 6 adds body-prose, `--type` collision, forked/mismatched chains, punctuation
  no-collapse, multi-alias union, deterministic-order.
