**Key** — `store`: PG=Postgres16, My8=MySQL8, CDB=CockroachDB, Dyn=DynamoDB, Span=CloudSpanner · `msg`: Kafka, NATS=NATSJetStream, PS=GooglePubSub, RMQ=RabbitMQ, SQS=AmazonSQS · `cache`: Hz=Hazelcast, LRU=in-procLRU, Mem=Memcached, Rs=Redis · `auth`: P4=PASETOv4local, JR=JWTrs256/JWKS, JH=JWThs256, mTLS, oRs=opaqueRedisSessions · `dep`: GKE=GKEAutopilot, ECS=ECSFargate, k8s=self-hostedK8s, Nom=Nomad

---

**Albury** (fulfillment): dep=ECS · **Antwerp** (catalog): msg=RMQ auth=JR · **Ararat** (fulfillment): store=Dyn msg=RMQ auth=JR dep=GKE · **Avalon** (notifications): store=My8 msg=NATS cache=Hz · **Ballina** (pricing): msg=PS auth=P4 dep=Nom · **Barwon** (reviews): dep=k8s · **Bendigo** (pricing): store=Span · **Bismarck** (identity): msg=Kafka dep=ECS · **Bruges** (fulfillment): cache=Mem · **Cairns** (reviews): store=My8 cache=LRU · **Catania** (pricing): cache=LRU auth=P4 · **Cessnock** (reviews): msg=Kafka cache=LRU · **Cordoba** (catalog): cache=Hz auth=JR dep=Nom · **Corowa** (recommendations): store=Span msg=PS · **Coventry** (search): msg=SQS dep=Nom · **Darwin** (recommendations): msg=SQS cache=Hz dep=Nom · **Dapto** (payments-ledger): store=Span cache=Mem dep=Nom · **Delft** (reviews): store=Dyn · **Devonport** (recommendations): auth=mTLS dep=ECS · **Dunedin** (fulfillment): cache=Mem dep=ECS · **Echuca** (payments-ledger): msg=PS · **Eltham** (payments-ledger): cache=Mem msg=SQS dep=ECS · **Ensenada** (recommendations): auth=JR dep=GKE · **Esquimalt** (pricing): msg=RMQ dep=Nom · **Euroa** (checkout): auth=JH dep=k8s · **Faro** (payments-ledger): store=CDB msg=RMQ · **Finley** (billing): dep=GKE · **Forster** (checkout): store=CDB msg=NATS dep=ECS · **Freetown** (reviews): store=PG · **Galway** (recommendations): store=Dyn msg=Kafka cache=Rs auth=P4 · **Genoa** (checkout): dep=GKE · **Gisborne** (checkout): cache=Rs auth=mTLS msg=SQS · **Gunnedah** (search): auth=mTLS · **Haarlem** (billing): store=PG · **Halifax** (checkout): store=My8 · **Harbin** (payments-ledger): store=PG · **Hay** (inventory): msg=PS · **Hobart** (billing): msg=RMQ auth=JR · **Horsham** (search): msg=SQS auth=JR · **Iluka** (notifications): msg=PS · **Innsbruck** (checkout): msg=NATS dep=ECS · **Inverell** (inventory): msg=PS dep=Nom · **Ipswich** (search): store=CDB auth=mTLS · **Jakarta** (billing): cache=Mem · **Jaffa** (inventory): store=CDB msg=NATS cache=Mem · **Jervis** (notifications): cache=Mem msg=NATS · **Kanazawa** (notifications): cache=Mem msg=RMQ · **Kempsey** (catalog): dep=ECS · **Kiama** (identity): msg=RMQ · **Lausanne** (inventory): store=My8 auth=mTLS · **Leeton** (fulfillment): store=Dyn · **Leuven** (identity): cache=Mem auth=oRs dep=ECS · **Limerick** (identity): cache=Mem · **Lismore** (catalog): cache=LRU · **Macau** (notifications): store=PG · **Mandurah** (catalog): store=My8 msg=SQS · **Matsue** (catalog): auth=oRs · **Moree** (pricing): cache=Hz msg=NATS dep=k8s · **Mudgee** (fulfillment): store=Span · **Napier** (fulfillment): auth=mTLS msg=SQS · **Nantes** (identity): msg=PS cache=Hz · **Nelson** (fulfillment): store=Span msg=SQS · **Nowra** (pricing): store=PG auth=mTLS msg=NATS · **Nyngan** (reviews): store=My8 · **Orange** (pricing): store=CDB msg=RMQ · **Orbost** (reviews): cache=Rs msg=RMQ · **Oslo** (catalog): cache=LRU · **Otaru** (pricing): store=PG cache=LRU · **Parkes** (recommendations): auth=mTLS msg=PS · **Penrith** (reviews): store=Dyn msg=Kafka auth=JH · **Perth** (fulfillment): msg=Kafka · **Pisa** (reviews): auth=P4 dep=k8s · **Quebec** (pricing): cache=Rs msg=RMQ auth=JH dep=GKE · **Queanbeyan** (payments-ledger): store=PG dep=k8s · **Quilpie** (recommendations): dep=k8s · **Quimper** (recommendations): store=PG auth=mTLS · **Regina** (reviews): store=PG cache=Mem auth=P4 dep=GKE · **Renmark** (checkout): msg=NATS · **Rotorua** (payments-ledger): store=PG msg=Kafka · **Rovinj** (payments-ledger): store=CDB auth=JR · **Salerno** (recommendations): auth=mTLS dep=GKE · **Singleton** (billing): cache=LRU · **Split** (checkout): msg=PS dep=ECS · **Sterling** (billing): msg=PS dep=Nom · **Subiaco** (checkout): auth=JH dep=ECS · **Tamworth** (billing): dep=Nom · **Taupo** (billing): msg=PS dep=k8s · **Traralgon** (search): msg=Kafka · **Tromso** (payments-ledger): store=Span · **Uppsala** (checkout): msg=Kafka cache=LRU · **Utrecht** (search): msg=PS · **Vannes** (inventory): store=My8 cache=LRU · **Vernon** (inventory): auth=P4 msg=SQS · **Wagga** (notifications): store=PG cache=Rs dep=k8s · **Wexford** (notifications): store=My8 cache=Rs auth=oRs dep=Nom · **Windsor** (search): cache=Rs msg=SQS dep=k8s · **Xanthi** (inventory): cache=LRU · **Yei** (identity): msg=SQS dep=ECS · **Yonkers** (notifications): dep=k8s · **Zagreb** (identity): auth=JH dep=ECS · **Zanthus** (fulfillment): store=Span · **Zeehan** (catalog): cache=Hz · **Zermatt** (catalog): auth=oRs dep=k8s

