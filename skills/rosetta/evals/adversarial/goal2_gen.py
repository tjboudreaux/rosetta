#!/usr/bin/env python3
"""GOAL 2 / Phase 0b fixture generator.

Emits synthetic, code-anchored decision-history corpora across FIVE retrieval-defeat
fixture types. Each fixture is a self-contained bundle:

  <out>/<fixture_id>/
    raw/                  normalized "session" transcripts + code + git-log (the SOLVER corpus)
    query.txt             the user question (given to both arms)
    gold.json             JUDGE-ONLY: gold answer + resolution claims + must/must_not rubric

The five types (each a distinct reason naive search / raw reading fails):

  1. glossary-present        — an explicit "X is internally Y" line exists, but it is buried and
                              an OLDER record names a now-superseded value. Tests supersession + decode.
  2. glossary-absent         — the codename is NEVER defined; the gold value is only inferable from
                              co-occurrence across scattered notes (implicit glossary).
  3. scattered-alias         — ONE entity referred to by 3+ aliases across files; the current decision
                              uses one alias, the code uses another. Must unify aliases then resolve.
  4. ambiguous-supersession  — two same-day records disagree; one is later AMENDED/superseded by a
                              third. A naive "latest wins" picks the wrong one; must follow the chain.
  5. code-vs-decision-conflict — a decision record asserts value A; the actual code/git evidence shows
                              value B shipped. Truth hierarchy: code wins; the ADR is stale.

Deterministic given --seed so fixtures are regenerable (contamination-resistant).
Pure stdlib.
"""
import argparse, json, os, random, shutil, textwrap
from pathlib import Path

# ---- domain pools -----------------------------------------------------------
SERVICES = [
    ("Atlas", "user-profile service", "profile_store"),
    ("Beacon", "notification dispatcher", "notify_svc"),
    ("Cobalt", "billing reconciler", "billing_core"),
    ("Drift", "feature-flag service", "flags_api"),
    ("Ember", "search-indexer", "index_worker"),
    ("Falcon", "session/auth gateway", "auth_gw"),
]
DATASTORES = ["DynamoDB", "Postgres", "Cloud Spanner", "CockroachDB", "MySQL", "Cassandra"]
IDPS = ["Okta", "Auth0", "Azure AD", "Keycloak", "Ping"]
QUEUES = ["Kafka", "SQS", "RabbitMQ", "Pub/Sub", "NATS"]
TEAMS = ["platform", "infra", "payments", "growth", "core-svc"]


def w(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(s).lstrip("\n"))


def session_header(agent, sid, date, cwd="~/repo"):
    return f"# session: {agent} · {sid} · {date}\n- agent: {agent}\n- cwd: {cwd}\n\n"


# ---- fixture builders -------------------------------------------------------
def build_glossary_present(out: Path, rng: random.Random, idx: int):
    code, name, mod = rng.choice(SERVICES)
    old, gold = rng.sample(DATASTORES, 2)
    raw = out / "raw"
    # explicit glossary line, but buried in an old onboarding doc
    w(raw / "01-onboarding-glossary.md", session_header("claude", f"glos{idx}a", "2025-09-01") + f"""
    Onboarding notes for new engineers.
    Glossary of internal codenames:
    - "{code}" is internally the {name}.
    - "ledger tier" refers to our strongly-consistent primary datastore.
    Please skim before your first week.
    """)
    # OLD decision naming the now-superseded datastore
    w(raw / "02-early-decision.md", session_header("codex", f"glos{idx}b", "2025-10-12") + f"""
    Reviewed {code}'s persistence. Decision: adopt {old} as the {code} primary datastore.
    Rationale: team familiarity. (status at the time: accepted)
    """)
    # NEW decision migrating to gold, references codename + ledger tier
    w(raw / "03-migration-decision.md", session_header("claude", f"glos{idx}c", "2026-04-22") + f"""
    Migration review for the {name}. After the {old} hotspotting incidents we are moving the
    {code} ledger tier to {gold} for strong consistency. This supersedes the earlier {old} call.
    Cutover complete in prod cluster on 2026-04-20.
    """)
    w(raw / "code/{}.py".format(mod), f"""
    # {mod}.py — {name}
    # current backend (post-migration)
    BACKEND = "{gold.lower().replace(' ', '_')}"
    # NOTE: legacy {old} client kept temporarily for backfill only
    LEGACY_{old.upper().replace(' ', '_')}_ENABLED = False
    """)
    w(raw / "git-log.txt", f"""
    a1b2c3d 2026-04-20 migrate {code} ledger tier to {gold}; disable {old} writes
    9f8e7d6 2025-10-12 add {old} client for {code}
    """)
    w(out / "query.txt", f"What is the current primary datastore for {code} (the {name})?")
    gold = dict(
        fixture_type="glossary-present",
        answer=gold,
        answer_aliases=[gold, gold.lower()],
        claims=[
            {"id": "decode", "text": f'"{code}" decodes to the {name} and "ledger tier" is its primary datastore', "supported_by": "01-onboarding-glossary.md"},
            {"id": "current", "text": f"the current primary datastore is {gold}", "supported_by": "03-migration-decision.md + code + git"},
            {"id": "supersession", "text": f"{old} was the earlier choice and is now superseded by {gold}", "supported_by": "02 superseded by 03"},
        ],
        rubric=dict(
            must=[f"names {gold} as current", f"acknowledges {old} is superseded/legacy, not current"],
            must_not=[f"asserts {old} as the current primary datastore"],
            negative_control=False,
        ),
    )
    w(out / "gold.json", json.dumps(gold, indent=2))


