#!/usr/bin/env python3
"""Rosetta loop-run ledger — isolated RUN records under loop-runs/."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decisions import atomic_write_text, counter_lock, load_counter, save_counter, slugify, today_iso  # noqa: E402

RUN_DIR = "loop-runs"
COUNTER_FILE = ".counter.json"
RUN_KEY = "run"
RUN_RE = re.compile(r"^#\s+RUN\s+(\d{4})\s*[—–-]+\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+([^:]+):\s*(.*)$")
FIELDS = [
    "Status", "Date", "Runner", "Trigger", "Scope", "Budget", "Outcome", "Stop reason",
    "Artifacts", "Checker result", "Harness improvement", "Sources",
]
TRIGGERS = {"manual", "ci", "goal", "loop", "other"}
OUTCOMES = {"pending", "success", "failure", "stopped"}
CHECKER_RESULTS = {"pass", "fail", "skip", "unknown"}
STATUSES = {"Open", "Closed"}


def run_dir(project_root):
    return Path(project_root).resolve() / RUN_DIR


def run_id(num):
    return f"RUN {str(num).zfill(4)}"


def nonblank(value):
    if not str(value).strip():
        raise argparse.ArgumentTypeError("must be nonblank")
    return value


def scan_max_run(d):
    mx = 0
    if not d.exists():
        return mx
    for f in d.glob("*.md"):
        m = re.match(r"^(\d{4})-", f.name)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx


def allocate_run_number(d):
    d.mkdir(parents=True, exist_ok=True)
    counter_path = d / COUNTER_FILE
    with counter_lock(d):
        counter = load_counter(counter_path)
        current = max(int(counter.get(RUN_KEY, 0) or 0), scan_max_run(d))
        nxt = current + 1
        counter[RUN_KEY] = nxt
        save_counter(counter_path, counter)
    return str(nxt).zfill(4)


def fmt_artifacts(values):
    return "; ".join(values or [])


def render_run(num, title, args):
    rid = run_id(num)
    fields = {
        "Status": "Open",
        "Date": today_iso(),
        "Runner": args.runner,
        "Trigger": args.trigger,
        "Scope": args.scope,
        "Budget": args.budget or "",
        "Outcome": "pending",
        "Stop reason": "",
        "Artifacts": fmt_artifacts(args.artifact),
        "Checker result": "unknown",
        "Harness improvement": "",
        "Sources": f"loop-run:{num}",
    }
    lines = [f"# {rid} — {title}", ""]
    lines.extend(f"- {field}: {fields[field]}" for field in FIELDS)
    lines.extend(["", "## Log", "", f"- {today_iso()} — opened run."])
    return "\n".join(lines) + "\n"


def parse_run(path):
    text = path.read_text()
    lines = text.splitlines()
    if not lines:
        return {"path": path, "error": "missing_h1"}
    m = RUN_RE.match(lines[0])
    if not m:
        return {"path": path, "error": "malformed_h1"}
    fields = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        if line.startswith("## "):
            break
        fm = FIELD_RE.match(line)
        if not fm:
            return {"path": path, "error": f"malformed_frontmatter_line:{line}"}
        fields[fm.group(1)] = fm.group(2)
    return {"path": path, "id": run_id(m.group(1)), "number": m.group(1), "title": m.group(2),
            "fields": fields, "text": text}


def validate_run_record(parsed):
    if parsed.get("error"):
        return [parsed["error"]]
    errors = []
    fields = parsed["fields"]
    if set(fields) != set(FIELDS):
        missing = [f for f in FIELDS if f not in fields]
        extra = [f for f in fields if f not in FIELDS]
        if missing:
            errors.append(f"missing fields: {', '.join(missing)}")
        if extra:
            errors.append(f"extra fields: {', '.join(extra)}")
    if fields.get("Status") not in STATUSES:
        errors.append("invalid Status")
    if fields.get("Trigger") not in TRIGGERS:
        errors.append("invalid Trigger")
    if fields.get("Outcome") not in OUTCOMES:
        errors.append("invalid Outcome")
    if fields.get("Checker result") not in CHECKER_RESULTS:
        errors.append("invalid Checker result")
    if fields.get("Status") == "Closed" and not fields.get("Stop reason", "").strip():
        errors.append("closed run missing Stop reason")
    expected_source = f"loop-run:{parsed.get('number')}"
    if fields.get("Sources") != expected_source:
        errors.append("invalid Sources")
    return errors


def find_run(project_root, rid):
    m = re.match(r"^RUN\s+(\d{4})$", rid.strip(), re.IGNORECASE)
    if not m:
        raise SystemExit("run id must look like RUN 0001")
    d = run_dir(project_root)
    matches = sorted(d.glob(f"{m.group(1)}-*.md"))
    if not matches:
        raise SystemExit(f"run not found: RUN {m.group(1)}")
    return matches[0]


def set_field(text, field, value):
    pattern = re.compile(rf"^-[ \t]+{re.escape(field)}:[ \t]*.*$", re.MULTILINE)
    repl = f"- {field}: {value}"
    if not pattern.search(text):
        raise SystemExit(f"malformed run: missing {field}")
    return pattern.sub(repl, text, count=1)


def append_artifacts(existing, new_values):
    parts = [p.strip() for p in (existing or "").split(";") if p.strip()]
    parts.extend(new_values or [])
    deduped = list(dict.fromkeys(parts))
    return fmt_artifacts(deduped)


def append_log(text, note, artifacts=None, closing=False):
    if "## Log" not in text:
        text = text.rstrip() + "\n\n## Log\n"
    entry = f"- {today_iso()} — {'closed: ' if closing else ''}{note}"
    if artifacts:
        entry += f" (artifacts: {fmt_artifacts(artifacts)})"
    return text.rstrip() + "\n" + entry + "\n"


def mutation_json(rid, path):
    return {"schema": "rosetta-runs/v1", "owner": "rosetta", "run_id": rid, "path": str(path)}


def cmd_new(args):
    project = Path(args.project_root).resolve()
    d = run_dir(project)
    num = allocate_run_number(d)
    title_slug = slugify(args.title)
    path = d / f"{num}-{title_slug}.md"
    atomic_write_text(path, render_run(num, args.title, args))
    print(json.dumps(mutation_json(run_id(num), path), indent=2))


def cmd_append(args):
    project = Path(args.project_root).resolve()
    path = find_run(project, args.run_id)
    parsed = parse_run(path)
    if parsed.get("error"):
        raise SystemExit(parsed["error"])
    if parsed["fields"].get("Status") != "Open":
        raise SystemExit("cannot append to a closed run")
    text = parsed["text"]
    if args.artifact:
        text = set_field(text, "Artifacts", append_artifacts(parsed["fields"].get("Artifacts"), args.artifact))
    if args.checker_result:
        text = set_field(text, "Checker result", args.checker_result)
    if args.outcome:
        text = set_field(text, "Outcome", args.outcome)
    if args.harness_improvement:
        text = set_field(text, "Harness improvement", args.harness_improvement)
    text = append_log(text, args.note, args.artifact)
    atomic_write_text(path, text)
    print(json.dumps(mutation_json(parsed["id"], path), indent=2))


def cmd_close(args):
    project = Path(args.project_root).resolve()
    path = find_run(project, args.run_id)
    parsed = parse_run(path)
    if parsed.get("error"):
        raise SystemExit(parsed["error"])
    text = parsed["text"]
    text = set_field(text, "Status", "Closed")
    text = set_field(text, "Outcome", args.outcome)
    text = set_field(text, "Stop reason", args.stop_reason)
    if args.checker_result:
        text = set_field(text, "Checker result", args.checker_result)
    text = append_log(text, args.stop_reason, closing=True)
    atomic_write_text(path, text)
    print(json.dumps(mutation_json(parsed["id"], path), indent=2))


def all_runs(project_root):
    d = run_dir(project_root)
    return sorted(d.glob("*.md")) if d.exists() else []


def cmd_index(args):
    project = Path(args.project_root).resolve()
    runs = []
    for path in all_runs(project):
        parsed = parse_run(path)
        if parsed.get("error"):
            runs.append({"path": str(path), "error": parsed["error"]})
            continue
        runs.append({"id": parsed["id"], "title": parsed["title"], "path": str(path),
                     "status": parsed["fields"].get("Status"),
                     "outcome": parsed["fields"].get("Outcome"),
                     "checker_result": parsed["fields"].get("Checker result")})
    print(json.dumps({"schema": "rosetta-runs-index/v1", "owner": "rosetta", "runs": runs}, indent=2))


def cmd_validate(args):
    project = Path(args.project_root).resolve()
    issues = []
    for path in all_runs(project):
        parsed = parse_run(path)
        errors = validate_run_record(parsed)
        for error in errors:
            issues.append({"path": str(path), "error": error})
    print(json.dumps({"schema": "rosetta-runs-validate/v1", "owner": "rosetta",
                      "ok": not issues, "issues": issues}, indent=2))
    if issues:
        sys.exit(1)


def add_project_root(p):
    p.add_argument("--project-root", required=True, help="project root")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rosetta loop-run ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="open a new loop run")
    add_project_root(p_new)
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--runner", required=True)
    p_new.add_argument("--trigger", choices=sorted(TRIGGERS), required=True)
    p_new.add_argument("--scope", required=True)
    p_new.add_argument("--budget", default="")
    p_new.add_argument("--artifact", action="append", default=[])

    p_append = sub.add_parser("append", help="append to an open loop run")
    add_project_root(p_append)
    p_append.add_argument("run_id")
    p_append.add_argument("--note", required=True)
    p_append.add_argument("--artifact", action="append", default=[])
    p_append.add_argument("--checker-result", choices=sorted(CHECKER_RESULTS), default=None)
    p_append.add_argument("--outcome", choices=sorted(OUTCOMES), default=None)
    p_append.add_argument("--harness-improvement", default=None)

    p_close = sub.add_parser("close", help="close a loop run")
    add_project_root(p_close)
    p_close.add_argument("run_id")
    p_close.add_argument("--stop-reason", type=nonblank, required=True)
    p_close.add_argument("--outcome", choices=sorted(OUTCOMES - {"pending"}), default="success")
    p_close.add_argument("--checker-result", choices=sorted(CHECKER_RESULTS), default=None)

    p_index = sub.add_parser("index", help="list loop runs")
    add_project_root(p_index)

    p_validate = sub.add_parser("validate", help="validate loop-run records")
    add_project_root(p_validate)

    args = ap.parse_args(argv)
    if args.cmd == "new":
        cmd_new(args)
    elif args.cmd == "append":
        cmd_append(args)
    elif args.cmd == "close":
        cmd_close(args)
    elif args.cmd == "index":
        cmd_index(args)
    elif args.cmd == "validate":
        cmd_validate(args)


if __name__ == "__main__":
    main()
