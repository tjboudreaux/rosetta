#!/usr/bin/env python3
"""GOAL 1 — recall-heavy fixture generator for the central-thesis experiment.

Produces ONE self-contained corpus on which the correct *current* answer requires:
  (1) decoding an IMPLICIT codename ("Project Halifax") that is NEVER defined as "Halifax is X" —
      it is inferable only from scattered co-occurrence (org notes, dashboards, a runbook),
  (2) resolving a SUPERSESSION chain (three successive auth decisions over time), and
  (3) ignoring DISTRACTORS: a stale-but-Accepted-looking older decision, and an adjacent service
      whose (different) auth choice is described in confident, recent language.

The question (asked identically of all three conditions):

    "What is the CURRENT session-token mechanism for Project Halifax, and what did it replace?"

GOLD ANSWER (read-verified rubric):
  - Codename decoded: Project Halifax == the checkout / payments service.
  - Current mechanism: PASETO v4 (local, paseto-py), adopted in the most recent decision.
  - It replaced: opaque Redis-backed session tokens (which had themselves replaced signed JWT/HS256).
  - Supersession order surfaced: JWT(HS256) -> opaque Redis tokens -> PASETO v4.
  - Must NOT answer "JWT" / "Redis" as current, and must NOT confuse it with the *billing* service
    (the distractor, which uses JWT RS256 and is unrelated to Halifax).

This writes:
  - corpus.md       : the raw messy corpus (condition A reads this; condition B is summarized FROM it)
  - QUESTION.txt    : the exact question string
  - GOLD.md         : the read-verified grading rubric
The Rosetta resolved decision graph (condition C) is compiled BY an Opus subagent from corpus.md
into a `decisions/` library, then served via decisions.py — not written here.
"""

import pathlib

OUT = pathlib.Path(__file__).resolve().parent / "goal1-outputs"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# The corpus. Deliberately messy: chronological-ish but interleaved with noise,
# distractors, and scattered codename clues. ~40 records. The codename "Halifax"
# is never glossed; it co-occurs with checkout/payments in 4 places.
# ---------------------------------------------------------------------------

