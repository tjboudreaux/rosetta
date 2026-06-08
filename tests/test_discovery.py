#!/usr/bin/env python3
"""Discovery tests — every supported agent's resolver+parser is exercised against a synthetic
fixture $HOME (tests/fixtures/build.py), plus the discovery sweep and the path encoders.

Run: python3 -m unittest discover -s tests   (pure stdlib, no deps)
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


class DiscoveryFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.home = cls._tmp.name
        cls.project = build.build(cls.home)
        os.environ["ROSETTA_HOME"] = cls.home

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("ROSETTA_HOME", None)
        cls._tmp.cleanup()

    def _run(self, agent):
        spec = collect.AGENTS[agent]
        res = spec["resolver"](self.project, False)
        msgs = []
        for unit in res["units"]:
            msgs += spec["parser"](unit, 4000)["messages"]
        return res, msgs

    def test_every_agent_discovers_the_session(self):
        """Each agent's resolver finds the fixture session and its parser yields both roles."""
        failures = []
        for agent in collect.AGENTS:
            with self.subTest(agent=agent):
                res, msgs = self._run(agent)
                roles = {m["role"] for m in msgs}
                texts = " ".join(m["text"] for m in msgs)
                if not (len(res["units"]) >= 1 and len(msgs) >= 2
                        and roles == {"user", "assistant"} and "hello from demo" in texts
                        and "hi back" in texts):
                    failures.append(f"{agent}: units={len(res['units'])} msgs={len(msgs)} roles={roles}")
        self.assertEqual(failures, [], "agents that failed discovery:\n" + "\n".join(failures))

    def test_hermes_excludes_request_dumps(self):
        res, _ = self._run("hermes")
        self.assertEqual(len(res["units"]), 1, "should match the session_*.json, not the request_dump")
        self.assertEqual(res["extra"].get("request_dumps_excluded"), 1)

    def test_gemini_expands_set_messages(self):
        _, msgs = self._run("gemini")
        # seed (in $set.messages) + the individual gemini line = both turns
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])

    def test_opencode_orders_by_time(self):
        _, msgs = self._run("opencode")
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])

    def test_sweep_classifies_known_excluded_unknown(self):
        sweep = collect.discovery_sweep()
        names = {Path(p).name for p in sweep}
        self.assertNotIn(".gemini", names, "supported store must not be flagged unknown")
        self.assertNotIn(".amplify", names, "non-agent must be excluded")
        self.assertNotIn(".totallyrandom", names, "non-hint dir must not be flagged")
        self.assertIn(".windsurfx", names, "hint-matching unknown agent must be flagged")


class Encoding(unittest.TestCase):
    def test_enc_path_collapses_dotdirs(self):
        self.assertEqual(collect.enc_path("/Users/tjboudreaux/.claude/skills/rosetta"),
                         "-Users-tjboudreaux--claude-skills-rosetta")
        self.assertEqual(collect.enc_path("/Users/tjboudreaux/Sandbox"),
                         "-Users-tjboudreaux-Sandbox")

    def test_cursor_enc_strips_leading_slash(self):
        self.assertEqual(collect.cursor_enc("/Users/u/Sandbox/x"), "Users-u-Sandbox-x")


class DefaultParserShapes(unittest.TestCase):
    def _parse(self, text, suffix=".jsonl"):
        with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as fh:
            fh.write(text); p = fh.name
        try:
            return collect.collect_session(p, 4000)
        finally:
            os.unlink(p)

    def test_jsonl_and_bare_list_and_object(self):
        jl = self._parse('{"role":"user","content":"a"}\n{"role":"assistant","content":"b"}\n')
        self.assertEqual(jl["kept"], 2)
        bare = self._parse('[{"role":"user","content":"a"},{"role":"assistant","content":"b"}]', ".json")
        self.assertEqual(bare["kept"], 2)
        obj = self._parse('{"messages":[{"role":"user","content":"a"}],"session_start":"2026-06-08T00:00:00Z"}', ".json")
        self.assertEqual(obj["kept"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
