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
import subprocess
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
    "optional_fields": ["Decided originally", "Related", "Supersedes", "Aliases"],
    "record_types": {
        "adr": {"label": "ADR", "name": "Architecture Decision Record",
                "dir": "architecture-decisions", "template": "templates/adr-template.md"},
        "pdr": {"label": "PDR", "name": "Product Decision Record",
                "dir": "product-decisions", "template": "templates/pdr-template.md"},
        "bdr": {"label": "BDR", "name": "Business Decision Record",
                "dir": "business-decisions", "template": "templates/bdr-template.md"},
    },
    "index": {"path": "README.md", "columns": ["Date", "ID", "Type", "Decision", "Status"]},
    "alias_stoplist": ["api", "app", "web", "auth", "prod", "test", "db", "data", "core", "service"],
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
GLOSSARY_MD = "GLOSSARY.md"
GLOSSARY_JSON = "GLOSSARY.json"


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

    # Derived alias glossary (SPEC-04): GLOSSARY.md (human) + GLOSSARY.json (machine). index is a
    # generator (exit 0) but surfaces ambiguous codenames / broken chains LOUDLY on stderr — `validate`
    # is the hard gate. resolve/validate always rebuild the map from records; this is never a cache.
    gmd, gjson, ares = build_glossary_artifacts(records, cfg)
    atomic_write_text(root / GLOSSARY_MD, gmd)
    atomic_write_text(root / GLOSSARY_JSON, json.dumps(gjson, indent=2) + "\n")
    for alias, ids in ares["collisions"].items():
        print(f"WARNING: alias '{alias}' is ambiguous -> {', '.join(ids)} "
              f"(`validate` will fail until disambiguated)", file=sys.stderr)
    for rid, why in sorted(ares["invalid_chains"].items()):
        print(f"WARNING: {rid}: invalid supersession chain on an aliased record ({why})", file=sys.stderr)
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

    # alias glossary hard gate (SPEC-04): an ambiguous codename (one alias → >=2 distinct current
    # decisions) or a broken alias-bearing supersession chain silently misresolves — so this is a HARD
    # error (exits nonzero even WITHOUT --strict, joining integrity's "ambiguous provenance" class).
    ares = build_alias_map(records, cfg)
    for alias, aids in sorted(ares["collisions"].items()):
        errors.append(f"alias '{alias}' is ambiguous — maps to {len(aids)} distinct current decisions "
                      f"({', '.join(aids)}); disambiguate by scope or supersede")
    for rid, why in sorted(ares["invalid_chains"].items()):
        errors.append(f"{rid}: invalid supersession chain on an aliased record ({why})")

    # optional integrity pass: fabricated ADR-id references and ghost source citations anywhere in a
    # record (the compiler-hallucination gate). These are hard errors — fabricated provenance has no
    # benign reading — so `validate --integrity` doubles as the CI anti-hallucination gate.
    if getattr(args, "integrity", False):
        intg = assess_integrity(records, cfg, root)
        for d in intg["dangling_refs"]:
            errors.append(f"{d['record']}: references {d['ref']} which does not exist "
                          f"(fabricated provenance)")
        for g in intg["ghost_sources"]:
            errors.append(f"{g['record']}: cites source '{g['source']}' which is not on disk "
                          f"(ghost citation)")

    # optional freshness pass: an Accepted record whose cited code moved past its Date is "stale" —
    # surfaced as a warning here (and a failure under --strict) so `validate --staleness` doubles as the
    # CI freshness gate without a separate invocation.
    stale_found = []
    if getattr(args, "staleness", False):
        git_ok, assessed = assess_staleness(records, root, cfg)
        if not git_ok:
            log("staleness: not a git work tree (or git unavailable); freshness check skipped")
        else:
            for a in assessed:
                if a["stale"] is True:
                    stale_found.append(a)
                    paths = ", ".join(sp["path"] for sp in a["stale_paths"])
                    warnings.append(f"{a['id']} ({a['title']}): STALE — cited code changed after "
                                    f"{a['date']} ({paths})")

    for w in warnings:
        log(f"warn: {w}")
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    strict_fail = bool(args.strict and warnings)
    note = " (--strict: warnings are failures)" if args.strict else ""
    stale_note = f", {len(stale_found)} stale" if getattr(args, "staleness", False) else ""
    print(f"validated {len(records)} records: {len(errors)} errors, "
          f"{len(warnings)} warnings{stale_note}{note}")
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


SUPERSEDED_BY_RE = re.compile(r"superseded\s+by\s+([A-Za-z]+\s*\d+)", re.IGNORECASE)


