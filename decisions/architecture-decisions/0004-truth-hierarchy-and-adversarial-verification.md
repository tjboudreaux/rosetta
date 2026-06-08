# ADR 0004 — Truth hierarchy + adversarial verification

- Status: Accepted (retroactive)
- Date: 2026-06-07 (recorded)
- Decided originally: 2026-05-29
- Decider: Travis
- Sources: `claude · bc09f7f6 · 2026-05-29`; SKILL.md (steps 6–7)
- Related: ADR 0001, PDR 0002

## Context

Transcripts are full of ideas that were discussed and then abandoned, reverted, or never built. A
summary that reports talk as fact invents decisions that never shipped — the second failure mode the
skill exists to defeat.

## Decision

Reconcile every source on one UTC timeline under a fixed truth hierarchy:
**current code / git state > committed decisions > project docs > latest conversation > older
conversation.** Code and git arbitrate what actually happened; a transcript claim the code doesn't
show is recorded as "discussed/intended," not "done." A skeptic pass then tries to *refute* each
material claim, demoting anything it can't substantiate into a "Contradictions & unverified" section.

## Consequences

Positive:
- Ground truths (and decision records) distinguish shipped reality from chatter.
- This discipline directly caught the dotdir-encoding claim later overturned in ADR 0005.

Negative:
- Verification costs an extra pass; users may request a "fast recap" to skip it (documented).

## Alternatives considered

- **Trust latest conversation** — over-reports abandoned ideas as decisions; rejected.
- **Code-only, ignore chat** — loses the *why* behind decisions; the hierarchy keeps both, ranked.

## Related

- SKILL.md "Synthesize / Adversarially verify"; the `Contradictions & unverified claims` section of
  `.agents/ground-truth.md`; the `Status: Proposed` convention for un-shipped decisions.
