#!/usr/bin/env python3
"""KILL TEST — large, high-compression recall fixture generator (the decisive thesis experiment).

Goals 1 & 2 both produced NULL results for the *same* reason: their corpora were ~1k tokens, so a flat
summary lost nothing and every arm tied. This generator fixes the one thing that was missing —
**compression pressure** — by emitting a ~100k-token corpus of MANY scattered supersession chains, so
that a fixed ~5k-token flat summary (≈20:1) physically cannot retain the current endpoint of every
chain. That is the regime where flat extraction is known to drop ~33-35 pts of factual recall, and the
only regime in which "does a resolved provenance graph recover that loss?" is even testable.

Design (deterministic, fixed seed — no Date/random nondeterminism in the artifacts):
  - N services, each codenamed (a city) with a domain, each carrying several decision DIMENSIONS
    (session-auth, datastore, message-bus, cache, deploy). Each (service, dimension) is a SUPERSESSION
    CHAIN of 2-4 successive decisions; the LAST link is the current state.
  - Every link emits scattered evidence: an eng-log decision ("supersedes the prior"), a code snapshot,
    and sometimes a dashboard/incident line. All entries from all services are INTERLEAVED by date, so a
    chain's links sit far apart — defeating lead/positional summaries.
  - DISTRACTORS: sibling services with confident, recent, DIFFERENT choices; and stale docs that still
    describe an early link as "current" (never updated after the migration).

It writes, under killtest-outputs/:
  - corpus.md         : the raw interleaved corpus (arm A1 reads this; A2 is summarized FROM it)
  - decisions/        : a ground-truth, integrity-clean, resolvable decision library (arm A4 queries this
                        via decisions.py resolve). Built deterministically from the chains — this tests
                        the RESOLUTION mechanism's recall ceiling, NOT the LLM compiler (whose fallibility
                        is a separate, now-gated concern: ADR 0024). Compile COST is accounted separately.
  - probes.json       : the sampled (service, dimension) questions asked identically of every arm
  - gold.json         : structured gold per probe (current value, replaced value, full chain, distractor)
  - retriever.py is a sibling module (pure-Python BM25-ish) used by the generic-RAG arm A3.

Pure stdlib. Run: python3 killtest_gen.py [--services N] [--seed S]
"""
import argparse
import json
import random
import pathlib

OUT = pathlib.Path(__file__).resolve().parent / "killtest-outputs"

# --- codenames (cities) and domains -------------------------------------------------
CITIES = [
    "Halifax", "Sterling", "Coventry", "Dresden", "Avalon", "Bismarck", "Cordoba", "Dunedin",
    "Esquimalt", "Freetown", "Galway", "Harbin", "Innsbruck", "Jakarta", "Kelowna", "Lausanne",
    "Macau", "Nantes", "Oslo", "Perth", "Quebec", "Regina", "Salerno", "Tromso", "Uppsala",
    "Verona", "Windsor", "Xanthi", "Yonkers", "Zagreb", "Antwerp", "Bruges", "Catania", "Delft",
    "Ensenada", "Faro", "Genoa", "Haarlem", "Ibadan", "Jaffa", "Kanazawa", "Leuven", "Matsue",
    "Nelson", "Otaru", "Pisa", "Quimper", "Rovinj", "Split", "Taupo", "Utrecht", "Vannes",
    "Wexford", "Yei", "Zermatt", "Albury", "Bendigo", "Cairns", "Darwin", "Echuca", "Gisborne",
    "Hobart", "Ipswich", "Jundiai", "Kumamoto", "Limerick", "Mandurah", "Napier", "Orange",
    "Penrith", "Quilpie", "Rotorua", "Subiaco", "Tamworth", "Ulladulla", "Vernon", "Wagga",
    "Yass", "Zeehan", "Ararat", "Ballina", "Cessnock", "Devonport", "Eltham", "Forster",
    "Goulburn", "Horsham", "Inverell", "Jervis", "Kiama", "Lismore", "Mudgee", "Nowra",
    "Orbost", "Parkes", "Queanbeyan", "Renmark", "Singleton", "Traralgon", "Ungarie", "Violet",
    "Walcha", "Yamba", "Zanthus", "Acton", "Barwon", "Corowa", "Dapto", "Euroa", "Finley",
    "Gunnedah", "Hay", "Iluka", "Junee", "Kempsey", "Leeton", "Moree", "Nyngan",
]
DOMAINS = ["checkout", "billing", "search", "inventory", "notifications", "identity", "catalog",
           "fulfillment", "pricing", "reviews", "recommendations", "payments-ledger"]