def resolve_current(records, rec, cfg, _seen=None):
    """Follow a 'Superseded by <ID>' chain to the current (live) record. Returns (current_rec, chain)
    where chain is the list of superseded ids walked through. Cycle-safe (stops if it revisits an id)."""
    seen = _seen if _seen is not None else set()
    chain = []
    cur = rec
    while True:
        rid = record_id(cur, cfg)
        if rid in seen:                      # defensive: supersede cycle (validate catches these)
            break
        seen.add(rid)
        m = SUPERSEDED_BY_RE.search(cur["fields"].get("Status", ""))
        if not m:
            break
        nxt = resolve_id(records, m.group(1), None)
        if not nxt:
            break
        chain.append(rid)
        cur = nxt
    return cur, chain


def immediately_superseded(records, cur, cfg):
    """The record the CURRENT record directly replaced — i.e. 'what it replaced'. Prefer cur's own
    `Supersedes: <ID>` field; fall back to the reverse edge (a record whose Status is
    'Superseded by <cur>'). Returns the prior record or None. Lets `resolve` answer not just the
    current decision but the one immediately before it (the smoke run showed consumers need this)."""
    label_re = re.compile(r"\b([A-Za-z]+)\s+(\d+)\b")
    m = label_re.search(cur["fields"].get("Supersedes", ""))
    if m:
        prior = resolve_id(records, f"{m.group(1)} {m.group(2)}", None)
        if prior:
            return prior
    cur_id = record_id(cur, cfg).lower()
    for rec in records:
        status = rec["fields"].get("Status", "")
        sm = SUPERSEDED_BY_RE.search(status)
        if sm and record_id(resolve_id(records, sm.group(1), None) or rec, cfg).lower() == cur_id \
                and rec is not cur:
            # the reverse edge can be ambiguous on long chains; only trust it when unambiguous
            return rec
    return None


# --- alias / glossary layer (the moat: deterministic codename resolution, SPEC-04) ---
# A record's optional `Aliases:` field lists `;`-separated codenames/synonyms for the concept it
# decides. Each alias maps to the record's CURRENT endpoint (following supersession) so a codename
# query resolves to the live decision. Precision-safe by construction: alias-FIELD text is excluded
# from the literal haystack (it matches ONLY via this map), one normalized phrase maps to one current
# decision, and an alias mapping to >=2 distinct current decisions is a HARD error (an ambiguous
# codename silently misresolves — the exact failure Rosetta exists to prevent). The signal is split:
# `conflict` stays literal-only; `resolved_unique` is the union-aware "did this uniquely resolve?" flag.
# Hardened across 4 adversarial-review rounds — see specs/SPEC-04-alias-glossary.md.

_ALIAS_SEP_RE = re.compile(r"[\s\-_/\\]+")            # separators: whitespace, - _ / \ (others kept)
_ALIAS_LINE_RE = re.compile(r"(?im)^[ \t]*-[ \t]*Aliases:.*$")        # the frontmatter Aliases line
_IDREF_RE = re.compile(r"\b([A-Za-z]+)\s*0*(\d+)\b")
DEFAULT_ALIAS_STOPLIST = DEFAULT_CONFIG["alias_stoplist"]


def normalize_alias(s):
    """Casefold; collapse runs of separator chars (whitespace, - _ / \\) to one space; strip. All other
    characters are preserved verbatim, so `C++`/`C#`/`.NET`/`A.1` stay distinct while `Project-Meridian`,
    `project_meridian`, `project meridian` all normalize equal. Returns '' if nothing survives."""
    return _ALIAS_SEP_RE.sub(" ", (s or "").casefold()).strip()


def parse_alias_field(value):
    """A record's raw `Aliases:` value -> de-duplicated, order-preserving list of normalized alias
    phrases. Splits on ';', drops blank segments (`foo;;bar`) and separator-only segments whose
    normalized form is empty (`-`), so no empty alias can ever enter the map (SPEC-04 R4 guard)."""
    out, seen = [], set()
    for seg in (value or "").split(";"):
        norm = normalize_alias(seg)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def literal_haystack(rec):
    """The text `resolve` matches literally: title + every field value EXCEPT `Aliases` + the record
    body (raw text with the `- Aliases:` frontmatter line removed). So alias-FIELD text never
    participates in literal matching (it matches only via the alias map), while body-prose mentions of
    a codename remain legitimate literal content."""
    fields = " ".join(v for k, v in rec["fields"].items() if k.lower() != "aliases")
    body = _ALIAS_LINE_RE.sub("", rec["path"].read_text(errors="replace"))
    return (rec["title"] + " " + fields + " " + body).lower()


def _norm_idref(lbl, num, cfg):
    return f"{lbl.upper()} {str(int(num)).zfill(cfg['number_width'])}"


