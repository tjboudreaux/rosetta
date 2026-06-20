#!/usr/bin/env python3
"""Importable console entry for the `rosetta` command (ADR 0013).

`pip install -e .` (from this directory) exposes `rosetta` on your PATH via the
`[project.scripts]` entry point below. It dispatches to the deterministic scripts in the sibling
`scripts/` directory — identical behavior to running `scripts/rosetta` directly.

Pure stdlib. No third-party deps.
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent / "scripts"
_DISPATCH = {
    "collect":   ["collect.py"],
    "discover":  ["collect.py", "--all-projects"],
    "decisions": ["decisions.py"],
    "ingest":    ["ingest.py"],
    "gates":     ["gates.py"],
    "runs":      ["runs.py"],
    "harness":   ["harness.py"],
    "drift":     ["drift.py"],
    "preflight": ["preflight.py"],
}
_USAGE = ("rosetta <command> [args...]\n"
          "  collect    [args...]      scripts/collect.py            gather + normalize transcripts for a project\n"
          "  discover   [args...]      scripts/collect.py --all-projects   machine-wide project index\n"
          "  decisions  <sub> [args]   scripts/decisions.py          new | index | validate | resolve | coverage\n"
          "  ingest     [args]         scripts/ingest.py             external decisions/signals -> Proposed records\n"
          "  gates      check [args]   scripts/gates.py              local provenance/evidence gates\n"
          "  runs       <sub> [args]   scripts/runs.py               loop-run ledger under loop-runs/\n"
          "  harness    export [args] scripts/harness.py             allowlisted harness doc export\n"
          "  drift      report [args] scripts/drift.py               JSON decision drift report\n"
          "  preflight  [args]        scripts/preflight.py           RA1 + decision state + gates JSON")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in _DISPATCH:
        print(f"unknown command: {cmd!r}\n\n{_USAGE}", file=sys.stderr)
        return 2
    target = _DISPATCH[cmd]
    return subprocess.call([sys.executable, str(SCRIPTS / target[0]), *target[1:], *rest])


if __name__ == "__main__":
    sys.exit(main())
