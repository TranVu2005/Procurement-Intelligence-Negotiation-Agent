import unittest

from src.graph import route_after_filter, route_after_verify, route_intent
from src.graph_state import MAX_REPLAN, new_state


def state_with(**kwargs):
    return {**new_state("x"), **kwargs}


class RouteIntentTests(unittest.TestCase):
    def test_each_intent_maps_to_its_entry_node(self) -> None:
        cases = {
            "search_new": "plan",
            "compare_specific": "tool_compare",
            "supplier_detail": "tool_detail",
            "out_of_scope": "respond_limits",
        }
        for intent, expected in cases.items():
            with self.subTest(intent=intent):
                self.assertEqual(route_intent(state_with(intent=intent)), expected)

    def test_unknown_intent_falls_back_to_respond_limits(self) -> None:
        # Khong duoc doan bua khi A tra ve intent la -> neu gioi han he thong
        self.assertEqual(route_intent(state_with(intent="dat_ve_may_bay")), "respond_limits")

    def test_missing_intent_falls_back_to_respond_limits(self) -> None:
        self.assertEqual(route_intent(new_state("x")), "respond_limits")


class RouteAfterFilterTests(unittest.TestCase):
    def test_candidates_present_goes_to_scoring(self) -> None:
        self.assertEqual(route_after_filter(state_with(candidates=[{"MaNCC": "NCC001"}])), "score_rank")

    def test_empty_candidates_under_cap_goes_to_diagnose(self) -> None:
        self.assertEqual(route_after_filter(state_with(candidates=[], replan_count=0)), "diagnose")
        self.assertEqual(
            route_after_filter(state_with(candidates=[], replan_count=MAX_REPLAN - 1)), "diagnose"
        )

    def test_empty_candidates_at_cap_goes_to_graceful_fail(self) -> None:
        self.assertEqual(
            route_after_filter(state_with(candidates=[], replan_count=MAX_REPLAN)), "graceful_fail"
        )

    def test_needs_input_short_circuits_to_graceful_fail(self) -> None:
        # Thieu thong tin nguoi dung phai cung cap -> re-plan khong cuu duoc
        self.assertEqual(
            route_after_filter(state_with(candidates=[], status="needs_input", replan_count=0)),
            "graceful_fail",
        )


class RouteAfterVerifyTests(unittest.TestCase):
    def test_passed_verdict_goes_to_respond(self) -> None:
        verdict = {"passed": True, "violations": [], "claims": []}
        self.assertEqual(route_after_verify(state_with(verdict=verdict)), "respond")

    def test_failed_verdict_under_cap_goes_to_diagnose(self) -> None:
        verdict = {"passed": False, "violations": [{"code": "x", "detail": "y"}], "claims": []}
        self.assertEqual(route_after_verify(state_with(verdict=verdict, replan_count=0)), "diagnose")

    def test_failed_verdict_at_cap_goes_to_graceful_fail(self) -> None:
        verdict = {"passed": False, "violations": [], "claims": []}
        self.assertEqual(
            route_after_verify(state_with(verdict=verdict, replan_count=MAX_REPLAN)), "graceful_fail"
        )

    def test_missing_verdict_is_treated_as_failed(self) -> None:
        self.assertEqual(route_after_verify(state_with(replan_count=MAX_REPLAN)), "graceful_fail")


if __name__ == "__main__":
    unittest.main()