def build_glossary_absent(out: Path, rng: random.Random, idx: int):
    code, name, mod = rng.choice(SERVICES)
    gold, trap = rng.sample(DATASTORES, 2)
    raw = out / "raw"
    cluster = f"{gold.lower().split()[0]}-prod-eu"
    # codename NEVER explicitly defined; inferable only by co-occurrence
    w(raw / "01-org-notes.md", session_header("hermes", f"abs{idx}a", "2025-12-03") + f"""
    Team roster: the {code} squad owns everything user-profile related — sign-up, profile reads,
    avatar storage. They report into {rng.choice(TEAMS)}.
    """)
    w(raw / "02-dashboard-export.md", session_header("droid", f"abs{idx}b", "2026-03-15") + f"""
    Infra dashboard export. Cluster {cluster} hosts the {code} workloads.
    Backend engine reported by the cluster: {gold}.
    """)
    w(raw / "03-stray-distractor.md", session_header("cursor", f"abs{idx}c", "2026-01-09") + f"""
    Random scratch note: "profile datastore: {trap}?" — someone's open question during planning,
    never confirmed. Marked TODO, never resolved.
    """)
    w(raw / "04-incident.md", session_header("claude", f"abs{idx}d", "2026-05-01") + f"""
    Incident review: latency spike on {cluster}. The {gold} read replicas lagged. {code}'s profile
    reads degraded. Root cause: replica failover. No datastore change.
    """)
    w(raw / "code/{}.py".format(mod), f"""
    # {mod}.py
    DSN = "{gold.lower().split()[0]}://{cluster}/profiles"  # connects to {cluster}
    """)
    w(raw / "git-log.txt", f"""
    44ee55f 2026-03-15 point {code} at {cluster}
    """)
    w(out / "query.txt", f"What datastore does the {code} service use for its profile data?")
    gold_d = dict(
        fixture_type="glossary-absent",
        answer=gold,
        answer_aliases=[gold, gold.lower(), cluster],
        claims=[
            {"id": "decode", "text": f"{code} is the user-profile service (inferred from org notes)", "supported_by": "01-org-notes.md"},
            {"id": "current", "text": f"{code} uses {gold} (inferred from cluster {cluster})", "supported_by": "02-dashboard + 04-incident + code"},
            {"id": "reject_trap", "text": f"{trap} was an unresolved TODO question, not the answer", "supported_by": "03-stray-distractor.md"},
        ],
        rubric=dict(
            must=[f"names {gold}", "does not present the TODO/distractor as fact"],
            must_not=[f"asserts {trap} as the datastore"],
            negative_control=False,
        ),
    )
    w(out / "gold.json", json.dumps(gold_d, indent=2))


