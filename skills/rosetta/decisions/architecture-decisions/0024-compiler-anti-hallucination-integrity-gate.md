# ADR 0024 — Compiler anti-hallucination integrity gate

- Status: Accepted
- Date: 2026-06-14
- Decider: Travis Boudreaux
- Sources: scripts/decisions.py, tests/test_integrity.py, evals/adversarial/GOAL2-PHASE0B.md
- Related: ADR 0020 (decision-library hardening), ADR 0017 (crash-safe writes), ADR 0023 (round-3 hardening)

## Context

Goal 2 (the preregistered raw-vs-compiled 2×2) surfaced the worst failure mode a provenance product
can have: when an LLM *compiles* a decision library from raw transcripts/code, it fabricated
provenance — it referenced ADR ids that did not exist in 2/5 fixtures, and the same mechanism could
just as easily cite a source file that isn't on disk. A "verified provenance graph" that invents its
own ids/citations is worse than no library at all: it is a confidently-wrong oracle. A Codex + Gemini
council independently ranked fixing this above every other next bet — both called an unverified
compiler a catastrophic-trust failure that must be closed *before* any accuracy claim is attempted.

The existing `validate` only checked supersede references inside three frontmatter fields and never
checked that cited `Sources:` paths exist, so both fabrication modes passed validation.

## Decision

Add an opt-in integrity pass that makes fabricated provenance mechanically detectable, exposed two ways:
a standalone `decisions.py integrity` subcommand (JSON, exit 1 on any finding) and a `validate
--integrity` flag (folds the findings in as hard errors). It checks:

1. **Dangling ADR-id references** — every `LABEL NNNN` reference *anywhere* in a record (frontmatter or
   body), not just the supersede fields, must resolve to a real record. A record's reference to itself
   is allowed.
2. **Ghost source citations** — every *file-shaped* token in `Sources:` (last segment carries a short
   file extension) must resolve, either by exact relative path under a source root (git repo root →
   decisions root → its parent) or by basename appearing anywhere in the repo (`git ls-files`, rglob
   fallback). Directory citations (`tests/`) and code-symbol citations (`load_counter/save_counter`)
   carry no file extension and are deliberately **not** checked — flagging them is noise, not signal.

Findings are always hard errors: fabricated provenance has no benign reading. The pass is pure stdlib
(subprocess to git only; ADR 0013) and degrades cleanly when git is absent.

## Consequences

Positive:
- The compiler hallucination from Goal 2 is now a falsifiable, CI-gateable defect — a prerequisite for
  ever claiming Rosetta is a *verified* resolution layer.
- The check ran clean on the live 28-record library after one genuine fix (ADR 0022 had mixed a CLI
  flag example, `--emit-bundle library.txt`, into its `Sources:` field — the gate caught it).

Negative:
- Best-effort path resolution means a citation to a path that legitimately lives outside the checkout
  would false-positive; mitigated by basename grounding and by keeping the pass opt-in so unrelated CI
  is never broken by an external citation style.

## Alternatives considered

- **Make it always-on in `validate`** — rejected for now: would risk breaking external/loose citation
  styles; opt-in lets the eval harness and CI turn it into a hard gate deliberately.
- **AST-level verification of cited symbols/line numbers** — deferred: higher engineering cost, and the
  id/path checks close the demonstrated Goal-2 failure. Revisit if symbol/line citations start drifting.

## Related

- `scripts/decisions.py` (`assess_integrity`, `cmd_integrity`, `validate --integrity`),
  `tests/test_integrity.py`, `evals/adversarial/GOAL2-PHASE0B.md` (the failure that motivated this).
