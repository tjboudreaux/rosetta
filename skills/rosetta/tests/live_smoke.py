#!/usr/bin/env python3
"""Live smoke — run every resolver against the REAL machine and print what it finds. Non-asserting:
this documents reality (P0 agents should be nonzero; P1 agents absent here report 0 without error).

Usage:
    python3 tests/live_smoke.py [project ...]      # defaults to a few known-populated projects
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import collect  # noqa: E402

DEFAULT_PROJECTS = [
    str(Path.home() / ".claude" / "skills" / "rosetta"),   # this skill itself
    str(Path.cwd()),                                       # the current directory
]   # pass your own project paths as args to probe them: `python3 tests/live_smoke.py <path> ...`


def main():
    projects = sys.argv[1:] or [p for p in DEFAULT_PROJECTS if Path(p).exists()]

    print("== machine-wide totals (discover_all_projects) ==")
    disc = collect.discover_all_projects()
    totals = {}
    for ag in disc["projects"].values():
        for name, v in ag.items():
            if isinstance(v, dict):
                totals[name] = totals.get(name, 0) + v.get("sessions", 0)
    for name in sorted(totals):
        print(f"  {name:14} {totals[name]} sessions across {sum(1 for a in disc['projects'].values() if name in a)} projects")
    print(f"  unscoped: {disc['unscoped_agents']}")
    print(f"  {disc['hermes_note']}")
    print(f"  unknown_stores still flagged: {[Path(p).name for p in collect.discovery_sweep()]}")

    print("\n== per-project resolver counts (real data) ==")
    for project in projects:
        print(f"\n[{project}]")
        for agent, spec in collect.AGENTS.items():
            try:
                res = spec["resolver"](project, False)
                n = len(res["units"])
            except Exception as e:
                print(f"  {agent:14} ERROR {e}")
                continue
            if n:
                msgs = sum(spec["parser"](u, 4000)["kept"] for u in res["units"])
                flag = " [UNVERIFIED]" if res["extra"].get("unverified") else ""
                print(f"  {agent:14} {n} sessions / {msgs} messages{flag}")


if __name__ == "__main__":
    main()