def _superseded_by_edges(records, cfg):
    """Map id -> set(ids that supersede it), from both `Status: Superseded by X` and `Supersedes: Y`.
    Only edges between existing records are kept (used to detect forked chains)."""
    valid = {record_id(r, cfg) for r in records}
    edges = {}
    for rec in records:
        rid = record_id(rec, cfg)
        sm = SUPERSEDED_BY_RE.search(rec["fields"].get("Status", ""))
        if sm:
            m = _IDREF_RE.search(sm.group(1))
            if m:
                tgt = _norm_idref(m.group(1), m.group(2), cfg)
                if tgt in valid:
                    edges.setdefault(rid, set()).add(tgt)
        for m in _IDREF_RE.finditer(rec["fields"].get("Supersedes", "")):
            y = _norm_idref(m.group(1), m.group(2), cfg)
            if y in valid:
                edges.setdefault(y, set()).add(rid)
    return edges


def _chain_invalid_reason(rec, records, cfg, sup_by, by_id):
    """Why a declaring record's supersession chain cannot be collapsed deterministically (or None):
    a fork (a record superseded by >=2 distinct records), a missing named superseder, or a
    contradiction (X says 'Superseded by Y' but Y's Supersedes omits X). Cycle-safe."""
    seen = set()
    cur = rec
    while True:
        rid = record_id(cur, cfg)
        if rid in seen:
            return "supersede cycle"
        seen.add(rid)
        if len(sup_by.get(rid, set())) >= 2:
            return f"forked — superseded by {', '.join(sorted(sup_by[rid]))}"
        sm = SUPERSEDED_BY_RE.search(cur["fields"].get("Status", ""))
        if not sm:
            return None
        m = _IDREF_RE.search(sm.group(1))
        nxt_id = _norm_idref(m.group(1), m.group(2), cfg) if m else None
        nxt = by_id.get(nxt_id)
        if nxt is None:
            return f"names missing superseder {nxt_id}"
        sup_field = nxt["fields"].get("Supersedes", "")
        if sup_field:
            back = {_norm_idref(mm.group(1), mm.group(2), cfg) for mm in _IDREF_RE.finditer(sup_field)}
            if rid not in back:
                return f"{rid} says superseded by {nxt_id}, but {nxt_id} does not list it under Supersedes"
        cur = nxt


def build_alias_map(records, cfg):
    """Return a dict:
        map:             {normalized_alias: [current Accepted endpoint id, ...]} (sorted)
        collisions:      {alias: [ids]} for an alias mapping to >=2 distinct current endpoints
        invalid_chains:  {record_id: reason} for alias-declaring records with broken chains
        invalid_aliases: {alias: [record_ids]} aliases dropped because their chain is invalid
    Aliases along one supersession chain collapse to the single live endpoint (NOT a collision)."""
    by_id = {record_id(r, cfg): r for r in records}
    sup_by = _superseded_by_edges(records, cfg)
    raw, invalid, invalid_aliases = {}, {}, {}
    for rec in records:
        aliases = parse_alias_field(rec["fields"].get("Aliases", ""))
        if not aliases:
            continue
        rid = record_id(rec, cfg)
        reason = _chain_invalid_reason(rec, records, cfg, sup_by, by_id)
        if reason:
            invalid[rid] = reason
            for a in aliases:
                invalid_aliases.setdefault(a, []).append(rid)
            continue
        cur, _chain = resolve_current(records, rec, cfg)
        if not cur["fields"].get("Status", "").lower().startswith("accepted"):
            continue                               # no live endpoint; contributes nothing live
        cid = record_id(cur, cfg)
        for a in aliases:
            raw.setdefault(a, set()).add(cid)
    alias_map = {a: sorted(ids) for a, ids in sorted(raw.items())}
    collisions = {a: ids for a, ids in alias_map.items() if len(ids) > 1}
    return {"map": alias_map, "collisions": collisions,
            "invalid_chains": invalid, "invalid_aliases": invalid_aliases}


def find_query_aliases(query, alias_map, stoplist):
    """Alias phrases present in `query`, matched on whole-token phrase boundaries, longest-then-leftmost
    greedy (a consumed span is not reused). Single-token aliases in `stoplist` are ignored. Returns an
    order-preserving, de-duplicated list of normalized alias phrases."""
    qtokens = normalize_alias(query).split()
    if not qtokens:
        return []
    cands = []
    for a in alias_map:
        atoks = a.split()
        if not atoks or (len(atoks) == 1 and atoks[0] in stoplist):
            continue
        cands.append(atoks)
    cands.sort(key=lambda t: (-len(t), t))            # longest first, then lexical (determinism)
    matched, used, i = [], [False] * len(qtokens), 0
    while i < len(qtokens):
        hit = None
        for atoks in cands:
            n = len(atoks)
            if i + n <= len(qtokens) and not any(used[i:i + n]) and qtokens[i:i + n] == atoks:
                hit = atoks
                break
        if hit:
            n = len(hit)
            for j in range(i, i + n):
                used[j] = True
            phrase = " ".join(hit)
            if phrase not in matched:
                matched.append(phrase)
            i += n
        else:
            i += 1
    return matched


