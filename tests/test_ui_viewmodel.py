import unittest

from src.ui_viewmodel import format_currency, run_metrics, safe_source_url, supplier_view_models


class FormatTests(unittest.TestCase):
    def test_missing_currency_is_explicit_not_zero(self):
        self.assertEqual(format_currency(None), "Chưa có dữ liệu")

    def test_currency_formats_vnd(self):
        self.assertEqual(format_currency(12_500_000), "12,500,000 ₫")

    def test_only_http_source_urls_are_exposed(self):
        self.assertEqual(safe_source_url("https://example.com/product"), "https://example.com/product")
        self.assertIsNone(safe_source_url("javascript:alert(1)"))
        self.assertIsNone(safe_source_url(None))


class SupplierViewModelTests(unittest.TestCase):
    def test_ranking_source_and_simulated_fields_are_preserved(self):
        cards = supplier_view_models([
            {
                "MaNCC": "NCC01",
                "TenNCC": "Nha cung cap A",
                "Gia": 1_000_000,
                "total_price": 10_000_000,
                "ThoiGianGiao": 7,
                "DiemUyTin": 4.5,
                "leverage_score": 88.2,
                "nguon_url": "https://example.com/a",
                "nguon_type": "website",
                "simulated_fields": ["TonKho", "DiemUyTin"],
            }
        ])
        self.assertEqual(cards[0]["rank"], 1)
        self.assertEqual(cards[0]["supplier_id"], "NCC01")
        self.assertEqual(cards[0]["source_url"], "https://example.com/a")
        self.assertEqual(cards[0]["simulated_fields"], ["TonKho", "DiemUyTin"])
        self.assertEqual(cards[0]["data_label"], "Có trường mô phỏng")

    def test_null_optional_values_do_not_crash_or_become_fake_numbers(self):
        card = supplier_view_models([{"MaNCC": "NCC02", "TenNCC": "B"}])[0]
        self.assertEqual(card["unit_price"], "Chưa có dữ liệu")
        self.assertEqual(card["delivery"], "Chưa có dữ liệu")
        self.assertEqual(card["trust"], "Chưa có dữ liệu")
        self.assertIsNone(card["source_url"])


class MetricsTests(unittest.TestCase):
    def test_metrics_are_derived_from_final_state(self):
        metrics = run_metrics({
            "status": "needs_confirmation",
            "intent": "search_new",
            "llm_calls": 2,
            "tool_results": [{}, {}, {}],
            "replan_count": 1,
            "latency_ms": 123.4,
            "verdict": {"passed": True},
            "trace_id": "trace-1",
        })
        self.assertEqual(metrics["tool_calls"], 3)
        self.assertTrue(metrics["verifier_passed"])
        self.assertEqual(metrics["trace_id"], "trace-1")


if __name__ == "__main__":
    unittest.main()
