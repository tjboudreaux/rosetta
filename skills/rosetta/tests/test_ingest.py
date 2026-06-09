#!/usr/bin/env python3
"""Tests for `ingest.py` — external decisions (meetings/Slack via MCP) -> Proposed records."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
INGEST = SKILL / "scripts" / "ingest.py"
CONFIG = SKILL / "decisions" / "config.json"


class Ingest(unittest.TestCase):
    def test_scaffolds_proposed_records_from_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "decisions"
            root.mkdir()
            (root / "config.json").write_text(CONFIG.read_text())
            data = [
                {"type": "bdr", "title": "Adopt usage based pricing", "decider": "Travis",
                 "date": "2026-06-02", "source": "circleback · mtg-7f3a · 2026-06-02",
                 "context": "Raised in the pricing meeting.", "decision": "Move to usage-based pricing.",
                 "why": "Aligns cost with delivered value."},
                {"type": "adr", "title": "Use a Postgres job queue",
                 "source": "slack · eng/123 · 2026-06-03"},
            ]
            p = subprocess.run([sys.executable, str(INGEST), "--root", str(root)],
                               input=json.dumps(data), text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)

            bdrs = list((root / "business-decisions").glob("*.md"))
            adrs = list((root / "architecture-decisions").glob("*.md"))
            self.assertEqual(len(bdrs), 1, "one BDR scaffolded")
            self.assertEqual(len(adrs), 1, "one ADR scaffolded")

            bdr = bdrs[0].read_text()
            self.assertIn("# BDR 0001 — Adopt usage based pricing", bdr)
            self.assertIn("- Status: Proposed", bdr)                 # never auto-Accepted
            self.assertIn("circleback · mtg-7f3a · 2026-06-02", bdr)  # provenance preserved
            self.assertIn("usage-based pricing", bdr)                # body draft carried through

    def test_validates_after_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "decisions"
            root.mkdir()
            (root / "config.json").write_text(CONFIG.read_text())
            subprocess.run([sys.executable, str(INGEST), "--root", str(root)],
                           input=json.dumps([{"type": "pdr", "title": "Ship weekly",
                                              "source": "slack · ops/9 · 2026-06-01"}]),
                           text=True, capture_output=True, check=True)
            v = subprocess.run([sys.executable, str(SKILL / "scripts" / "decisions.py"),
                                "--root", str(root), "validate"], capture_output=True, text=True)
            self.assertEqual(v.returncode, 0, v.stdout + v.stderr)   # ingested records are well-formed


if __name__ == "__main__":
    unittest.main(verbosity=2)