def _type_of_id(idstr, records, cfg):
    for r in records:
        if record_id(r, cfg) == idstr:
            return r["type"]
    return None


def build_glossary_artifacts(records, cfg):
    """Build (glossary_md, glossary_json_obj, alias_result) — the human + machine artifacts `index`
    emits. Deterministically sorted. `_alias_conflicts`/`_invalid_chains` are surfaced in the artifact
    so the ambiguous codenames are visible (validate is the hard gate)."""
    res = build_alias_map(records, cfg)
    by_id = {record_id(r, cfg): r for r in records}
    rows, entries = [], {}
    for alias, ids in res["map"].items():
        targets = []
        for cid in ids:
            rec = by_id.get(cid)
            title = rec["title"] if rec else ""
            status = rec["fields"].get("Status", "") if rec else ""
            targets.append({"id": cid, "title": title, "status": status})
            rows.append((alias, title, cid, status))
        entries[alias] = targets
    obj = {"aliases": entries,
           "_alias_conflicts": [{"alias": a, "candidates": ids} for a, ids in res["collisions"].items()],
           "_invalid_chains": [{"record": rid, "reason": why}
                               for rid, why in sorted(res["invalid_chains"].items())]}
    header = "| Alias | Canonical concept | Record id | Status |\n|---|---|---|---|\n"
    body = "".join(f"| {a} | {t} | {cid} | {st} |\n" for a, t, cid, st in sorted(rows))
    md = ("# Glossary — codename -> current decision\n\n"
          "Derived from each record's `Aliases:` field by `decisions.py index`. Do not edit by hand.\n\n"
          + header + (body or "| _(no aliases declared)_ |  |  |  |\n"))
    if res["collisions"]:
        md += "\n## Ambiguous codenames (FIX — `validate` fails on these)\n\n"
        for a, ids in res["collisions"].items():
            md += f"- `{a}` -> {', '.join(ids)}\n"
    return md, obj, res


# --- freshness / staleness (Phase 1 drift guard) ------------------------------------
# A record can be Accepted yet stale: the code it cites under `Sources:` has changed in git since the
# record's Date. A library that silently serves such a record is a confidently-wrong oracle — worse
# than no library (EVAL-AND-PRODUCT-ROADMAP Phase 1, "freshness is mandatory"). This layer is
# BEST-EFFORT against git: if there's no git, or git can't answer, it degrades to "unknown" rather
# than guessing. Pure stdlib (subprocess to the git binary only; ADR 0013).

# A code-path token in Sources: a slash-path or a dotted filename. We deliberately EXCLUDE Rosetta's
# transcript citations (`agent · session · date`, recognised by the ` · ` separator) and bare prose
# words (no slash, no dotted extension) so we never treat "this conversation" as a code path.
_CODE_PATH_RE = re.compile(
    r"""(?:^|[\s,(`])              # boundary: start, space, comma, paren, or backtick
        (?!https?://)             # not a URL
        (                         # capture the path
          [A-Za-z0-9_.\-]+        #   a leading segment …
          (?:/[A-Za-z0-9_.\-]+)*  #   … optionally with /subsegments
          /?                      #   maybe a trailing slash (a directory like tests/)
        )
    """,
    re.VERBOSE,
)


def _looks_like_code_path(tok):
    """True if a token is plausibly a repo code path, not prose. Accept anything with a '/' (incl. a
    trailing-slash directory like `tests/`) or a dotted filename with a short extension (foo.py, ci.yml).
    Reject bare prose words and transcript-citation fragments."""
    raw = tok.strip().strip("`").rstrip(",.;)").strip()
    if not raw or " " in raw:
        return False
    if "·" in raw:                                   # a transcript citation fragment, never a path
        return False
    if "/" in raw:                                   # incl. a trailing-slash dir like 'tests/'
        return True
    # no slash → only accept a dotted filename with a short alpha-num extension (foo.py, ci.yml)
    return bool(re.match(r"^[A-Za-z0-9_.\-]+\.[A-Za-z0-9]{1,5}$", raw))


