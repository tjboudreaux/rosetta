#!/usr/bin/env python3
"""Rosetta decisions — deterministic scaffold / index / validate for a decision library.

A decision library is a `decisions/` root holding ADRs (architecture), PDRs (product), and BDRs
(business) in the canonical "rosetta format": a `# <LABEL> NNNN — title` heading, a bullet-list
frontmatter (Status / Date / Decided originally / Decider / Sources / Related), then fixed body
sections. See references/decision-schema.md.

This tool does the MECHANICAL work so agents/humans spend tokens only on the actual decision prose:

  new       allocate the next number, render a template, write <dir>/NNNN-slug.md
  index     parse every record's frontmatter and regenerate the timeline table in the index file
  validate  check frontmatter contract, unique numbering, status values, and supersede links

Pure stdlib. The per-team contract lives in `<root>/config.json` (optional; rosetta defaults apply
when absent), so any team uses their own record types, dirs, numbering, statuses, and templates
without touching this script. Mirrors the conventions of scripts/collect.py.
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent          # ~/.claude/skills/rosetta
DEFAULT_TEMPLATES = SKILL_ROOT / "templates"

TIMELINE_START = "<!-- ROSETTA:TIMELINE:START -->"
TIMELINE_END = "<!-- ROSETTA:TIMELINE:END -->"

DEFAULT_CONFIG = {
    "number_width": 4,
    "statuses": ["Proposed", "Accepted", "Superseded", "Deprecated", "Rejected"],
    "required_fields": ["Status", "Date", "Decider"],
    "recommended_fields": ["Sources"],
    "optional_fields": ["Decided originally", "Related", "Supersedes"],
    "record_types": {
        "adr": {"label": "ADR", "name": "Architecture Decision Record",
                "dir": "architecture-decisions", "template": "templates/adr-template.md"},
        "pdr": {"label": "PDR", "name": "Product Decision Record",
                "dir": "product-decisions", "template": "templates/pdr-template.md"},
        "bdr": {"label": "BDR", "name": "Business Decision Record",
                "dir": "business-decisions", "template": "templates/bdr-template.md"},
    },
    "index": {"path": "README.md", "columns": ["Date", "ID", "Type", "Decision", "Status"]},
}

FRONT_RE = re.compile(r"^-\s+([A-Za-z][A-Za-z ]*?):\s*(.*)$")      # "- Status: Accepted"
H1_RE = re.compile(r"^#\s+(\w+)\s+(\d+)\s*[—–-]+\s*(.+?)\s*$")     # "# ADR 0005 — title"


def log(msg):
    print(f"[rosetta] {msg}", file=sys.stderr)


def slugify(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return s.strip("-") or "untitled"


def today_iso():
    return dt.date.today().isoformat()


# --- config --------------------------------------------------------------------------
def load_config(root):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))   # deep copy
    cfg_path = root / "config.json"
    if cfg_path.exists():
        try:
            user = json.loads(cfg_path.read_text())
        except Exception as e:
            log(f"WARNING: could not parse {cfg_path}: {e}; using defaults")
            user = {}
        for k, v in user.items():
            if k.startswith("_") or k == "schema":
                continue
            cfg[k] = v          # top-level override (record_types replaced wholesale by design)
    return cfg


def label_to_type(cfg):
    return {rt["label"].upper(): t for t, rt in cfg["record_types"].items()}


def resolve_template(root, rtype, rt):
    cand = rt.get("template")
    if cand:
        p = (root / cand) if not Path(cand).is_absolute() else Path(cand)
        if p.exists():
            return p
    fallback = DEFAULT_TEMPLATES / f"{rtype}-template.md"
    if fallback.exists():
        return fallback
    raise SystemExit(f"no template found for type '{rtype}' (looked at {cand!r} and {fallback})")


# --- record parsing ------------------------------------------------------------------
def parse_record(path):
    """Return dict(label, number, title, fields{}, path) or None if the H1 doesn't parse."""
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    h1 = None
    for ln in lines:
        if ln.strip():
            h1 = ln
            break
    if not h1:
        return None
    m = H1_RE.match(h1)
    if not m:
        return None
    label, number, title = m.group(1).upper(), int(m.group(2)), m.group(3).strip()
    fields = {}
    started = False
    for ln in lines:
        if H1_RE.match(ln):
            started = True
            continue
        if not started:
            continue
        if ln.startswith("## "):          # frontmatter ends at the first body section
            break
        fm = FRONT_RE.match(ln)
        if fm:
            fields[fm.group(1).strip()] = fm.group(2).strip()
    return {"label": label, "number": number, "title": title, "fields": fields, "path": path}