# --- decision dimensions: pools of mutually-exclusive choices ------------------------
DIMENSIONS = {
    "session-auth": ["signed JWT (HS256)", "opaque Redis-backed sessions", "PASETO v4 (local)",
                     "JWT (RS256 via JWKS)", "mutual-TLS client certs"],
    "datastore": ["Postgres 16", "MySQL 8", "DynamoDB", "CockroachDB", "Cloud Spanner"],
    "message-bus": ["RabbitMQ", "Apache Kafka", "Google Pub/Sub", "NATS JetStream", "Amazon SQS"],
    "cache": ["Redis", "Memcached", "in-process LRU", "Hazelcast"],
    "deploy-target": ["self-hosted k8s", "GKE Autopilot", "ECS Fargate", "HashiCorp Nomad"],
}
# a short code snippet per choice, so the corpus carries code evidence (the "code wins" anchor)
CODE_HINT = {
    "signed JWT (HS256)": "jwt.encode(p, SECRET, algorithm='HS256')",
    "opaque Redis-backed sessions": "redis.setex(f'sess:{tok}', 1800, uid)",
    "PASETO v4 (local)": "V4Local.encrypt(p, KEY, exp=900)",
    "JWT (RS256 via JWKS)": "jwt.encode(p, PRIV, algorithm='RS256')  # JWKS",
    "mutual-TLS client certs": "ssl_ctx.verify_mode = CERT_REQUIRED",
    "Postgres 16": "engine = create_engine('postgresql+psycopg://...:5432/db')",
    "MySQL 8": "engine = create_engine('mysql+mysqldb://...:3306/db')",
    "DynamoDB": "boto3.resource('dynamodb').Table(name)",
    "CockroachDB": "create_engine('cockroachdb://...:26257/db')",
    "Cloud Spanner": "spanner.Client().instance(i).database(d)",
    "RabbitMQ": "pika.BlockingConnection(URL).channel()",
    "Apache Kafka": "KafkaProducer(bootstrap_servers=BROKERS)",
    "Google Pub/Sub": "pubsub_v1.PublisherClient().publish(topic, data)",
    "NATS JetStream": "await nats.connect(); js = nc.jetstream()",
    "Amazon SQS": "boto3.client('sqs').send_message(QueueUrl=q, ...)",
    "Redis": "r = redis.Redis(host=H); r.get(k)",
    "Memcached": "mc = pylibmc.Client([H]); mc.get(k)",
    "in-process LRU": "@lru_cache(maxsize=4096)",
    "Hazelcast": "hz = hazelcast.HazelcastClient(); m = hz.get_map(n)",
    "self-hosted k8s": "kubectl apply -f deploy.yaml  # on-prem cluster",
    "GKE Autopilot": "gcloud container clusters create --autopilot",
    "ECS Fargate": "aws ecs create-service --launch-type FARGATE",
    "HashiCorp Nomad": "nomad job run service.nomad",
}
NOISE = [
    "Adopt OpenTelemetry tracing across the pod.",
    "Tighten the latency SLO to 250ms p99.",
    "Move CI to self-hosted runners for this repo.",
    "Nightly backups to object storage, 30-day retention.",
    "Enable feature flags via the central flag service.",
    "Rotate on-call to a follow-the-sun schedule.",
    "Add a synthetic canary for the public endpoint.",
    "Bump the base image and re-run the CVE scan.",
]


