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
}
_USAGE = ("rosetta <command> [args...]\n"
          "  collect    gather + normalize a project's transcripts\n"
          "  discover   machine-wide index of projects with agent history\n"
          "  decisions  new | index | validate the decision library\n"
          "  ingest     external decisions (meetings/Slack) -> Proposed records")


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
