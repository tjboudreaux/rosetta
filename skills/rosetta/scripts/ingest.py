#!/usr/bin/env python3
"""rosetta ingest — turn decisions made OUTSIDE code and agent chat (meetings via Circleback,
Slack threads, trackers) into reviewable decision records, deterministically. Backs ADR 0012.

Split of responsibility (the honest design — see references/external-sources.md):
  - The AGENT does the non-deterministic part: query the external sources via their MCP tools
    (Circleback, Slack, Gmail, Atlassian, …), extract candidate decisions, and emit a JSON array.
  - THIS SCRIPT does the deterministic part: allocate numbers, write one record per decision with
    a first-draft body, and stamp every one `Status: Proposed` — because a thing decided in a
    meeting is "proposed/intended" until a human confirms it (the truth hierarchy). A human then
    reviews, flips confirmed ones to `Accepted`, and runs `decisions.py index` + `validate`.

Input JSON (via --from <file> or stdin) — a list of objects:
  [
    {
      "type": "bdr",                                  # adr | pdr | bdr (record type key)
      "title": "Adopt usage-based pricing",
      "decider": "Travis",
      "date": "2026-06-02",                           # optional (default: today)
      "source": "circleback · mtg-7f3a · 2026-06-02", # provenance citation (recommended)
      "context": "...", "decision": "...", "why": "..."   # optional body drafts
    }
  ]

Pure stdlib. Reuses scripts/decisions.py for config, numbering width, and slugs.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decisions  # noqa: E402  (sibling: config / slug / today helpers)


def next_number(d, width):
    used = []
    for f in d.glob("*.md"):
        m = re.match(r"^(\d+)-", f.name)
        if m:
            used.append(int(m.group(1)))
    return str((max(used) + 1) if used else 1).zfill(width)


def build_record(item, label, num):
    title = item["title"]
    date = item.get("date") or decisions.today_iso()
    decider = item.get("decider") or "unknown"
    source = item.get("source")
    src_line = (f"- Sources: `{source}` (external; **unconfirmed** — pending human review)"
                if source else "- Sources: (external source; **unconfirmed** — pending human review)")
    lines = [
        f"# {label} {num} — {title}", "",
        "- Status: Proposed",
        f"- Date: {date}",
        f"- Decided originally: {date}",
        f"- Decider: {decider}",
        src_line,
        "- Related: ingested via `scripts/ingest.py` (ADR 0012)",
        "",
        "## Context", "",
        item.get("context") or "_Captured from an external source (meeting/chat). Confirm and expand._", "",
        "## Decision", "",
        item.get("decision") or "_Confirm the decision exactly as it was made._", "",
        "## Consequences", "",
        "Positive:",
        f"- {item['why']}" if item.get("why") else "- _Why this was decided._",
        "",
        "Negative:",
        "- _To assess._",
        "",
        "## Alternatives considered", "",
        "- _Capture what else was on the table._",
        "",
        "## Related", "",
        "- Ingested from an external source. **Review, then set `Status: Accepted`** (or delete).",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Ingest external decisions into Proposed records")
    ap.add_argument("--root", default=None, help="decisions library root (default: ./decisions or .)")
    ap.add_argument("--from", dest="src", default=None, help="JSON file of decisions (default: stdin)")
    args = ap.parse_args()

    if args.root:
        root = Path(args.root).resolve()
    elif (Path.cwd() / "decisions").is_dir():
        root = (Path.cwd() / "decisions").resolve()
    else:
        root = Path.cwd().resolve()
    cfg = decisions.load_config(root)

    raw = Path(args.src).read_text() if args.src else sys.stdin.read()
    try:
        items = json.loads(raw)
    except Exception as e:
        raise SystemExit(f"could not parse decisions JSON: {e}")
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise SystemExit("input must be a JSON array of decision objects")

    written = 0
    for item in items:
        if not isinstance(item, dict) or not item.get("title"):
            print(f"skip (no title): {item!r}", file=sys.stderr)
            continue
        rtype = (item.get("type") or "adr").lower()
        if rtype not in cfg["record_types"]:
            raise SystemExit(f"unknown type '{rtype}' (known: {', '.join(cfg['record_types'])})")
        rt = cfg["record_types"][rtype]
        d = root / rt["dir"]
        d.mkdir(parents=True, exist_ok=True)
        num = next_number(d, cfg["number_width"])
        out = d / f"{num}-{decisions.slugify(item['title'])}.md"
        if out.exists():
            print(f"skip (exists): {out}", file=sys.stderr)
            continue
        out.write_text(build_record(item, rt["label"], num))
        print(out)
        written += 1
    print(f"ingested {written} decision(s) as Proposed records — review, then "
          f"`decisions.py index` + `validate`.", file=sys.stderr)


if __name__ == "__main__":
    main()
