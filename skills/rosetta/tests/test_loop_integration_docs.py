import unittest
from pathlib import Path

from tests._loop_helpers import ROOT

BOUNDARY = "Rosetta's deterministic CLI is local and does not call external APIs except `rosetta preflight --allow-ra1-github`, which delegates GitHub-dependent checks to RA1. Agent-run external-source collection for ADR 0012 is outside the deterministic CLI, opt-in, may use authenticated MCP/network tools, and may only feed `rosetta ingest` records as `Status: Proposed` drafts pending human confirmation. Rosetta is read-only against transcript stores and product source by default; default writes are limited to `.agents/**`, `decisions/**`, and `loop-runs/**`, plus the allowlisted harness docs only under explicit `harness export --apply`. Rosetta records, cites, and checks evidence; it never runs product builds/tests/deploys, asserts behavior, schedules loops, merges/pushes, or grades autonomy."


class LoopIntegrationDocsTests(unittest.TestCase):
    def test_boundary_language_is_public(self):
        paths = [
            ROOT.parents[1] / "README.md",
            ROOT / "SKILL.md",
            ROOT / "docs" / "PLAN-loop-integration.md",
            ROOT / "docs" / "cli.md",
            ROOT / "references" / "loop-integration.md",
            ROOT / "commands" / "rosetta-preflight.md",
        ]
        for path in paths:
            self.assertIn(BOUNDARY, path.read_text(), str(path))

    def test_docs_do_not_claim_external_execution_or_grading(self):
        docs = [ROOT.parents[1] / "README.md"]
        docs.extend((ROOT / "docs").glob("*.md"))
        docs.extend((ROOT / "references").glob("*.md"))
        docs.extend((ROOT / "commands").glob("*.md"))
        forbidden = ["behavioral verification", "simulator success", "skill execution",
                     "autonomy clearance", "L0 grading", "L1 grading", "L2 grading", "L3 grading"]
        for path in docs:
            text = path.read_text().lower()
            for phrase in forbidden:
                self.assertNotIn(phrase.lower(), text, f"{phrase} in {path}")

    def test_new_docs_exist(self):
        self.assertTrue((ROOT / "references" / "loop-integration.md").exists())
        self.assertTrue((ROOT / "commands" / "rosetta-preflight.md").exists())
        self.assertIn("rosetta-preflight", (ROOT / "commands" / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
