#!/usr/bin/env python3
"""Rosetta drift report — JSON freshness report for decision records."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decisions  # noqa: E402


def build_drift_report(project_root, decisions_root, status="Accepted"):
    project_root = Path(project_root).resolve()
    decisions_root = Path(decisions_root).resolve()
    cfg = decisions.load_config(decisions_root)
    records = decisions.collect_records(decisions_root, cfg)
    git_ok, assessed = decisions.assess_staleness(records, decisions_root, cfg, (status.lower(),))
    suggested_actions = {
        "review": "Review stale records against their cited code paths and add Reviewed only after confirmation.",
        "supersede": "Supersede records whose decisions no longer match the current implementation.",
        "recollect_or_grill": "Recollect sources or grill the owner when code and recorded decisions diverge.",
    }
    if not git_ok:
        return {
            "schema": "rosetta-drift/v1",
            "owner": "rosetta",
            "status": "skip",
            "git": False,
            "stale_count": 0,
            "stale": [],
            "unknown": [],
            "fresh_count": 0,
            "skip_reason": "not_git",
            "suggested_actions": suggested_actions,
        }
    stale = [a for a in assessed if a["stale"] is True]
    unknown = [a for a in assessed if a["stale"] is None]
    fresh = [a for a in assessed if a["stale"] is False]
    return {
        "schema": "rosetta-drift/v1",
        "owner": "rosetta",
        "status": "stale" if stale else "fresh",
        "git": True,
        "stale_count": len(stale),
        "stale": stale,
        "unknown": unknown,
        "fresh_count": len(fresh),
        "skip_reason": None,
        "suggested_actions": suggested_actions,
    }


def write_report(report, out):
    text = json.dumps(report, indent=2) + "\n"
    if out == "-":
        print(text, end="")
    else:
        Path(out).write_text(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Report decision-record drift")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("report", help="emit drift JSON")
    p.add_argument("--project-root", required=True)
    p.add_argument("--decisions-root", required=True)
    p.add_argument("--status", default="Accepted")
    p.add_argument("--out", default="-")
    args = ap.parse_args(argv)
    report = build_drift_report(args.project_root, args.decisions_root, args.status)
    write_report(report, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