def _date(rng, year_lo=2024, year_hi=2026):
    y = rng.randint(year_lo, year_hi)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    return f"{y}-{m:02d}-{d:02d}"


def _codenames(n):
    """Up to len(CITIES) real names, then synthesize unique resolvable codenames (e.g. 'Halifax-2')
    so the corpus can scale past the base list for the context-window scaling experiment."""
    if n <= len(CITIES):
        return CITIES[:n]
    names = list(CITIES)
    k = 2
    while len(names) < n:
        names += [f"{c}-{k}" for c in CITIES]
        k += 1
    return names[:n]


def build(n_services, seed):
    rng = random.Random(seed)
    services = []
    cities = _codenames(n_services)
    for i, city in enumerate(cities):
        domain = DOMAINS[i % len(DOMAINS)]
        # each service carries 2-4 dimensions
        dims = rng.sample(list(DIMENSIONS), rng.randint(2, 4))
        chains = {}
        for dim in dims:
            pool = DIMENSIONS[dim][:]
            rng.shuffle(pool)
            chain_len = rng.randint(2, 4)
            chain = pool[:chain_len]
            # assign increasing dates to the chain links
            dates = sorted(_date(rng) for _ in chain)
            chains[dim] = list(zip(chain, dates))
        services.append({"city": city, "domain": domain, "chains": chains})
    return services


def render_corpus(services, rng):
    """Emit every link's scattered evidence as dated entries, interleaved across all services."""
    entries = []   # (date, kind, text)
    for svc in services:
        city, domain = svc["city"], svc["domain"]
        for dim, chain in svc["chains"].items():
            for j, (val, date) in enumerate(chain):
                prior = chain[j - 1][0] if j > 0 else None
                if prior:
                    txt = (f"Decision: {city} ({domain}) — migrate {dim} from {prior} to {val}. "
                           f"Supersedes the earlier {prior} decision. Owner: {city} pod.")
                else:
                    txt = (f"Decision: {city} ({domain}) — adopt {val} for {dim}. "
                           f"Initial choice. Owner: {city} pod.")
                entries.append((date, "eng-log", txt))
                entries.append((date, "code", f"services/{city.lower()}/{dim.replace('-', '_')}.py: "
                                              f"{CODE_HINT[val]}  # {city} {dim}"))
                if j == len(chain) - 1:           # current link gets a dashboard confirmation
                    entries.append((date, "dashboard", f"board '{city.lower()}-prod': {dim} now on "
                                                        f"{val}; migration counters trending green."))
            # stale doc distractor: still describes the FIRST link as current
            if len(chain) > 1:
                stale_val = chain[0][0]
                entries.append((rng.choice([c[1] for c in chain]), "doc",
                                f"Architecture overview for {city}: '{city} uses {stale_val} for {dim}.' "
                                f"[NOTE: not updated after later migrations.]"))
        # per-service noise
        for _ in range(rng.randint(1, 3)):
            entries.append((_date(rng), "eng-log", f"{city}: {rng.choice(NOISE)}"))
    rng.shuffle(entries)                          # interleave: defeat positional/lead summaries
    entries.sort(key=lambda e: e[0])              # then chronological-ish (links still scattered)
    lines = ["# Engineering decision history (raw multi-source export) — unnormalized",
             "", "_eng-log, code, dashboards, docs, incidents. Codenames are internal & undefined._", ""]
    for i, (date, kind, text) in enumerate(entries, 1):
        lines.append(f"## R{i:04d} · {date} · [{kind}]")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def render_decisions(services):
    """Build a ground-truth, resolvable, integrity-clean decision library from the chains.
    One ADR per chain link; prior links Superseded by the next; current link Accepted."""
    adr_dir = OUT / "decisions" / "architecture-decisions"
    adr_dir.mkdir(parents=True, exist_ok=True)
    cfg = {"record_types": {"adr": {"label": "ADR", "dir": "architecture-decisions",
                                    "title": "Architecture Decision Record"}},
           "statuses": ["Proposed", "Accepted", "Superseded", "Deprecated", "Rejected"],
           "required_fields": ["Status", "Date", "Decider"], "recommended_fields": ["Sources"],
           "number_width": 4}
    (OUT / "decisions" / ".rosetta-decisions.json").write_text(json.dumps(cfg, indent=2) + "\n")
    n = 0
    index = []
    for svc in services:
        city = svc["city"]
        for dim, chain in svc["chains"].items():
            ids = list(range(n + 1, n + 1 + len(chain)))
            for j, (val, date) in enumerate(chain):
                num = ids[j]
                slug = f"{city.lower()}-{dim}-{val.split()[0].lower().strip('(')}"
                slug = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in slug).strip("-")
                is_last = j == len(chain) - 1
                status = "Accepted" if is_last else f"Superseded by ADR {ids[j + 1]:04d}"
                lines = [f"# ADR {num:04d} — {city} {dim}: {val}", "",
                         f"- Status: {status}", f"- Date: {date}", f"- Decider: {city} pod",
                         f"- Sources: `corpus · {city} · {date}`"]
                if j > 0:
                    lines.append(f"- Supersedes: ADR {ids[j - 1]:04d}")
                lines += ["", "## Decision", "",
                          f"{city} ({svc['domain']}) uses **{val}** for {dim}."]
                if j > 0:
                    lines.append(f"This superseded the earlier {chain[j-1][0]} decision (ADR {ids[j-1]:04d}).")
                (adr_dir / f"{num:04d}-{slug}.md").write_text("\n".join(lines) + "\n")
                index.append({"id": f"ADR {num:04d}", "city": city, "dim": dim,
                              "value": val, "status": status})
            n += len(chain)
    return n


