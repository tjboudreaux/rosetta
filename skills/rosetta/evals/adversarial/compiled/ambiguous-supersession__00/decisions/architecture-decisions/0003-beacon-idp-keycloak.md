# ADR 0003 — Beacon IdP: Keycloak (SCIM-capable, supersedes both 2026-03-04 calls)

- Status: Accepted
- Date: 2026-04-19
- Decided originally: 2026-04-19
- Decider: claude (amb0c)
- Supersedes: ADR 0001, ADR 0002
- Sources: claude · amb0c · 2026-04-19 (raw/03-amendment.md), git 33cc44d 2026-04-19 "configure Keycloak as IdP for Beacon", raw/code/notify_svc.py (`IDP_PROVIDER = "keycloak"`)
- Related: ADR 0001 (Ping, AM), ADR 0002 (Auth0, PM)

## Context

Beacon's IdP had two unresolved, conflicting same-day calls from 2026-03-04: Ping in the AM
(ADR 0001) and Auth0 in the PM (ADR 0002). A follow-up review on 2026-04-19 evaluated both
against Beacon's SCIM (provisioning) requirements and found that neither Ping nor Auth0 met them.

## Decision

Adopt Keycloak as the IdP for Beacon. This is the current, live decision and it supersedes BOTH
the 2026-03-04 AM (Ping, ADR 0001) and PM (Auth0, ADR 0002) decisions.

## Consequences

Positive:
- Resolves the dangling AM/PM conflict with a single SCIM-capable provider.
- Confirmed in code and git: `notify_svc.py` sets `IDP_PROVIDER = "keycloak"  # SCIM-capable`, and
  commit 33cc44d "configure Keycloak as IdP for Beacon" lands the change on 2026-04-19.

Negative:
- Required dropping both previously evaluated vendors; mitigated because neither satisfied the SCIM
  requirement that drove the decision.

## Alternatives considered

- **Ping** (ADR 0001) — did not meet Beacon's SCIM requirements.
- **Auth0** (ADR 0002) — did not meet Beacon's SCIM requirements.

## Related

- Supersedes ADR 0001 (Ping) and ADR 0002 (Auth0).
- raw/03-amendment.md, raw/code/notify_svc.py, git commit 33cc44d.