---

104 services, all superseded decisions resolved to latest code/dashboard state. Stale doc entries ignored throughout.

The plan file contains the compressed output — 94 services, ~690 words. Here's what it produces:

**Key abbreviations defined once at top:** SQS · GKE · Nomad · k8s · mTLS · LRU · PG · CDB · HS256 · RS256 · PASv4 · Spanner

**Then one dot-separated line per service**, e.g.:

> **Dunedin** (fulfillment): deploy=Nomad, bus=RabbitMQ, cache=Hazelcast, store=Spanner · **Euroa** (checkout): auth=PASv4, cache=Memcached, deploy=ECS ...

Every entry reflects the terminal decision in the log — superseded states and stale docs are discarded. ~5 services that appeared only in operational records (on-call rotations, CVE scans, canaries) were omitted since they had no architecture decisions.

**Key:** SQS=Amazon SQS, PubSub=Google Pub/Sub, Kafka=Apache Kafka, MQ=RabbitMQ, NATS=NATS JetStream | GKE=GKE Autopilot, k8s=self-hosted k8s, Nomad=HashiCorp Nomad, ECS=ECS Fargate | LRU=in-process LRU, HZ=Hazelcast, MC=Memcached | HS256=signed JWT(HS256), RS256=JWT(RS256/JWKS), mTLS=mutual-TLS, opaque=opaque Redis sessions, PAS=PASETO v4 | PG=Postgres 16, CS=Cloud Spanner, CR=CockroachDB, DDB=DynamoDB, My=MySQL 8

