#!/usr/bin/env python3
"""Rosetta gates — deterministic evidence/decision checks for a proposed change."""
import argparse
import datetime as dt
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decisions  # noqa: E402

UI_SUFFIXES = {
    ".html", ".css", ".scss", ".sass", ".less", ".js", ".jsx", ".ts", ".tsx",
    ".vue", ".svelte", ".swift", ".kt", ".java", ".xml", ".storyboard", ".xib",
}


class ChangeSourceError(ValueError):
    pass


def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def split_semicolon(value):
    return [p.strip() for p in (value or "").split(";") if p.strip()]


def is_accepted(rec):
    return rec["fields"].get("Status", "").strip().lower().startswith("accepted")


def rel_record_path(rec, root):
    try:
        return rec["path"].relative_to(root).as_posix()
    except ValueError:
        return rec["path"].as_posix()


def clean_changed_path(raw):
    value = (raw or "").strip()
    if not value:
        return None
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    if value.startswith("a/") or value.startswith("b/"):
        value = value[2:]
    if value == "/dev/null":
        return None
    p = Path(value)
    if p.is_absolute() or ".." in p.parts:
        raise ChangeSourceError(f"changed path must be repo-relative and stay inside the project: {raw!r}")
    return p.as_posix()


def parse_diff_paths(text):
    lines = text.splitlines()
    has_git_markers = any(line.startswith("diff --git ") or line.startswith("+++") or line.startswith("---")
                          for line in lines)
    paths = []
    if has_git_markers:
        for line in lines:
            if line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    p = clean_changed_path(parts[3])
                    if p:
                        paths.append(p)
            elif line.startswith("+++ ") or line.startswith("--- "):
                p = clean_changed_path(line[4:].split("\t", 1)[0])
                if p:
                    paths.append(p)
    else:
        for line in lines:
            p = clean_changed_path(line)
            if p:
                paths.append(p)
    return sorted(dict.fromkeys(paths))


def git_changed_paths(project_root, base, head):
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{base}...{head}"]
    proc = subprocess.run(cmd, cwd=project_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or "git diff failed")
    return parse_diff_paths(proc.stdout)


def validation_gate(records, cfg, decisions_root):
    report = decisions.assess_validation(records, cfg, decisions_root, integrity=False, staleness=False)
    evidence = [{"type": "error", "message": m} for m in report["errors"]]
    evidence.extend({"type": "warning", "message": m} for m in report["warnings"])
    if report["errors"] or report["warnings"]:
        return {"gate": "validation", "owner": "rosetta", "status": "fail",
                "reason": f"{len(report['errors'])} errors, {len(report['warnings'])} warnings",
                "evidence": evidence}
    return {"gate": "validation", "owner": "rosetta", "status": "pass",
            "reason": "no validation errors or warnings", "evidence": []}


def integrity_gate(records, cfg, decisions_root):
    report = decisions.assess_integrity(records, cfg, decisions_root)
    evidence = []
    evidence.extend({"type": "dangling_ref", **d} for d in report["dangling_refs"])
    evidence.extend({"type": "ghost_source", **g} for g in report["ghost_sources"])
    if evidence:
        return {"gate": "integrity", "owner": "rosetta", "status": "fail",
                "reason": f"{len(evidence)} integrity issue(s)", "evidence": evidence}
    return {"gate": "integrity", "owner": "rosetta", "status": "pass",
            "reason": "no fabricated references or ghost sources", "evidence": []}


def staleness_gate(records, cfg, decisions_root):
    git_ok, assessed = decisions.assess_staleness(records, decisions_root, cfg)
    if not git_ok:
        return {"gate": "staleness", "owner": "rosetta", "status": "skip",
                "reason": "not_git", "evidence": []}
    stale = [a for a in assessed if a["stale"] is True]
    if stale:
        return {"gate": "staleness", "owner": "rosetta", "status": "fail",
                "reason": f"{len(stale)} stale record(s)", "evidence": stale}
    unknown = [a for a in assessed if a["stale"] is None]
    return {"gate": "staleness", "owner": "rosetta", "status": "pass",
            "reason": f"no stale records ({len(unknown)} unknown)", "evidence": unknown}


