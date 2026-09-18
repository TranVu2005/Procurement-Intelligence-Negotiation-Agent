import csv
import tempfile
import unittest
from pathlib import Path

from src.tools.dataset_builder import (
    SOURCE_COLUMNS, SOURCE_NGUON_TYPE, SourceValidationError, build_source_records,
    distribution, read_source_rows, to_record, validate_rows, version_matches, write_dataset,
)


def row(**overrides):
    base = {col: "" for col in SOURCE_COLUMNS}
    base.update({
        "supplier_name": "Noi That Linco", "product_type": "sofa",
        "product_name": "Sofa KT62 Cornwall", "price": "9400000", "unit": "bo",
        "region": "TP.HCM", "source_url": "https://www.noithatlinco.com/sofa-kt62",
        "collected_at": "2026-09-17", "collected_by": "C", "_origin": "sofa.csv:2",
    })
    base.update(overrides)
    return base


def write_csv(directory: Path, name: str, rows: list[dict], header=SOURCE_COLUMNS) -> Path:
    path = directory / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header))
        writer.writeheader()
        for item in rows:
            writer.writerow({k: v for k, v in item.items() if k in header})
    return path


class ToRecordTests(unittest.TestCase):
    def test_real_fields_are_mapped_and_not_marked_simulated(self) -> None:
        record = to_record(row(), "SRC001")
        self.assertEqual(record["MaNCC"], "SRC001")
        self.assertEqual(record["TenNCC"], "Noi That Linco")
        self.assertEqual(record["TenSanPham"], "Sofa KT62 Cornwall")
        self.assertEqual(record["Gia"], 9_400_000)
        self.assertEqual(record["KhuVuc"], "TP.HCM")
        self.assertEqual(record["nguon_url"], "https://www.noithatlinco.com/sofa-kt62")
        self.assertEqual(record["nguon_type"], SOURCE_NGUON_TYPE)
        self.assertEqual(record["fetched_at"], "2026-09-17")
        self.assertEqual(record["nguoi_thu"], "C")
        self.assertNotIn("Gia", record["simulated_fields"])

    def test_filter_fields_are_simulated_and_labelled_when_missing(self) -> None:
        record = to_record(row(), "SRC001")
        for field in ("MOQ", "TonKho", "ThoiGianGiao"):
            with self.subTest(field=field):
                self.assertIsInstance(record[field], int)
                self.assertIn(field, record["simulated_fields"])
        self.assertIn("ChietKhauTheoSoLuong", record["simulated_fields"])

    def test_evidence_fields_stay_null_when_missing(self) -> None:
        record = to_record(row(price=""), "SRC001")
        for field in ("Gia", "BaoHanh", "DiemUyTin", "ChatLieu"):
            with self.subTest(field=field):
                self.assertIsNone(record[field])
                self.assertNotIn(field, record["simulated_fields"])

    def test_a_collected_value_overrides_simulation(self) -> None:
        record = to_record(row(moq="5", stock="0", warranty_months="12", trust_score="4.2"),
                           "SRC001")
        self.assertEqual(record["MOQ"], 5)
        self.assertEqual(record["TonKho"], 0)  # 0 = het hang, van la so lieu hop le
        self.assertEqual(record["BaoHanh"], 12)
        self.assertEqual(record["DiemUyTin"], 4.2)
        for field in ("MOQ", "TonKho", "BaoHanh", "DiemUyTin"):
            self.assertNotIn(field, record["simulated_fields"])

    def test_simulation_is_deterministic_per_source_url(self) -> None:
        self.assertEqual(to_record(row(), "SRC001"), to_record(row(), "SRC001"))


class ValidationTests(unittest.TestCase):
    def test_all_problems_are_reported_with_their_origin(self) -> None:
        bad = row(product_type="giường", region="Hue", collected_at="17/09/2026",
                  price="9.400.000", source_url="www.khong-co-giao-thuc.vn")
        with self.assertRaises(SourceValidationError) as ctx:
            validate_rows([bad])
        problems = ctx.exception.problems
        self.assertEqual(len(problems), 5)
        self.assertTrue(all(p.startswith("sofa.csv:2") for p in problems))

    def test_missing_required_value_is_rejected(self) -> None:
        with self.assertRaises(SourceValidationError) as ctx:
            validate_rows([row(product_name="")])
        self.assertIn("product_name", ctx.exception.problems[0])

    def test_the_same_product_url_cannot_back_two_rows(self) -> None:
        with self.assertRaises(SourceValidationError) as ctx:
            validate_rows([row(), row(_origin="sofa.csv:3", region="Ha Noi")])
        self.assertIn("trung", ctx.exception.problems[0])

    def test_trust_score_outside_one_to_five_is_rejected(self) -> None:
        with self.assertRaises(SourceValidationError):
            validate_rows([row(trust_score="7")])


class ReadAndBuildTests(unittest.TestCase):
    def test_rows_are_read_across_files_in_name_order_with_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_csv(directory, "sofa.csv", [row()])
            write_csv(directory, "ke.csv", [row(product_type="kệ", product_name="Ke sat V lo",
                                               source_url="https://vi.du/ke")])
            rows = read_source_rows(directory.glob("*.csv"))
        self.assertEqual([r["_origin"] for r in rows], ["ke.csv:2", "sofa.csv:2"])
        records = build_source_records(rows)
        self.assertEqual([r["MaNCC"] for r in records], ["SRC001", "SRC002"])

    def test_a_file_missing_a_required_column_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(Path(tmp), "sofa.csv", [row()],
                             header=[c for c in SOURCE_COLUMNS if c != "source_url"])
            with self.assertRaises(SourceValidationError) as ctx:
                read_source_rows([path])
        self.assertIn("source_url", ctx.exception.problems[0])

    def test_blank_lines_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(Path(tmp), "sofa.csv", [row(), {c: "" for c in SOURCE_COLUMNS}])
            self.assertEqual(len(read_source_rows([path])), 1)


class VersionTests(unittest.TestCase):
    def test_version_matches_until_the_data_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data, version = Path(tmp) / "suppliers.json", Path(tmp) / "VERSION"
            text = write_dataset([to_record(row(), "SRC001")], data, version, "2026-09-18")
            self.assertRegex(text, r"^2026-09-18\+sha256\.[0-9a-f]{12} records=1$")
            self.assertTrue(version_matches(data, version))
            data.write_text("[]", encoding="utf-8")
            self.assertFalse(version_matches(data, version))


class DistributionTests(unittest.TestCase):
    def test_only_real_source_records_are_counted(self) -> None:
        legacy = {"MaNCC": "NCC001", "LoaiSanPham": "sofa", "KhuVuc": "Ha Noi",
                  "nguon_type": "website_chinh_thuc"}
        dist = distribution([to_record(row(), "SRC001"), legacy])
        self.assertEqual(dist["total"], 1)
        self.assertEqual(dist["product_type"]["sofa"], 1)
        self.assertEqual(dist["region"]["TP.HCM"], 1)


if __name__ == "__main__":
    unittest.main()