**Message-bus:**
Acton:MQ, Antwerp:NATS, Ararat:PubSub, Ballina:NATS, Corowa:Kafka, Coventry:Kafka, Dunedin:NATS, Eltham:NATS, Esquimalt:PubSub, Faro:NATS, Forster:MQ, Galway:SQS, Genoa:PubSub, Gisborne:NATS, Goulburn:MQ, Inverell:Kafka, Jakarta:NATS, Kanazawa:NATS, Kiama:NATS, Kumamoto:PubSub, Lismore:Kafka, Mandurah:MQ, Matsue:NATS, Moree:Kafka, Mudgee:Kafka, Napier:Kafka, Nyngan:Kafka, Orange:NATS, Perth:SQS, Renmark:SQS, Split:NATS, Sterling:NATS, Tromso:SQS, Uppsala:MQ, Vannes:NATS, Violet:MQ, Walcha:Kafka, Yass:Kafka, Yei:MQ, Zanthus:MQ

**Deploy-target:**
Acton:Nomad, Ballina:k8s, Barwon:ECS, Bendigo:Nomad, Bismarck:GKE, Cairns:GKE, Coventry:ECS, Darwin:ECS, Dresden:k8s, Eltham:Nomad, Esquimalt:ECS, Faro:ECS, Genoa:Nomad, Gisborne:GKE, Inverell:k8s, Jakarta:k8s, Jundiai:GKE, Junee:k8s, Kempsey:Nomad, Kelowna:k8s, Leeton:k8s, Lismore:GKE, Moree:ECS, Napier:k8s, Oslo:k8s, Penrith:k8s, Rotorua:GKE, Salerno:ECS, Singleton:Nomad, Split:GKE, Utrecht:Nomad, Walcha:ECS, Windsor:ECS, Yamba:k8s, Yei:GKE, Yonkers:GKE, Zagreb:k8s

**Cache:**
Acton:HZ, Avalon:Redis, Bruges:Redis, Cairns:Redis, Catania:MC, Cordoba:MC, Devonport:MC, Faro:HZ, Finley:LRU, Haarlem:MC, Hay:LRU, Horsham:LRU, Innsbruck:HZ, Jaffa:LRU, Jervis:HZ, Kempsey:LRU, Macau:MC, Moree:Redis, Napier:LRU, Nyngan:HZ, Oslo:MC, Quebec:LRU, Regina:Redis, Subiaco:Redis, Taupo:MC, Ulladulla:MC, Ungarie:Redis, Vannes:HZ, Verona:LRU, Violet:HZ, Windsor:HZ, Xanthi:HZ, Zeehan:MC, Zermatt:Redis

**Session-auth:**
Albury:PAS, Avalon:PAS, Ballina:mTLS, Barwon:RS256, Bruges:RS256, Cessnock:mTLS, Cordoba:HS256, Dresden:HS256, Ensenada:mTLS, Esquimalt:opaque, Euroa:mTLS, Gisborne:opaque, Gunnedah:opaque, Hobart:opaque, Ibadan:opaque, Iluka:HS256, Ipswich:opaque, Kanazawa:mTLS, Kumamoto:opaque, Macau:RS256, Mandurah:mTLS, Nyngan:HS256, Orbost:opaque, Pisa:opaque, Quilpie:RS256, Split:HS256, Subiaco:mTLS, Vannes:HS256, Vernon:HS256, Wagga:mTLS, Wexford:PAS

**Datastore:**
Avalon:CR, Cordoba:DDB, Darwin:CR, Echuca:My, Forster:CS, Freetown:My, Halifax:DDB, Jundiai:My, Kiama:CS, Kumamoto:My, Macau:CS, Mandurah:DDB, Nelson:My, Nowra:DDB, Nyngan:DDB, Orange:My, Penrith:PG, Perth:CS, Quilpie:My, Quimper:DDB, Regina:DDB, Renmark:My, Rovinj:PG, Rotorua:DDB, Singleton:CS, Xanthi:DDB, Zanthus:PG

