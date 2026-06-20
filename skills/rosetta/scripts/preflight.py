#!/usr/bin/env python3
"""Rosetta preflight — local decision/gate orchestration with optional RA1 structural report."""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decisions  # noqa: E402
import gates  # noqa: E402


def write_report(report, out):
    text = json.dumps(report, indent=2) + "\n"
    if out == "-":
        print(text, end="")
    else:
        Path(out).write_text(text)


def ra1_section(project_root, allow_github, timeout):
    exe = shutil.which("ra1")
    if exe is None:
        return {"name": "ra1_structural", "owner": "ra1", "status": "skip",
                "reason": "ra1_not_found", "data": {}}
    argv = [exe, "report", "--format", "json"]
    if not allow_github:
        argv.append("--no-github")
    try:
        proc = subprocess.run(argv, cwd=project_root, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return {"name": "ra1_structural", "owner": "ra1", "status": "fail",
                "reason": "timeout", "data": {"exit_code": None, "stderr": e.stderr or ""}}
    if proc.returncode != 0:
        return {"name": "ra1_structural", "owner": "ra1", "status": "fail",
                "reason": "nonzero_exit",
                "data": {"exit_code": proc.returncode, "stderr": proc.stderr}}
    if not proc.stdout.strip() and proc.stderr.strip():
        return {"name": "ra1_structural", "owner": "ra1", "status": "fail",
                "reason": "stderr_only_failure",
                "data": {"exit_code": proc.returncode, "stderr": proc.stderr}}
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return {"name": "ra1_structural", "owner": "ra1", "status": "fail",
                "reason": "invalid_json",
                "data": {"exit_code": proc.returncode, "stderr": proc.stderr}}
    return {"name": "ra1_structural", "owner": "ra1", "status": "pass",
            "reason": "ra1_report_ok", "data": data}


def decision_state_section(decisions_root, scope):
    cfg = decisions.load_config(decisions_root)
    records = decisions.collect_records(decisions_root, cfg)
    report = decisions.build_resolve_report(records, cfg, decisions_root, scope, no_stale_check=False)
    live = report.get("current", []) + report.get("via_alias", [])
    stale_current = any(entry.get("stale") is True for entry in report.get("current", []))
    alias_conflict = bool(report.get("alias_conflict"))
    invalid_alias_note = "invalid supersession chain" in report.get("note", "")
    fail = (
        report.get("conflict") or alias_conflict or invalid_alias_note or stale_current or
        (not report.get("resolved_unique") and report.get("matched_records", 0) > 0)
    )
    if not live and not fail:
        return {"name": "decision_state", "owner": "rosetta", "status": "skip",
                "reason": "no_current_decision", "data": report}
    if fail:
        reasons = []
        if report.get("conflict"):
            reasons.append("conflict")
        if alias_conflict:
            reasons.append("alias_conflict")
        if invalid_alias_note:
            reasons.append("invalid_alias_note")
        if stale_current:
            reasons.append("stale_current")
        if not report.get("resolved_unique") and report.get("matched_records", 0) > 0:
            reasons.append("not_resolved_unique")
        return {"name": "decision_state", "owner": "rosetta", "status": "fail",
                "reason": ",".join(dict.fromkeys(reasons)), "data": report}
    return {"name": "decision_state", "owner": "rosetta", "status": "pass",
            "reason": "decision_state_resolved", "data": report}


def gates_section(project_root, decisions_root, min_coverage, changed_paths, change_id):
    report = gates.build_gates_report(project_root, decisions_root, min_coverage,
                                      changed_paths=changed_paths, change_id=change_id)
    if any(g["status"] == "fail" for g in report["gates"]):
        return {"name": "gates", "owner": "rosetta", "status": "fail",
                "reason": "gate_failure", "data": report}
    return {"name": "gates", "owner": "rosetta", "status": "pass",
            "reason": "gates_ok", "data": report}


def build_preflight_report(project_root, decisions_root, scope, min_coverage, *, changed_paths=None,
                           change_id=None, allow_ra1_github=False, ra1_timeout=30):
    project_root = Path(project_root).resolve()
    decisions_root = Path(decisions_root).resolve()
    sections = [
        ra1_section(project_root, allow_ra1_github, ra1_timeout),
        decision_state_section(decisions_root, scope),
        gates_section(project_root, decisions_root, min_coverage, changed_paths or [], change_id),
    ]
    ok = not any(s["status"] == "fail" for s in sections)
    return {
        "schema": "rosetta-preflight/v1",
        "owner": "rosetta",
        "ok": ok,
        "generated_at": gates.utc_now_iso(),
        "network_allowed": bool(allow_ra1_github),
        "sections": sections,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rosetta preflight")
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--decisions-root", required=True)
    ap.add_argument("--scope", required=True, help="decision query")
    ap.add_argument("--min-coverage", type=decisions._unit_float, required=True)
    gates.add_change_source_args(ap)
    ap.add_argument("--change-id", default=None)
    ap.add_argument("--allow-ra1-github", action="store_true")
    ap.add_argument("--ra1-timeout", type=float, default=30)
    ap.add_argument("--out", default="-")
    args = ap.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    decisions_root = Path(args.decisions_root).resolve()
    changed_paths = gates.changed_paths_from_args(args, ap, project_root)
    report = build_preflight_report(project_root, decisions_root, args.scope, args.min_coverage,
                                    changed_paths=changed_paths, change_id=args.change_id,
                                    allow_ra1_github=args.allow_ra1_github,
                                    ra1_timeout=args.ra1_timeout)
    write_report(report, args.out)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