def extract_source_paths(sources):
    """Pull the distinct code-path tokens out of a `Sources:` value, dropping transcript citations
    (`agent · id · date`) and prose. Order-preserving, de-duplicated."""
    if not sources:
        return []
    # remove `agent · session · date` citations wholesale so their dates/ids aren't mistaken for paths
    cleaned = re.sub(r"`[^`]*·[^`]*`", " ", sources)
    out, seen = [], set()
    for m in _CODE_PATH_RE.finditer(cleaned):
        raw = m.group(1).strip().strip("`").rstrip(",.;)")        # keep a trailing '/' for the test
        if not _looks_like_code_path(raw):
            continue
        tok = raw.rstrip("/")                                     # normalise 'tests/' -> 'tests'
        if tok and tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _git_repo_root(root):
    """The git work-tree root containing `root`, or None. Best-effort: no git binary, not a repo, or a
    perms error all return None so the staleness check skips cleanly rather than guessing."""
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def _last_change_after(repo_root, path, since_date):
    """Return (changed, last_iso) for `path`: whether git recorded a commit touching it strictly AFTER
    `since_date` (a YYYY-MM-DD string), and the most-recent commit date if known. `path` is resolved
    relative to the decisions root first, then tried as repo-relative. A path git doesn't know returns
    (None, None) — 'unknown', not 'stale'."""
    # `--since` is inclusive of the day; we want commits strictly after the record's Date, so ask for
    # the full commit date and compare date-strings ourselves (robust, tz-agnostic at day resolution).
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%cI", "--", path],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None, None
    if r.returncode != 0:
        return None, None
    out = r.stdout.strip()
    if not out:
        return None, None                            # git knows no history for this path
    last_day = out[:10]                              # YYYY-MM-DD from the ISO timestamp
    return (last_day > since_date), last_day


def staleness_for_record(rec, repo_root, decisions_root):
    """Assess one record's freshness against git. Returns a dict:
        {stale: bool|None, date: str, checked: [paths], stale_paths: [{path,last_change}], reason}
    stale is None when freshness can't be determined (no Date, no cited paths, or git can't resolve any
    path) — callers must treat None as 'unknown', never as fresh."""
    date = effective_date(rec)
    sources = rec["fields"].get("Sources", "")
    paths = extract_source_paths(sources)
    result = {"stale": None, "date": date, "checked": [], "stale_paths": [], "reason": ""}
    if not date:
        result["reason"] = "no Date to compare against"
        return result
    if not paths:
        result["reason"] = "no cited code paths in Sources"
        return result
    any_resolved = False
    for p in paths:
        # try the path as decisions-root-relative first, then verbatim (repo-relative)
        candidates = []
        abs = (decisions_root / p)
        with contextlib.suppress(ValueError):
            candidates.append(abs.resolve().relative_to(repo_root.resolve()).as_posix())
        candidates.append(p)
        changed = last = None
        for cand in candidates:
            changed, last = _last_change_after(repo_root, cand, date)
            if changed is not None:
                break
        if changed is None:
            continue                                 # git doesn't know this path → skip (unknown)
        any_resolved = True
        result["checked"].append(p)
        if changed:
            result["stale_paths"].append({"path": p, "last_change": last})
    if not any_resolved:
        result["reason"] = "none of the cited paths are tracked in git"
        return result
    result["stale"] = bool(result["stale_paths"])
    result["reason"] = ("cited code changed after the record's Date"
                        if result["stale"] else "cited code unchanged since the record's Date")
    return result


def assess_staleness(records, root, cfg, statuses=("accepted",)):
    """Run the freshness check across `records` (default: only Accepted records — the ones a library
    actively serves). Returns (git_ok, [per-record dict]). Each dict carries the record id + title plus
    the staleness_for_record payload. If git isn't available, returns (False, []) so the caller can
    report 'skipped' rather than a false all-fresh."""
    repo_root = _git_repo_root(root)
    if repo_root is None:
        return False, []
    out = []
    want = tuple(s.lower() for s in statuses)
    for rec in records:
        status = rec["fields"].get("Status", "").lower()
        if want and not any(status.startswith(s) for s in want):
            continue
        info = staleness_for_record(rec, repo_root, root)
        info["id"] = record_id(rec, cfg)
        info["title"] = rec["title"]
        out.append(info)
    return True, out


# --- integrity (compiler anti-hallucination gate) -----------------------------------
# Goal-2 finding: an LLM that compiles a decision library from raw transcripts/code can INVENT
# provenance — it referenced ADR ids that did not exist in 2/5 fixtures and could just as easily cite
# a source file that isn't there. A "verified provenance graph" that fabricates its own ids/citations
# is worse than no library (both council reviewers ranked this a catastrophic-trust failure). This pass
# makes that fabrication mechanically detectable so it can be a hard gate:
#   1. every `LABEL NNNN` reference anywhere in a record must resolve to a real record (no ghost ids);
#   2. every code-path cited in `Sources:` must exist on disk (no ghost citations).
# Pure stdlib; best-effort on the source-root resolution so it never false-positives on paths that
# genuinely live outside the checkout.

def _source_roots(root):
    """Candidate roots a cited `Sources:` path may be relative to, most-specific first: the git repo
    root (the usual case for the real library), then the decisions root and its parent (covers eval
    fixtures where a compiled library sits beside the raw corpus it was built from)."""
    roots = []
    repo = _git_repo_root(root)
    if repo is not None:
        roots.append(repo)
    roots.append(root)
    roots.append(root.parent)
    # de-dup while preserving order
    seen, out = set(), []
    for r in roots:
        rp = r.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