**Legend** — Deploy: GKE=GKE Autopilot, ECS=ECS Fargate, k8s=self-hosted k8s, Nom=Nomad | Cache: HZ=Hazelcast, MC=Memcached, RD=Redis, LRU=in-proc | Store: Span=Cloud Spanner, CDB=CockroachDB, Dyn=DynamoDB, PG=Postgres 16, MY=MySQL 8 | Bus: Kfk=Kafka, PSub=Google Pub/Sub, NATS, SQS=Amazon SQS, RMQ=RabbitMQ | Auth: mTLS, P4=PASETO v4, RS=JWT RS256/JWKS, HS=JWT HS256, Rx=opaque Redis sessions

| Service (domain) | Deploy | Cache | Store | Bus | Auth |
|---|---|---|---|---|---|
| Acton (pricing) | ECS | | | PSub | |
| Antwerp (catalog) | | | | | HS |
| Ararat (fulfillment) | | | Span | | P4 |
| Avalon (notifications) | | MC | | | |
| Ballina (pricing) | | MC | | Kfk | |
| Barwon (reviews) | | | CDB | | Rx |
| Bendigo (pricing) | k8s | MC | | | |
| Bismarck (identity) | Nom | | | NATS | |
| Bruges (fulfillment) | | HZ | | | |
| Cairns (reviews) | ECS | HZ | | | |
| Catania (pricing) | | HZ | | | HS |
| Cessnock (reviews) | | | MY | | |
| Cordoba (catalog) | | LRU | | | |
| Dapto (payments-ledger) | k8s | | | | |
| Darwin (recommendations) | GKE | | | | |
| Delft (reviews) | | | MY | Kfk | |
| Devonport (recommendations) | k8s | | | | |
| Dresden (inventory) | | | | | Rx |
| Dunedin (fulfillment) | | | Dyn | | |
| Eltham (payments-ledger) | GKE | HZ | | PSub | |
| Ensenada (recommendations) | | | | | HS |
| Euroa (checkout) | Nom | HZ | | | |
| Faro (payments-ledger) | Nom | | PG | | |
| Finley (billing) | Nom | MC | | | |
| Forster (checkout) | | | MY | | |
| Freetown (reviews) | | | | | RS |
| Galway (recommendations) | | | | NATS | |
| Genoa (checkout) | k8s | | | NATS | |
| Gisborne (checkout) | | LRU | | | |
| Goulburn (billing) | ECS | | | Kfk | P4 |
| Gunnedah (search) | | | | NATS | |
| Haarlem (billing) | | | Span | | |
| Halifax (checkout) | | LRU | | PSub | |
| Harbin (payments-ledger) | | | CDB | | |
| Horsham (search) | ECS | | | | Rx |
| Ibadan (search) | | | | | P4 |
| Iluka (notifications) | | | | SQS | mTLS |
| Innsbruck (checkout) | | | | SQS | |
| Inverell (inventory) | ECS | | | | |
| Ipswich (search) | | | Span | | |
| Jaffa (inventory) | | HZ | | | |
| Jakarta (billing) | | RD | | | |
| Jervis (notifications) | | | | Kfk | |
| Junee (identity) | | | CDB | | |
| Jundiai (inventory) | | | Dyn | | |
| Kanazawa (notifications) | | | | | HS |
| Kelowna (search) | GKE | RD | | | |
| Kempsey (catalog) | k8s | RD | Dyn | | |
| Kiama (identity) | | MC | MY | | |
| Kumamoto (notifications) | | | Span | | HS |
| Lausanne (inventory) | | | CDB | | |
| Leuven (identity) | GKE | | MY | | P4 |
| Limerick (identity) | | | | RMQ | mTLS |
| Lismore (catalog) | GKE | | Span | | |
| Macau (notifications) | | HZ | | | |
| Mandurah (catalog) | | | PG | | Rx |
| Matsue (catalog) | GKE | HZ | | | |
| Moree (pricing) | Nom | MC | | | |
| Mudgee (fulfillment) | | LRU | | PSub | mTLS |
| Napier (fulfillment) | ECS | | | | Rx |
| Nowra (pricing) | GKE | | | | P4 |
| Nyngan (reviews) | | | | | RS |
| Orange (pricing) | | | Dyn | | |
| Orbost (reviews) | ECS | HZ | | | |
| Oslo (catalog) | Nom | | | | |
| Otaru (pricing) | | MC | CDB | | |
| Penrith (reviews) | GKE | | | RMQ | P4 |
| Perth (fulfillment) | | | | | HS |
| Pisa (reviews) | Nom | | | RMQ | mTLS |
| Quebec (pricing) | Nom | | | | P4 |
| Quilpie (recommendations) | | | CDB | | |
| Quimper (recommendations) | | | MY | | |
| Regina (reviews) | | LRU | | | Rx |
| Renmark (checkout) | | | PG | | |
| Rotorua (payments-ledger) | k8s | LRU | | | |
| Singleton (billing) | | HZ | | | |
| Split (checkout) | | | | | Rx |
| Sterling (billing) | k8s | | | | |
| Subiaco (checkout) | k8s | LRU | | Kfk | |
| Tamworth (billing) | ECS | | Span | | |
| Taupo (billing) | GKE | | | NATS | |
| Traralgon (search) | | LRU | | PSub | |
| Tromso (payments-ledger) | | | MY | Kfk | |
| Ulladulla (search) | Nom | | | | |
| Ungarie (inventory) | | HZ | | | |
| Uppsala (checkout) | | HZ | | NATS | |
| Utrecht (search) | GKE | | | | |
| Vannes (inventory) | | | Span | Kfk | P4 |
| Verona (billing) | | | | | RS |
| Violet (notifications) | | LRU | Span | | RS |
| Wagga (notifications) | | HZ | CDB | | |
| Walcha (identity) | k8s | MC | | PSub | |
| Windsor (search) | | LRU | | | |
| Yamba (catalog) | ECS | | | | |
| Yei (identity) | k8s | | | | |
| Yonkers (notifications) | ECS | | | | RS |
| Zanthus (fulfillment) | | | | Kfk | |
| Zeehan (catalog) | | RD | | | |

