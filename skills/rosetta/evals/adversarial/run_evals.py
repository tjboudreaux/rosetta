#!/usr/bin/env python3
"""Adversarial eval runner.

For each scenario in dataset.json: materialize its fixture into a throwaway `$HOME`, run the
collector against the planted project, then execute the Tier-A deterministic checks:

  * coverage      — collector surfaced exactly the planted sessions per agent (no silent drop)
  * provenance    — each expected agent has a real citation anchor (normalized file)
  * substrate     — every planted content phrase is present in the normalized corpus (the judgment
                    half is GIVEN what it needs) and code/doc/git markers exist where the truth
                    hierarchy must find them
  * leakage lint  — no gold token (anti-pattern label, scenario id, or scenario `banned_in_fixture`)
                    appears in any solver-visible file (project tree + normalized corpus)
  * git evidence  — for requires_git scenarios, expected commit subjects are in the project's git log;
                    if git is unavailable the scenario is SKIPPED LOUDLY, never silently downgraded

Tier A proves the substrate; it does NOT grade the model's reasoning. Tier B (judge_prompt.md) does
that against the judge_only gold — run it with `--emit-bundle <dir>` to produce judge-ready bundles.

Pure stdlib. Usage:
  python3 run_evals.py                      # run Tier-A checks for all scenarios, print a report
  python3 run_evals.py --scenario <id>      # one scenario
  python3 run_evals.py --emit-bundle <dir>  # also write Tier-B judge bundles (contain gold; judge-only)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "scripts"))
import collect    # noqa: E402
import fixtures    # noqa: E402

DATASET = HERE / "dataset.json"


class CheckError(AssertionError):
    pass


def load_dataset():
    return json.loads(DATASET.read_text())


def run_collector(home, project):
    """Run collect against the sandboxed home; return (manifest, {normalized_name: text})."""
    out = Path(home) / "_rosetta_out"
    argv = ["collect", "--project", project, "--out", str(out), "--reprocess"]
    old_argv, old_home = sys.argv, os.environ.get("ROSETTA_HOME")
    sys.argv = argv
    os.environ["ROSETTA_HOME"] = str(home)
    try:
        collect.main()
    finally:
        sys.argv = old_argv
        if old_home is None:
            os.environ.pop("ROSETTA_HOME", None)
        else:
            os.environ["ROSETTA_HOME"] = old_home
    manifest = json.loads((out / "manifest.json").read_text())
    corpus = {p.name: p.read_text() for p in out.glob("*.md")}
    return manifest, corpus, out


def _solver_visible_text(project, corpus):
    """Everything a solver could read per SKILL.md: the project file tree (text + relative paths),
    the normalized corpus, and the git history (`git log` is part of step 5)."""
    chunks = list(corpus.values())
    for fp in sorted(Path(project).rglob("*")):
        if fp.is_file() and ".agents" not in fp.parts and ".git" not in fp.parts:
            chunks.append(str(fp.relative_to(project)))          # filenames are visible too
            try:
                chunks.append(fp.read_text())
            except (UnicodeDecodeError, OSError):
                pass
    if fixtures.GIT and (Path(project) / ".git").exists():
        chunks.append(subprocess.run([fixtures.GIT, "-C", project, "log", "--format=%s%n%b"],
                                     capture_output=True, text=True).stdout)
    return "\n".join(chunks)


def tier_a_checks(scenario, planted, manifest, corpus, project):
    """Return list of (check_name, ok, detail). Raises nothing; collects all results."""
    results = []

    def add(name, ok, detail=""):
        results.append((name, ok, detail))

    # coverage — per-agent session counts (exact)
    expected = planted.get("expected_sessions", {})
    for agent, n in expected.items():
        got = manifest["agents"].get(agent, {}).get("sessions", 0)
        add(f"coverage:{agent}={n}", got == n, f"got {got}")
    if planted.get("expect_zero_sessions"):
        add("coverage:zero", manifest["totals"]["sessions"] == 0,
            f"got {manifest['totals']['sessions']}")
    else:
        # exact total — catches duplicated/extra sessions a per-agent check would miss
        add("coverage:total", manifest["totals"]["sessions"] == sum(expected.values()),
            f"total={manifest['totals']['sessions']} expected={sum(expected.values())}")

    # misattribution guard — no agent OUTSIDE the expected set may carry sessions
    for agent, a in manifest["agents"].items():
        if a.get("sessions", 0) > 0 and agent not in expected:
            add(f"misattrib:{agent}", False, f"{a['sessions']} unexpected sessions")

    # provenance — each expected agent has exactly its files, and each planted session id resolves
    # to a real source path (pins attribution, not just a count)
    for agent in expected:
        files = manifest["agents"].get(agent, {}).get("files", [])
        add(f"provenance:{agent}", len(files) == expected[agent], f"{len(files)} files")
    srcs_by_agent = {ag: " ".join(f["source"] + " " + f["normalized"] for f in a.get("files", []))
                     for ag, a in manifest["agents"].items()}
    for anchor in planted.get("anchors", []):
        ag, sid = anchor["agent"], str(anchor["session"])
        add(f"anchor:{ag}:{sid[:24]}", sid in srcs_by_agent.get(ag, ""),
            "session id not found in any source path")

    # unmatchable counters (e.g. codex.sessions_without_cwd > 0)
    for agent, want in planted.get("expected_extra", {}).items():
        extra = manifest["agents"].get(agent, {}).get("extra", {})
        for key, val in want.items():
            if key.endswith("_gt0"):
                field = key[:-4]
                add(f"extra:{agent}.{field}>0", extra.get(field, 0) > 0, f"extra={extra}")
            else:
                add(f"extra:{agent}.{key}={val}", extra.get(key) == val, f"extra={extra}")

    # substrate — planted content phrases reachable in the normalized corpus
    blob = "\n".join(corpus.values())
    for phrase in planted.get("content_present", []):
        add(f"substrate:'{phrase[:32]}'", phrase in blob, "missing from corpus")
    # contamination guard — excluded/fabricated content must NOT reach the corpus
    for phrase in planted.get("absent_in_corpus", []):
        add(f"excluded:'{phrase[:32]}'", phrase not in blob, "leaked into corpus")
    # unknown-store visibility — an unsupported store must be surfaced, not silently skipped
    if planted.get("expect_unknown_store"):
        add("unknown_store", len(manifest.get("unknown_stores", [])) > 0, "no unknown store flagged")

    # decision-library substrate — the seeded ADR library exists at the planted size, the buried
    # needle + near-miss distractor are present, and the library is decisions.py-valid. This proves
    # the model was GIVEN a well-formed, correctly-sized library to operate over (Tier B grades
    # whether it found the right record).
    lib = planted.get("decision_library")
    if lib:
        d = Path(project) / lib["dir"]
        files = sorted(d.glob("*.md"))
        add("declib:count", len(files) >= lib["count"], f"{len(files)} records, want >= {lib['count']}")
        needle = Path(project) / lib["needle_path"] if lib.get("needle_path") else None
        ntxt = needle.read_text() if needle and needle.exists() else ""
        for s in lib.get("needle_contains", []):
            add(f"needle:{s[:20]}", s in ntxt, "missing from needle ADR")
        for rel in lib.get("distractor_paths", []):
            add(f"distractor:{Path(rel).name if rel else '?'}",
                bool(rel) and (Path(project) / rel).exists(), "near-miss distractor missing")
        if lib.get("validate"):
            r = subprocess.run([sys.executable, str(HERE.parents[1] / "scripts" / "decisions.py"),
                                "--root", str(Path(project) / "decisions"), "validate"],
                               capture_output=True, text=True)
            tail = (r.stderr or r.stdout).strip().replace("\n", " ")[-80:]
            add("declib:valid", r.returncode == 0, tail)

    # code/doc markers present on disk
    for rel, subs in planted.get("code_markers", {}).items():
        fp = Path(project) / rel
        txt = fp.read_text() if fp.exists() else ""
        for s in subs:
            add(f"marker:{rel}:{s}", s in txt, "absent" if fp.exists() else "file missing")
    for rel, subs in planted.get("stale_doc_markers", {}).items():
        fp = Path(project) / rel
        txt = fp.read_text() if fp.exists() else ""
        for s in subs:
            add(f"stale_doc:{rel}:{s}", s in txt, "absent")

    # absent markers / files (what must NOT be in the current checkout)
    for rel, subs in planted.get("absent_markers", {}).items():
        fp = Path(project) / rel
        txt = fp.read_text() if fp.exists() else ""
        for s in subs:
            add(f"absent_marker:{rel}:{s}", s not in txt, "unexpectedly present")
    for rel in planted.get("absent_files", []):
        add(f"absent_file:{rel}", not (Path(project) / rel).exists(), "still present")

    # git evidence
    if planted.get("requires_git") or scenario.get("requires_git"):
        subjects = planted.get("git_subjects", [])
        if not fixtures.GIT:
            add("git:available", False, "SKIP — git unavailable")
        else:
            log = subprocess.run([fixtures.GIT, "-C", project, "log", "--format=%s"],
                                 capture_output=True, text=True).stdout
            for subj in subjects:
                add(f"git:'{subj[:40]}'", subj in log, "commit subject missing")

    # leakage lint — no gold token in solver-visible text
    visible = _solver_visible_text(project, corpus).lower()
    banned = list(planted.get("banned_in_fixture", []))
    banned += [scenario["id"], scenario["anti_pattern"].replace("-", " ")]
    for tok in banned:
        t = tok.lower().strip()
        if t:
            add(f"leak:{tok[:32]}", t not in visible, "TOKEN LEAKED into fixture")

    return results


def run_scenario(scenario, emit_bundle=None):
    """Build fixture, run collector, run Tier-A checks. Returns a result dict."""
    requires_git = scenario.get("requires_git", False)
    # NB: neutral prefix — the scenario id must NOT appear in the sandbox path, or it leaks into the
    # normalized .md `source:`/`project:` lines and trips the leakage linter against itself.
    tmp = tempfile.mkdtemp(prefix="rosetta-adv-")
    try:
        planted = fixtures.build(scenario["fixture"], tmp)
        requires_git = requires_git or planted.get("requires_git", False)
        meta = {"id": scenario["id"], "anti_pattern": scenario.get("anti_pattern"),
                "drift_size": scenario.get("drift_size")}
        if requires_git and not fixtures.GIT:
            return {**meta, "status": "skipped", "reason": "requires git; git unavailable", "checks": []}
        manifest, corpus, out = run_collector(tmp, planted["project"])
        checks = tier_a_checks(scenario, planted, manifest, corpus, planted["project"])
        failed = [c for c in checks if not c[1]]
        status = "pass" if not failed else "fail"

        if emit_bundle:
            _write_bundle(Path(emit_bundle) / scenario["id"], scenario, planted, manifest, corpus,
                          out, planted["project"])
        return {**meta, "status": status, "checks": checks,
                "n_checks": len(checks), "n_failed": len(failed)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _write_bundle(dst, scenario, planted, manifest, corpus, out, project):
    """Judge-ready Tier-B bundle. CONTAINS GOLD — never give this to the solver."""
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "prompt.txt").write_text(scenario["prompt"].replace("{project}", project))
    (dst / "gold.json").write_text(json.dumps(scenario["judge_only"], indent=2))
    # the legitimate citation anchor set, straight from the manifest
    anchors = []
    for agent, a in manifest["agents"].items():
        for f in a.get("files", []):
            anchors.append({"agent": agent, "source": f["source"], "normalized": f["normalized"],
                            "first_ts": f["first_ts"], "last_ts": f["last_ts"]})
    (dst / "anchors.json").write_text(json.dumps(anchors, indent=2))
    corpus_dir = dst / "normalized"
    corpus_dir.mkdir(exist_ok=True)
    for name, text in corpus.items():
        (corpus_dir / name).write_text(text)
    # the manifest the judge needs to check coverage claims (match modes, extras, unknown stores)
    (dst / "manifest.json").write_text(json.dumps(manifest, indent=2))
    # a snapshot of the project tree so the judge can verify code/doc-grounded claims (truth hierarchy)
    code_dir = dst / "project"
    for fp in sorted(Path(project).rglob("*")):
        if fp.is_file() and ".agents" not in fp.parts and ".git" not in fp.parts:
            rel = fp.relative_to(project)
            (code_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            try:
                (code_dir / rel).write_text(fp.read_text())
            except (UnicodeDecodeError, OSError):
                pass
    if fixtures.GIT and (Path(project) / ".git").exists():
        gitlog = subprocess.run([fixtures.GIT, "-C", project, "log", "--format=%H %ad %s",
                                 "--date=short"], capture_output=True, text=True).stdout
        (dst / "git-log.txt").write_text(gitlog)

    # No-tools long-context variant: concatenate the whole decision library into one text blob so a
    # solver can be tested WITHOUT grep/search tools — measuring genuine long-context recall rather
    # than retrieval-with-tools (the calibration distinction in ADR 0022 / CALIBRATION.md).
    lib_dir = code_dir / "decisions" / "architecture-decisions"
    if lib_dir.exists():
        records = sorted(lib_dir.glob("*.md"))
        blob = "\n\n".join(f"===== {p.name} =====\n{p.read_text()}" for p in records)
        (dst / "library.txt").write_text(blob)


def main():
    ap = argparse.ArgumentParser(description="Rosetta adversarial eval runner (Tier-A + bundle emit)")
    ap.add_argument("--scenario", help="run only this scenario id")
    ap.add_argument("--emit-bundle", help="dir to write Tier-B judge bundles into (contain gold)")
    ap.add_argument("--report", help="write a machine-readable results.json (rosetta-eval-results/v1)")
    args = ap.parse_args()

    data = load_dataset()
    scenarios = data["scenarios"]
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] == args.scenario]
        if not scenarios:
            ap.error(f"unknown scenario: {args.scenario}")

    n_pass = n_fail = n_skip = 0
    report_scenarios = []
    for s in scenarios:
        r = run_scenario(s, emit_bundle=args.emit_bundle)
        report_scenarios.append({"id": r["id"], "anti_pattern": r.get("anti_pattern"),
                                 "drift_size": r.get("drift_size"), "status": r["status"],
                                 "checks": r.get("n_checks", 0), "failed": r.get("n_failed", 0)})
        if r["status"] == "skipped":
            n_skip += 1
            print(f"SKIP  {r['id']:32}  {r['reason']}")
            continue
        if r["status"] == "pass":
            n_pass += 1
            print(f"PASS  {r['id']:32}  {r['n_checks']} checks")
        else:
            n_fail += 1
            print(f"FAIL  {r['id']:32}  {r['n_failed']}/{r['n_checks']} checks failed")
            for name, ok, detail in r["checks"]:
                if not ok:
                    print(f"        ✗ {name}  ({detail})")
    print(f"\n{n_pass} passed, {n_fail} failed, {n_skip} skipped "
          f"of {len(scenarios)} scenarios")

    if args.report:
        # rosetta-eval-results/v1 — a "runs" list so multiple tiers/runs (Tier-A here, Tier-B and
        # multi-model from elsewhere) merge into one report.py render. generated_at is omitted
        # (Date.now is unavailable here); stamp it externally if needed.
        result = {"schema": "rosetta-eval-results/v1",
                  "runs": [{"tier": "A", "model": "deterministic", "scenarios": report_scenarios,
                            "totals": {"passed": n_pass, "failed": n_fail, "skipped": n_skip,
                                       "total": len(scenarios)}}]}
        Path(args.report).write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {args.report}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
