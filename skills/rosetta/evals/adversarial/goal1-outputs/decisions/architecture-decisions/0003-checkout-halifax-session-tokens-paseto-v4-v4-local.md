# ADR 0003 — Checkout (Halifax) session tokens: PASETO v4 (v4.local)

- Status: Accepted
- Supersedes: ADR 0002
- Date: 2026-05-18
- Decided originally: 2026-05-18
- Decider: R. Okafor
- Sources: corpus R22 (eng-log · 2026-05-18), R23 (code · services/checkout/auth.py · 2026-05-19), R24 (migration note · 2026-05-22), R25 (dashboard halifax-prod · 2026-05-29)
- Related: ADR 0002, ADR 0004

## Context

Codename mapping: **Halifax = checkout / payments** (see ADR 0001 for the decoding evidence). This
is the checkout service's auth, distinct from billing/Sterling (ADR 0004). Resolution anchors for
this question: the current Halifax session token, the current checkout session token, and the
current checkout payments session token mechanism all resolve here (PASETO v4).

The opaque Redis-backed sessions (ADR 0002) put a Redis read on the checkout hot path. The team
wanted to keep statelessness and per-token revocation while dropping the Redis hot-path dependency.

NOTE on the stale architecture doc: R18 (architecture overview, last edited 2026-03-01) still
describes checkout as using "opaque Redis-backed session tokens … Status: Accepted." That doc was
NOT updated after this May 2026 PASETO migration (it says so explicitly). It therefore does NOT
represent the current state and gets no separate current ADR — this live decision wins.

## Decision

Migrate checkout (Halifax) session tokens from opaque Redis sessions to **PASETO v4 (local,
`v4.local`) using paseto-py**, with a 15-minute expiry and key-id rotation (R22). Implemented in
`services/checkout/auth.py`: `from paseto import V4Local; token = V4Local.encrypt(payload, KEY,
exp=900)` — PASETO v4 session token, 15m (R23). Tokens are verified locally; Redis session reads on
the checkout hot path dropped to 0 and old `sess:*` keys TTL-expire out (R24, R25).

This decision explicitly supersedes the 2025-08-12 opaque-Redis-session decision (R22), i.e.
ADR 0002. **This is the CURRENT session-token mechanism for checkout (Halifax).**

## Consequences

Positive:
- Stateless, locally-verified tokens; no Redis on the hot path.
- Revocation handled via short 15-minute expiry plus key-id rotation.

Negative:
- A leaked token remains valid until its 15-minute expiry (no instant per-token revoke as with
  Redis); mitigated by the short TTL and key rotation.

## Alternatives considered

- **Keep opaque Redis sessions** — rejected to remove the Redis hot-path dependency.
- **Return to JWT** — rejected; PASETO v4 local avoids JWT algorithm-confusion footguns.

## Related

- Supersedes ADR 0002 (opaque Redis-backed sessions).
- Code: `services/checkout/auth.py` (R23).
- Stale doc that this overrides: corpus R18 (architecture overview, not updated post-migration).