# A "file-shaped" citation: its final segment ends in a short file extension (foo.py, ci.yml,
# DESIGN.md). Only these are existence-checked — a token whose last segment has no extension is a
# directory (`tests/`) or a code-symbol citation (`load_counter/save_counter`), which we deliberately
# do NOT treat as a ghost (the real library cites symbols this way; flagging them is noise, not signal).
_FILE_TOKEN_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _repo_basenames(roots):
    """Set of basenames of every file under the source roots — used to ground a basename-only citation
    (`DESIGN.md`) that the real library writes without a full path. Prefer `git ls-files` (fast, tracked
    files only); fall back to a bounded rglob when git can't answer. Best-effort: an empty set just
    means every file-shaped citation must resolve by exact relative path instead."""
    names = set()
    for r in roots:
        try:
            res = subprocess.run(["git", "-C", str(r), "ls-files"],
                                 capture_output=True, text=True, timeout=20)
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    names.add(line.rsplit("/", 1)[-1])
                continue
        except (OSError, subprocess.SubprocessError):
            pass
        with contextlib.suppress(OSError):
            for p in r.rglob("*"):
                if p.is_file():
                    names.add(p.name)
    return names


def assess_integrity(records, cfg, root):
    """Return {dangling_refs: [...], ghost_sources: [...]} — fabricated provenance the compiler emitted.
    `dangling_refs`: a `LABEL NNNN` reference (in frontmatter OR body) that resolves to no real record.
    `ghost_sources`: a *file-shaped* code-path cited under `Sources:` that exists under no source root
    AND whose basename appears nowhere in the repo. Directory/symbol citations are not checked (they're
    not falsifiable as files). Both lists empty ⇒ every id and file citation is grounded."""
    valid_labels = {rt["label"].upper() for rt in cfg["record_types"].values()}
    all_ids = {(rec["label"].upper(), rec["number"]) for rec in records}
    label_re = re.compile(r"\b(" + "|".join(sorted(valid_labels)) + r")\s+(\d+)\b")
    roots = _source_roots(root)
    basenames = _repo_basenames(roots)
    dangling, ghost = [], []
    for rec in records:
        rid = (rec["label"].upper(), rec["number"])
        name = rec["path"].name
        text = rec["path"].read_text(errors="replace")
        seen_refs = set()
        for lbl, num in label_re.findall(text):
            ref = (lbl.upper(), int(num))
            if ref == rid or ref in seen_refs:
                continue
            seen_refs.add(ref)
            if ref not in all_ids:
                dangling.append({"record": name, "ref": f"{lbl.upper()} {num}"})
        for p in extract_source_paths(rec["fields"].get("Sources", "")):
            base = p.rsplit("/", 1)[-1]
            if not _FILE_TOKEN_RE.search(base):
                continue                                 # directory or symbol citation — not checkable
            if any((r / p).exists() for r in roots):     # exact relative path resolves
                continue
            if base in basenames:                        # basename grounded somewhere in the repo
                continue
            ghost.append({"record": name, "source": p})
    return {"dangling_refs": dangling, "ghost_sources": ghost}


def cmd_integrity(args, root, cfg):
    """Compiler anti-hallucination gate: report fabricated ADR-id references and ghost source citations
    in the library. JSON out. Exit 1 when anything is found (always a hard error — fabricated provenance
    has no benign reading), so this is CI-gateable on its own and via `validate --integrity`."""
    records = collect_records(root, cfg)
    result = assess_integrity(records, cfg, root)
    n = len(result["dangling_refs"]) + len(result["ghost_sources"])
    out = {"checked_records": len(records),
           "dangling_refs": result["dangling_refs"],
           "ghost_sources": result["ghost_sources"],
           "ok": n == 0}
    if n:
        out["note"] = (f"{len(result['dangling_refs'])} fabricated ADR reference(s) and "
                       f"{len(result['ghost_sources'])} ghost source citation(s) — the library "
                       f"asserts provenance that does not exist (likely an LLM-compiler hallucination)")
    print(json.dumps(out, indent=2))
    if n:
        sys.exit(1)


def cmd_staleness(args, root, cfg):
    """Flag Accepted records whose cited `Sources:` code paths changed in git after the record's Date —
    so a library can't silently serve a stale-but-Accepted decision (Phase 1 freshness guard). JSON out.
    Best-effort: with no git (or no resolvable paths) it reports 'skipped'/'unknown', never a false pass.
    Exit code 1 when --strict and at least one stale record is found (CI-gateable)."""
    records = collect_records(root, cfg)
    statuses = (args.status,) if getattr(args, "status", None) else ("accepted",)
    git_ok, assessed = assess_staleness(records, root, cfg, statuses)
    if not git_ok:
        out = {"git": False, "skipped": True,
               "note": "not a git work tree (or git unavailable); staleness check skipped"}
        print(json.dumps(out, indent=2))
        return
    stale = [a for a in assessed if a["stale"] is True]
    unknown = [a for a in assessed if a["stale"] is None]
    fresh = [a for a in assessed if a["stale"] is False]
    out = {
        "git": True,
        "checked_records": len(assessed),
        "stale": [{"id": a["id"], "title": a["title"], "date": a["date"],
                   "stale_paths": a["stale_paths"]} for a in stale],
        "unknown": [{"id": a["id"], "title": a["title"], "reason": a["reason"]} for a in unknown],
        "fresh_count": len(fresh),
    }
    if stale:
        out["note"] = (f"{len(stale)} Accepted record(s) cite code that changed after their Date — "
                       f"review and re-validate (the library may be serving a stale decision)")
    print(json.dumps(out, indent=2))
    if getattr(args, "strict", False) and stale:
        sys.exit(1)


