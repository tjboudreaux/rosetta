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
import contextlib
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
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


def atomic_write_text(path, text):
    """Crash-safe write: temp file in the same dir, then os.replace (atomic on POSIX + Windows).
    A killed process never leaves a half-written record/index behind (mirrors collect.py, ADR 0017)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


MAX_SLUG = 80
COUNTER_FILE = ".counter.json"
INDEX_JSON = "INDEX.json"


def load_counter(path):
    """Per-type highest-number hint for O(1) `new`. Missing/corrupt → {} (rebuilt on demand)."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except Exception as e:
        log(f"counter at {path} unreadable ({e}); will rebuild from disk")
        return {}


def save_counter(path, counter):
    atomic_write_text(path, json.dumps(counter, indent=2))


@contextlib.contextmanager
def counter_lock(root, stale=30.0, max_wait=60.0):
    """Portable advisory lock serializing number allocation (ADR 0023). An O_EXCL lock file is the
    cross-platform primitive (no fcntl → works on Windows too). A lock older than `stale` seconds is
    reclaimed (crash recovery), so it can never deadlock permanently."""
    lock = Path(root) / ".counter.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale:
                    os.unlink(lock)            # reclaim a stale lock
                    continue
            except OSError:
                continue
            if time.monotonic() - start > max_wait:
                raise SystemExit(f"could not acquire {lock} (held > {max_wait}s)")
            time.sleep(0.01)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.unlink(lock)


def allocate_and_write(root, d, rtype, slug, render, cfg):
    """Atomically allocate the next number for a record type and write the record. Serialized by
    counter_lock so concurrent `new`/`ingest` can never collide on a number (fixes the prior
    O_EXCL-reserve-protects-filename-not-number race, ADR 0023). `render(num_str) -> text` builds the
    body once the number is known. Crash-safe: the record is written via atomic_write_text (temp +
    replace), so a crash leaves no 0-byte tombstone occupying the number."""
    width = cfg["number_width"]
    counter_path = Path(root) / COUNTER_FILE
    with counter_lock(root):
        counter = load_counter(counter_path)
        number = (counter[rtype] + 1) if rtype in counter else (scan_max_number(d) + 1)
        # guard against counter drift / externally-created files at this number (targeted glob, fast)
        while next(d.glob(f"{str(number).zfill(max(width, len(str(number))))}-*.md"), None) is not None:
            number += 1
        num_str = str(number).zfill(max(width, len(str(number))))
        out = d / f"{num_str}-{slug}.md"
        atomic_write_text(out, render(num_str))
        counter[rtype] = number
        save_counter(counter_path, counter)
    return out, num_str


