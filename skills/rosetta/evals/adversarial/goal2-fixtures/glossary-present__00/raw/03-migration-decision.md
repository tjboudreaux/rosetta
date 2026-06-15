# session: claude · glos0c · 2026-04-22
- agent: claude
- cwd: ~/repo


    Migration review for the notification dispatcher. After the MySQL hotspotting incidents we are moving the
    Beacon ledger tier to Postgres for strong consistency. This supersedes the earlier MySQL call.
    Cutover complete in prod cluster on 2026-04-20.
