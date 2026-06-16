# ADR 0006 — Adopt OpenTelemetry across all pods

- Status: Accepted
- Date: 2025-06-01
- Decided originally: 2025-06-01
- Decider: Eng
- Sources: corpus R08 (eng-log · 2025-06-01)

## Context

The org wanted standardized, vendor-neutral telemetry (traces/metrics/logs) across all pods.
R08 notes this is unrelated to auth.

## Decision

Adopt **OpenTelemetry** across all pods (R08).

## Consequences

Positive:
- Consistent instrumentation and portability across backends.

Negative:
- Migration/instrumentation effort across every service.

## Alternatives considered

- **Per-vendor SDKs** — rejected to avoid lock-in and inconsistent instrumentation.

## Related

- corpus R08.