def slugify(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return (s.strip("-") or "untitled")[:MAX_SLUG].strip("-")


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
def scan_max_number(d):
    """Highest NNNN-prefixed record number in a directory (0 if none). O(n) glob — Phase 2 replaces
    this with an O(1) counter file; kept as the rebuildable source of truth."""
    mx = 0
    for f in d.glob("*.md"):
        m = re.match(r"^(\d+)-", f.name)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx


def render_record(template, label, num_str, title, status, date, decider):
    rendered, h1_done = [], False
    for ln in template.splitlines():
        if not h1_done and ln.startswith("# "):       # the heading placeholder (NNNN is non-numeric)
            rendered.append(f"# {label} {num_str} — {title}")
            h1_done = True
        elif ln.startswith("- Status:"):
            rendered.append(f"- Status: {status}")
        elif ln.startswith("- Date:"):
            rendered.append(f"- Date: {date}")
        elif ln.startswith("- Decider:") and decider:
            rendered.append(f"- Decider: {decider}")
        else:
            rendered.append(ln)
    return "\n".join(rendered) + "\n"


def cmd_new(args, root, cfg):
    rtype = args.type.lower()
    if rtype not in cfg["record_types"]:
        raise SystemExit(f"unknown type '{rtype}'; known: {', '.join(cfg['record_types'])}")
    rt = cfg["record_types"][rtype]
    d = root / rt["dir"]
    d.mkdir(parents=True, exist_ok=True)
    label = rt["label"]
    slug = slugify(args.title)
    template = resolve_template(root, rtype, rt).read_text()
    date = args.date or today_iso()

    # O(1) numbering via a lock-serialized per-type counter (ADR 0021/0023). The lock guarantees number
    # uniqueness even across concurrent `new`; atomic_write_text guarantees no 0-byte tombstone.
    out, _ = allocate_and_write(
        root, d, rtype, slug,
        lambda num_str: render_record(template, label, num_str, args.title, args.status, date, args.decider),
        cfg)
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
    atomic_write_text(index_path, new)

    # Refresh the O(1) numbering counter from disk (self-heals drift) and emit a machine-readable
    # INDEX.json so the agent / external tools can query the library without reading every record.
    width = cfg["number_width"]
    counter, idx = {}, []
    for rec in records:
        counter[rec["type"]] = max(counter.get(rec["type"], 0), rec["number"])
        idx.append({"id": f"{rec['label']} {str(rec['number']).zfill(width)}", "type": rec["type"],
                    "number": rec["number"], "title": rec["title"],
                    "status": rec["fields"].get("Status", ""), "date": effective_date(rec),
                    "path": rec["path"].relative_to(root).as_posix()})
    save_counter(root / COUNTER_FILE, counter)
    atomic_write_text(root / INDEX_JSON, json.dumps(idx, indent=2) + "\n")
    print(f"indexed {len(records)} records → {index_path}")


def _find_supersede_cycle(edges):
    """Return a cycle [id, …, id] in the supersede graph, or None. Iterative DFS (no recursion limit
    risk on long chains). A cycle means records supersede each other in a loop — forbidden oscillation."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}
    for start in list(edges):
        if color.get(start, WHITE) != WHITE:
            continue
        stack = [(start, iter(edges.get(start, ())))]
        path = [start]
        color[start] = GRAY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if color.get(nxt, WHITE) == GRAY:        # back-edge → cycle
                    return path[path.index(nxt):] + [nxt]
                if color.get(nxt, WHITE) == WHITE:
                    color[nxt] = GRAY
                    path.append(nxt)
                    stack.append((nxt, iter(edges.get(nxt, ()))))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()
                path.pop()
    return None


def cmd_validate(args, root, cfg):
    records = collect_records(root, cfg)
    l2t = label_to_type(cfg)
    valid_labels = {rt["label"].upper() for rt in cfg["record_types"].values()}
    statuses = cfg["statuses"]
    errors, warnings = [], []

    ids = {}                      # (type, number) -> path
    all_ids = set()               # "ADR 5" style for supersede resolution
    supersede_edges = {}          # (LABEL, num) -> {(LABEL, num)}: "is superseded by"
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
        # supersede graph: edge u->v means "u is superseded by v" (v replaces u)
        rec_id = (rec["label"].upper(), rec["number"])
        for lbl, num in label_re.findall(rec["fields"].get("Status", "")):
            if "supersed" in rec["fields"].get("Status", "").lower():
                supersede_edges.setdefault(rec_id, set()).add((lbl.upper(), int(num)))
        for lbl, num in label_re.findall(rec["fields"].get("Supersedes", "")):
            supersede_edges.setdefault((lbl.upper(), int(num)), set()).add(rec_id)

    cycle = _find_supersede_cycle(supersede_edges)
    if cycle:
        chain = " → ".join(f"{lbl} {num}" for lbl, num in cycle)
        errors.append(f"supersede cycle (oscillation): {chain}")

    for w in warnings:
        log(f"warn: {w}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    strict_fail = bool(args.strict and warnings)
    note = " (--strict: warnings are failures)" if args.strict else ""
    print(f"validated {len(records)} records: {len(errors)} errors, {len(warnings)} warnings{note}")
    if errors or strict_fail:
        sys.exit(1)


# --- scale: query the library instead of reading it whole (ADR 0021) -----------------
def record_id(rec, cfg):
    return f"{rec['label']} {str(rec['number']).zfill(cfg['number_width'])}"


def resolve_id(records, idstr, want_type=None):
    """Resolve 'ADR 0002' / 'ADR 2' / 'adr2' / '2' (+ optional --type) to exactly one record."""
    m = re.match(r"\s*([A-Za-z]+)?\s*0*(\d+)\s*$", idstr or "")
    if not m:
        raise SystemExit(f"bad record id '{idstr}' (expected e.g. 'ADR 0002')")
    lbl = m.group(1).upper() if m.group(1) else None
    num = int(m.group(2))
    cands = [r for r in records if r["number"] == num
             and (lbl is None or r["label"].upper() == lbl)
             and (want_type is None or r["type"] == want_type)]
    if not cands:
        raise SystemExit(f"no record matches '{idstr}'")
    if len(cands) > 1:
        ids = ", ".join(f"{r['label']} {r['number']}" for r in cands)
        raise SystemExit(f"ambiguous id '{idstr}' (matches {ids}); qualify with a label")
    return cands[0]


def cmd_search(args, root, cfg):
    """Return only the records matching a filter — so the agent queries a 50k-ADR library instead of
    reading it into context. Prints a compact JSON array (token-frugal)."""
    records = collect_records(root, cfg)
    q = (args.text or "").lower()
    limit = args.limit
    hits, total = [], 0
    for rec in records:
        if args.type and rec["type"] != args.type.lower():
            continue
        if args.status and not rec["fields"].get("Status", "").lower().startswith(args.status.lower()):
            continue
        if q:
            hay = (rec["title"] + " " + " ".join(rec["fields"].values())).lower()
            if q not in hay and q not in rec["path"].read_text(errors="replace").lower():
                continue
        total += 1
        if limit and len(hits) >= limit:
            continue
        hits.append({"id": record_id(rec, cfg), "type": rec["type"],
                     "status": rec["fields"].get("Status", ""), "title": rec["title"],
                     "path": rec["path"].relative_to(root).as_posix()})
    out = {"hits": hits, "returned": len(hits), "total_matches": total}
    if limit and total > len(hits):          # surface truncation loudly — never silently cap
        out["truncated"] = True
        out["note"] = f"showing {len(hits)} of {total}; narrow the query or raise --limit"
    print(json.dumps(out, indent=2))


def cmd_get(args, root, cfg):
    """Print one record in full (so the agent reads a single record, not the whole library)."""
    rec = resolve_id(collect_records(root, cfg), args.id, args.type.lower() if args.type else None)
    print(rec["path"].read_text())


def _set_frontmatter_line(text, field, value):
    """Replace the first `- <field>: …` line, or insert it right after `- Status:` if absent. Raises
    ValueError if it can do NEITHER (a malformed record with no frontmatter) so callers fail loudly
    instead of silently no-op'ing (ADR 0023)."""
    pat = re.compile(rf"^-\s+{re.escape(field)}:.*$", re.MULTILINE)
    if pat.search(text):
        return pat.sub(f"- {field}: {value}", text, count=1)
    new_text, n = re.subn(r"^(-\s+Status:.*)$", rf"\1\n- {field}: {value}", text, count=1,
                          flags=re.MULTILINE)
    if n == 0:
        raise ValueError(f"cannot set '{field}': record has no '- {field}:' or '- Status:' line")
    return new_text


def cmd_supersede(args, root, cfg):
    """Deterministically supersede one record by another: flip the old record's Status to
    'Superseded by <new>' and set the new record's 'Supersedes: <old>'. Removes the error-prone manual
    edit the agent would otherwise do by hand across thousands of records."""
    records = collect_records(root, cfg)
    old = resolve_id(records, args.old, args.type.lower() if args.type else None)
    new = resolve_id(records, getattr(args, "by"), args.type.lower() if args.type else None)
    old_id, new_id = record_id(old, cfg), record_id(new, cfg)
    if old["path"] == new["path"]:
        raise SystemExit("a record cannot supersede itself")

    try:
        old_text = _set_frontmatter_line(old["path"].read_text(), "Status", f"Superseded by {new_id}")
    except ValueError as e:
        raise SystemExit(f"{old_id}: {e}")     # fail loudly instead of a silent no-op
    atomic_write_text(old["path"], old_text)
    new_text = _set_frontmatter_line(new["path"].read_text(), "Supersedes", old_id)
    atomic_write_text(new["path"], new_text)
    print(f"{old_id} → Superseded by {new_id}; {new_id} Supersedes {old_id}")
    log("run `decisions.py index` to refresh the timeline, then `validate`")


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

    add_root(sub.add_parser("index", help="regenerate the timeline table + INDEX.json + counter"))
    p_val = sub.add_parser("validate", help="check frontmatter, numbering, statuses, supersede links")
    add_root(p_val)
    p_val.add_argument("--strict", action="store_true", help="treat warnings as failures (nonzero exit)")

    p_search = sub.add_parser("search", help="query the library (returns only matches as JSON)")
    add_root(p_search)
    p_search.add_argument("--text", default=None, help="substring to match in title/frontmatter/body")
    p_search.add_argument("--type", default=None, help="restrict to a record type (adr|pdr|bdr|…)")
    p_search.add_argument("--status", default=None, help="restrict to a Status prefix (e.g. Accepted)")
    p_search.add_argument("--limit", type=int, default=50, help="max hits to return (0 = no limit)")

    p_get = sub.add_parser("get", help="print one record in full by id (e.g. 'ADR 0002')")
    add_root(p_get)
    p_get.add_argument("id", help="record id, e.g. 'ADR 0002' or '2'")
    p_get.add_argument("--type", default=None, help="disambiguate when the number spans types")

    p_sup = sub.add_parser("supersede", help="flip <old> to 'Superseded by <new>' and link <new>")
    add_root(p_sup)
    p_sup.add_argument("old", help="record being superseded, e.g. 'ADR 0002'")
    p_sup.add_argument("--by", required=True, help="superseding record, e.g. 'ADR 0026'")
    p_sup.add_argument("--type", default=None, help="disambiguate ids when a number spans types")

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
    elif args.cmd == "search":
        cmd_search(args, root, cfg)
    elif args.cmd == "get":
        cmd_get(args, root, cfg)
    elif args.cmd == "supersede":
        cmd_supersede(args, root, cfg)


if __name__ == "__main__":
    main()