def collect_records(root, cfg):
    records = []
    for rtype, rt in cfg["record_types"].items():
        d = root / rt["dir"]
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            rec = parse_record(f)
            if rec is None:
                log(f"WARNING: {f} has no parseable '# LABEL NNNN — title' heading; skipped")
                continue
            rec["type"] = rtype
            records.append(rec)
    return records


def effective_date(rec):
    return rec["fields"].get("Decided originally", "") or rec["fields"].get("Date", "")


# --- commands ------------------------------------------------------------------------
def cmd_new(args, root, cfg):
    rtype = args.type.lower()
    if rtype not in cfg["record_types"]:
        raise SystemExit(f"unknown type '{rtype}'; known: {', '.join(cfg['record_types'])}")
    rt = cfg["record_types"][rtype]
    d = root / rt["dir"]
    d.mkdir(parents=True, exist_ok=True)
    width = cfg["number_width"]

    used = []
    for f in d.glob("*.md"):
        m = re.match(r"^(\d+)-", f.name)
        if m:
            used.append(int(m.group(1)))
    number = (max(used) + 1) if used else 1
    num_str = str(number).zfill(width)
    label = rt["label"]
    slug = slugify(args.title)
    out = d / f"{num_str}-{slug}.md"
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing {out}")

    template = resolve_template(root, rtype, rt).read_text()
    date = args.date or today_iso()
    rendered = []
    h1_done = False
    for ln in template.splitlines():
        if not h1_done and ln.startswith("# "):       # the heading placeholder (NNNN is non-numeric)
            rendered.append(f"# {label} {num_str} — {args.title}")
            h1_done = True
        elif ln.startswith("- Status:"):
            rendered.append(f"- Status: {args.status}")
        elif ln.startswith("- Date:"):
            rendered.append(f"- Date: {date}")
        elif ln.startswith("- Decider:") and args.decider:
            rendered.append(f"- Decider: {args.decider}")
        else:
            rendered.append(ln)
    out.write_text("\n".join(rendered) + "\n")
    print(out)


def build_timeline(records, cfg, index_path):
    cols = cfg["index"]["columns"]
    rows = []
    for rec in sorted(records, key=lambda r: (effective_date(r), r["type"], r["number"])):
        rid = f"{rec['label']} {str(rec['number']).zfill(cfg['number_width'])}"
        rel = rec["path"].relative_to(index_path.parent) if index_path.parent in rec["path"].parents \
            else Path("..") / rec["path"].name
        cellmap = {
            "Date": effective_date(rec) or "—",
            "ID": f"[{rid}]({rel.as_posix()})",
            "Type": rec["type"],
            "Decision": rec["title"],
            "Status": rec["fields"].get("Status", "—"),
        }
        rows.append("| " + " | ".join(cellmap.get(c, "—") for c in cols) + " |")
    header = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    return "\n".join([header, sep] + rows)


def cmd_index(args, root, cfg):
    records = collect_records(root, cfg)
    index_path = root / cfg["index"]["path"]
    table = build_timeline(records, cfg, index_path)
    block = f"{TIMELINE_START}\n{table}\n{TIMELINE_END}"

    if index_path.exists():
        text = index_path.read_text()
        if TIMELINE_START in text and TIMELINE_END in text:
            new = re.sub(re.escape(TIMELINE_START) + r".*?" + re.escape(TIMELINE_END),
                         lambda _m: block, text, flags=re.DOTALL)
        else:
            new = text.rstrip() + "\n\n## Timeline\n\n" + block + "\n"
    else:
        new = (f"# Decision Library — index & timeline\n\n"
               f"Catalog of decisions, reconciled onto one timeline. Each record cites its evidence "
               f"as `agent · session-id · date`, a git commit, a code path, or a task id.\n\n"
               f"## Timeline\n\n{block}\n")
    index_path.write_text(new)
    print(f"indexed {len(records)} records → {index_path}")


