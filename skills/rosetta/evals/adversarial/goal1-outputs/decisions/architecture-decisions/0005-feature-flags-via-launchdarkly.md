# ADR 0005 — Feature flags via LaunchDarkly

- Status: Accepted
- Date: 2025-04-11
- Decided originally: 2025-04-11
- Decider: Eng
- Sources: corpus R06 (eng-log · 2025-04-11)

## Context

The org needed a managed feature-flag mechanism for progressive rollout and kill switches.
Unrelated to the checkout/billing auth decisions.

## Decision

Adopt feature flags via **LaunchDarkly** (R06).

## Consequences

Positive:
- Managed flag delivery and targeting without building in-house.

Negative:
- External vendor dependency and cost.

## Alternatives considered

- **Home-grown flags** — rejected to avoid building/operating flag infrastructure.

## Related

- corpus R06.
