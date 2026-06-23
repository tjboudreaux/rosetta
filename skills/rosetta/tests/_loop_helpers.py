import json
import os
import subprocess
import tempfile
import contextlib
import importlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = ROOT / "scripts"


def load_script(name):
    """Import scripts/<name>.py in-process so coverage measures it."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module(name)


def call_main(module, argv, *, stdin_text=None):
    """Run a module's main() in-process; return (code, stdout, stderr).

    Pass argv=None for mains that read sys.argv directly (set sys.argv first).
    SystemExit (argparse or explicit) is normalized to an int code.
    """
    out, err = io.StringIO(), io.StringIO()
    code = 0
    saved_stdin = sys.stdin
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = module.main() if argv is None else module.main(argv)
                code = rc if isinstance(rc, int) else 0
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.stdin = saved_stdin
    return code, out.getvalue(), err.getvalue()


def run_cli(args, cwd=ROOT, env=None, input_text=None):
    return subprocess.run(args, cwd=cwd, env=env, input=input_text, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ProjectFixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve()
        self.decisions = self.project / "decisions"
        (self.decisions / "architecture-decisions").mkdir(parents=True)
        (self.decisions / "product-decisions").mkdir(parents=True)
        (self.decisions / "business-decisions").mkdir(parents=True)

    def cleanup(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def record(self, rel, label="ADR", num="0001", title="Decision", status="Accepted",
               sources="src/a.py", extra="", body="Decision."):
        dirs = {"ADR": "architecture-decisions", "PDR": "product-decisions", "BDR": "business-decisions"}
        path = self.decisions / dirs[label] / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = (f"# {label} {num} — {title}\n\n"
                f"- Status: {status}\n"
                "- Date: 2026-06-01\n"
                "- Decider: Me\n"
                f"- Sources: {sources}\n"
                f"{extra}"
                "\n## Decision\n\n"
                f"{body}\n")
        path.write_text(text)
        return path

    def init_git(self):
        run_cli(["git", "init"], cwd=self.project)
        run_cli(["git", "config", "user.email", "test@example.com"], cwd=self.project)
        run_cli(["git", "config", "user.name", "Test"], cwd=self.project)

    def commit_all(self, message="commit"):
        run_cli(["git", "add", "."], cwd=self.project)
        return run_cli(["git", "commit", "-m", message], cwd=self.project)


def parse_json(proc):
    return json.loads(proc.stdout)