def anchoring_gate(records, cfg, decisions_root, min_coverage):
    report = decisions.assess_coverage(records, cfg, decisions_root)
    anchoring = report["anchoring"]
    rate = anchoring.get("rate_raw")
    if rate is None:
        return {"gate": "anchoring", "owner": "rosetta", "status": "skip",
                "reason": "rate_raw_null", "evidence": [anchoring]}
    if rate < min_coverage:
        return {"gate": "anchoring", "owner": "rosetta", "status": "fail",
                "reason": f"coverage {rate:.3f} below minimum {min_coverage:.3f}", "evidence": [anchoring]}
    return {"gate": "anchoring", "owner": "rosetta", "status": "pass",
            "reason": f"coverage {rate:.3f} meets minimum {min_coverage:.3f}", "evidence": [anchoring]}




def approval_records(records, cfg, decisions_root, change_id):
    out = []
    for rec in records:
        if not is_accepted(rec) or rec.get("type") not in {"adr", "pdr", "bdr"}:
            continue
        if rec["fields"].get("Human approval for", "").strip() != change_id:
            continue
        if not rec["fields"].get("Sources", "").strip() or not rec["fields"].get("Decider", "").strip():
            continue
        out.append({"record": decisions.record_id(rec, cfg), "path": rel_record_path(rec, decisions_root)})
    return out


def denylist_gate(records, cfg, decisions_root, changed_paths, change_id):
    if not changed_paths:
        return {"gate": "denylist", "owner": "rosetta", "status": "skip",
                "reason": "no_changed_paths", "evidence": []}
    matches = []
    for rec in records:
        if not is_accepted(rec) or rec.get("type") not in {"adr", "pdr"}:
            continue
        for pattern in split_semicolon(rec["fields"].get("Human gated paths", "")):
            for path in changed_paths:
                if fnmatch.fnmatchcase(path, pattern):
                    matches.append({"path": path, "pattern": pattern,
                                    "record": decisions.record_id(rec, cfg),
                                    "record_path": rel_record_path(rec, decisions_root)})
    if not matches:
        return {"gate": "denylist", "owner": "rosetta", "status": "pass",
                "reason": "no_human_gated_paths_touched", "evidence": []}
    if not change_id:
        return {"gate": "denylist", "owner": "rosetta", "status": "fail",
                "reason": "change_id_required_for_human_gated_paths", "evidence": matches}
    approvals = approval_records(records, cfg, decisions_root, change_id)
    if not approvals:
        return {"gate": "denylist", "owner": "rosetta", "status": "fail",
                "reason": "missing_human_approval", "evidence": matches}
    return {"gate": "denylist", "owner": "rosetta", "status": "pass",
            "reason": "human_approval_found", "evidence": [{"matches": matches, "approvals": approvals}]}


def is_ui_path(path):
    return Path(path).suffix.lower() in UI_SUFFIXES


def artifact_target(project_root, ref):
    if not (ref.startswith("screenshot:") or ref.startswith("video:")):
        return None
    _, raw = ref.split(":", 1)
    raw = raw.strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute() or ".." in p.parts:
        return None
    target = (project_root / p).resolve()
    try:
        target.relative_to(project_root.resolve())
    except ValueError:
        return None
    return target


def evidence_records(records, cfg, project_root, decisions_root, change_id):
    out = []
    missing = []
    for rec in records:
        if not is_accepted(rec) or rec.get("type") not in {"adr", "pdr", "bdr"}:
            continue
        if rec["fields"].get("Evidence for", "").strip() != change_id:
            continue
        existing = []
        for ref in split_semicolon(rec["fields"].get("Evidence artifacts", "")):
            target = artifact_target(project_root, ref)
            if target is not None and target.exists():
                existing.append(ref)
            else:
                missing.append({"record": decisions.record_id(rec, cfg), "artifact": ref})
        out.append({"record": decisions.record_id(rec, cfg), "path": rel_record_path(rec, decisions_root),
                    "existing_artifacts": existing})
    return out, missing


def evidence_presence_gate(records, cfg, project_root, decisions_root, changed_paths, change_id):
    if not changed_paths:
        return {"gate": "evidence_presence", "owner": "rosetta", "status": "skip",
                "reason": "no_changed_paths", "evidence": []}
    ui_paths = [p for p in changed_paths if is_ui_path(p)]
    if not ui_paths:
        return {"gate": "evidence_presence", "owner": "rosetta", "status": "pass",
                "reason": "no_ui_paths_touched", "evidence": []}
    if not change_id:
        return {"gate": "evidence_presence", "owner": "rosetta", "status": "fail",
                "reason": "change_id_required_for_ui_evidence", "evidence": [{"ui_paths": ui_paths}]}
    records_with_evidence, missing = evidence_records(records, cfg, project_root, decisions_root, change_id)
    records_with_existing = [r for r in records_with_evidence if r["existing_artifacts"]]
    if not records_with_existing:
        return {"gate": "evidence_presence", "owner": "rosetta", "status": "fail",
                "reason": "missing_existing_evidence_artifact",
                "evidence": [{"ui_paths": ui_paths, "records": records_with_evidence,
                              "missing": missing}]}
    return {"gate": "evidence_presence", "owner": "rosetta", "status": "pass",
            "reason": "existing_evidence_artifact_found",
            "evidence": [{"ui_paths": ui_paths, "records": records_with_existing}]}


