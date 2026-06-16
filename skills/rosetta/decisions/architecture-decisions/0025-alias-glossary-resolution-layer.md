# ADR 0025 — Alias/glossary codename-resolution layer

- Status: Accepted
- Date: 2026-06-16
- Decider: Travis Boudreaux
- Sources: scripts/decisions.py, tests/test_glossary.py, specs/SPEC-04-alias-glossary.md
- Related: ADR 0021 (scalable decision store / `resolve`), ADR 0024 (anti-hallucination integrity gate), ADR 0009 (deterministic decisions tooling), ADR 0020 (decision-library hardening)
- Aliases: alias layer; codename resolution; the glossary

## Context

Rosetta's whole value is *resolving a query to the one live decision*. But teams do not refer to a
decision by its ADR number — they use a **codename** ("Project Meridian", "the new pipeline",
"Zephyr"). A literal-substring `resolve` silently misses every codename query, which is the same
confidently-wrong-oracle failure ADR 0024 closed for fabricated provenance, just on the read path.

A latent `Aliases:` field was already half-wired (`resolve` printed it; nothing populated, documented,
normalized, or validated it), and an eval prototype (`evals/adversarial/phase0_alias_retriever.py`)
showed codename retrieval was the highest-value missing primitive. The risk in promoting it is
**precision**: a naive implementation that expands the query with canonical-title terms manufactures
false conflicts, and an alias that maps to two live decisions silently misresolves. The design was
hardened across four adversarial-review rounds (codex + gemini) recorded in
`specs/SPEC-04-alias-glossary.md`; two reviewer-split decisions were escalated and resolved by the
maintainer (literal-only `conflict` + a new union-aware `resolved_unique`).

## Decision

Promote aliases to a shipped, precision-safe resolution layer built on **Direct Record Mapping** — the
query is never rewritten; an alias maps straight to a record id.

1. **`Aliases:` field** — optional, single-line, `;`-separated. `normalize_alias` casefolds and
   collapses only separator runs (`[\s\-_/\\]`), preserving everything else so `Project-Meridian` ==
   `project_meridian` while `C++`, `C#`, `.NET` stay distinct. Blank/separator-only segments are
   dropped, so the empty template line and `foo;;bar` contribute nothing.
2. **Literal/alias signal split** — the `Aliases:` *field* text is excluded from the literal haystack
   (it matches only via the map; body-prose mentions still match literally). `conflict` stays
   literal-only (byte-stable). A new top-level **`resolved_unique`** is true only when the whole query
   — literal hits plus alias targets — resolves to exactly one current decision; unambiguous aliases
   add their target under `via_alias`, ambiguous ones are reported under `alias_conflict` (never
   merged). `--no-alias-expand` disables the layer.
3. **Uniqueness is a hard gate** — `validate` errors (exits nonzero even without `--strict`) when one
   normalized alias maps to ≥2 distinct current decisions, or when an aliased record sits on a forked
   or self-contradictory supersession chain. Converging chains (A→C, B→C) collapse to one endpoint and
   are *not* a collision. A single-word `alias_stoplist` suppresses generic tokens (`api`, `db`, …).
4. **Derived glossary** — `index` emits `GLOSSARY.md` (human) and `GLOSSARY.json` (machine) and prints
   ambiguous codenames loudly on stderr. `resolve`/`validate` rebuild the map from records every run;
   the artifacts are derived output, never a cache.

Scope is field-authored aliases only; automatic prose-glossary extraction is deferred to the
collector/ingest path.

## Consequences

Positive:
- Codename queries resolve to the live decision, and an ambiguous codename is now a falsifiable,
  CI-gateable defect rather than a silent misresolution.
- Fully additive: alias-free libraries resolve byte-for-byte as before; 193 tests pass (24 new).

Negative:
- Aliases must be authored to pay off — an unpopulated `Aliases:` field adds nothing until someone
  fills it; mitigated by documenting it in the schema/templates and surfacing the glossary from `index`.
- The collision gate can fail CI on a genuinely ambiguous codename, which is the intended pressure to
  disambiguate by scope or supersession.

## Alternatives considered

- **Free-text query expansion** (inject canonical title terms / reverse-expand) — rejected in review
  round 1: both reviewers showed it manufactures false conflicts and is poisoned by common-word aliases.
- **Treat alias ambiguity as a warning** — rejected: an ambiguous codename silently misresolves, so it
  belongs in the same hard-error class as ADR 0024's fabricated provenance.
- **Standalone `glossary` subcommand** — cut: folding emission into `index` keeps one generator and one
  derived-artifact lifecycle.

## Related

- `scripts/decisions.py` (`normalize_alias`, `parse_alias_field`, `literal_haystack`, `build_alias_map`,
  `find_query_aliases`, `build_glossary_artifacts`; `resolve`/`validate`/`index` wiring),
  `tests/test_glossary.py`, `specs/SPEC-04-alias-glossary.md` (4-round adversarial review),
  `references/decision-schema.md` (the authored contract).