def build_scattered_alias(out: Path, rng: random.Random, idx: int):
    code, name, mod = rng.choice(SERVICES)
    gold, old = rng.sample(QUEUES, 2)
    # three aliases for ONE service
    alias_a, alias_b, alias_c = code, f"{name}", f"svc-{mod}"
    raw = out / "raw"
    w(raw / "01-arch-note.md", session_header("claude", f"sca{idx}a", "2025-11-02") + f"""
    The {alias_a} pipeline publishes events to {old}. (early architecture)
    """)
    w(raw / "02-ops-runbook.md", session_header("codex", f"sca{idx}b", "2026-02-10") + f"""
    Runbook for the {alias_b}: on incident, drain the {old} consumer group first.
    """)
    w(raw / "03-platform-decision.md", session_header("claude", f"sca{idx}c", "2026-05-18") + f"""
    Platform decision: migrate {alias_c} off {old} onto {gold} for ordering guarantees.
    Note: {alias_c}, the {alias_b}, and what older docs call "{alias_a}" are the SAME service.
    Cutover done 2026-05-17.
    """)
    w(raw / "code/{}.py".format(mod), f"""
    # {mod}.py — also known as {alias_a} / {alias_b}
    EVENT_BUS = "{gold.lower()}"  # migrated from {old.lower()}
    """)
    w(raw / "git-log.txt", f"""
    77aa88b 2026-05-17 {mod}: switch event bus to {gold}
    11bb22c 2025-11-02 {mod}: publish to {old}
    """)
    w(out / "query.txt", f"What message queue / event bus does the {alias_a} service publish to today?")
    gold_d = dict(
        fixture_type="scattered-alias",
        answer=gold,
        answer_aliases=[gold, gold.lower()],
        claims=[
            {"id": "decode", "text": f'"{alias_a}", "{alias_b}", and "{alias_c}" are the same service', "supported_by": "03-platform-decision.md"},
            {"id": "current", "text": f"the service publishes to {gold} today", "supported_by": "03 + code + git"},
            {"id": "supersession", "text": f"{old} was earlier and was migrated away", "supported_by": "01/02 superseded by 03"},
        ],
        rubric=dict(
            must=[f"names {gold} as current", f"recognizes the aliases refer to one service"],
            must_not=[f"asserts {old} as the current bus"],
            negative_control=False,
        ),
    )
    w(out / "gold.json", json.dumps(gold_d, indent=2))


def build_ambiguous_supersession(out: Path, rng: random.Random, idx: int):
    code, name, mod = rng.choice(SERVICES)
    a, b, gold = rng.sample(IDPS, 3)
    raw = out / "raw"
    # two SAME-DAY conflicting records, then a later amendment that picks gold
    w(raw / "01-decision-morning.md", session_header("claude", f"amb{idx}a", "2026-03-04T09:12") + f"""
    Auth review (AM): decision — adopt {a} as the IdP for {code} ({name}).
    """)
    w(raw / "02-decision-afternoon.md", session_header("codex", f"amb{idx}b", "2026-03-04T16:40") + f"""
    Auth review (PM, separate meeting): decision — adopt {b} as the IdP for {code}.
    (Note: conflicts with the AM call; unresolved at end of day.)
    """)
    # later amendment supersedes BOTH with a third choice
    w(raw / "03-amendment.md", session_header("claude", f"amb{idx}c", "2026-04-19") + f"""
    Follow-up: neither {a} nor {b} met our SCIM requirements. Final decision: adopt {gold} as the
    IdP for {code}. This supersedes BOTH the 2026-03-04 AM ({a}) and PM ({b}) decisions.
    """)
    w(raw / "code/{}.py".format(mod), f"""
    # {mod}.py
    IDP_PROVIDER = "{gold.lower().replace(' ', '')}"  # SCIM-capable
    """)
    w(raw / "git-log.txt", f"""
    33cc44d 2026-04-19 configure {gold} as IdP for {code}
    """)
    w(out / "query.txt", f"Which identity provider (IdP) did we settle on for {code} ({name})?")
    gold_d = dict(
        fixture_type="ambiguous-supersession",
        answer=gold,
        answer_aliases=[gold, gold.lower()],
        claims=[
            {"id": "current", "text": f"the IdP is {gold}", "supported_by": "03-amendment.md + code + git"},
            {"id": "supersession", "text": f"both {a} (AM) and {b} (PM) were superseded by {gold}", "supported_by": "03 supersedes 01 and 02"},
            {"id": "no_latest_wins", "text": f"naive latest-of-same-day would wrongly pick {b}; the amendment overrides", "supported_by": "01,02 vs 03"},
        ],
        rubric=dict(
            must=[f"names {gold}", f"shows {a} and {b} were both superseded"],
            must_not=[f"asserts {a} as final", f"asserts {b} as final"],
            negative_control=False,
        ),
    )
    w(out / "gold.json", json.dumps(gold_d, indent=2))