def build_gates_report(project_root, decisions_root, min_coverage, *, changed_paths=None, change_id=None,
                       generated_at=None):
    project_root = Path(project_root).resolve()
    decisions_root = Path(decisions_root).resolve()
    changed_paths = sorted(dict.fromkeys(changed_paths or []))
    cfg = decisions.load_config(decisions_root)
    records = decisions.collect_records(decisions_root, cfg)
    gates = [
        validation_gate(records, cfg, decisions_root),
        integrity_gate(records, cfg, decisions_root),
        staleness_gate(records, cfg, decisions_root),
        anchoring_gate(records, cfg, decisions_root, min_coverage),
        denylist_gate(records, cfg, decisions_root, changed_paths, change_id),
        evidence_presence_gate(records, cfg, project_root, decisions_root, changed_paths, change_id),
    ]
    ok = not any(g["status"] == "fail" for g in gates)
    return {
        "schema": "rosetta-gates/v1",
        "owner": "rosetta",
        "ok": ok,
        "generated_at": generated_at or utc_now_iso(),
        "project_root": str(project_root),
        "decisions_root": str(decisions_root),
        "change_id": change_id,
        "changed_paths": changed_paths,
        "thresholds": {"min_coverage": min_coverage},
        "gates": gates,
    }


def resolve_default_decisions_root(project_root, explicit):
    if explicit:
        return Path(explicit).resolve()
    default = project_root / "decisions"
    return default.resolve() if default.is_dir() else project_root.resolve()


def changed_paths_from_args(args, parser, project_root):
    has_changed = bool(args.changed_path)
    has_diff = args.diff_file is not None
    has_base_head = bool(args.base or args.head)
    if has_base_head and not (args.base and args.head):
        parser.error("--base and --head must be supplied together")
    if sum(bool(x) for x in (has_changed, has_diff, has_base_head)) > 1:
        parser.error("supply exactly one change source")
    try:
        if has_changed:
            paths = [clean_changed_path(p) for p in args.changed_path]
            return sorted(dict.fromkeys(p for p in paths if p))
        if has_diff:
            text = sys.stdin.read() if args.diff_file == "-" else Path(args.diff_file).read_text()
            return parse_diff_paths(text)
        if has_base_head:
            return git_changed_paths(project_root, args.base, args.head)
    except ChangeSourceError as e:
        parser.error(str(e))
    return []


def write_report(report, out):
    text = json.dumps(report, indent=2) + "\n"
    if out == "-":
        print(text, end="")
    else:
        Path(out).write_text(text)


def add_change_source_args(parser):
    parser.add_argument("--changed-path", action="append", default=[], help="repo-relative changed path")
    parser.add_argument("--diff-file", default=None, help="path to name-only/unified diff, or - for stdin")
    parser.add_argument("--base", default=None, help="base revision for local git diff")
    parser.add_argument("--head", default=None, help="head revision for local git diff")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rosetta gate checks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="emit deterministic gate JSON")
    p.add_argument("--project-root", default=None, help="repo/project root (default: cwd)")
    p.add_argument("--decisions-root", default=None,
                   help="decisions root (default: <project>/decisions if present, else <project>)")
    p.add_argument("--min-coverage", type=decisions._unit_float, required=True,
                   help="minimum anchoring coverage in [0,1]")
    add_change_source_args(p)
    p.add_argument("--change-id", default=None, help="stable id for approvals/evidence joins")
    p.add_argument("--out", default="-", help="JSON output path, or - for stdout")

    args = ap.parse_args(argv)
    if args.cmd != "check":
        ap.error("unknown command")
    project_root = Path(args.project_root).resolve() if args.project_root else Path.cwd().resolve()
    decisions_root = resolve_default_decisions_root(project_root, args.decisions_root)
    changed_paths = changed_paths_from_args(args, p, project_root)
    report = build_gates_report(project_root, decisions_root, args.min_coverage,
                                changed_paths=changed_paths, change_id=args.change_id)
    write_report(report, args.out)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
