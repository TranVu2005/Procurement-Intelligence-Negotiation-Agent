import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import compare_b2b_vs_web as compare
from scripts import refresh_sources
from src.nodes.respond import respond
from src.tools.dataset_builder import SOURCE_COLUMNS, read_source_rows, build_source_records
from src.tools.supplier_tools import compare_price


class ReviewRegressions(unittest.TestCase):
    def test_stream_failure_before_first_chunk_counts_attempt(self):
        class Broken:
            def stream(self, messages):
                raise TimeoutError("TEST_TIMEOUT")
        with patch("src.nodes.respond.get_llm", return_value=Broken()):
            out = respond({"ranked": [{"MaNCC": "TEST"}]})
        self.assertEqual(out["llm_calls"], 1)

    def test_client_initialization_failure_does_not_count_an_api_call(self):
        with patch("src.nodes.respond.get_llm", side_effect=EnvironmentError("TEST_CONFIG")):
            out = respond({"ranked": [{"MaNCC": "TEST"}]})
        self.assertEqual(out["llm_calls"], 0)

    def test_b2b_rank_uses_same_constraints_and_preserves_nonprice_fields(self):
        web = {"MaNCC": "TEST_WEB", "TenNCC": "TEST", "TenSanPham": "TEST_P",
               "LoaiSanPham": "ghế văn phòng", "nguon_type": "trang_san_pham", "Gia": 1000000,
               "MOQ": 1, "TonKho": 100, "ThoiGianGiao": 5, "BaoHanh": 24, "DiemUyTin": 4,
               "nguon_url": "https://example.test/web", "simulated_fields": []}
        quote = {**web, "MaNCC": "TEST_QUOTE", "Gia": 900000, "nguon_type": "b2b_quote",
                 "quote_date": "2026-10-09", "quote_quantity": 50, "quote_channel": "email",
                 "MOQ": 5, "TonKho": 207, "ThoiGianGiao": 20, "BaoHanh": None, "DiemUyTin": None,
                 "nguon_url": "https://example.test/quote"}
        calls = []
        def ranker(records, sid, quote, hard):
            calls.append((records, hard))
            return {"rank": 1, "status": "success"}
        compare.compare_quotes([web, quote], ranker=ranker)
        self.assertEqual(calls[0][1], calls[1][1])
        scenario = calls[1][0][0]
        for field in ("MOQ", "TonKho", "ThoiGianGiao", "BaoHanh", "DiemUyTin"):
            self.assertEqual(scenario[field], web[field])
        self.assertEqual(scenario["price_source_url"], quote["nguon_url"])
        with patch("src.tools.supplier_tools._load_data", return_value=[scenario]):
            priced = compare_price([scenario["MaNCC"]], 50)["comparisons"][0]
        self.assertEqual(priced["nguon_url"], quote["nguon_url"])

    def test_refresh_cache_is_separate_per_source_and_run(self):
        row = read_source_rows([Path("tests/fixtures/b2b_quotes_test.csv")])[0]
        row = {key: row.get(key, "") for key in SOURCE_COLUMNS}
        folders = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "sources"; source.mkdir()
            for filename in ("a.csv", "b.csv"):
                with (source / filename).open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=SOURCE_COLUMNS)
                    writer.writeheader(); writer.writerow({**row, "source_url": f"https://example.test/{filename}"})
            def verify(rows, folder):
                folders.append(folder)
                return []
            with patch.object(refresh_sources.verify_sources, "verify", side_effect=verify), \
                    patch.object(refresh_sources.verify_sources, "apply", return_value=[]):
                refresh_sources.refresh(sources_dir=source, output_dir=root, cache_dir=root / "cache")
                refresh_sources.refresh(sources_dir=source, output_dir=root, cache_dir=root / "cache")
        self.assertEqual(len(set(folders)), 4)

    def test_csv_fixture_is_test_only_and_not_in_production_data(self):
        rows = read_source_rows([Path("tests/fixtures/b2b_quotes_test.csv")])
        record = build_source_records(rows)[0]
        self.assertTrue(record["TenNCC"].startswith("TEST_"))
        self.assertIn("TEST DATA ONLY", rows[0]["note"])
