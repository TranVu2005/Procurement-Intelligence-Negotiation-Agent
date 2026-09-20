import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import crawl_sources_draft as crawl  # noqa: E402
from src.tools.dataset_builder import SOURCE_COLUMNS  # noqa: E402


class ClassifyTests(unittest.TestCase):
    def test_a_sofa_set_is_a_sofa_not_an_office_chair(self) -> None:
        self.assertEqual(crawl.classify("Bộ ghế sofa phòng khách giá rẻ KL4 GBL2"), "sofa")

    def test_earliest_keyword_still_decides_other_products(self) -> None:
        self.assertEqual(crawl.classify("Bàn làm việc có tủ ngăn kéo"), "bàn làm việc")
        self.assertEqual(crawl.classify("Ghế xoay lưới văn phòng"), "ghế văn phòng")

    def test_services_and_non_office_items_are_excluded(self) -> None:
        for name in ("Lắp đặt giá kệ kho hàng công nghiệp", "Kệ nhà bếp",
                     "Kệ siêu thị đơn 3 tầng", "Kệ gia dụng 4 tầng", "Bàn bệt chân sắt"):
            with self.subTest(name=name):
                self.assertIsNone(crawl.classify(name))


class UsableTests(unittest.TestCase):
    def test_implausibly_cheap_price_is_dropped(self) -> None:
        self.assertFalse(crawl.is_usable(crawl.RawProduct("Ke", "https://x", 1000)))

    def test_unknown_price_is_kept_for_manual_review(self) -> None:
        self.assertTrue(crawl.is_usable(crawl.RawProduct("Tu", "https://x", None)))


class SourceRowTests(unittest.TestCase):
    def test_row_uses_the_shared_source_schema(self) -> None:
        product = crawl.RawProduct("Bộ ghế sofa KT62", "https://vi.du/sofa", 9_400_000)
        row = crawl.to_source_row("Noi That Linco", "TP.HCM", "sofa", product)
        self.assertEqual(list(row), list(SOURCE_COLUMNS))
        self.assertEqual(row["product_name"], "Bộ ghế sofa KT62")
        self.assertEqual(row["price"], 9_400_000)
        self.assertEqual(row["unit"], "bo")
        self.assertEqual(row["collected_by"], "C(script)")

    def test_missing_price_becomes_an_empty_cell(self) -> None:
        row = crawl.to_source_row("Xuan Hoa", "Ha Noi", "tủ hồ sơ",
                                  crawl.RawProduct("Tủ sắt CA-1A", "https://x", None))
        self.assertEqual(row["price"], "")
        self.assertEqual(row["unit"], "cai")


if __name__ == "__main__":
    unittest.main()