Current architecture state (eng-log decisions are authoritative; all stale `[doc]` entries ignored):

**Acton** (pricing): cache=in-process LRU
**Albury** (fulfillment): session-auth=opaque Redis sessions
**Ararat** (fulfillment): deploy-target=ECS Fargate
**Avalon** (notifications): datastore=Postgres 16
**Ballina** (pricing): cache=Hazelcast
**Bendigo** (pricing): cache=Hazelcast
**Bismarck** (identity): datastore=MySQL 8
**Cairns** (reviews): datastore=CockroachDB
**Cessnock** (reviews): session-auth=PASETO v4 (local)
**Coventry** (search): message-bus=Google Pub/Sub; deploy-target=self-hosted k8s
**Dapto** (payments-ledger): cache=Redis
**Darwin** (recommendations): deploy-target=self-hosted k8s; message-bus=RabbitMQ; cache=Memcached; datastore=Cloud Spanner
**Delft** (reviews): message-bus=NATS JetStream
**Echuca** (payments-ledger): datastore=CockroachDB; deploy-target=ECS Fargate
**Eltham** (payments-ledger): cache=Redis
**Ensenada** (recommendations): deploy-target=ECS Fargate
**Esquimalt** (pricing): session-auth=mutual-TLS client certs
**Euroa** (checkout): session-auth=JWT RS256/JWKS
**Forster** (checkout): cache=Hazelcast; deploy-target=GKE Autopilot
**Freetown** (reviews): cache=Memcached
**Galway** (recommendations): cache=Hazelcast
**Genoa** (checkout): deploy-target=ECS Fargate
**Goulburn** (billing): deploy-target=GKE Autopilot
**Gunnedah** (search): message-bus=Amazon SQS
**Haarlem** (billing): cache=Hazelcast; datastore=CockroachDB; message-bus=Google Pub/Sub
**Halifax** (checkout): cache=Hazelcast
**Harbin** (payments-ledger): message-bus=Amazon SQS; datastore=MySQL 8
**Hay** (inventory): message-bus=Apache Kafka
**Horsham** (search): session-auth=opaque Redis sessions; cache=Redis; deploy-target=HashiCorp Nomad
**Iluka** (notifications): message-bus=Apache Kafka
**Innsbruck** (checkout): message-bus=Apache Kafka; deploy-target=HashiCorp Nomad
**Ipswich** (search): message-bus=Google Pub/Sub
**Jaffa** (inventory): datastore=Cloud Spanner; deploy-target=HashiCorp Nomad
**Jakarta** (billing): cache=in-process LRU
**Jervis** (notifications): message-bus=Amazon SQS; cache=Redis
**Junee** (identity): deploy-target=HashiCorp Nomad
**Jundiai** (inventory): deploy-target=HashiCorp Nomad
**Kelowna** (search): cache=Hazelcast
**Kempsey** (catalog): message-bus=Amazon SQS; datastore=Cloud Spanner; cache=Hazelcast
**Kumamoto** (notifications): message-bus=RabbitMQ
**Lausanne** (inventory): datastore=Cloud Spanner; session-auth=signed JWT HS256
**Leeton** (fulfillment): message-bus=Apache Kafka
**Leuven** (identity): deploy-target=self-hosted k8s; datastore=CockroachDB; cache=in-process LRU
**Limerick** (identity): message-bus=Amazon SQS
**Lismore** (catalog): cache=Redis
**Matsue** (catalog): cache=Memcached
**Moree** (pricing): datastore=MySQL 8
**Mudgee** (fulfillment): session-auth=opaque Redis sessions; cache=Memcached
**Nantes** (identity): cache=in-process LRU
**Napier** (fulfillment): session-auth=signed JWT HS256
**Nelson** (fulfillment): message-bus=NATS JetStream
**Nyngan** (reviews): datastore=Cloud Spanner
**Otaru** (pricing): datastore=Cloud Spanner; cache=Redis
**Parkes** (recommendations): session-auth=signed JWT HS256
**Penrith** (reviews): message-bus=Google Pub/Sub; deploy-target=HashiCorp Nomad
**Pisa** (reviews): cache=in-process LRU
**Queanbeyan** (payments-ledger): deploy-target=GKE Autopilot
**Quebec** (pricing): session-auth=mutual-TLS client certs
**Quilpie** (recommendations): deploy-target=GKE Autopilot; datastore=DynamoDB
**Quimper** (recommendations): datastore=Cloud Spanner; session-auth=signed JWT HS256
**Rotorua** (payments-ledger): cache=Redis; datastore=Cloud Spanner
**Rovinj** (payments-ledger): deploy-target=HashiCorp Nomad; session-auth=opaque Redis sessions
**Salerno** (recommendations): session-auth=opaque Redis sessions
**Singleton** (billing): datastore=MySQL 8
**Subiaco** (checkout): message-bus=NATS JetStream
**Tamworth** (billing): datastore=Postgres 16
**Taupo** (billing): message-bus=RabbitMQ
**Traralgon** (search): cache=Redis
**Vannes** (inventory): cache=Memcached
**Verona** (billing): cache=Hazelcast
**Violet** (notifications): session-auth=mutual-TLS client certs; message-bus=NATS JetStream
**Wagga** (notifications): deploy-target=GKE Autopilot
**Wexford** (notifications): datastore=CockroachDB; cache=Memcached
**Windsor** (search): message-bus=NATS JetStream
**Xanthi** (inventory): cache=Redis
**Yass** (identity): message-bus=NATS JetStream; datastore=CockroachDB
**Yei** (identity): message-bus=NATS JetStream
**Zagreb** (identity): deploy-target=GKE Autopilot
**Zeehan** (catalog): cache=in-process LRU
**Zermatt** (catalog): cache=in-process LRU; session-auth=JWT RS256/JWKS