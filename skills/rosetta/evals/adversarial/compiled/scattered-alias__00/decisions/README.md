# Decision Library — index & timeline

Catalog of decisions, reconciled onto one timeline. Each record cites its evidence as `agent · session-id · date`, a git commit, a code path, or a task id.

## Timeline

<!-- ROSETTA:TIMELINE:START -->
| Date | ID | Type | Decision | Status |
|---|---|---|---|---|
| 2025-11-02 | [ADR 0003](architecture-decisions/0003-event-bus-rabbitmq.md) | adr | svc-flags_api event bus: RabbitMQ (early architecture) | Superseded by ADR 0002 |
| 2026-05-18 | [ADR 0001](architecture-decisions/0001-canonical-service-identity-flags-api.md) | adr | Canonical service identity: svc-flags_api (feature-flag service, fka "Drift") | Accepted |
| 2026-05-18 | [ADR 0002](architecture-decisions/0002-event-bus-pubsub.md) | adr | svc-flags_api event bus: Pub/Sub (migrated off RabbitMQ) | Accepted |
<!-- ROSETTA:TIMELINE:END -->
