import csv
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.tools import dataset_builder as builder
from src.tools import supplier_tools as tools
from src.nodes.respond import respond


def source_row(**values):
    return {**dict.fromkeys(builder.SOURCE_COLUMNS, ""), "supplier_name": "TEST_ONLY",
            "product_name": "TEST_CHAIR", "product_type": "ghế văn phòng", "price": "1000000",
            "unit": "cai", "region": "Ha Noi", "source_url": "https://example.test/test-product",
            "collected_at": "2026-10-01", "collected_by": "TEST", **values}


class StaleTests(unittest.TestCase):
    def test_staleness_in_all_three_tools_is_clock_injectable(self):
        record = {"MaNCC": "TEST", "TenNCC": "TEST_ONLY", "LoaiSanPham": "ghế văn phòng",
                  "Gia": 1000000, "MOQ": 1, "fetched_at": "2026-10-01"}
        for fetched, stale in (("2026-10-01", False), ("2026-09-01", True), (None, True)):
            with self.subTest(fetched=fetched), patch.object(tools, "_load_data", return_value=[{**record, "fetched_at": fetched}]), \
                    patch.object(tools, "_today", return_value=date(2026, 10, 9)):
                results = [tools.search_suppliers("ghế văn phòng")["suppliers"][0],
                           tools.get_supplier_detail("TEST"), tools.compare_price(["TEST"], 10)["comparisons"][0]]
            for result in results:
                self.assertEqual(result["stale"], stale)
                if fetched is None:
                    self.assertEqual(result["stale_reason"], "missing_fetched_at")

    def test_threshold_and_invalid_dates(self):
        with patch.object(tools, "_today", return_value=date(2026, 10, 9)), \
                patch.dict("os.environ", {"DATA_STALE_DAYS": "2"}):
            self.assertTrue(tools._freshness({"fetched_at": "2026-10-01"})["stale"])
            self.assertTrue(tools._freshness({"fetched_at": "bad"})["stale"])

    def test_respond_adds_dated_source_warning_without_an_extra_llm(self):
        class LLM:
            def stream(self, messages):
                from langchain_core.messages import AIMessage
                yield AIMessage(content="Kết quả")
        with patch("src.nodes.respond.get_llm", return_value=LLM()) as factory:
            final = respond({"ranked": [{"MaNCC": "TEST", "stale": True,
                "fetched_at": "2026-09-01", "nguon_url": "https://example.test/test-product"}]})
        self.assertIn("có thể đã thay đổi", final["answer"])
        self.assertIn("2026-09-01", final["answer"])
        self.assertIn("https://example.test/test-product", final["answer"])
        factory.assert_called_once()


class QuoteTests(unittest.TestCase):
    def test_quote_metadata_and_missing_business_fields(self):
        row = source_row(nguon_type="b2b_quote", quote_date="2026-10-01", quote_quantity="50", quote_channel="email")
        record = builder.build_source_records([row])[0]
        self.assertEqual(record["nguon_type"], "b2b_quote")
        self.assertEqual(record["quote_quantity"], 50)
        for field in ("MOQ", "TonKho", "ThoiGianGiao", "BaoHanh", "DiemUyTin"):
            self.assertIn(field, record["simulated_fields"])

    def test_invalid_quotes_rejected(self):
        base = source_row(nguon_type="b2b_quote", quote_date="2026-10-01", quote_quantity="50", quote_channel="zalo")
        for changes in ({"quote_date": "2026-02-30"}, {"quote_quantity": "0"},
                        {"quote_channel": "unknown"}, {"price": ""}, {"seller_email": "personal@example.test"}):
            with self.subTest(changes=changes), self.assertRaises(builder.SourceValidationError):
                builder.build_source_records([{**base, **changes}])

    def test_template_is_skipped_and_does_not_renumber_web_records(self):
        template = Path("src/tools/mock_data/sources/b2b_quotes_template.csv")
        self.assertEqual(builder.read_source_rows([template]), [])
        quote = source_row(nguon_type="b2b_quote", quote_date="2026-10-01", quote_quantity="50", quote_channel="phone")
        records = builder.build_source_records([quote, source_row()])
        self.assertEqual(records[1]["MaNCC"], "SRC001")
        self.assertTrue(records[0]["MaNCC"].startswith("QTE"))

    def test_quote_cannot_be_used_at_another_quantity(self):
        record = builder.to_record(source_row(nguon_type="b2b_quote", quote_date="2026-10-01", quote_quantity="50", quote_channel="phone"), "TEST_QUOTE")
        with patch.object(tools, "_load_data", return_value=[record]):
            result = tools.compare_price(["TEST_QUOTE"], 10)["comparisons"][0]
        self.assertEqual(result["error_type"], "invalid_input")


class RefreshTests(unittest.TestCase):
    def test_dry_run_never_fetches_or_writes(self):
        from scripts import refresh_sources
        with patch.object(refresh_sources.verify_sources, "verify") as fetch:
            result = refresh_sources.refresh(dry_run=True)
        fetch.assert_not_called()
        self.assertTrue(result["dry_run"])

    def test_mocked_fetch_updates_source_and_dataset_version(self):
        from scripts import refresh_sources
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sources"
            source.mkdir()
            path = source / "web.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=builder.SOURCE_COLUMNS)
                writer.writeheader(); writer.writerow(source_row())
            def fake_verify(rows, cache):
                return [{"http_status": 200, "row": 1, "price_status": "price_mismatch",
                         "page_price": 1200000, "variant_used": "", "page_material": "",
                         "page_warranty": None, "regular_price": None, "ex_vat": False,
                         "page_material_text": ""}]
            with patch.object(refresh_sources.verify_sources, "verify", side_effect=fake_verify):
                refresh_sources.refresh(sources_dir=source, output_dir=root, today=date(2026, 10, 9))
            self.assertEqual(builder.read_source_rows([path])[0]["price"], "1200000")
            self.assertTrue(builder.version_matches(root / "suppliers.json", root / "VERSION"))

    def test_comparison_without_real_quotes_is_successful(self):
        from scripts.compare_b2b_vs_web import compare_quotes
        result = compare_quotes([{"nguon_type": "trang_san_pham"}])
        self.assertEqual(result, [])
