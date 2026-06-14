#!/usr/bin/env python3
"""10x-harder fixture. Same truth in two forms (raw transcripts vs compiled ADR library), but built
to defeat the three shortcuts that made v3 trivial:
 1. NO single-file code oracle — legacy code is MISLEADING; only the governing ADR is authoritative.
 2. Context-overflowing raw history (~hundreds of k tokens) — forces lossy retrieval.
 3. Date-inverting reversal + region×tier conditional + high near-miss density — grep misleads.

Needle: the APPROVED event-store standard that NEW *EU enterprise* billing services must use =
managed Postgres (CloudSQL), per ADR 0985 (a revert that reaffirms ADR 0500 after ADR 0980's
ClickHouse attempt failed GDPR review). Traps: EU pro/free legitimately use ClickHouse; the legacy EU
enterprise service still runs self-hosted Postgres (code is stale/misleading); 0980 (newest-dated
change) says ClickHouse but was reverted.
"""
import os, shutil, random
from pathlib import Path
random.seed(7)
ROOT=Path("/tmp/v4"); RAW=ROOT/"raw-fixture"; ADR=ROOT/"adr-fixture"
for d in (RAW,ADR):
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)

REGIONS=["us","eu","apac","latam"]; TIERS=["free","pro","enterprise"]
SUBS=["billing","ledger","fraud","ingest","search","notify","catalog","identity","shipping","inventory","reporting","media"]
TOPICS=["event-store","queue","cache","transport","serialization","retry","index","partitioning","ratelimit","auth"]
DS=["ClickHouse","DynamoDB","Cassandra","self-hosted Postgres","managed Postgres (CloudSQL)","DuckDB","BigQuery","Kafka log"]
N=1100
recs={}
dates=[f"2025-{m:02d}-{random.randint(1,28):02d}" for m in range(1,13)]+[f"2026-{m:02d}-{random.randint(1,28):02d}" for m in range(1,7)]
LOREM=("Under sustained change volume the team weighed throughput, data-residency, operational burden, "
 "cost, and migration risk across the candidate backends before committing. Owners signed off after review.")
def body(sub,top,reg,tier,ch):
    return (f"The {sub} subsystem ({reg}/{tier}) required a {top} decision. Candidates considered: "
            f"{', '.join(random.sample(DS,4))}. {LOREM} Selected: {ch} for {sub} {top} in {reg}/{tier}.")
# distractors
for n in range(1,N+1):
    sub=random.choice(SUBS); top=random.choice(TOPICS); reg=random.choice(REGIONS); tier=random.choice(TIERS)
    ch=random.choice(DS); recs[n]=dict(n=n,date=random.choice(dates),status="Accepted",
        title=f"{sub} {top} [{reg}/{tier}]: {ch}",sub=sub,top=top,reg=reg,tier=tier,ch=ch,
        body=body(sub,top,reg,tier,ch),related="")
# near-miss density: many billing event-store EU rows across tiers + ClickHouse mentions
NEAR=[(120,"eu","pro","ClickHouse"),(180,"eu","free","ClickHouse"),(244,"us","enterprise","DynamoDB"),
 (300,"apac","enterprise","Cassandra"),(355,"eu","pro","ClickHouse"),(410,"latam","enterprise","managed Postgres (CloudSQL)"),
 (455,"us","pro","ClickHouse"),(520,"eu","free","ClickHouse"),(610,"apac","pro","ClickHouse"),(680,"us","enterprise","ClickHouse"),
 (744,"eu","pro","ClickHouse"),(802,"latam","pro","DynamoDB"),(860,"apac","enterprise","ClickHouse"),(905,"us","free","DuckDB")]
for n,reg,tier,ch in NEAR:
    recs[n].update(sub="billing",top="event-store",reg=reg,tier=tier,ch=ch,
        title=f"billing event-store [{reg}/{tier}]: {ch}",body=body("billing","event-store",reg,tier,ch))
# ---- the needle chain (date-inverting reversal) ----
recs[500].update(sub="billing",top="event-store",reg="eu",tier="enterprise",ch="managed Postgres (CloudSQL)",
 date="2026-03-01",status="Accepted",related="",
 title="billing event-store [eu/enterprise]: managed Postgres (CloudSQL), GDPR-reviewed",
 body="APPROVED STANDARD: new EU enterprise billing services must use managed Postgres (CloudSQL). "
      "Chosen after GDPR data-residency review; ClickHouse rejected for EU enterprise on residency grounds. "
      "Note: EU pro/free tiers use ClickHouse; this decision is enterprise-tier only.")
