import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

from tests._loop_helpers import ROOT


class CLIDispatchTests(unittest.TestCase):
    def test_dispatch_parity_for_loop_commands(self):
        spec = importlib.util.spec_from_file_location("rosetta_cli", ROOT / "rosetta_cli.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        expected = {
            "gates": ["gates.py"],
            "runs": ["runs.py"],
            "harness": ["harness.py"],
            "drift": ["drift.py"],
            "preflight": ["preflight.py"],
        }
        for name, target in expected.items():
            self.assertEqual(mod._DISPATCH[name], target)

        text = (ROOT / "scripts" / "rosetta").read_text()
        for const, script in [("GATES", "gates.py"), ("RUNS", "runs.py"), ("HARNESS", "harness.py"),
                              ("DRIFT", "drift.py"), ("PREFLIGHT", "preflight.py")]:
            self.assertIn(f'{const} = SCRIPTS / "{script}"', text)

    def test_loop_namespace_is_unknown(self):
        proc = subprocess.run([sys.executable, "scripts/rosetta", "loop", "preflight"], cwd=ROOT,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown command", proc.stderr)


if __name__ == "__main__":
    unittest.main()
