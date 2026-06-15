# Engineering decision history (raw export) — mixed sources, chronological

_Sources: eng-log entries, code snapshots, dashboards, runbooks, org notes, incidents, docs. No normalization. Codenames are internal and undefined here._

## R01 · 2025-01-14 · [org]
Team roster: the Halifax pod owns the checkout funnel end-to-end (cart -> pay -> receipt). Lead: R. Okafor. Sister pod 'Sterling' owns billing/invoicing.

## R02 · 2025-02-03 · [dashboard]
Grafana board 'halifax-prod' panels: checkout_p99_latency_ms, cart_abandon_rate, payments_authorized_total. On-call rotation: #checkout-oncall.

## R03 · 2025-02-19 · [runbook]
Runbook: when checkout 5xx spikes, page the Halifax on-call. Service repo: services/checkout. Do not confuse with services/billing (Sterling).

## R04 · 2025-03-05 · [eng-log]
Decision: checkout (Halifax) will issue signed JWT session tokens, HS256, 30-min expiry. Rationale: stateless, simple. Owner: R. Okafor.

## R05 · 2025-03-06 · [code]
services/checkout/auth.py: def issue_token(): jwt.encode(payload, SECRET, algorithm='HS256')  # session token, 30m

## R06 · 2025-04-11 · [eng-log]
Decision: adopt feature flags via LaunchDarkly.

## R07 · 2025-05-09 · [org]
Sterling pod owns dunning + invoice PDFs.

## R08 · 2025-06-01 · [eng-log]
Decision: adopt OpenTelemetry across all pods. Unrelated to auth.

## R09 · 2025-07-10 · [eng-log]
Decision: standardize on Postgres 16 for transactional stores.

## R10 · 2025-08-12 · [eng-log]
Decision: replace checkout's JWT(HS256) session tokens with OPAQUE random tokens stored in Redis (server-side sessions). Reason: instant revocation after the Q2 token-leak incident; HS256 secret sprawl. Supersedes the 2025-03-05 checkout JWT decision. Owner: R. Okafor.

## R11 · 2025-08-13 · [code]
services/checkout/auth.py: token = secrets.token_urlsafe(32); redis.setex(f'sess:{token}', 1800, user_id)  # opaque session, server-side

## R12 · 2025-08-20 · [incident]
Postmortem (Q2 token leak): static HS256 secret could not be rotated without mass logout. Opaque Redis sessions chosen so we can revoke a single token.

## R13 · 2025-09-30 · [infra]
Cost report: namespace 'halifax' (checkout-api, checkout-worker) is 38% of payments spend. 'sterling' namespace (billing-api) is 12%.

## R14 · 2025-10-02 · [org]
Halifax pod adds two engineers; checkout latency SLO tightened to 250ms.

## R15 · 2025-11-03 · [eng-log]
Decision: nightly DB backups to S3 with 30-day retention.

## R16 · 2026-01-15 · [eng-log]
Decision: move CI to self-hosted runners. Unrelated to auth.

## R17 · 2026-02-08 · [dashboard]
halifax-prod adds panel: redis_session_count (server-side sessions in use).

## R18 · 2026-03-01 · [doc]
Architecture overview (last edited 2026-03-01): 'Checkout (Halifax) uses opaque Redis-backed session tokens for authentication.' Status: Accepted. [NOTE: this doc was NOT updated after the May PASETO migration.]

## R19 · 2026-03-20 · [dashboard]
global-prod: error_budget_burn across all services.

## R20 · 2026-04-22 · [eng-log]
Decision (Sterling/billing): adopt JWT RS256 for service-to-service auth, rotating keys via JWKS. This is the CURRENT and final auth design for billing. Owner: P. Nadeem.

## R21 · 2026-04-23 · [code]
services/billing/auth.py: ALG='RS256'  # billing service tokens, JWKS

## R22 · 2026-05-18 · [eng-log]
Decision: migrate checkout (Halifax) session tokens from opaque Redis sessions to PASETO v4 (local, v4.local) using paseto-py. Reason: keep statelessness + revocation via short 15-min expiry + key-id rotation; drop Redis hot-path dependency. Supersedes the 2025-08-12 opaque-Redis-session decision. Owner: R. Okafor. Status: Accepted.

## R23 · 2026-05-19 · [code]
services/checkout/auth.py: from paseto import V4Local; token = V4Local.encrypt(payload, KEY, exp=900)  # PASETO v4 session token, 15m

## R24 · 2026-05-22 · [incident]
Migration note: Redis session reads now 0 on checkout hot path; PASETO v4 tokens verified locally. Old sess:* keys TTL-expiring out.

## R25 · 2026-05-29 · [dashboard]
halifax-prod: paseto_verify_total climbing, redis_session_count trending to 0. Checkout now on PASETO v4.

## R26 · 2026-05-30 · [dashboard]
Board 'sterling-prod': jwt_verify_errors, jwks_refresh_total. Billing tokens are RS256.

## R27 · 2026-06-01 · [org]
Halifax + Sterling jointly own the payment-status webhook.