def build_code_vs_decision(out: Path, rng: random.Random, idx: int):
    code, name, mod = rng.choice(SERVICES)
    decided, shipped = rng.sample(DATASTORES, 2)
    raw = out / "raw"
    # an ADR-style record asserts `decided`, but code + git show `shipped` actually went live
    w(raw / "01-adr-record.md", session_header("codex", f"cvd{idx}a", "2026-02-01") + f"""
    ADR: {code} ({name}) will use {decided} as its datastore. Status: Accepted.
    Decider: {rng.choice(TEAMS)} lead. (This record was never updated after implementation.)
    """)
    w(raw / "02-impl-note.md", session_header("claude", f"cvd{idx}b", "2026-05-25") + f"""
    Implementation note: during build we hit a licensing blocker on {decided}; shipped on {shipped}
    instead. The ADR was not amended (oversight). Prod has been on {shipped} since cutover.
    """)
    w(raw / "code/{}.py".format(mod), f"""
    # {mod}.py — PRODUCTION
    DATASTORE = "{shipped.lower().replace(' ', '_')}"  # what actually shipped
    # ADR says {decided} but licensing blocked it; see impl note
    """)
    w(raw / "git-log.txt", f"""
    55dd66e 2026-05-24 {mod}: provision {shipped} (prod), retire {decided} POC
    88ff99a 2026-02-01 {mod}: scaffold against {decided} (POC)
    """)
    w(out / "query.txt", f"What datastore is {code} ({name}) actually running on in production?")
    gold_d = dict(
        fixture_type="code-vs-decision-conflict",
        answer=shipped,
        answer_aliases=[shipped, shipped.lower()],
        claims=[
            {"id": "current", "text": f"production runs on {shipped} (code + git win)", "supported_by": "code + git + 02-impl-note.md"},
            {"id": "stale_adr", "text": f"the ADR still says {decided} but it is stale/never amended", "supported_by": "01 vs 02/code"},
            {"id": "truth_hierarchy", "text": f"code/git evidence overrides the stale decision record", "supported_by": "truth hierarchy"},
        ],
        rubric=dict(
            must=[f"names {shipped} as what production runs", f"flags the ADR ({decided}) as stale/superseded"],
            must_not=[f"asserts {decided} as the production datastore"],
            negative_control=False,
        ),
    )
    w(out / "gold.json", json.dumps(gold_d, indent=2))


BUILDERS = {
    "glossary-present": build_glossary_present,
    "glossary-absent": build_glossary_absent,
    "scattered-alias": build_scattered_alias,
    "ambiguous-supersession": build_ambiguous_supersession,
    "code-vs-decision-conflict": build_code_vs_decision,
}


def main():
    ap = argparse.ArgumentParser(description="Phase 0b fixture generator (5 retrieval-defeat types)")
    ap.add_argument("--out", default="goal2-fixtures", help="output dir")
    ap.add_argument("--seed", type=int, default=20260614)
    ap.add_argument("--per-type", type=int, default=1, help="fixtures per type")
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    rng = random.Random(args.seed)
    manifest = []
    for typ, fn in BUILDERS.items():
        for i in range(args.per_type):
            fid = f"{typ}__{i:02d}"
            fdir = out / fid
            fn(fdir, rng, i)
            manifest.append(dict(id=fid, type=typ, query=(fdir / "query.txt").read_text().strip()))
    w(out / "MANIFEST.json", json.dumps(dict(seed=args.seed, per_type=args.per_type, fixtures=manifest), indent=2))
    print(f"wrote {len(manifest)} fixtures to {out}/")
    for m in manifest:
        print(f"  {m['id']}: {m['query']}")


if __name__ == "__main__":
    main()
