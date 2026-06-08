# ADR 0007 — Decision records as a first-class Rosetta output

- Status: Accepted
- Date: 2026-06-07
- Decided originally: 2026-06-07
- Decider: Travis
- Sources: `claude · 4b80b004 · 2026-06-07` (this conversation); format from a sibling project's Rosetta-produced decision library
- Related: PDR 0001, PDR 0002, ADR 0008, ADR 0009

## Context

A `ground-truth.md` is a snapshot of state; decisions deserve their own durable, individually-addressable
records with provenance and a status lifecycle. A sibling project's library — itself produced by Rosetta
— already established a clean ADR/PDR format with `Sources: agent · session-id · date` citations. Adopting it
(rather than inventing one) makes Rosetta dogfood the exact format it emits for others.

## Decision

Make ADRs (architecture/technical), PDRs (product) and BDRs (business) a first-class Rosetta output
alongside `ground-truth.md`, in the canonical format: `# <LABEL> NNNN — title` heading, bullet-list
frontmatter (Status / Date / Decided originally / Decider / Sources / Related), then
`Context → Decision → Consequences → [Open questions] → Alternatives considered → Related`. A library
lives under `decisions/` with one dir per type and a generated index. Rosetta's own decisions
(`decisions/`) are the reference implementation.

## Consequences

Positive:
- Decisions survive context windows and onboarding; each is cited and supersedable.
- The format is proven in real use and human-readable in any markdown viewer.

Negative:
- Frontmatter is bullet-list, not YAML, so tooling parses it with light regex (acceptable; matches the
  established corpus rather than rewriting it).

## Alternatives considered

- **MADR/YAML-frontmatter ADRs** — cleaner to parse but diverges from the existing in-house corpus and the
  human-friendly bullet style the user already uses; rejected in favor of the in-house format.
- **Keep everything in ground-truth.md** — decisions get buried and can't carry their own status;
  rejected.

## Related

- `templates/{adr,pdr,bdr}-template.md`, `references/decision-schema.md`, `decisions/`.
