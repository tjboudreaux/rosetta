# Eng decision digest (flat)

Teams: Halifax pod owns checkout funnel (services/checkout), lead R. Okafor; Sterling owns billing/invoicing, dunning, invoice PDFs (P. Nadeem); both jointly own payment-status webhook. On-call #checkout-oncall.

Checkout auth history: signed JWT HS256 30-min sessions; then opaque random tokens in Redis (server-side, instant revocation after Q2 token-leak incident); then PASETO v4 local, 15-min, key-id rotation, dropping Redis hot-path. Billing auth: JWT RS256 service-to-service, JWKS key rotation.

Infra/ops: Postgres 16 for transactional stores; nightly S3 DB backups, 30-day retention; OpenTelemetry across pods; LaunchDarkly flags; self-hosted CI runners. Dashboards: halifax-prod (p99 latency, cart abandon, payments, redis_session_count, paseto), sterling-prod (jwt errors, jwks). Checkout SLO 250ms. Cost: halifax 38%, sterling 12% of payments spend.
