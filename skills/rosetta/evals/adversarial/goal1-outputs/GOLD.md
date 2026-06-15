# GOLD — read-verified grading rubric (GOAL 1)

Question: What is the CURRENT session-token mechanism for Project Halifax, and what did it replace?

A correct answer (graded by READING the claim, NOT grepping) must satisfy ALL of:

1. CODENAME DECODED: identifies Project Halifax as the **checkout / payments** service
   (NOT billing/Sterling). Implicitly fine if the answer is unambiguously about checkout.
2. CURRENT MECHANISM: **PASETO v4** (v4.local / paseto-py), adopted 2026-05-18. This is the
   single most important fact — the supersession endpoint.
3. WHAT IT REPLACED: the immediately prior mechanism was **opaque Redis-backed session tokens**
   (adopted 2025-08-12).
4. NO STALE/DISTRACTOR ERROR: must NOT state the current mechanism is "Redis" or "JWT", and must
   NOT answer with the billing service's **JWT RS256** (that is the Sterling distractor).

Scoring per run (k):
  - FULL CORRECT (1.0): #2 PASETO v4 AND #3 replaced opaque-Redis, AND no distractor error,
    AND codename clearly tied to checkout.
  - PARTIAL (0.5): names PASETO v4 as current but botches "what it replaced" (e.g. says JWT),
    or right mechanism but hedges codename.
  - WRONG (0.0): current mechanism stated as Redis or JWT, or answers about billing/RS256,
    or cannot decode the codename.

Bonus (not required for FULL): surfaces the full chain JWT(HS256) -> opaque-Redis -> PASETO v4.
