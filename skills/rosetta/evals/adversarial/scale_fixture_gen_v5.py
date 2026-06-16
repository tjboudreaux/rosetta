#!/usr/bin/env python3
"""v5 — defeat RETRIEVAL, not scale. The keyword-obvious answer is WRONG; the correct one is reachable
only via a terminology pivot (codename glossary) + an implicitly-superseding later record that shares
NO keywords with the question.

Question: current event-store backend for NEW EU enterprise billing services.
- Keyword-obvious (WRONG): ClickHouse. ADR 0500 (old) and ADR 0980 (recent, confident) both say
  'EU enterprise billing event-store: ClickHouse' — keyword-rich, so grep('EU enterprise billing
  event store') surfaces these and a greedy reader answers ClickHouse.
- Correct: managed Postgres (CloudSQL). Established by ADR 0985 (most recent) which uses ONLY codenames:
  'Project Meridian persistence migrates to the managed relational tier'. It shares no keywords with
  the question. To decode it you must find the glossary (ADR 0300): 'Project Meridian = EU enterprise
  billing event sink; managed relational tier = CloudSQL Postgres; columnar tier = ClickHouse'.
- Misleading legacy code: eu_enterprise/store.py = self-hosted-postgres.
A compiled ADR library would normalize the codenames at compile time, so search returns 0985 directly.
"""
import shutil, random
from pathlib import Path
random.seed(11)
ROOT=Path("/tmp/v5"); RAW=ROOT/"raw-fixture"; ADR=ROOT/"adr-fixture"
for d in (RAW,ADR):
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)
REGIONS=["us","eu","apac","latam"]; TIERS=["free","pro","enterprise"]
SUBS=["billing","ledger","fraud","ingest","search","notify","catalog","identity","shipping","inventory"]
TOPICS=["event-store","queue","cache","transport","serialization","retry","index","partitioning"]
DS=["ClickHouse","DynamoDB","Cassandra","self-hosted Postgres","managed Postgres (CloudSQL)","DuckDB","BigQuery","Kafka log"]
N=1000
recs={}
dates=[f"2025-{m:02d}-{random.randint(1,28):02d}" for m in range(1,13)]+[f"2026-{m:02d}-{random.randint(1,28):02d}" for m in range(1,7)]
LOREM="Throughput, data-residency, cost, and migration risk were weighed across candidates before sign-off."
def body(sub,top,reg,tier,ch): return (f"The {sub} subsystem ({reg}/{tier}) needed a {top} decision. "
    f"Candidates: {', '.join(random.sample(DS,4))}. {LOREM} Selected {ch} for {sub} {top} in {reg}/{tier}.")
for n in range(1,N+1):
    sub=random.choice(SUBS); top=random.choice(TOPICS); reg=random.choice(REGIONS); tier=random.choice(TIERS); ch=random.choice(DS)
    recs[n]=dict(n=n,date=random.choice(dates),status="Accepted",title=f"{sub} {top} [{reg}/{tier}]: {ch}",
        sub=sub,top=top,reg=reg,tier=tier,ch=ch,body=body(sub,top,reg,tier,ch),related="")
# adversarial keyword density: MANY 'EU enterprise billing event-store ClickHouse' distractors
for n in [60,110,170,230,290,340,400,470,540,610,690,750]:
    recs[n].update(sub="billing",top="event-store",reg="eu",tier="enterprise",ch="ClickHouse",
        title="billing event-store [eu/enterprise]: ClickHouse",
        body="EU enterprise billing event-store on ClickHouse for analytics throughput. "+LOREM)
# the trap pair (keyword-rich, ClickHouse) — old + recent reaffirm
recs[500].update(sub="billing",top="event-store",reg="eu",tier="enterprise",ch="ClickHouse",date="2026-02-10",
    title="billing event-store [eu/enterprise]: ClickHouse",
    body="EU enterprise billing event-store standard: ClickHouse. Chosen for query throughput. "+LOREM)
recs[980].update(sub="billing",top="event-store",reg="eu",tier="enterprise",ch="ClickHouse",date="2026-06-05",
    title="billing event-store [eu/enterprise]: ClickHouse (reaffirmed, all teams)",
    body="Reaffirmed: EU enterprise billing event-store remains ClickHouse, effective immediately, all teams. "+LOREM)
