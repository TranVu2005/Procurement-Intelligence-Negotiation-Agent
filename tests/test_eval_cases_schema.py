import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "tests" / "eval_set"

VALID_CATEGORIES = {
    "happy_path", "missing_info", "conflict", "tool_failure", "adversarial", "multi_turn",
}
VALID_STATUS = {"success", "graceful_fail", "needs_confirmation", "needs_input", "out_of_scope"}
VALID_TOOLS = {"search_suppliers", "get_supplier_detail", "compare_price", "confirm_order"}


def load_all_cases():
    cases = []
    for path in sorted(EVAL_DIR.glob("cases*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append((path.name, json.loads(line)))
    return cases


class CaseSchemaTests(unittest.TestCase):
    def test_c_cases_file_exists_with_both_categories(self) -> None:
        cases = [json.loads(l) for l in
                 (EVAL_DIR / "cases_c.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        categories = {c["category"] for c in cases}
        self.assertIn("tool_failure", categories)
        self.assertIn("adversarial", categories)
        self.assertGreaterEqual(len(cases), 10)

    def test_every_case_has_the_agreed_keys(self) -> None:
        for filename, case in load_all_cases():
            if "oracle" not in case:
                continue  # cases.jsonl cu cua A, se doi sang tests/ o Dot 4
            with self.subTest(case=f"{filename}:{case.get('id')}"):
                self.assertIn("id", case)
                self.assertIn(case["category"], VALID_CATEGORIES)
                self.assertIsInstance(case["turns"], list)
                self.assertTrue(case["turns"])
                self.assertIn(case["oracle"]["expect_status"], VALID_STATUS)

    def test_tool_names_in_oracles_actually_exist(self) -> None:
        for filename, case in load_all_cases():
            oracle = case.get("oracle")
            if not oracle:
                continue
            for key in ("must_call_tools", "must_not_call_tools"):
                for tool in oracle.get(key) or []:
                    with self.subTest(case=f"{filename}:{case['id']}", tool=tool):
                        self.assertIn(tool, VALID_TOOLS)

    def test_every_injected_case_names_a_known_error_type(self) -> None:
        from src.nodes.tool_exec import INJECTABLE_ERROR_TYPES
        for filename, case in load_all_cases():
            for tool, error_type in (case.get("inject") or {}).items():
                with self.subTest(case=f"{filename}:{case['id']}"):
                    self.assertIn(tool, VALID_TOOLS)
                    self.assertIn(error_type, INJECTABLE_ERROR_TYPES)

    def test_case_ids_are_unique_across_files(self) -> None:
        ids = [case["id"] for _f, case in load_all_cases()]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
