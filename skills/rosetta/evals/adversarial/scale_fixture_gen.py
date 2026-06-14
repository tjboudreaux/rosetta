#!/usr/bin/env python3
"""Generate a high-churn decision history in two forms that encode the SAME truth:
  raw-fixture/  : messy chronological transcripts + git log + code  (NO decisions/)
  adr-fixture/  : a Rosetta-compiled decisions/ ADR library + code  (+ decisions.py CLI)
Planted needle: current EU billing event-store = managed Postgres (CloudSQL), reachable only by
tracing a supersession chain + a regional conditional + a recent migration + a code override, among
~400 distractor decisions. Both fixtures share the code override.
"""
import os, shutil, subprocess, random
from pathlib import Path
random.seed(42)  # deterministic (Math.random forbidden note is JS-only; python seed ok)

ROOT = Path("/tmp/v3")
RAW = ROOT/"raw-fixture"; ADR = ROOT/"adr-fixture"
for d in (RAW, ADR):
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)

SUBS = ["analytics","ingest","search","notifications","auth","payments","catalog","shipping",
        "inventory","reporting","fraud","recommend","media","identity","ledger"]
TOPICS = ["datastore","queue","cache","transport","serialization","auth-scheme","rate-limit",
          "retry-policy","index","partitioning"]
CHOICES = {"datastore":["Postgres","MySQL","DuckDB","ClickHouse","Cassandra","DynamoDB","SQLite"],
 "queue":["Kafka","RabbitMQ","SQS","NATS","Redis Streams"],"cache":["Redis","Memcached","in-process LRU"],
 "transport":["gRPC","REST","GraphQL","Thrift"],"serialization":["protobuf","JSON","Avro","msgpack"],
 "auth-scheme":["JWT","session cookies","OAuth2","mTLS"],"rate-limit":["token bucket","sliding window","fixed window"],
 "retry-policy":["exponential backoff","fixed delay","no retry"],"index":["btree","gin","brin","hash"],
 "partitioning":["by-tenant","by-date","by-region","none"]}

# ---- planted needle: billing/EU event-store ----
NEEDLE = [
 (12 ,"2025-07-02","payments event-store on self-hosted Postgres", "Superseded by ADR 0088"),
 (88 ,"2025-08-19","move payments event-store to Kafka log",       "Superseded by ADR 0211"),
 (211,"2025-10-30","payments event-store to DuckDB columnar",      "Superseded by ADR 0357"),
 (357,"2026-01-15","payments event-store to ClickHouse (global default)", "Accepted"),
 (402,"2026-02-20","EU EXCEPTION: keep payments event-store on Postgres in the EU region for GDPR data-residency; ClickHouse applies to non-EU only", "Accepted"),
 (489,"2026-05-28","migrate EU payments event-store to MANAGED Postgres (CloudSQL); supersedes the self-hosted EU Postgres operationally; new EU code must use the CloudSQL client", "Accepted"),
]
NEEDLE_NUMS = {n for n,_,_,_ in NEEDLE}

def adr_md(n, title, date, status, sources, body_ctx, body_dec, related=""):
    return (f"# ADR {n:04d} — {title}\n\n"
            f"- Status: {status}\n- Date: {date}\n- Decider: platform-team\n"
            f"- Sources: {sources}\n- Related: {related or '—'}\n\n"
            f"## Context\n\n{body_ctx}\n\n## Decision\n\n{body_dec}\n")

# build 400 records; reserve needle numbers
N=400
records={}  # num -> dict
# distractors
dates = [f"2025-{m:02d}-{random.randint(1,28):02d}" for m in range(6,13)] + \
        [f"2026-{m:02d}-{random.randint(1,28):02d}" for m in range(1,6)]
for n in range(1, N+1):
    if n in NEEDLE_NUMS: continue
    sub=random.choice(SUBS); top=random.choice(TOPICS); ch=random.choice(CHOICES[top])
    date=random.choice(dates)
    # ~25% superseded by a later existing distractor
    status="Accepted"
    title=f"{sub} {top}: use {ch}"
    ctx=f"The {sub} subsystem needed a {top} decision under high change volume. Options weighed: {', '.join(CHOICES[top])}."
    dec=f"Adopt {ch} for {sub} {top}. Owner: {sub}-team."
    records[n]=dict(n=n,title=title,date=date,status=status,sources=f"{sub}/{top}.py",ctx=ctx,dec=dec,related="",sub=sub,top=top,ch=ch)
# add needle records
SRC={12:"payments/store.py",88:"payments/store.py",211:"payments/store.py",357:"payments/store.py",
     402:"payments/eu/store.py",489:"payments/eu/store.py"}
