"""In-process coverage for the loop CLIs (drift/gates/harness/preflight/runs/ingest).

The sibling ``test_*_cli.py`` suites drive these modules via ``subprocess`` — correct end-to-end
checks, but coverage.py only instruments the parent process, so those runs register 0% for the
modules themselves. These tests import each module and call its functions / ``main()`` in-process
so the coverage gate measures the shipped loop code. The behavior asserted here mirrors the
subprocess suites (same fixtures, same expected returncodes/JSON).
"""
import json
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

from tests._loop_helpers import ROOT, ProjectFixture, call_main, load_script

drift = load_script("drift")
gates = load_script("gates")
harness = load_script("harness")
preflight = load_script("preflight")
runs = load_script("runs")
ingest = load_script("ingest")


class DriftInProcess(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()

    def tearDown(self):
        self.fx.cleanup()

    def test_non_git_skips(self):
        self.fx.record("0001-a.md", sources="src/a.py")
        report = drift.build_drift_report(self.fx.project, self.fx.decisions)
        self.assertEqual(report["status"], "skip")
        self.assertEqual(report["skip_reason"], "not_git")
        self.assertEqual(report["stale_count"], 0)

    def test_git_stale(self):
        self.fx.init_git()
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.commit_all("add source")
        rec = self.fx.record("0001-a.md", sources="src/a.py")
        rec.write_text(rec.read_text().replace("2026-06-01", "2020-01-01"))
        report = drift.build_drift_report(self.fx.project, self.fx.decisions)
        self.assertEqual(report["status"], "stale")
        self.assertEqual(report["stale_count"], 1)

    def test_git_unknown_source_is_fresh(self):
        self.fx.init_git()
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.commit_all("add source")
        self.fx.record("0001-a.md", sources="src/missing.py")
        report = drift.build_drift_report(self.fx.project, self.fx.decisions)
        self.assertEqual(report["status"], "fresh")
        self.assertEqual(report["stale_count"], 0)
        self.assertTrue(report["unknown"])

    def test_main_writes_file_and_stdout(self):
        self.fx.record("0001-a.md", sources="src/a.py")
        out = self.fx.project / "drift.json"
        code, _, _ = call_main(drift, ["report", "--project-root", str(self.fx.project),
                                       "--decisions-root", str(self.fx.decisions), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.read_text())["schema"], "rosetta-drift/v1")
        code2, stdout2, _ = call_main(drift, ["report", "--project-root", str(self.fx.project),
                                              "--decisions-root", str(self.fx.decisions)])
        self.assertEqual(code2, 0)
        self.assertEqual(json.loads(stdout2)["owner"], "rosetta")


class GatesInProcess(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()

    def tearDown(self):
        self.fx.cleanup()

    def report(self, **kw):
        min_cov = kw.pop("min_coverage", 1.0)
        return gates.build_gates_report(self.fx.project, self.fx.decisions, min_cov, **kw)

    @staticmethod
    def by_gate(report):
        return {g["gate"]: g for g in report["gates"]}

    def test_validation_and_anchoring_fail(self):
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.record("0001-a.md", sources="")
        report = self.report()
        self.assertFalse(report["ok"])
        bg = self.by_gate(report)
        self.assertEqual(bg["validation"]["status"], "fail")
        self.assertEqual(bg["anchoring"]["status"], "fail")

    def test_staleness_fail(self):
        self.fx.init_git()
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.commit_all("add source")
        rec = self.fx.record("0001-a.md", sources="src/a.py")
        rec.write_text(rec.read_text().replace("2026-06-01", "2020-01-01"))
        self.assertEqual(self.by_gate(self.report())["staleness"]["status"], "fail")

    def test_no_changed_paths_skips(self):
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.record("0001-a.md", sources="src/a.py")
        report = self.report()
        self.assertTrue(report["ok"])
        bg = self.by_gate(report)
        self.assertEqual(bg["denylist"]["status"], "skip")
        self.assertEqual(bg["evidence_presence"]["status"], "skip")

    def test_denylist_requires_approval(self):
        self.fx.write("src/payments/Pay.tsx", "x\n")
        self.fx.record("0001-gate.md", sources="src/payments/Pay.tsx",
                       extra="- Human gated paths: src/payments/**\n")
        r1 = self.report(changed_paths=["src/payments/Pay.tsx"], change_id="change-1")
        self.assertEqual(self.by_gate(r1)["denylist"]["status"], "fail")
        self.fx.record("0002-approve.md", num="0002", title="Approve", sources="src/payments/Pay.tsx",
                       extra="- Human approval for: change-1\n")
        r2 = self.report(changed_paths=["src/payments/Pay.tsx"], change_id="change-1")
        self.assertEqual(self.by_gate(r2)["denylist"]["status"], "pass")

    def test_evidence_presence_requires_artifact(self):
        self.fx.write("src/App.tsx", "x\n")
        self.fx.record("0001-ui.md", sources="src/App.tsx")
        r1 = self.report(changed_paths=["src/App.tsx"], change_id="change-1")
        self.assertEqual(self.by_gate(r1)["evidence_presence"]["status"], "fail")
        self.fx.write("artifacts/app.png", "png")
        self.fx.record("0002-evidence.md", num="0002", title="Evidence", sources="src/App.tsx",
                       extra="- Evidence for: change-1\n- Evidence artifacts: screenshot:artifacts/app.png\n")
        r2 = self.report(changed_paths=["src/App.tsx"], change_id="change-1")
        self.assertEqual(self.by_gate(r2)["evidence_presence"]["status"], "pass")

    def test_main_check_exit_codes_and_change_sources(self):
        self.fx.write("src/a.py", "print(1)\n")
        self.fx.record("0001-a.md", sources="src/a.py")
        base = ["check", "--project-root", str(self.fx.project), "--decisions-root", str(self.fx.decisions),
                "--min-coverage", "1.0"]
        code, stdout, _ = call_main(gates, base)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["schema"], "rosetta-gates/v1")
        self.assertIn(call_main(gates, base + ["--changed-path", "src/a.py", "--change-id", "c1"])[0], (0, 1))
        diff = self.fx.project / "d.diff"
        diff.write_text("diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n")
        self.assertIn(call_main(gates, base + ["--diff-file", str(diff), "--change-id", "c1"])[0], (0, 1))
        self.assertIn(call_main(gates, base + ["--diff-file", "-", "--change-id", "c1"], stdin_text="src/a.py\n")[0], (0, 1))
        # conflicting / incomplete change sources -> argparse error (exit 2)
        self.assertEqual(call_main(gates, base + ["--changed-path", "x", "--diff-file", str(diff)])[0], 2)
        self.assertEqual(call_main(gates, base + ["--base", "HEAD"])[0], 2)

    def test_git_changed_paths_helper(self):
        self.fx.init_git()
        self.fx.write("src/a.py", "1\n")
        self.fx.commit_all("c1")
        self.fx.write("src/b.py", "2\n")
        self.fx.commit_all("c2")
        self.assertIn("src/b.py", gates.git_changed_paths(self.fx.project, "HEAD~1", "HEAD"))
        with self.assertRaises(SystemExit):
            gates.git_changed_paths(self.fx.project, "nope1", "nope2")

    def test_clean_changed_path_and_parse_diff(self):
        self.assertIsNone(gates.clean_changed_path(""))
        self.assertIsNone(gates.clean_changed_path("/dev/null"))
        self.assertEqual(gates.clean_changed_path('"a/src/x.py"'), "src/x.py")
        self.assertEqual(gates.clean_changed_path("b/src/y.py"), "src/y.py")
        with self.assertRaises(gates.ChangeSourceError):
            gates.clean_changed_path("/abs/path")
        with self.assertRaises(gates.ChangeSourceError):
            gates.clean_changed_path("../escape")
        git_diff = "diff --git a/p/q.py b/p/q.py\n+++ b/p/q.py\n--- a/p/q.py\n"
        self.assertEqual(gates.parse_diff_paths(git_diff), ["p/q.py"])
        self.assertEqual(gates.parse_diff_paths("one.py\ntwo.py\n"), ["one.py", "two.py"])


class HarnessInProcess(unittest.TestCase):
    SCHEMA = "rosetta-harness-export/v1"

    def setUp(self):
        self.fx = ProjectFixture()
        self.contract = self.fx.project / "contract.json"
        self.contract.write_text(json.dumps({
            "schema": self.SCHEMA,
            "architecture": {"summary": "New arch", "components": [], "status": "accepted"},
            "mobile": {"summary": "New mobile", "facts": ["fact"], "decisions": [], "status": "accepted"},
            "domains": [{"slug": "payments", "title": "Payments", "summary": "Pay",
                         "paths": ["src/payments"], "decisions": [], "status": "confirm"},
                        {"slug": "Bad Slug", "title": "Bad"}],
        }))

    def tearDown(self):
        self.fx.cleanup()

    def export(self, *args):
        return call_main(harness, ["export", "--project-root", str(self.fx.project),
                                   "--from-json", str(self.contract), *args])

    def test_dry_run_lists_targets_and_warns(self):
        code, stdout, _ = self.export()
        self.assertEqual(code, 0)
        report = json.loads(stdout)
        self.assertEqual([t["path"] for t in report["targets"]],
                         ["ARCHITECTURE.md", "docs/MOBILE.md", "domains/payments/README.md"])
        self.assertEqual(report["warnings"][0]["code"], "invalid_domain_slug")

    def test_patch_writes_nothing(self):
        self.fx.write("ARCHITECTURE.md", "B\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\n")
        code, stdout, _ = self.export("--patch")
        self.assertEqual(code, 0)
        self.assertIn("New arch", stdout)
        self.assertIn("old", (self.fx.project / "ARCHITECTURE.md").read_text())

    def test_apply_requires_all_marked_targets(self):
        self.fx.write("ARCHITECTURE.md", "B\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\nA\n")
        self.fx.write("docs/MOBILE.md", "B\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\nA\n")
        self.assertEqual(self.export("--apply")[0], 3)  # missing domain target blocks all writes
        self.fx.write("domains/payments/README.md", "B\n<!-- ROSETTA:HARNESS:START -->\nold\n<!-- ROSETTA:HARNESS:END -->\n")
        self.assertEqual(self.export("--apply")[0], 0)
        self.assertIn("New arch", (self.fx.project / "ARCHITECTURE.md").read_text())

    def test_load_contract_errors(self):
        self.assertNotEqual(call_main(harness, ["export", "--project-root", str(self.fx.project),
                                                "--from-json", str(self.fx.project / "nope.json")])[0], 0)
        bad = self.fx.project / "bad.json"
        bad.write_text("{not json")
        self.assertNotEqual(call_main(harness, ["export", "--project-root", str(self.fx.project),
                                                "--from-json", str(bad)])[0], 0)
        wrong = self.fx.project / "wrong.json"
        wrong.write_text(json.dumps({"schema": "x"}))
        self.assertNotEqual(call_main(harness, ["export", "--project-root", str(self.fx.project),
                                                "--from-json", str(wrong)])[0], 0)

    def test_target_allowlist(self):
        self.assertEqual(harness.validate_target_rel("ARCHITECTURE.md"), "ARCHITECTURE.md")
        self.assertEqual(harness.validate_target_rel("docs/MOBILE.md"), "docs/MOBILE.md")
        self.assertEqual(harness.validate_target_rel("domains/pay/README.md"), "domains/pay/README.md")
        for bad in ("secrets.md", "/etc/passwd", "../x/README.md", "domains/Bad Slug/README.md"):
            with self.assertRaises(ValueError):
                harness.validate_target_rel(bad)
        self.assertTrue(str(harness.ensure_safe_target(self.fx.project, "ARCHITECTURE.md")).endswith("ARCHITECTURE.md"))

    def test_build_targets_warning_variants(self):
        targets, warnings = harness.build_targets({"schema": self.SCHEMA, "domains": "nope"}, self.fx.project)
        self.assertEqual([w["code"] for w in warnings], ["invalid_domains"])
        self.assertEqual([t["path"] for t in targets], ["ARCHITECTURE.md", "docs/MOBILE.md"])
        _, w2 = harness.build_targets({"schema": self.SCHEMA, "domains": ["nota-dict"]}, self.fx.project)
        self.assertEqual(w2[0]["code"], "invalid_domain")


class PreflightInProcess(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()

    def tearDown(self):
        self.fx.cleanup()

    @staticmethod
    def _run(returncode=0, stdout='{"ok": true}', stderr="", side_effect=None):
        if side_effect is not None:
            return mock.Mock(side_effect=side_effect)
        return mock.Mock(return_value=SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr))

    def test_ra1_section_variants(self):
        P = self.fx.project
        with mock.patch.object(preflight.shutil, "which", return_value=None):
            self.assertEqual(preflight.ra1_section(P, False, 30)["status"], "skip")
        with mock.patch.object(preflight.shutil, "which", return_value="/fake/ra1"):
            with mock.patch.object(preflight.subprocess, "run", self._run(stdout='{"ok": true}')):
                self.assertEqual(preflight.ra1_section(P, False, 30)["status"], "pass")
            with mock.patch.object(preflight.subprocess, "run", self._run(stdout="not json")):
                self.assertEqual(preflight.ra1_section(P, False, 30)["reason"], "invalid_json")
            with mock.patch.object(preflight.subprocess, "run", self._run(returncode=7, stderr="boom")):
                self.assertEqual(preflight.ra1_section(P, False, 30)["reason"], "nonzero_exit")
            with mock.patch.object(preflight.subprocess, "run", self._run(stdout="", stderr="boom")):
                self.assertEqual(preflight.ra1_section(P, False, 30)["reason"], "stderr_only_failure")
            timeout = subprocess.TimeoutExpired(cmd=["ra1"], timeout=0.01)
            with mock.patch.object(preflight.subprocess, "run", self._run(side_effect=timeout)):
                self.assertEqual(preflight.ra1_section(P, True, 0.01)["reason"], "timeout")

    def test_decision_state_skip_pass_fail(self):
        D = self.fx.decisions
        self.assertEqual(preflight.decision_state_section(D, "anything")["status"], "skip")
        self.fx.record("0001-onb.md", title="Onboarding flow", sources="src/a.py", body="Onboarding flow body.")
        self.assertEqual(preflight.decision_state_section(D, "Onboarding")["status"], "pass")
        self.fx.record("0002-prop.md", num="0002", title="Proposed thing", status="Proposed",
                       sources="src/b.py", body="Proposed thing body.")
        sec = preflight.decision_state_section(D, "Proposed thing")
        self.assertEqual(sec["status"], "fail")
        self.assertIn("not_resolved_unique", sec["reason"])

    def test_decision_state_alias_conflict(self):
        D = self.fx.decisions
        self.fx.record("0001-a.md", title="First", sources="src/a.py", extra="- Aliases: zeta-codename\n", body="One.")
        self.fx.record("0002-b.md", num="0002", title="Second", sources="src/b.py",
                       extra="- Aliases: zeta-codename\n", body="Two.")
        sec = preflight.decision_state_section(D, "zeta-codename")
        self.assertEqual(sec["status"], "fail")
        self.assertIn("alias_conflict", sec["reason"])

    def test_build_report_and_main(self):
        self.fx.write("src/a.py", "x\n")
        self.fx.record("0001-a.md", title="Clean decision", sources="src/a.py", body="Clean.")
        with mock.patch.object(preflight.shutil, "which", return_value=None):
            rep = preflight.build_preflight_report(self.fx.project, self.fx.decisions, "no-match-scope", 0.0)
        self.assertEqual(rep["schema"], "rosetta-preflight/v1")
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["sections"][0]["status"], "skip")
        with mock.patch.object(preflight.shutil, "which", return_value=None):
            code, stdout, _ = call_main(preflight, ["--project-root", str(self.fx.project),
                                                    "--decisions-root", str(self.fx.decisions),
                                                    "--scope", "no-match-scope", "--min-coverage", "0.0"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["owner"], "rosetta")


class RunsInProcess(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()

    def tearDown(self):
        self.fx.cleanup()

    def runs_main(self, *args):
        return call_main(runs, list(args))

    def test_new_append_index_close_validate(self):
        P = str(self.fx.project)
        code, stdout, _ = self.runs_main("new", "--project-root", P, "--title", "Loop One",
                                         "--runner", "agent", "--trigger", "manual", "--scope", "scope",
                                         "--artifact", "logs/a.txt")
        self.assertEqual(code, 0)
        info = json.loads(stdout)
        self.assertEqual(info["schema"], "rosetta-runs/v1")
        self.assertEqual(info["run_id"], "RUN 0001")
        _, stdout_b, _ = self.runs_main("new", "--project-root", P, "--title", "Loop Two",
                                        "--runner", "agent", "--trigger", "ci", "--scope", "scope2")
        self.assertEqual(json.loads(stdout_b)["run_id"], "RUN 0002")
        self.assertEqual(self.runs_main("append", "--project-root", P, "RUN 0001", "--note", "note",
                                        "--artifact", "logs/b.txt", "--checker-result", "pass",
                                        "--outcome", "success", "--harness-improvement", "better")[0], 0)
        _, idx_out, _ = self.runs_main("index", "--project-root", P)
        by_id = {r["id"]: r for r in json.loads(idx_out)["runs"]}
        self.assertEqual(by_id["RUN 0001"]["checker_result"], "pass")
        self.assertEqual(self.runs_main("close", "--project-root", P, "RUN 0001")[0], 2)  # missing --stop-reason
        self.assertEqual(self.runs_main("close", "--project-root", P, "RUN 0001", "--stop-reason", "done",
                                        "--outcome", "success", "--checker-result", "pass")[0], 0)
        self.assertNotEqual(self.runs_main("append", "--project-root", P, "RUN 0001", "--note", "late")[0], 0)
        code6, v_out, _ = self.runs_main("validate", "--project-root", P)
        self.assertEqual(code6, 0)
        self.assertTrue(json.loads(v_out)["ok"])

    def test_validate_flags_malformed_closed_run(self):
        rundir = self.fx.project / "loop-runs"
        rundir.mkdir()
        (rundir / "0001-bad.md").write_text(
            "# RUN 0001 — Bad\n\n- Status: Closed\n- Date: 2026-06-20\n- Runner: agent\n"
            "- Trigger: manual\n- Scope: scope\n- Budget: \n- Outcome: success\n- Stop reason: \n"
            "- Artifacts: \n- Checker result: pass\n- Harness improvement: \n- Sources: loop-run:0001\n"
        )
        code, out, _ = self.runs_main("validate", "--project-root", str(self.fx.project))
        self.assertEqual(code, 1)
        self.assertIn("closed run missing Stop reason", out)

    def test_find_run_and_set_field_errors(self):
        with self.assertRaises(SystemExit):
            runs.find_run(self.fx.project, "not-an-id")
        with self.assertRaises(SystemExit):
            runs.find_run(self.fx.project, "RUN 9999")
        with self.assertRaises(SystemExit):
            runs.set_field("# RUN 0001 — X\n\n- Status: Open\n", "Nonexistent", "v")

    def test_validate_run_record_branches(self):
        base = {"Status": "Open", "Date": "2026-06-01", "Runner": "agent", "Trigger": "manual",
                "Scope": "s", "Budget": "", "Outcome": "pending", "Stop reason": "",
                "Artifacts": "", "Checker result": "unknown", "Harness improvement": "",
                "Sources": "loop-run:0001"}
        self.assertEqual(runs.validate_run_record({"number": "0001", "fields": dict(base)}), [])
        self.assertEqual(runs.validate_run_record({"error": "boom"}), ["boom"])
        bad_enum = dict(base, Status="Bogus", Trigger="nope", Outcome="???")
        bad_enum["Checker result"] = "x"
        self.assertTrue(any("invalid Status" in e for e in runs.validate_run_record({"number": "0001", "fields": bad_enum})))
        missing = dict(base)
        del missing["Budget"]
        self.assertTrue(any("missing fields" in e
                            for e in runs.validate_run_record({"number": "0001", "fields": missing})))
        extra = dict(base, Bonus="x")
        self.assertTrue(any("extra fields" in e
                            for e in runs.validate_run_record({"number": "0001", "fields": extra})))
        bad_src = dict(base)
        bad_src["Sources"] = "loop-run:9999"
        self.assertTrue(any("invalid Sources" in e
                            for e in runs.validate_run_record({"number": "0001", "fields": bad_src})))


_SIGNAL = {
    "id": "sig-1", "source": "support", "product_area": "onboarding", "platform": "ios",
    "app_version": "1.0", "device_os": "iOS 18",
    "content_summary": "Users cannot complete onboarding",
    "raw_refs": [{"url_or_path": "support/ticket-1"}],
    "customer_impact": "high", "actionability": "immediately_actionable",
    "privacy_class": "internal", "suggested_owner": "PM", "created_at": "2026-06-18T12:30:00Z",
}


class IngestInProcess(unittest.TestCase):
    def setUp(self):
        self.fx = ProjectFixture()
        (self.fx.decisions / "config.json").write_text((ROOT / "decisions" / "config.json").read_text())
        self.src = self.fx.project / "input.json"
        self._argv = sys.argv

    def tearDown(self):
        sys.argv = self._argv
        self.fx.cleanup()

    def run_ingest(self, data, *args, stdin_text=None):
        if stdin_text is not None:
            sys.argv = ["ingest", "--root", str(self.fx.decisions), *args]
            return call_main(ingest, None, stdin_text=stdin_text)
        self.src.write_text(json.dumps(data))
        sys.argv = ["ingest", "--root", str(self.fx.decisions), "--from", str(self.src), *args]
        return call_main(ingest, None)

    def records(self):
        return list(self.fx.decisions.rglob("*.md"))

    def test_valid_signal_writes_pdr(self):
        code, _, _ = self.run_ingest([dict(_SIGNAL)])
        self.assertEqual(code, 0)
        pdrs = list((self.fx.decisions / "product-decisions").glob("*.md"))
        self.assertEqual(len(pdrs), 1)
        text = pdrs[0].read_text()
        self.assertIn("- Status: Proposed", text)
        self.assertIn("`signal:sig-1`", text)

    def test_signal_validation_errors_block_writes(self):
        bad = dict(_SIGNAL)
        del bad["id"]
        code, _, _ = self.run_ingest([bad], "--schema", "signals")
        self.assertNotEqual(code, 0)
        self.assertEqual(self.records(), [])

    def test_sensitive_requires_redaction(self):
        sensitive = dict(_SIGNAL, privacy_class="sensitive",
                         content_summary="email user@example.com",
                         raw_refs=[{"url_or_path": "https://secret.example/replay"}])
        self.assertNotEqual(self.run_ingest([sensitive])[0], 0)
        self.assertNotEqual(self.run_ingest([sensitive], "--allow-sensitive")[0], 0)
        code, _, _ = self.run_ingest([dict(sensitive, redacted=True)], "--allow-sensitive")
        self.assertEqual(code, 0)
        text = self.records()[0].read_text()
        self.assertIn("[redacted: sensitive signal]", text)
        self.assertNotIn("user@example.com", text)

    def test_decisions_skip_and_unknown_type(self):
        data = [
            {"type": "bdr", "title": "Adopt usage pricing", "decider": "T", "date": "2026-06-02",
             "source": "circleback · m-1 · 2026-06-02", "context": "ctx",
             "decision": "Move to usage pricing.", "why": "value"},
            {"type": "adr", "title": "Use a job queue", "source": "slack · e/1 · 2026-06-03"},
            {"source": "slack · z/9 · 2026-06-04"},  # no title -> skipped, not fatal
        ]
        code, _, _ = self.run_ingest(data)
        self.assertEqual(code, 0)
        self.assertEqual(len(list((self.fx.decisions / "business-decisions").glob("*.md"))), 1)
        self.assertEqual(len(list((self.fx.decisions / "architecture-decisions").glob("*.md"))), 1)
        self.assertNotEqual(self.run_ingest([{"type": "zzz", "title": "Bad type"}])[0], 0)

    def test_stdin_input(self):
        code, _, _ = self.run_ingest(None, stdin_text=json.dumps([dict(_SIGNAL, id="sig-2")]))
        self.assertEqual(code, 0)
        self.assertTrue(any("signal:sig-2" in p.read_text() for p in self.records()))


class LoopExtraCoverage(unittest.TestCase):
    """Targeted branch coverage for loop-module helpers not reached by the happy-path suites."""

    def setUp(self):
        self.fx = ProjectFixture()

    def tearDown(self):
        self.fx.cleanup()

    def test_gates_artifact_target_and_diff_edges(self):
        P = self.fx.project
        self.assertIsNone(gates.artifact_target(P, "note:foo"))          # non-artifact prefix
        self.assertIsNone(gates.artifact_target(P, "screenshot:   "))    # empty ref
        self.assertIsNone(gates.artifact_target(P, "screenshot:/abs/x.png"))  # absolute
        self.assertIsNone(gates.artifact_target(P, "video:../up.png"))   # traversal
        self.assertIsNotNone(gates.artifact_target(P, "screenshot:a/b.png"))
        self.assertTrue(gates.is_ui_path("x/App.tsx"))
        self.assertFalse(gates.is_ui_path("x/notes.md"))
        self.assertEqual(gates.parse_diff_paths("diff --git onlythree\n+++ /dev/null\n--- a/keep.py\n"), ["keep.py"])
        self.assertEqual(gates.parse_diff_paths("\n/dev/null\nkeep2.py\n"), ["keep2.py"])

    def test_gates_change_id_required_branches(self):
        self.fx.write("src/App.tsx", "x\n")
        self.fx.write("src/payments/Pay.tsx", "x\n")
        self.fx.record("0001-gate.md", sources="src/payments/Pay.tsx",
                       extra="- Human gated paths: src/payments/**\n")
        report = gates.build_gates_report(self.fx.project, self.fx.decisions, 1.0,
                                          changed_paths=["src/App.tsx", "src/payments/Pay.tsx"], change_id=None)
        bg = {g["gate"]: g for g in report["gates"]}
        self.assertEqual(bg["denylist"]["reason"], "change_id_required_for_human_gated_paths")
        self.assertEqual(bg["evidence_presence"]["reason"], "change_id_required_for_ui_evidence")

    def test_harness_render_missing_sections(self):
        schema = "rosetta-harness-export/v1"
        targets, warnings = harness.build_targets({"schema": schema}, self.fx.project)
        self.assertEqual([t["path"] for t in targets], ["ARCHITECTURE.md", "docs/MOBILE.md"])
        self.assertEqual(warnings, [])
        self.assertIn("[confirm]", targets[0]["content"])
        targets2, _ = harness.build_targets(
            {"schema": schema, "domains": [{"slug": "pay", "title": "Pay", "summary": "S",
                                            "paths": ["src/pay"], "decisions": ["d"]}]}, self.fx.project)
        self.assertEqual(targets2[-1]["path"], "domains/pay/README.md")

    def test_preflight_out_file_and_gates_fail(self):
        self.fx.write("src/App.tsx", "x\n")
        self.fx.record("0001-ui.md", title="UI", sources="src/App.tsx", body="UI flow.")
        out = self.fx.project / "pf.json"
        with mock.patch.object(preflight.shutil, "which", return_value=None):
            code, _, _ = call_main(preflight, ["--project-root", str(self.fx.project),
                                               "--decisions-root", str(self.fx.decisions), "--scope", "UI",
                                               "--min-coverage", "1.0", "--changed-path", "src/App.tsx",
                                               "--change-id", "c1", "--out", str(out)])
        report = json.loads(out.read_text())
        self.assertEqual(report["sections"][2]["status"], "fail")  # UI change without evidence artifact
        self.assertEqual(code, 1)

    def test_runs_parse_and_helper_edges(self):
        rundir = self.fx.project / "loop-runs"
        rundir.mkdir()
        (rundir / "0001-empty.md").write_text("")
        self.assertEqual(runs.parse_run(rundir / "0001-empty.md")["error"], "missing_h1")
        (rundir / "0002-bad.md").write_text("# Not a run\n")
        self.assertEqual(runs.parse_run(rundir / "0002-bad.md")["error"], "malformed_h1")
        (rundir / "0003-fm.md").write_text("# RUN 0003 — X\n\nnot a field line\n")
        self.assertTrue(runs.parse_run(rundir / "0003-fm.md")["error"].startswith("malformed_frontmatter_line"))
        _, idx_out, _ = call_main(runs, ["index", "--project-root", str(self.fx.project)])
        self.assertTrue(any("error" in r for r in json.loads(idx_out)["runs"]))
        with self.assertRaises(Exception):
            runs.nonblank("   ")
        self.assertEqual(runs.nonblank("ok"), "ok")
        self.assertIn("## Log", runs.append_log("# RUN 0001 — X\n\n- Status: Open\n", "note"))
        self.assertEqual(runs.scan_max_run(self.fx.project / "nope-dir"), 0)


if __name__ == "__main__":
    unittest.main()
