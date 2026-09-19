import csv
import unittest
from pathlib import Path
from urllib.parse import urlparse


SOURCE_FILE = Path(__file__).parents[1] / "data" / "sources_b_tu_ke.csv"


class PersonBRealSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with SOURCE_FILE.open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_handoff_contains_both_assigned_product_types(self):
        self.assertGreaterEqual(len(self.rows), 8)
        self.assertEqual({row["product_type"] for row in self.rows}, {"tủ hồ sơ", "kệ"})

    def test_every_row_has_required_real_source_fields(self):
        required = {
            "supplier_name",
            "region",
            "product_type",
            "product_name",
            "price",
            "unit",
            "source_url",
            "collected_at",
        }
        for row in self.rows:
            with self.subTest(product=row.get("product_code")):
                self.assertTrue(all(row.get(field, "").strip() for field in required))
                self.assertGreater(float(row["price"]), 0)
                parsed = urlparse(row["source_url"])
                self.assertEqual(parsed.scheme, "https")
                self.assertTrue(parsed.netloc)

    def test_unknown_procurement_fields_remain_explicitly_missing(self):
        fields_that_must_not_be_invented = {
            "MOQ",
            "inventory",
            "delivery_days",
            "discounts",
            "trust_score",
        }
        for row in self.rows:
            missing = set(row["missing_evidence_fields"].split(";"))
            with self.subTest(product=row["product_code"]):
                self.assertTrue(fields_that_must_not_be_invented.issubset(missing))


if __name__ == "__main__":
    unittest.main()