def cmd_validate(args, root, cfg):
    records = collect_records(root, cfg)
    l2t = label_to_type(cfg)
    valid_labels = {rt["label"].upper() for rt in cfg["record_types"].values()}
    statuses = cfg["statuses"]
    errors, warnings = [], []

    ids = {}                      # (type, number) -> path
    all_ids = set()               # "ADR 5" style for supersede resolution
    for rec in records:
        if rec["label"] not in valid_labels:
            errors.append(f"{rec['path'].name}: unknown record label '{rec['label']}'")
        key = (rec["type"], rec["number"])
        if key in ids:
            errors.append(f"duplicate number {rec['label']} {rec['number']}: "
                          f"{ids[key].name} and {rec['path'].name}")
        ids[key] = rec["path"]
        all_ids.add((rec["label"].upper(), rec["number"]))

    label_re = re.compile(r"\b(" + "|".join(sorted(valid_labels)) + r")\s+(\d+)\b")
    for rec in records:
        name = rec["path"].name
        for req in cfg["required_fields"]:
            if not rec["fields"].get(req):
                errors.append(f"{name}: missing required field '{req}'")
        status = rec["fields"].get("Status", "")
        if status and not any(status.startswith(s) for s in statuses):
            errors.append(f"{name}: Status '{status}' not in {statuses} (or 'Superseded by <ID>')")
        if "Sources" in cfg.get("recommended_fields", []) and not rec["fields"].get("Sources"):
            warnings.append(f"{name}: no Sources (recommended for provenance)")
        if not re.match(r"^\d+-[a-z0-9][a-z0-9-]*$", rec["path"].stem):
            warnings.append(f"{name}: filename should be 'NNNN-kebab-slug.md'")
        # supersede links resolve
        link_text = " ".join(rec["fields"].get(k, "") for k in ("Status", "Supersedes", "Related"))
        for lbl, num in label_re.findall(link_text):
            if (lbl.upper(), int(num)) not in all_ids and (lbl.upper(), int(num)) != \
                    (rec["label"].upper(), rec["number"]):
                # only flag when it's an explicit supersede/supersedes reference
                if "supersed" in link_text.lower():
                    errors.append(f"{name}: references {lbl} {num} which does not exist")

    for w in warnings:
        log(f"warn: {w}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    print(f"validated {len(records)} records: {len(errors)} errors, {len(warnings)} warnings")
    if errors:
        sys.exit(1)


# --- main ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Rosetta decision-record tool")
    ROOT_HELP = "decisions library root (default: ./decisions if it exists, else .)"
    ap.add_argument("--root", default=None, help=ROOT_HELP)
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --root is accepted before OR after the subcommand. The subparser copies use SUPPRESS so an
    # omitted --root there never clobbers a value parsed at the top level.
    def add_root(p):
        p.add_argument("--root", default=argparse.SUPPRESS, help=ROOT_HELP)

    p_new = sub.add_parser("new", help="scaffold the next-numbered record from a template")
    add_root(p_new)
    p_new.add_argument("--type", required=True, help="record type key (adr|pdr|bdr|…)")
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--status", default="Proposed")
    p_new.add_argument("--decider", default=None)
    p_new.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")

    add_root(sub.add_parser("index", help="regenerate the timeline table in the index file"))
    add_root(sub.add_parser("validate", help="check frontmatter, numbering, statuses, supersede links"))

    args = ap.parse_args()

    if args.root:
        root = Path(args.root).resolve()
    elif (Path.cwd() / "decisions").is_dir():
        root = (Path.cwd() / "decisions").resolve()
    else:
        root = Path.cwd().resolve()
    cfg = load_config(root)

    if args.cmd == "new":
        cmd_new(args, root, cfg)
    elif args.cmd == "index":
        cmd_index(args, root, cfg)
    elif args.cmd == "validate":
        cmd_validate(args, root, cfg)


if __name__ == "__main__":
    main()