for n,date,desc,status in NEEDLE:
    records[n]=dict(n=n,title=f"payments event-store: {desc[:48]}",date=date,status=status,
        sources=SRC[n],ctx=f"Event-store decision for the payments subsystem. {desc}.",
        dec=desc.capitalize()+".",related=("ADR 0357" if n in (402,489) else ""),sub="payments",top="datastore",ch="")
# make ~90 distractors superseded by a later existing distractor (valid chains/noise)
nums=sorted(records)
for n in nums:
    if n in NEEDLE_NUMS: continue
    if random.random()<0.22:
        later=[x for x in nums if x>n and x not in NEEDLE_NUMS]
        if later:
            tgt=random.choice(later[:50] or later)
            records[n]["status"]=f"Superseded by ADR {tgt:04d}"

# distractor near-misses: a few OTHER subsystems also on ClickHouse / Postgres event stores
for n,desc in [(150,"analytics event-store to ClickHouse"),(220,"reporting event-store to ClickHouse"),
               (330,"ingest event-store on Postgres"),(371,"fraud event-store to ClickHouse")]:
    if n in records and n not in NEEDLE_NUMS:
        records[n].update(title=desc, ctx=f"Event-store choice for that subsystem. {desc}.", dec=desc.capitalize()+".", top="datastore")

# ---- write ADR fixture ----
adir=ADR/"decisions"/"architecture-decisions"; adir.mkdir(parents=True)
for n in sorted(records):
    r=records[n]
    (adir/f"{n:04d}-{r['sub']}-{r['top']}.md").write_text(
        adr_md(n,r["title"],r["date"],r["status"],r["sources"],r["ctx"],r["dec"],r["related"]))
# code override (both fixtures): EU billing uses CloudSQL managed Postgres
CODE={"payments/eu/store.py":"# EU payments event store — managed Postgres (CloudSQL)\nfrom cloudsql import Client\nENGINE='cloudsql-postgres'\nREGION='eu'\ndef store(e):\n    return Client().write('billing_events_eu', e)\n",
 "payments/store.py":"# global (non-EU) payments event store\nENGINE='clickhouse'\ndef store(e):\n    ...\n",
 "README.md":"# platform\nHigh-churn backend. See decisions/ for ADRs.\n"}
for rel,c in CODE.items():
    p=ADR/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(c)
    p2=RAW/rel; p2.parent.mkdir(parents=True,exist_ok=True); p2.write_text(c)
# copy decisions.py CLI into ADR fixture (self-contained)
shutil.copy("/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/scripts/decisions.py", ADR/"decisions.py")

# ---- write RAW fixture: same facts as messy chronological transcripts + git log, NO decisions/ ----
tdir=RAW/"history"; tdir.mkdir(parents=True)
# one transcript file per ~month, many terse lines
bydate=sorted(records.values(), key=lambda r:(r["date"],r["n"]))
buckets={}
for r in bydate: buckets.setdefault(r["date"][:7],[]).append(r)
for ym,rs in buckets.items():
    lines=[f"# agent log {ym}"]
    for r in rs:
        verb=random.choice(["decided","agreed","switched to","going with","settled on"])
        line=f"- [{r['date']}] {r['sub']}/{r['top']}: {verb} {r['ch'] or r['dec']}"
        if str(r['status']).startswith("Superseded"):
            line+=f"  (later revisited)"
        lines.append(line)
    (tdir/f"{ym}.md").write_text("\n".join(lines)+"\n")
# git log (terse) — code changes; include the EU cloudsql migration commit recent
gitlog=[]
for r in bydate:
    gitlog.append(f"{r['date']} {r['sub']}: {r['top']} -> {r['ch'] or r['dec'][:30]}")
gitlog.append("2026-05-29 payments(eu): migrate event store to CloudSQL managed Postgres")
(RAW/"git-log.txt").write_text("\n".join(gitlog)+"\n")

# stats
adr_bytes=sum(f.stat().st_size for f in adir.glob("*.md"))
raw_bytes=sum(f.stat().st_size for f in tdir.glob("*.md"))+ (RAW/"git-log.txt").stat().st_size
print(f"ADR fixture: {len(list(adir.glob('*.md')))} ADRs, {adr_bytes//1024}KB (~{adr_bytes//4//1000}k tokens)")
print(f"RAW fixture: {len(list(tdir.glob('*.md')))} history files, {raw_bytes//1024}KB (~{raw_bytes//4//1000}k tokens)")
print("needle: current EU payments event-store = managed Postgres (CloudSQL), ADR 0489 + payments/eu/store.py")
