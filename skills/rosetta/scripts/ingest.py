#!/usr/bin/env python3
"""rosetta ingest — turn external decisions and product signals into Proposed records.

Legacy decision JSON behavior is preserved. Signal JSON widens ingest for crash/analytics/support/etc.
inputs, with conservative privacy handling: sensitive payloads are refused unless explicitly redacted.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decisions  # noqa: E402  (sibling: config / slug / today helpers)


SIGNAL_DISCRIMINATORS = {
    "id", "source", "content_summary", "raw_refs", "created_at", "customer_impact",
    "actionability", "privacy_class",
}
SIGNAL_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
SIGNAL_ENUMS = {
    "source": {"crash", "anr", "analytics", "session_replay", "support", "app_review", "ci",
               "device_farm", "experiment", "security", "privacy"},
    "product_area": {"onboarding", "monetization", "gameplay", "notifications", "social",
                     "account", "unknown"},
    "platform": {"ios", "android", "both", "backend"},
    "customer_impact": {"none", "low", "medium", "high", "critical"},
    "actionability": {"unknown", "needs_more_data", "needs_human_product_judgment",
                      "immediately_actionable"},
    "privacy_class": {"public", "internal", "pii", "sensitive"},
}
SIGNAL_REQUIRED = [
    "id", "source", "product_area", "platform", "app_version", "device_os",
    "content_summary", "raw_refs", "customer_impact", "actionability", "privacy_class",
    "suggested_owner", "created_at",
]


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


def is_signal_item(item):
    return isinstance(item, dict) and SIGNAL_DISCRIMINATORS.issubset(item.keys())


def parse_created_at(value):
    if not isinstance(value, str) or len(value) < 10:
        raise ValueError("created_at must be an ISO-8601 datetime")
    dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value[:10]


def validate_signal_item(item, index, cfg, allow_sensitive):
    errors = []
    if not isinstance(item, dict):
        return None, [f"item {index}: signal must be an object"]
    for field in SIGNAL_REQUIRED:
        if field not in item or item[field] in ("", None):
            errors.append(f"item {index}: missing required signal field '{field}'")
    sid = item.get("id")
    if sid is not None and (not isinstance(sid, str) or not SIGNAL_ID_RE.match(sid)):
        errors.append(f"item {index}: id must match ^[A-Za-z0-9._:-]+$")
    for field, allowed in SIGNAL_ENUMS.items():
        value = item.get(field)
        if value is not None and value not in allowed:
            errors.append(f"item {index}: {field} must be one of {sorted(allowed)}")
    raw_refs = item.get("raw_refs")
    if not isinstance(raw_refs, list) or not raw_refs:
        errors.append(f"item {index}: raw_refs must be a non-empty list")
    else:
        for j, ref in enumerate(raw_refs):
            if not isinstance(ref, dict) or not isinstance(ref.get("url_or_path"), str) or not ref.get("url_or_path"):
                errors.append(f"item {index}: raw_refs[{j}].url_or_path must be a non-empty string")
    try:
        record_date = parse_created_at(item.get("created_at"))
    except Exception as e:
        errors.append(f"item {index}: {e}")
        record_date = None
    rtype = (item.get("type") or "pdr").lower()
    if rtype not in cfg["record_types"]:
        errors.append(f"item {index}: unknown type '{rtype}' (known: {', '.join(cfg['record_types'])})")
    privacy = item.get("privacy_class")
    if privacy in {"pii", "sensitive"}:
        if not allow_sensitive:
            errors.append(f"item {index}: privacy_class {privacy!r} requires --allow-sensitive and redacted: true")
        elif item.get("redacted") is not True:
            errors.append(f"item {index}: --allow-sensitive requires redacted: true for {privacy!r} signals")
    elif "redacted" in item and not isinstance(item.get("redacted"), bool):
        errors.append(f"item {index}: redacted must be boolean when present")
    if errors:
        return None, errors
    summary = item["content_summary"]
    refs = [r["url_or_path"] for r in raw_refs]
    redacted = privacy in {"pii", "sensitive"}
    if redacted:
        summary = f"[redacted: {privacy} signal]"
        refs = []
    title_summary = summary if not redacted else f"{privacy} signal"
    normalized = dict(item)
    normalized.update({
        "type": rtype,
        "record_date": record_date,
        "decider": item.get("suggested_owner") or "unknown",
        "content_summary": summary,
        "raw_ref_values": refs,
        "redacted_signal": redacted,
        "title": f"Signal [{item['source']}/{item['product_area']}]: {title_summary[:72]}",
    })
    return normalized, []


def source_line_for_signal(item):
    refs = [f"`signal:{item['id']}`"]
    if item["privacy_class"] in {"public", "internal"}:
        refs.extend(f"`{ref}`" for ref in item["raw_ref_values"])
    return "- Sources: " + "; ".join(refs)


def build_signal_record(item, label, num):
    raw_refs = item["raw_ref_values"] or [f"[redacted: {item['privacy_class']} signal]"]
    lines = [
        f"# {label} {num} — {item['title']}", "",
        "- Status: Proposed",
        f"- Date: {item['record_date']}",
        f"- Decided originally: {item['record_date']}",
        f"- Decider: {item['decider']}",
        source_line_for_signal(item),
        "- Related: ingested via `scripts/ingest.py` signal mode (ADR 0012)",
        "",
        "## Context", "",
        f"- Platform: {item['platform']}",
        f"- App version: {item['app_version']}",
        f"- Device OS: {item['device_os']}",
        f"- Customer impact: {item['customer_impact']}",
        f"- Actionability: {item['actionability']}",
        f"- Privacy class: {item['privacy_class']}",
        "",
        "## Decision", "",
        "_Signal captured for human product judgment. Confirm before accepting._",
        "",
        "## Consequences", "",
        "Positive:",
        f"- Content summary: {item['content_summary']}",
        "",
        "Negative:",
        "- _To assess._",
        "",
        "## Alternatives considered", "",
        "- _Not applicable to raw signal ingest._",
        "",
        "## Related", "",
        f"- Signal id: `signal:{item['id']}`",
        "- Raw refs:",
    ]
    lines.extend(f"  - {ref}" for ref in raw_refs)
    lines.append("- Review, then set `Status: Accepted` only after human confirmation.")
    return "\n".join(lines) + "\n"


def classify_items(items, schema):
    classified = []
    for item in items:
        if schema == "signals":
            classified.append(("signal", item))
        elif schema == "decisions":
            classified.append(("decision", item))
        elif is_signal_item(item):
            classified.append(("signal", item))
        else:
            classified.append(("decision", item))
    return classified


def load_items(src):
    raw = Path(src).read_text() if src else sys.stdin.read()
    try:
        items = json.loads(raw)
    except Exception as e:
        raise SystemExit(f"could not parse decisions JSON: {e}")
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise SystemExit("input must be a JSON array of decision objects")
    return items


def main():
    ap = argparse.ArgumentParser(description="Ingest external decisions/signals into Proposed records")
    ap.add_argument("--root", default=None, help="decisions library root (default: ./decisions or .)")
    ap.add_argument("--from", dest="src", default=None, help="JSON file of decisions/signals (default: stdin)")
    ap.add_argument("--schema", choices=("auto", "decisions", "signals"), default="auto",
                    help="input schema (default: auto)")
    ap.add_argument("--allow-sensitive", action="store_true",
                    help="allow pii/sensitive signals only when redacted: true")
    args = ap.parse_args()

    if args.root:
        root = Path(args.root).resolve()
    elif (Path.cwd() / "decisions").is_dir():
        root = (Path.cwd() / "decisions").resolve()
    else:
        root = Path.cwd().resolve()
    cfg = decisions.load_config(root)

    items = load_items(args.src)
    classified = classify_items(items, args.schema)

    normalized_signals = {}
    signal_errors = []
    for idx, (kind, item) in enumerate(classified):
        if kind != "signal":
            continue
        normalized, errors = validate_signal_item(item, idx, cfg, args.allow_sensitive)
        if errors:
            signal_errors.extend(errors)
        else:
            normalized_signals[idx] = normalized
    if signal_errors:
        raise SystemExit("signal validation failed:\n- " + "\n- ".join(signal_errors))

    written = 0
    for idx, (kind, item) in enumerate(classified):
        if kind == "signal":
            item = normalized_signals[idx]
            rtype = item["type"]
            rt = cfg["record_types"][rtype]
            d = root / rt["dir"]
            d.mkdir(parents=True, exist_ok=True)
            out, _ = decisions.allocate_and_write(
                root, d, rtype, decisions.slugify(item["title"]),
                lambda num, item=item, rt=rt: build_signal_record(item, rt["label"], num), cfg)
            print(out)
            written += 1
            continue

        if not isinstance(item, dict) or not item.get("title"):
            print(f"skip (no title): {item!r}", file=sys.stderr)
            continue
        rtype = (item.get("type") or "adr").lower()
        if rtype not in cfg["record_types"]:
            raise SystemExit(f"unknown type '{rtype}' (known: {', '.join(cfg['record_types'])})")
        rt = cfg["record_types"][rtype]
        d = root / rt["dir"]
        d.mkdir(parents=True, exist_ok=True)
        # Share the lock-serialized, counter-based allocation with `decisions.py new` (ADR 0023) so
        # ingest is O(1) and race-safe too — no glob, no duplicate-number race.
        out, _ = decisions.allocate_and_write(
            root, d, rtype, decisions.slugify(item["title"]),
            lambda num, item=item, rt=rt: build_record(item, rt["label"], num), cfg)
        print(out)
        written += 1
    print(f"ingested {written} decision(s) as Proposed records — review, then "
          f"`decisions.py index` + `validate`.", file=sys.stderr)


if __name__ == "__main__":
    main()
