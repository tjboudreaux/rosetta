#!/usr/bin/env python3
"""Resolver edge-branch coverage: with an EMPTY $HOME every agent resolver must return zero units
without crashing (exercising the 'store absent / no match' branches), and with the full fixture the
include-subdirs and discovery paths must work. Pure stdlib.

Run: python3 -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE / "fixtures"))
import collect          # noqa: E402
import build            # noqa: E402


class EmptyHomeResolvers(unittest.TestCase):
    """No stores on disk -> every resolver yields no units, gracefully."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["ROSETTA_HOME"] = self._tmp.name
        self.project = str(Path(self._tmp.name) / "nope" / "proj")

    def tearDown(self):
        os.environ.pop("ROSETTA_HOME", None)
        self._tmp.cleanup()

    def test_all_resolvers_empty(self):
        for agent, spec in collect.AGENTS.items():
            for subdirs in (False, True):
                res = spec["resolver"](self.project, subdirs)
                self.assertEqual(res["units"], [], f"{agent} (subdirs={subdirs}) should yield no units")
                self.assertIn("match_mode", res)
                self.assertIn("extra", res)

    def test_discovery_sweep_empty(self):
        # no agent-like dirs -> nothing flagged
        self.assertEqual(collect.discovery_sweep(), [])

    def test_discover_all_projects_empty(self):
        disc = collect.discover_all_projects()
        self.assertEqual(disc["projects"], {})


class FullFixtureResolvers(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.project = build.build(self.home)
        os.environ["ROSETTA_HOME"] = str(self.home)

    def tearDown(self):
        os.environ.pop("ROSETTA_HOME", None)
        self._tmp.cleanup()

    def test_discover_all_projects_finds_fixture(self):
        disc = collect.discover_all_projects()
        self.assertTrue(any(self.project in cwd for cwd in disc["projects"]))
        # discovery sweep flags the planted unknown/hint store, not the random one
        flagged = " ".join(collect.discovery_sweep())
        self.assertIn("windsurfx", flagged)
        self.assertNotIn("totallyrandom", flagged)

    def test_include_subdirs_matches_child(self):
        # a claude session whose cwd is a CHILD of the project is only matched with include_subdirs
        child = str(Path(self.project) / "packages" / "api")
        sess = (self.home / ".claude" / "projects" / collect.enc_path(child) / "c.jsonl")
        sess.parent.mkdir(parents=True, exist_ok=True)
        sess.write_text('{"type":"user","cwd":"%s","timestamp":"2026-06-08T00:00:00Z",'
                        '"message":{"role":"user","content":"hi"}}\n' % child)
        exact = collect.resolve_claude(self.project, False)
        withsub = collect.resolve_claude(self.project, True)
        self.assertEqual(len(withsub["units"]) - len(exact["units"]), 1)


class DiscoveryEdges(unittest.TestCase):
    """Build a $HOME hitting discover_all_projects' edge branches: empty dirs, codex-without-cwd,
    malformed gemini projects.json, opencode with an unreadable message, and a claude-agent audit.jsonl."""
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        os.environ["ROSETTA_HOME"] = str(self.home)

    def tearDown(self):
        os.environ.pop("ROSETTA_HOME", None)
        self._tmp.cleanup()

    def _w(self, rel, text):
        p = self.home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def test_edge_branches(self):
        proj = "/work/app"
        # claude dir with NO jsonl -> skipped (continue)
        (self.home / ".claude" / "projects" / "empty-dir").mkdir(parents=True)
        # codex rollout with no cwd anywhere -> codex_sessions_without_cwd
        self._w(".codex/sessions/2026/06/08/rollout-x.jsonl",
                __import__("json").dumps({"type": "response_item",
                                          "payload": {"type": "message", "role": "user",
                                                      "content": [{"type": "input_text", "text": "hi"}]}}))
        # gemini with a malformed projects.json + a chats-less dir
        self._w(".gemini/projects.json", "{ not json")
        (self.home / ".gemini" / "tmp" / "noschats").mkdir(parents=True)
        # opencode message whose json is unreadable (cwd probe exception -> falls back)
        self._w(".local/share/opencode/storage/message/ses_x/msg.json", "{ broken")
        # claude-agent audit.jsonl must be skipped; a real session is counted
        self._w("Library/Application Support/Claude/local-agent-mode-sessions/w/audit.jsonl", "{}")
        self._w("Library/Application Support/Claude/local-agent-mode-sessions/w/s.jsonl",
                __import__("json").dumps({"type": "user", "cwd": proj, "timestamp": "2026-06-08T00:00:00Z",
                                          "message": {"role": "user", "content": "hi"}}))
        disc = collect.discover_all_projects()
        self.assertGreaterEqual(disc["codex_sessions_without_cwd"], 1)
        # the claude-agent real session was attributed to its cwd
        self.assertTrue(any("/work/app" in cwd for cwd in disc["projects"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
