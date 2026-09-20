import json
import unittest
from pathlib import Path

from src.tools.dataset_builder import SOURCE_NGUON_TYPE, version_matches

ROOT = Path(__file__).resolve().parent.parent
MOCK_DIR = ROOT / "src" / "tools" / "mock_data"
DATA_PATH = MOCK_DIR / "suppliers.json"
VERSION_PATH = MOCK_DIR / "VERSION"
SOURCE_FIELDS = ("nguon_url", "nguon_type", "fetched_at", "simulated_fields")


def load_records():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


class CommittedDatasetTests(unittest.TestCase):
    def test_version_file_matches_the_committed_dataset(self) -> None:
        self.assertTrue(VERSION_PATH.exists(), "chua co VERSION - chay python generate_mock_data.py")
        self.assertTrue(version_matches(DATA_PATH, VERSION_PATH),
                        "suppliers.json doi ma chua sinh lai VERSION")

    def test_every_record_carries_the_four_source_fields(self) -> None:
        for record in load_records():
            with self.subTest(ma=record.get("MaNCC")):
                for field in SOURCE_FIELDS:
                    self.assertIn(field, record)

    def test_ids_are_unique(self) -> None:
        ids = [r["MaNCC"] for r in load_records()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_real_source_records_name_the_product_and_collector(self) -> None:
        for record in load_records():
            if record["nguon_type"] != SOURCE_NGUON_TYPE:
                continue
            with self.subTest(ma=record["MaNCC"]):
                self.assertTrue(record["MaNCC"].startswith("SRC"))
                self.assertTrue(record["TenSanPham"])
                self.assertTrue(record["nguoi_thu"])
                self.assertTrue(record["nguon_url"].startswith("http"))


class SourceTemplateTests(unittest.TestCase):
    def test_source_csv_has_the_agreed_header(self) -> None:
        from src.tools.dataset_builder import SOURCE_COLUMNS
        path = MOCK_DIR / "sources" / "c_sourced_products.csv"
        header = path.read_text(encoding="utf-8-sig").splitlines()[0]
        self.assertEqual(header.split(","), list(SOURCE_COLUMNS))


if __name__ == "__main__":
    unittest.main()