RECORDS = [
    # --- scattered codename clues (never "Halifax is the checkout service") ---
    ("2025-01-14", "org", "Team roster: the Halifax pod owns the checkout funnel end-to-end "
     "(cart -> pay -> receipt). Lead: R. Okafor. Sister pod 'Sterling' owns billing/invoicing."),
    ("2025-02-03", "dashboard", "Grafana board 'halifax-prod' panels: checkout_p99_latency_ms, "
     "cart_abandon_rate, payments_authorized_total. On-call rotation: #checkout-oncall."),
    ("2025-02-19", "runbook", "Runbook: when checkout 5xx spikes, page the Halifax on-call. "
     "Service repo: services/checkout. Do not confuse with services/billing (Sterling)."),
    ("2025-09-30", "infra", "Cost report: namespace 'halifax' (checkout-api, checkout-worker) "
     "is 38% of payments spend. 'sterling' namespace (billing-api) is 12%."),

    # --- auth decision #1 (oldest): signed JWT HS256 for checkout ---
    ("2025-03-05", "eng-log", "Decision: checkout (Halifax) will issue signed JWT session tokens, "
     "HS256, 30-min expiry. Rationale: stateless, simple. Owner: R. Okafor."),
    ("2025-03-06", "code", "services/checkout/auth.py: def issue_token(): jwt.encode(payload, "
     "SECRET, algorithm='HS256')  # session token, 30m"),

    # --- distractor service: billing/Sterling uses JWT RS256, recent & confident ---
    ("2026-04-22", "eng-log", "Decision (Sterling/billing): adopt JWT RS256 for service-to-service "
     "auth, rotating keys via JWKS. This is the CURRENT and final auth design for billing. "
     "Owner: P. Nadeem."),
    ("2026-04-23", "code", "services/billing/auth.py: ALG='RS256'  # billing service tokens, JWKS"),
    ("2026-05-30", "dashboard", "Board 'sterling-prod': jwt_verify_errors, jwks_refresh_total. "
     "Billing tokens are RS256."),

    # --- auth decision #2: opaque Redis-backed session tokens for checkout ---
    ("2025-08-12", "eng-log", "Decision: replace checkout's JWT(HS256) session tokens with OPAQUE "
     "random tokens stored in Redis (server-side sessions). Reason: instant revocation after the "
     "Q2 token-leak incident; HS256 secret sprawl. Supersedes the 2025-03-05 checkout JWT decision. "
     "Owner: R. Okafor."),
    ("2025-08-13", "code", "services/checkout/auth.py: token = secrets.token_urlsafe(32); "
     "redis.setex(f'sess:{token}', 1800, user_id)  # opaque session, server-side"),
    ("2025-08-20", "incident", "Postmortem (Q2 token leak): static HS256 secret could not be rotated "
     "without mass logout. Opaque Redis sessions chosen so we can revoke a single token."),

    # --- noise / unrelated decisions interleaved ---
    ("2025-06-01", "eng-log", "Decision: adopt OpenTelemetry across all pods. Unrelated to auth."),
    ("2025-07-10", "eng-log", "Decision: standardize on Postgres 16 for transactional stores."),
    ("2025-10-02", "org", "Halifax pod adds two engineers; checkout latency SLO tightened to 250ms."),
    ("2026-01-15", "eng-log", "Decision: move CI to self-hosted runners. Unrelated to auth."),
    ("2026-02-08", "dashboard", "halifax-prod adds panel: redis_session_count (server-side sessions "
     "in use)."),

    # --- the STALE-but-Accepted-looking distractor: a doc that still describes Redis as current ---
    ("2026-03-01", "doc", "Architecture overview (last edited 2026-03-01): 'Checkout (Halifax) uses "
     "opaque Redis-backed session tokens for authentication.' Status: Accepted. "
     "[NOTE: this doc was NOT updated after the May PASETO migration.]"),

    # --- auth decision #3 (NEWEST, the current one): PASETO v4 for checkout ---
    ("2026-05-18", "eng-log", "Decision: migrate checkout (Halifax) session tokens from opaque "
     "Redis sessions to PASETO v4 (local, v4.local) using paseto-py. Reason: keep statelessness + "
     "revocation via short 15-min expiry + key-id rotation; drop Redis hot-path dependency. "
     "Supersedes the 2025-08-12 opaque-Redis-session decision. Owner: R. Okafor. Status: Accepted."),
    ("2026-05-19", "code", "services/checkout/auth.py: from paseto import V4Local; "
     "token = V4Local.encrypt(payload, KEY, exp=900)  # PASETO v4 session token, 15m"),
    ("2026-05-22", "incident", "Migration note: Redis session reads now 0 on checkout hot path; "
     "PASETO v4 tokens verified locally. Old sess:* keys TTL-expiring out."),
    ("2026-05-29", "dashboard", "halifax-prod: paseto_verify_total climbing, redis_session_count "
     "trending to 0. Checkout now on PASETO v4."),
]

NOISE_FILLER = [
    ("2025-04-11", "eng-log", "Decision: adopt feature flags via LaunchDarkly."),
    ("2025-05-09", "org", "Sterling pod owns dunning + invoice PDFs."),
    ("2025-11-03", "eng-log", "Decision: nightly DB backups to S3 with 30-day retention."),
    ("2026-03-20", "dashboard", "global-prod: error_budget_burn across all services."),
    ("2026-06-01", "org", "Halifax + Sterling jointly own the payment-status webhook."),
]


def render_corpus():
    rows = sorted(RECORDS + NOISE_FILLER, key=lambda r: r[0])
    lines = ["# Engineering decision history (raw export) — mixed sources, chronological",
             "",
             "_Sources: eng-log entries, code snapshots, dashboards, runbooks, org notes, incidents, "
             "docs. No normalization. Codenames are internal and undefined here._", ""]
    for i, (date, kind, text) in enumerate(rows, 1):
        lines.append(f"## R{i:02d} · {date} · [{kind}]")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


QUESTION = ("What is the CURRENT session-token mechanism for Project Halifax, "
            "and what mechanism did it replace? Be specific about the current choice "
            "and the immediately prior one.")

GOLD = """# GOLD — read-verified grading rubric (GOAL 1)

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
"""


def main():
    (OUT / "corpus.md").write_text(render_corpus())
    (OUT / "QUESTION.txt").write_text(QUESTION + "\n")
    (OUT / "GOLD.md").write_text(GOLD)
    corpus = (OUT / "corpus.md").read_text()
    print(f"corpus.md: {len(RECORDS)+len(NOISE_FILLER)} records, {len(corpus)} chars, "
          f"~{len(corpus)//4} tokens (rough)")
    print(f"QUESTION.txt and GOLD.md written to {OUT}")


if __name__ == "__main__":
    main()
