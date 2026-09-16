import unittest

from src.reasoning.scoring import diagnose, verify_output


REQ = {
    "hard_constraints": {
        "product_type": "ghế văn phòng",
        "quantity": 20,
        "budget_max": 40_000_000,
        "delivery_deadline_days": 10,
    }
}


def candidate(**overrides) -> dict:
    result = {
        "MaNCC": "NCC001",
        "LoaiSanPham": "ghế văn phòng",
        "MOQ": 5,
        "TonKho": 71,
        "ThoiGianGiao": 6,
        "BaoHanh": 36,
        "DiemUyTin": 4.3,
        "unit_price": 1_600_000,
        "total_price": 32_000_000,
    }
    result.update(overrides)
    return result


class DiagnosisTests(unittest.TestCase):
    def test_diagnose_returns_primary_code_and_affected_suppliers(self) -> None:
        rejected = [
            {"supplier_id": "A", "violations": [{"code": "delivery_deadline_unmet"}]},
            {"supplier_id": "B", "violations": [{"code": "delivery_deadline_unmet"}]},
            {"supplier_id": "C", "violations": [{"code": "budget_exceeded"}]},
        ]

        result = diagnose(rejected)

        self.assertEqual(result["primary_code"], "delivery_deadline_unmet")
        self.assertIn("delivery_deadline_unmet", result["replan_reason"])
        self.assertEqual(result["causes"][0]["affected_suppliers"], 2)

    def test_diagnose_empty_input_is_explicit(self) -> None:
        result = diagnose([])

        self.assertEqual(result["primary_code"], "no_candidate_evidence")


class VerificationTests(unittest.TestCase):
    def test_verified_candidate_has_structured_claims(self) -> None:
        ranked = [candidate()]
        tool_results = [
            {
                "MaNCC": "NCC001",
                "LoaiSanPham": "ghế văn phòng",
                "MOQ": 5,
                "TonKho": 71,
                "ThoiGianGiao": 6,
                "BaoHanh": 36,
                "DiemUyTin": 4.3,
                "nguon_url": "https://example.test/ncc001",
                "nguon_type": "public_listing",
            },
            {"comparisons": [{
                "MaNCC": "NCC001",
                "unit_price": 1_600_000,
                "total_price": 32_000_000,
            }]},
        ]

        verdict = verify_output(ranked, REQ, tool_results)

        self.assertTrue(verdict["passed"])
        self.assertGreater(len(verdict["claims"]), 0)
        self.assertTrue(all(claim["supported"] for claim in verdict["claims"]))
        self.assertTrue(all(claim["evidence"]["nguon_url"] for claim in verdict["claims"]))

    def test_missing_citation_blocks_output_in_strict_mode(self) -> None:
        ranked = [candidate()]
        tool_results = [candidate()]

        verdict = verify_output(ranked, REQ, tool_results)

        self.assertFalse(verdict["passed"])
        self.assertTrue(any(item["code"] == "missing_citation" for item in verdict["violations"]))

    def test_inconsistent_total_is_detected(self) -> None:
        bad = candidate(total_price=31_000_000)

        verdict = verify_output([bad], REQ, [dict(bad, nguon_url="https://example.test")])

        self.assertFalse(verdict["passed"])
        self.assertTrue(any(
            item["code"] == "total_price_inconsistent"
            for item in verdict["violations"]
        ))

    def test_hard_constraint_violation_blocks_output(self) -> None:
        late = candidate(ThoiGianGiao=15)

        verdict = verify_output(
            [late],
            REQ,
            [dict(late, nguon_url="https://example.test")],
        )

        self.assertFalse(verdict["passed"])
        self.assertTrue(any(
            item["code"] == "delivery_deadline_unmet"
            for item in verdict["violations"]
        ))

    def test_empty_ranking_fails_gracefully(self) -> None:
        verdict = verify_output([], REQ, [])

        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["violations"][0]["code"], "no_ranked_candidate")


if __name__ == "__main__":
    unittest.main()