# the glossary (findable via 'EU enterprise billing' keyword) — maps codenames
recs[300].update(sub="platform",top="naming",reg="eu",tier="enterprise",ch="",date="2025-09-01",
    title="naming: internal project codenames and persistence tiers",
    body="Codenames: 'Project Meridian' = the EU enterprise billing (payments) event sink. Persistence tiers: "
         "'managed relational tier' = CloudSQL Postgres; 'columnar tier' = ClickHouse; 'document tier' = DynamoDB. "
         "Use codenames in migration ADRs.")
# the CURRENT record — codenamed, NO question keywords, implicitly supersedes, most recent
recs[985].update(sub="meridian",top="persistence",reg="eu",tier="enterprise",ch="managed relational tier",date="2026-06-12",
    title="Project Meridian persistence migrates to the managed relational tier",
    body="For GDPR data-residency, Project Meridian persistence migrates to the managed relational tier, "
         "replacing the prior columnar choice for this sink. Effective for all GDPR-zone tier-1 sinks going forward.")
NEEDLE={300,500,980,985}
def fn(r): return f"{r['n']:04d}-{r['sub']}-{r['top']}.md"
adir=ADR/"decisions"/"architecture-decisions"; adir.mkdir(parents=True)
for n in sorted(recs):
    r=recs[n]
    (adir/fn(r)).write_text(f"# ADR {n:04d} — {r['title']}\n\n- Status: {r['status']}\n- Date: {r['date']}\n"
        f"- Decider: platform-team\n- Sources: {r['sub']}/services/{r['reg']}_{r['tier']}/store.py\n- Related: {r['related'] or '—'}\n\n"
        f"## Context\n\n{r['body']}\n\n## Decision\n\nAdopt {r['ch'] or 'the managed relational tier'} for {r['sub']} {r['top']} in {r['reg']}/{r['tier']}.\n")
CODE={"billing/services/eu_enterprise/store.py":"# LEGACY EU enterprise billing service (pre-migration)\nENGINE='self-hosted-postgres'\ndef store(e):\n    ...\n",
 "billing/services/eu_pro/store.py":"ENGINE='clickhouse'\n","billing/services/us_enterprise/store.py":"ENGINE='dynamodb'\n",
 "README.md":"# platform\nNew-service standards are governed by ADRs in decisions/. Codenames in ADR 0300.\n"}
for rel,c in CODE.items():
    for base in (ADR,RAW):
        p=base/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(c)
shutil.copy("/Users/tjboudreaux/Sandbox/rosetta/skills/rosetta/scripts/decisions.py", ADR/"decisions.py")
tdir=RAW/"history"; tdir.mkdir(parents=True)
bydate=sorted(recs.values(), key=lambda r:(r["date"],r["n"])); buck={}
for r in bydate: buck.setdefault(r["date"][:7],[]).append(r)
for ym,rs in buck.items():
    lines=[f"# engineering decision log — {ym}",""]
    for r in rs:
        lines.append(f"## [{r['date']}] {r['sub']} / {r['top']} / {r['reg']} / {r['tier']}")
        lines.append(f"{r['body']}"); lines.append("")
    (tdir/f"{ym}.md").write_text("\n".join(lines))
(RAW/"git-log.txt").write_text("\n".join(f"{r['date']} {r['sub']}({r['reg']}/{r['tier']}): {r['top']} -> {r['ch'] or 'managed relational tier'}" for r in bydate)+"\n")
cd=ADR/"adr-fixture" if False else None
adr_b=sum(f.stat().st_size for f in adir.glob("*.md")); raw_b=sum(f.stat().st_size for f in tdir.glob("*.md"))
print(f"ADR: {len(list(adir.glob('*.md')))} ADRs ~{adr_b//4//1000}k tok | RAW history ~{raw_b//4//1000}k tok")
print("GOLD: managed Postgres (CloudSQL) — via glossary(0300): Meridian=EU ent billing, managed relational tier=CloudSQL; ADR 0985 (2026-06-12) supersedes the ClickHouse reaffirmation 0980.")
print("TRAP (wrong): ClickHouse (0500/0980 keyword-rich, recent); self-hosted Postgres (legacy code).")
