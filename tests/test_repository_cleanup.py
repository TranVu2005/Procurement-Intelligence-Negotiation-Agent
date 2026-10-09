"""Kiem tra cac duong chay sau khi don artifact va live test."""

import contextlib
import importlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate_mock_data as generator
from src.tools.dataset_builder import version_matches


class RepositoryCleanupTests(unittest.TestCase):
    def test_demo_outputs_stay_in_reports(self):
        from scripts import run_demo_scenarios as demo

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            version = root / "src/tools/mock_data/VERSION"
            version.parent.mkdir(parents=True)
            version.write_text("test-version", encoding="utf-8")
            (root / "docs").mkdir()
            with patch.object(demo, "ROOT", root), patch.object(demo, "SCENARIOS", []), \
                    patch.object(demo.sys, "argv", ["run_demo_scenarios.py"]), \
                    patch.object(demo.sys, "stdout"):
                demo.main()
            self.assertTrue((root / "reports" / f"demo_run_{demo.TODAY}.json").is_file())
            self.assertTrue((root / "reports" / f"demo-run-{demo.TODAY}.md").is_file())
            self.assertEqual(list((root / "docs").iterdir()), [])

    def test_dataset_command_writes_only_dataset_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / generator.OUT_PATH).parent.mkdir(parents=True)
            previous = Path.cwd()
            try:
                os.chdir(root)
                with contextlib.redirect_stdout(io.StringIO()):
                    generator.main()
            finally:
                os.chdir(previous)
            self.assertTrue(version_matches(root / generator.OUT_PATH, root / generator.VERSION_PATH))
            self.assertFalse((root / "eval_cases.json").exists())
            self.assertFalse((root / "session_states_sample.json").exists())

    def test_live_modules_use_unittest_and_skip_without_explicit_opt_in(self):
        with patch.dict(os.environ, {"AGENT_LLM": "stub", "RUN_LIVE_TESTS": ""}):
            for name in ("tests.test_gemini_intent_live", "tests.test_gemini_memory_live"):
                with self.subTest(module=name):
                    module = importlib.import_module(name)
                    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
                    self.assertGreater(suite.countTestCases(), 0)
                    result = unittest.TestResult()
                    suite.run(result)
                    self.assertTrue(result.wasSuccessful(), result.errors)
                    self.assertEqual(len(result.skipped), result.testsRun)


if __name__ == "__main__":
    unittest.main()
