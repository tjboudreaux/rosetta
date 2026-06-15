# ADR 0004 — Billing (Sterling) service-to-service auth: JWT RS256 via JWKS

- Status: Accepted
- Date: 2026-04-22
- Decided originally: 2026-04-22
- Decider: P. Nadeem
- Sources: corpus R20 (eng-log · 2026-04-22), R21 (code · services/billing/auth.py · 2026-04-23), R26 (dashboard sterling-prod · 2026-05-30)
- Related: ADR 0003

## Context

Codename mapping: **Sterling = the billing / invoicing service** (a different service from the
sister funnel pod). Evidence: R01 ("Sister pod 'Sterling' owns billing/invoicing"), R07
(Sterling owns dunning + invoice PDFs), R13 (cost report: `sterling` namespace = `billing-api`),
R21 (code path `services/billing/auth.py`), R26 (board `sterling-prod` with `jwks_refresh_total`).

This is a SEPARATE service. Its auth choice must not be merged with the sister funnel pod's auth
chain (ADR 0001–0003): different service, different decider (P. Nadeem vs R. Okafor), different
mechanism.

## Decision

Billing (Sterling) adopts **JWT RS256 for service-to-service auth, with rotating keys served via
JWKS** (R20). Implemented in `services/billing/auth.py`: `ALG='RS256'  # billing service tokens,
JWKS` (R21). R20 states this is the current and final auth design for billing.

## Consequences

Positive:
- Asymmetric RS256 + JWKS lets services verify tokens with public keys and rotate keys without
  shared secrets.

Negative:
- JWKS refresh and key distribution add operational surface (`jwks_refresh_total`,
  `jwt_verify_errors` tracked on `sterling-prod`, R26).

## Alternatives considered

- **Opaque/PASETO sessions (as the sister funnel pod uses)** — not chosen; billing's need is service-to-service
  verification across services, which suits asymmetric JWT + JWKS.

## Related

- Sibling current auth decision: ADR 0003 (the payments-funnel pod's PASETO v4) — kept separate by design.
- Code: `services/billing/auth.py` (R21).