recs[980].update(sub="billing",top="event-store",reg="eu",tier="enterprise",ch="ClickHouse-managed",
 date="2026-06-05",status="Superseded by ADR 0985",related="ADR 0500",
 title="billing event-store [eu/enterprise]: migrate to ClickHouse-managed (cost)",
 body="Proposed migrating EU enterprise billing event-store from CloudSQL Postgres to ClickHouse-managed "
      "to cut cost. Supersedes nothing yet; pending compliance sign-off.")
recs[985].update(sub="billing",top="event-store",reg="eu",tier="enterprise",ch="managed Postgres (CloudSQL)",
 date="2026-06-07",status="Accepted",related="ADR 0500, ADR 0980",
 title="REVERT billing event-store [eu/enterprise] to managed Postgres (CloudSQL)",
 body="ClickHouse-managed (ADR 0980) FAILED the EU GDPR data-residency review. Revert: new EU enterprise "
      "billing services REMAIN on managed Postgres (CloudSQL) per ADR 0500. This is the current approved standard.")
NEEDLE={500,980,985}

def fname(r): return f"{r['n']:04d}-{r['sub']}-{r['top']}.md"
# write ADR fixture
adir=ADR/"decisions"/"architecture-decisions"; adir.mkdir(parents=True)
for n in sorted(recs):
    r=recs[n]
    (adir/fname(r)).write_text(
     f"# ADR {n:04d} — {r['title']}\n\n- Status: {r['status']}\n- Date: {r['date']}\n- Decider: platform-team\n"
     f"- Sources: {r['sub']}/services/{r['reg']}_{r['tier']}/store.py\n- Related: {r['related'] or '—'}\n\n"
     f"## Context\n\n{r['body']}\n\n## Decision\n\nAdopt {r['ch']} for {r['sub']} {r['top']} in {r['reg']}/{r['tier']}.\n")
# MISLEADING code: legacy EU enterprise billing service still on self-hosted Postgres (mid-migration);
# many other service files use a mix -> no single oracle, and the obvious one is STALE.
CODE={
 "billing/services/eu_enterprise/store.py":"# LEGACY EU enterprise billing service (pre-migration; still running)\nENGINE='self-hosted-postgres'\ndef store(e):\n    ...\n",
 "billing/services/eu_pro/store.py":"ENGINE='clickhouse'\n",
 "billing/services/eu_free/store.py":"ENGINE='clickhouse'\n",
 "billing/services/us_enterprise/store.py":"ENGINE='dynamodb'\n",
 "billing/services/apac_enterprise/store.py":"ENGINE='cassandra'\n",
 "billing/services/latam_enterprise/store.py":"ENGINE='cloudsql-postgres'\n",
 "README.md":"# platform\nHigh-churn backend; new-service standards are governed by ADRs in decisions/.\n"}
for rel,c in CODE.items():
    for base in (ADR,RAW):
        p=base/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(c)
shutil.copy("/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/scripts/decisions.py", ADR/"decisions.py")
# write RAW fixture: verbose chronological transcripts (overflow), NO decisions/
tdir=RAW/"history"; tdir.mkdir(parents=True)
bydate=sorted(recs.values(), key=lambda r:(r["date"],r["n"]))
buck={}
for r in bydate: buck.setdefault(r["date"][:7],[]).append(r)
for ym,rs in buck.items():
    lines=[f"# engineering decision log — {ym}",""]
    for r in rs:
        verb=random.choice(["We decided","After review we chose","The team committed to","Settled on","Adopted"])
        rev=" (NOTE: later revisited)" if str(r['status']).startswith("Superseded") else ""
        lines.append(f"## [{r['date']}] {r['sub']} / {r['top']} / {r['reg']} / {r['tier']}{rev}")
        lines.append(f"{verb} {r['ch']} for {r['sub']} {r['top']} in the {r['reg']} {r['tier']} tier. {r['body']}")
        lines.append("")
    (tdir/f"{ym}.md").write_text("\n".join(lines))
glog=[f"{r['date']} {r['sub']}({r['reg']}/{r['tier']}): {r['top']} -> {r['ch']}" for r in bydate]
(RAW/"git-log.txt").write_text("\n".join(glog)+"\n")
adr_b=sum(f.stat().st_size for f in adir.glob("*.md"))
raw_b=sum(f.stat().st_size for f in tdir.glob("*.md"))+(RAW/"git-log.txt").stat().st_size
print(f"ADR fixture: {len(list(adir.glob('*.md')))} ADRs, {adr_b//1024}KB (~{adr_b//4//1000}k tokens)")
print(f"RAW fixture: {raw_b//1024}KB (~{raw_b//4//1000}k tokens)")
print("needle: EU/enterprise new billing event-store = managed Postgres (CloudSQL); ADR 0985 reverts 0980, reaffirms 0500")
print("traps: 0980 newest-dated says ClickHouse (reverted); EU pro/free=ClickHouse; legacy code=self-hosted-postgres")
