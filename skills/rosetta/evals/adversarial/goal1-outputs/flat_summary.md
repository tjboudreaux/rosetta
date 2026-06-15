# Engineering Decision History — Summary Digest

Compressed digest of mixed-source decision history (eng-logs, code, dashboards, runbooks, incidents, docs), Jan 2025–Jun 2026.

## Teams & Ownership
- Halifax pod owns the checkout funnel (cart -> pay -> receipt); repo `services/checkout`. Lead: R. Okafor.
- Sterling pod owns billing/invoicing, dunning, invoice PDFs; repo `services/billing`. Ref: P. Nadeem.
- Checkout 5xx spikes page Halifax on-call (`#checkout-oncall`). Don't confuse checkout (Halifax) with billing (Sterling).
- Oct 2025: Halifax added two engineers; checkout latency SLO tightened to 250ms.
- Jun 2026: Halifax + Sterling jointly own the payment-status webhook.

## Checkout (Halifax) Authentication
Described differently across the corpus over time:
- Mar 2025: checkout issues signed JWT session tokens, HS256, 30-min expiry (stateless, simple). Code: `jwt.encode(payload, SECRET, algorithm='HS256')`. Owner: R. Okafor.
- Aug 2025: replace JWT(HS256) with opaque random tokens in Redis (server-side sessions); reason: instant revocation after Q2 token-leak, HS256 secret sprawl. Supersedes Mar 2025 JWT decision. Code: `secrets.token_urlsafe(32); redis.setex('sess:'+token, 1800, user_id)`. Owner: R. Okafor.
- Aug 2025 postmortem (Q2 token leak): static HS256 secret couldn't rotate without mass logout; opaque Redis chosen to revoke a single token.
- Mar 2026 architecture doc: "Checkout uses opaque Redis-backed session tokens." Status: Accepted. (Doc not updated after later PASETO migration.)
- May 2026: migrate checkout from opaque Redis sessions to PASETO v4 (v4.local) via paseto-py; keeps statelessness + revocation via 15-min expiry + key-id rotation, drops Redis hot-path dependency. Supersedes Aug 2025 opaque-Redis decision. Code: `V4Local.encrypt(payload, KEY, exp=900)`. Owner: R. Okafor. Status: Accepted.
- May 2026 migration note: Redis session reads now 0 on checkout hot path; PASETO verified locally; old `sess:*` keys TTL-expiring.

## Billing (Sterling) Authentication
- Apr 2026: adopt JWT RS256 for service-to-service auth, rotating keys via JWKS; described as current/final billing auth. Code: `services/billing/auth.py` `ALG='RS256'`. Owner: P. Nadeem.

## Other Decisions
- Feature flags: LaunchDarkly (Apr 2025).
- Observability: OpenTelemetry across all pods (Jun 2025; unrelated to auth).
- Datastores: Postgres 16 for transactional stores (Jul 2025).
- Backups: nightly to S3, 30-day retention (Nov 2025).
- CI: self-hosted runners (Jan 2026; unrelated to auth).

## Dashboards & Cost
- halifax-prod: checkout_p99_latency_ms, cart_abandon_rate, payments_authorized_total; added redis_session_count (Feb 2026); by May 2026 paseto_verify_total climbing, redis_session_count -> 0.
- sterling-prod: jwt_verify_errors, jwks_refresh_total; billing tokens RS256.
- global-prod: error_budget_burn across services.
- Sep 2025 cost: `halifax` namespace 38% of payments spend; `sterling` 12%.
