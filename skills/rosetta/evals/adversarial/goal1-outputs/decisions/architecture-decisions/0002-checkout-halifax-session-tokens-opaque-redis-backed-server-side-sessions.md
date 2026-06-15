# ADR 0002 — Checkout (Halifax) session tokens: opaque Redis-backed server-side sessions

- Status: Superseded by ADR 0003
- Supersedes: ADR 0001
- Date: 2025-08-12
- Decided originally: 2025-08-12
- Decider: R. Okafor
- Sources: corpus R10 (eng-log · 2025-08-12), R11 (code · services/checkout/auth.py · 2025-08-13), R12 (incident postmortem · 2025-08-20)
- Related: ADR 0001, ADR 0003

## Context

Codename mapping: **Halifax = checkout / payments** (see ADR 0001 for the decoding evidence).

The Q2 token-leak postmortem (R12) found that checkout's HS256 JWTs (ADR 0001) used a static
secret that could not be rotated without logging everyone out, and there was no way to revoke a
single leaked token. Instant per-token revocation became a hard requirement.

## Decision

Replace checkout's JWT(HS256) session tokens with **opaque random tokens stored in Redis**
(server-side sessions): instant revocation, no secret sprawl (R10). Implemented in
`services/checkout/auth.py`: `token = secrets.token_urlsafe(32); redis.setex(f'sess:{token}',
1800, user_id)` — opaque session, server-side, 30-minute TTL (R11).

This decision explicitly supersedes the 2025-03-05 checkout JWT decision (R10), i.e. ADR 0001.

## Consequences

Positive:
- A single leaked token can be revoked by deleting its Redis key.
- No static signing-secret rotation problem.

Negative:
- Adds a Redis dependency on the checkout hot path (every verify is a Redis read). This hot-path
  coupling later motivated the move to PASETO v4 (ADR 0003).

## Alternatives considered

- **Rotating JWT signing keys** — would address rotation but not single-token revocation; rejected.

## Related

- Supersedes ADR 0001 (JWT HS256).
- Superseded by ADR 0003 (PASETO v4).
- Code: `services/checkout/auth.py` (R11).