def sample_probes(services, rng, k):
    """Pick k (service, dimension) chains (length≥2 so 'what it replaced' is well-defined) to probe."""
    candidates = [(svc["city"], svc["domain"], dim, chain)
                  for svc in services for dim, chain in svc["chains"].items() if len(chain) >= 2]
    rng.shuffle(candidates)
    probes, gold = [], []
    for qi, (city, domain, dim, chain) in enumerate(candidates[:k], 1):
        current = chain[-1][0]
        replaced = chain[-2][0]
        qid = f"Q{qi:03d}"
        probes.append({"id": qid,
                       "question": f"What is the CURRENT {dim} for Project {city}, and what did it "
                                   f"replace? Name the current choice and the immediately prior one."})
        gold.append({"id": qid, "city": city, "domain": domain, "dimension": dim,
                     "current": current, "replaced": replaced,
                     "chain": [c[0] for c in chain],
                     "avoid": [c[0] for c in chain[:-1]]})   # any non-final link is a recall failure
    return probes, gold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--services", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--probes", type=int, default=40)
    ap.add_argument("--out", default=None, help="override output dir (for the scaling experiment)")
    args = ap.parse_args()

    global OUT
    if args.out:
        OUT = pathlib.Path(args.out).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    services = build(args.services, args.seed)
    corpus = render_corpus(services, random.Random(args.seed + 1))
    (OUT / "corpus.md").write_text(corpus)
    n_adrs = render_decisions(services)
    probes, gold = sample_probes(services, random.Random(args.seed + 2), args.probes)
    (OUT / "probes.json").write_text(json.dumps(probes, indent=2) + "\n")
    (OUT / "gold.json").write_text(json.dumps(gold, indent=2) + "\n")

    approx_tok = len(corpus) // 4
    print(f"services={len(services)}  adrs={n_adrs}  probes={len(probes)}")
    print(f"corpus.md: {len(corpus)} chars, ~{approx_tok} tokens (rough 4-char/tok)")
    print(f"compression to a 5k-token flat summary: ~{approx_tok/5000:.1f}:1")
    print(f"written under {OUT}")


if __name__ == "__main__":
    main()
