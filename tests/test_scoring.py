import unittest

from src.reasoning.scoring import (
    ScoringError,
    evaluate_candidates,
    detect_evidence_conflicts,
    filter_hard_constraints,
    leverage_score,
    rank_suppliers,
    score_breakdown,
)


STATE = {
    "session_id": "sess_test",
    "hard_constraints": {
        "product_type": "ghế văn phòng",
        "quantity": 20,
        "budget_max": 40_000_000,
        "delivery_deadline_days": 10,
    },
    "soft_constraints": {
        "material_preference": "vai_boc",
        "region_preference": "Ha Noi",
        "min_trust_score": 4.0,
    },
}


def supplier(supplier_id: str = "NCC001", **overrides) -> dict:
    record = {
        "MaNCC": supplier_id,
        "TenNCC": "Nội thất mẫu",
        "LoaiSanPham": "ghế văn phòng",
        "ChatLieu": "vai_boc",
        "Gia": 1_500_000,
        "MOQ": 10,
        "TonKho": 100,
        "ThoiGianGiao": 7,
        "BaoHanh": 24,
        "DiemUyTin": 4.5,
        "KhuVuc": "Ha Noi",
        "total_price": 30_000_000,
    }
    record.update(overrides)
    return record


class ScoringTests(unittest.TestCase):
    def test_score_is_reproducible_and_has_five_components(self) -> None:
        record = supplier()

        first = leverage_score(record, STATE["hard_constraints"])
        second = leverage_score(record, STATE["hard_constraints"])

        self.assertEqual(first, second)
        self.assertGreaterEqual(first, 0)
        self.assertLessEqual(first, 100)
        self.assertEqual(
            set(score_breakdown(record, STATE["hard_constraints"])),
            {"price", "moq", "delivery", "warranty", "trust"},
        )

    def test_missing_trust_is_not_invented(self) -> None:
        record = supplier(DiemUyTin=None)

        breakdown = score_breakdown(record, STATE["hard_constraints"])
        ranked = rank_suppliers([record], STATE)

        self.assertIsNone(breakdown["trust"])
        self.assertTrue(any(
            "Chưa có dữ liệu điểm uy tín" in text
            for text in ranked[0]["explanation"]["trade_offs"]
        ))

    def test_hard_filter_reports_all_reasons(self) -> None:
        record = supplier(MOQ=100, TonKho=5, ThoiGianGiao=20, total_price=90_000_000)

        result = filter_hard_constraints([record], STATE["hard_constraints"])
        codes = {item["code"] for item in result["rejected"][0]["violations"]}

        self.assertEqual(result["eligible"], [])
        self.assertEqual(
            codes,
            {"quantity_below_moq", "stock_below_quantity", "budget_exceeded", "delivery_deadline_unmet"},
        )

    def test_missing_price_evidence_is_rejected(self) -> None:
        record = supplier()
        del record["total_price"]

        result = filter_hard_constraints([record], STATE["hard_constraints"])

        self.assertEqual(
            result["rejected"][0]["violations"][0]["code"],
            "missing_price_evidence",
        )

    def test_rank_is_best_first_and_explains_soft_tradeoff(self) -> None:
        cheaper = supplier("NCC_A", total_price=20_000_000)
        expensive = supplier(
            "NCC_B",
            total_price=35_000_000,
            ChatLieu="da_that",
            KhuVuc="Da Nang",
            DiemUyTin=3.5,
        )

        ranked = rank_suppliers([expensive, cheaper], STATE)

        self.assertEqual(ranked[0]["MaNCC"], "NCC_A")
        self.assertEqual(len(ranked[1]["explanation"]["trade_offs"]), 3)

    def test_evaluate_candidates_uses_price_tool_output(self) -> None:
        detail = supplier()
        detail.pop("total_price")
        price_result = {
            "comparisons": [{
                "MaNCC": "NCC001",
                "unit_price": 1_425_000,
                "discount_applied": "5%",
                "total_price": 28_500_000,
                "meets_moq": True,
            }]
        }

        result = evaluate_candidates(STATE, [detail], price_result)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["recommended_supplier_id"], "NCC001")
        self.assertEqual(result["ranked_suppliers"][0]["total_price"], 28_500_000)

    def test_scoring_requires_real_price_evidence(self) -> None:
        record = supplier()
        del record["total_price"]

        with self.assertRaisesRegex(ScoringError, "total_price"):
            leverage_score(record, STATE["hard_constraints"])

    def test_conflicting_source_records_block_recommendation(self) -> None:
        first = supplier("EDGE004A", TenNCC="Noi That Viet Tin", LoaiSanPham="sofa", Gia=15_000_000)
        second = supplier("EDGE004B", TenNCC="Noi That Viet Tin", LoaiSanPham="sofa", Gia=19_800_000)

        conflicts = detect_evidence_conflicts([first, second])

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["differing_fields"]["Gia"], [15_000_000, 19_800_000])


if __name__ == "__main__":
    unittest.main()