def cmd_get(args, root, cfg):
    """Print one record in full (so the agent reads a single record, not the whole library).
    With --resolve, if the requested record is superseded, follow the chain to the CURRENT record and
    print that instead (with a header noting the redirect) — so an agent that lands on a stale decision
    is steered to the live one rather than reporting superseded state as current (Phase 0 retrieval layer)."""
    records = collect_records(root, cfg)
    rec = resolve_id(records, args.id, args.type.lower() if args.type else None)
    if getattr(args, "resolve", False):
        current, chain = resolve_current(records, rec, cfg)
        if chain:
            print(f"<!-- resolved: {' → superseded by → '.join(chain + [record_id(current, cfg)])}; "
                  f"showing the CURRENT record -->")
        print(current["path"].read_text())
    else:
        print(rec["path"].read_text())


def cmd_resolve(args, root, cfg):
    """Decision-resolution primitive (the product's core capability): given a query, find matching
    records, follow each to its CURRENT (non-superseded) form, and return the live decision(s) with
    provenance — explicitly FLAGGING when two or more distinct current records match (an unresolved
    conflict, the failure that silently poisons naive search/compilation). Prints compact JSON."""
    records = collect_records(root, cfg)
    q = (args.text or "").lower()
    type_filter = args.type.lower() if args.type else None
    no_alias = getattr(args, "no_alias_expand", False)

    # literal matches — alias-FIELD text is excluded from the haystack (it matches ONLY via the map)
    matched = []
    for rec in records:
        if type_filter and rec["type"] != type_filter:
            continue
        if not q or q in literal_haystack(rec):
            matched.append(rec)
    current = {}                                   # id -> entry (literal current endpoints)
    current_recs = {}                              # id -> live record object (for the freshness pass)
    for rec in matched:
        cur, chain = resolve_current(records, rec, cfg)
        if not cur["fields"].get("Status", "").lower().startswith("accepted"):
            continue                               # only surface live (Accepted) endpoints
        cid = record_id(cur, cfg)
        current_recs[cid] = cur
        entry = current.setdefault(cid, {
            "id": cid, "title": cur["title"], "status": cur["fields"].get("Status", ""),
            "date": effective_date(cur), "path": cur["path"].relative_to(root).as_posix(),
            "aliases": cur["fields"].get("Aliases", ""), "superseded_from": []})
        if chain:
            entry["superseded_from"] = sorted(set(entry["superseded_from"]) | set(chain))
        if "replaced" not in entry:               # what the current decision immediately replaced
            prior = immediately_superseded(records, cur, cfg)
            if prior:
                entry["replaced"] = {"id": record_id(prior, cfg), "title": prior["title"]}

    conflict = len(current) > 1                    # LITERAL-only conflict signal (unchanged semantics)

    # alias layer (Direct Record Mapping): union an unambiguous alias's target record by id; report an
    # ambiguous alias separately. This NEVER rewrites the query and NEVER flips `conflict` (SPEC-04).
    via_alias, alias_conflict, invalid_note = [], [], None
    if not no_alias and args.text:
        ares = build_alias_map(records, cfg)
        amap, inv_aliases = ares["map"], ares["invalid_aliases"]
        stoplist = {normalize_alias(s) for s in cfg.get("alias_stoplist", DEFAULT_ALIAS_STOPLIST)}
        by_id = {record_id(r, cfg): r for r in records}
        for a in find_query_aliases(args.text, amap, stoplist):
            ids = amap.get(a, [])
            if type_filter:                        # resolve ambiguity is --type-scoped
                ids = [i for i in ids if _type_of_id(i, records, cfg) == type_filter]
            if not ids:
                continue
            if len(ids) > 1:                       # ambiguous within scope → report, inject nothing
                alias_conflict.append({"alias": a, "candidates": ids})
                continue
            cid = ids[0]
            if cid in current:
                continue                           # already a literal match (dedup; stays in `current`)
            rec = by_id.get(cid)
            if rec is None:
                continue
            via_alias.append({"id": cid, "title": rec["title"], "alias": a, "target_id": cid,
                              "path": rec["path"].relative_to(root).as_posix()})
        bad = find_query_aliases(args.text, inv_aliases, stoplist)
        if bad:
            invalid_note = ("query alias(es) " + ", ".join(f"'{a}'" for a in bad) +
                            " map through an invalid supersession chain; cannot resolve deterministically")
        via_alias.sort(key=lambda v: (v["id"], v["alias"]))
        alias_conflict.sort(key=lambda c: (c["alias"], c["candidates"]))

    # Freshness annotation (the moat: a resolved record that's Accepted but whose cited code has moved
    # is a stale oracle). Best-effort against git; unless --no-stale-check is passed. `stale` is True /
    # False / null(unknown) so a consumer never reads "absent flag" as "fresh".
    git_stale = False
    if not getattr(args, "no_stale_check", False):
        repo_root = _git_repo_root(root)
        if repo_root is not None:
            git_stale = True
            for cid, entry in current.items():
                info = staleness_for_record(current_recs[cid], repo_root, root)
                entry["stale"] = info["stale"]
                if info["stale"]:
                    entry["stale_paths"] = info["stale_paths"]

    live = list(current.values())
    union_ids = set(current.keys()) | {v["id"] for v in via_alias}
    resolved_unique = (len(union_ids) == 1 and not alias_conflict and invalid_note is None)
    out = {"query": args.text, "current": live, "matched_records": len(matched), "conflict": conflict}
    if not no_alias:
        out["via_alias"] = via_alias
        if alias_conflict:
            out["alias_conflict"] = alias_conflict
    out["resolved_unique"] = resolved_unique
    out["freshness_checked"] = git_stale
    if git_stale and any(e.get("stale") for e in live):
        out["stale"] = True
    notes = []
    if conflict:
        notes.append("MULTIPLE current records match — unresolved conflict; the library does not "
                     "uniquely resolve this query. Disambiguate (scope/subsystem) or supersede.")
    elif not live and not via_alias:
        notes.append("no current (Accepted) record matches; all matches are superseded or none found")
    if alias_conflict:
        notes.append("ambiguous codename(s) — an alias maps to multiple current decisions; "
                     "disambiguate by scope.")
    if invalid_note:
        notes.append(invalid_note)
    if notes:
        out["note"] = " ".join(notes)
    print(json.dumps(out, indent=2))


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
    p_val.add_argument("--staleness", action="store_true",
                       help="also flag Accepted records whose cited code changed in git since their Date")
    p_val.add_argument("--integrity", action="store_true",
                       help="also fail on fabricated ADR-id references and ghost source citations "
                            "(compiler anti-hallucination gate)")

    p_intg = sub.add_parser("integrity", help="report fabricated ADR-id references + ghost source "
                                              "citations (compiler anti-hallucination gate)")
    add_root(p_intg)

    p_stale = sub.add_parser("staleness", help="flag Accepted records whose cited code moved in git "
                                               "since their Date (freshness/drift guard)")
    add_root(p_stale)
    p_stale.add_argument("--status", default=None,
                         help="status prefix to check (default: Accepted — the records a library serves)")
    p_stale.add_argument("--strict", action="store_true",
                         help="exit nonzero if any stale record is found (CI gate)")

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
    p_get.add_argument("--resolve", action="store_true",
                       help="if the record is superseded, follow the chain and print the CURRENT record")

    p_sup = sub.add_parser("supersede", help="flip <old> to 'Superseded by <new>' and link <new>")
    add_root(p_sup)
    p_sup.add_argument("old", help="record being superseded, e.g. 'ADR 0002'")
    p_sup.add_argument("--by", required=True, help="superseding record, e.g. 'ADR 0026'")
    p_sup.add_argument("--type", default=None, help="disambiguate ids when a number spans types")

    p_res = sub.add_parser("resolve", help="resolve a query to its CURRENT decision(s), following "
                                           "supersession and flagging unresolved conflicts")
    add_root(p_res)
    p_res.add_argument("--text", default=None, help="substring/term to resolve (title/frontmatter/body)")
    p_res.add_argument("--type", default=None, help="restrict to a record type (adr|pdr|bdr|…)")
    p_res.add_argument("--no-stale-check", action="store_true",
                       help="skip the git freshness annotation on resolved records")
    p_res.add_argument("--no-alias-expand", action="store_true",
                       help="disable alias/codename resolution (literal matching only)")

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
    elif args.cmd == "staleness":
        cmd_staleness(args, root, cfg)
    elif args.cmd == "integrity":
        cmd_integrity(args, root, cfg)
    elif args.cmd == "search":
        cmd_search(args, root, cfg)
    elif args.cmd == "get":
        cmd_get(args, root, cfg)
    elif args.cmd == "supersede":
        cmd_supersede(args, root, cfg)
    elif args.cmd == "resolve":
        cmd_resolve(args, root, cfg)


if __name__ == "__main__":
    main()
