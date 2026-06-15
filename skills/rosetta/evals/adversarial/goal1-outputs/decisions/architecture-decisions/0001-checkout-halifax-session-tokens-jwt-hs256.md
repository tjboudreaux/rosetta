# ADR 0001 — Checkout (Halifax) session tokens: JWT HS256

- Status: Superseded by ADR 0002
- Date: 2025-03-05
- Decided originally: 2025-03-05
- Decider: R. Okafor
- Sources: corpus R04 (eng-log · 2025-03-05), R05 (code · services/checkout/auth.py · 2025-03-06)
- Related: ADR 0002, ADR 0003

## Context

Codename mapping: **Halifax = the checkout / payments service.** Evidence: R01 ("the Halifax
pod owns the checkout funnel end-to-end (cart -> pay -> receipt)"), R02 (Grafana board
`halifax-prod` with `checkout_p99_latency_ms` / `payments_authorized_total` panels), R03
(runbook: Halifax on-call owns `services/checkout`), R13 (cost report: namespace `halifax` =
`checkout-api`, `checkout-worker`). This is distinct from **Sterling = billing** (R01, R07, R13,
R21), whose auth is tracked separately in ADR 0004.

Checkout needed an authentication/session mechanism. The team wanted something stateless and
simple to stand up.

## Decision

Checkout (Halifax) issues signed JWT session tokens using HS256, with a 30-minute expiry
(R04). Implemented in `services/checkout/auth.py`: `jwt.encode(payload, SECRET, algorithm='HS256')`
(R05).

## Consequences

Positive:
- Stateless verification; no session store on the hot path.
- Simple to implement.

Negative:
- A static shared HS256 secret cannot be rotated without mass logout, and there is no way to
  revoke a single leaked token. This deficiency drove the Q2 token-leak postmortem (R12) and the
  move to opaque Redis sessions (ADR 0002).

## Alternatives considered

- **Opaque server-side sessions** — rejected here for simplicity/statelessness; later adopted in
  ADR 0002 after the revocation gap became an incident.

## Related

- Superseded by ADR 0002 (opaque Redis-backed server-side sessions).
- Code: `services/checkout/auth.py` (R05).
