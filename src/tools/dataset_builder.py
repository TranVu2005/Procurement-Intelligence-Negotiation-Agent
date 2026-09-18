"""Chuan hoa du lieu nguon (mock_data/sources/*.csv) thanh record suppliers.json.

Owner: Nguoi C. Moi dong CSV = 1 san pham that tren 1 trang ban hang, do nguoi
thu (hoac script crawl roi nguoi duyet). Schema cot theo PHAN-CONG-CON-LAI muc 6;
ten truong record giu nguyen theo interface-contracts.md muc 3.

Nguyen tac so lieu:
- Gia, BaoHanh, DiemUyTin la bang chung cot loi -> khong co nguon thi None,
  KHONG mo phong.
- MOQ, TonKho, ThoiGianGiao can cho filter_hard cua B chay duoc -> khong co
  nguon thi mo phong va ghi ten truong vao simulated_fields.
- ChietKhauTheoSoLuong luon mo phong.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

REQUIRED_COLUMNS = (
    "supplier_name", "product_type", "product_name", "price", "unit",
    "region", "source_url", "collected_at", "collected_by",
)
OPTIONAL_COLUMNS = (
    "material", "moq", "stock", "delivery_days", "warranty_months", "trust_score", "note",
)
SOURCE_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

VALID_PRODUCT_TYPES = ("ghế văn phòng", "bàn làm việc", "tủ hồ sơ", "kệ", "sofa")
VALID_REGIONS = ("Ha Noi", "TP.HCM", "Da Nang")
SOURCE_NGUON_TYPE = "trang_san_pham"

# Cot so tuy chon -> truong record. Co gia tri = so lieu that tu source_url cua dong.
_OPTIONAL_NUMERIC = {
    "moq": ("MOQ", int),
    "stock": ("TonKho", int),
    "delivery_days": ("ThoiGianGiao", int),
    "warranty_months": ("BaoHanh", int),
    "trust_score": ("DiemUyTin", float),
}
_SIMULATE_IF_MISSING = ("MOQ", "TonKho", "ThoiGianGiao")
_FIELD_ORDER = ("Gia", "MOQ", "TonKho", "ThoiGianGiao", "BaoHanh",
                "ChietKhauTheoSoLuong", "DiemUyTin")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VERSION_SHA = re.compile(r"sha256\.([0-9a-f]{12})")


class SourceValidationError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Du lieu nguon khong hop le:\n" + "\n".join(problems))


def _parse_price(text: str) -> int | None:
    """VND so nguyen duong viet lien (SYSTEM-RULES muc 3: khong dau cham/phay)."""
    return int(text) if text.isdigit() and int(text) > 0 else None


def _parse_optional(column: str, text: str) -> int | float | None:
    _field, kind = _OPTIONAL_NUMERIC[column]
    try:
        value = kind(text)
    except ValueError:
        return None
    if column == "trust_score":
        return value if 1.0 <= value <= 5.0 else None
    return value if value >= (0 if column == "stock" else 1) else None


def read_source_rows(paths: Iterable[Path | str]) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(Path(p) for p in paths):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise SourceValidationError([f"{path.name}: thieu cot {', '.join(missing)}"])
            for line_no, raw in enumerate(reader, start=2):
                clean = {k: (v or "").strip() for k, v in raw.items() if isinstance(k, str)}
                if not any(clean.values()):
                    continue
                clean["_origin"] = f"{path.name}:{line_no}"
                rows.append(clean)
    return rows


def _row_problems(row: dict) -> list[str]:
    problems = [f"thieu {col}" for col in REQUIRED_COLUMNS
                if col != "price" and not row.get(col)]
    if row.get("product_type") and row["product_type"] not in VALID_PRODUCT_TYPES:
        problems.append(f"product_type '{row['product_type']}' khong thuoc {VALID_PRODUCT_TYPES}")
    if row.get("region") and row["region"] not in VALID_REGIONS:
        problems.append(f"region '{row['region']}' khong thuoc {VALID_REGIONS}")
    if row.get("source_url") and not row["source_url"].startswith(("http://", "https://")):
        problems.append(f"source_url '{row['source_url']}' phai bat dau bang http(s)://")
    if row.get("collected_at") and not _ISO_DATE.match(row["collected_at"]):
        problems.append(f"collected_at '{row['collected_at']}' phai dang YYYY-MM-DD")
    if row.get("price") and _parse_price(row["price"]) is None:
        problems.append(f"price '{row['price']}' phai la so VND nguyen duong viet lien")
    for column in _OPTIONAL_NUMERIC:
        if row.get(column) and _parse_optional(column, row[column]) is None:
            problems.append(f"{column} '{row[column]}' khong hop le")
    return problems


def validate_rows(rows: list[dict]) -> None:
    problems = [f"{row.get('_origin', '?')}: {p}" for row in rows for p in _row_problems(row)]
    seen: dict[str, str] = {}
    for row in rows:
        url = row.get("source_url")
        if not url:
            continue
        if url in seen:
            # 1 san pham khong duoc lam bang chung cho 2 dong (vd 2 khu vuc khac nhau)
            problems.append(f"{row.get('_origin', '?')}: source_url trung voi {seen[url]}")
        else:
            seen[url] = row.get("_origin", "?")
    if problems:
        raise SourceValidationError(problems)


def _discount_tiers(rng: random.Random) -> list[dict]:
    tiers = [{"tu_so_luong": 10, "phan_tram_giam": 3}]
    if rng.random() > 0.3:
        tiers.append({"tu_so_luong": 50, "phan_tram_giam": 7})
    if rng.random() > 0.6:
        tiers.append({"tu_so_luong": 100, "phan_tram_giam": 12})
    return tiers


_SIMULATORS = {
    "MOQ": lambda rng: rng.choice([1, 5, 10, 20, 50]),
    "TonKho": lambda rng: rng.randint(20, 300),  # khong mo phong het hang cho SP that
    "ThoiGianGiao": lambda rng: rng.randint(3, 25),
}


def to_record(row: dict, supplier_id: str) -> dict:
    rng = random.Random(row["source_url"])
    record = {
        "MaNCC": supplier_id,
        "TenNCC": row["supplier_name"],
        "LoaiSanPham": row["product_type"],
        "TenSanPham": row["product_name"],
        "ChatLieu": row.get("material") or None,
        "Gia": _parse_price(row["price"]) if row.get("price") else None,
        "DonViTinh": row["unit"],
        "MOQ": None,
        "TonKho": None,
        "ThoiGianGiao": None,
        "BaoHanh": None,
        "ChietKhauTheoSoLuong": _discount_tiers(rng),
        "DiemUyTin": None,
        "KhuVuc": row["region"],
        "nguon_url": row["source_url"],
        "nguon_type": SOURCE_NGUON_TYPE,
        "fetched_at": row["collected_at"],
        "nguoi_thu": row["collected_by"],
    }
    for column, (field, _kind) in _OPTIONAL_NUMERIC.items():
        if row.get(column):
            record[field] = _parse_optional(column, row[column])

    simulated = {"ChietKhauTheoSoLuong"}
    for field in _SIMULATE_IF_MISSING:
        if record[field] is None:
            record[field] = _SIMULATORS[field](rng)
            simulated.add(field)
    record["simulated_fields"] = [f for f in _FIELD_ORDER if f in simulated]
    return record


def build_source_records(rows: list[dict], prefix: str = "SRC") -> list[dict]:
    validate_rows(rows)
    return [to_record(row, f"{prefix}{index:03d}") for index, row in enumerate(rows, start=1)]


def _sha12(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def write_dataset(records: list[dict], data_path, version_path, built_on: str) -> str:
    text = json.dumps(records, ensure_ascii=False, indent=2)
    Path(data_path).write_text(text, encoding="utf-8")
    version = f"{built_on}+sha256.{_sha12(text)} records={len(records)}"
    Path(version_path).write_text(version + "\n", encoding="utf-8")
    return version


def version_matches(data_path, version_path) -> bool:
    """VERSION con dung voi suppliers.json hien tai? Sai = quen chay lai generator."""
    match = _VERSION_SHA.search(Path(version_path).read_text(encoding="utf-8"))
    text = Path(data_path).read_text(encoding="utf-8")
    return bool(match) and match.group(1) == _sha12(text)


def distribution(records: list[dict]) -> dict:
    real = [r for r in records if r.get("nguon_type") == SOURCE_NGUON_TYPE]
    return {
        "total": len(real),
        "product_type": Counter(r.get("LoaiSanPham") for r in real),
        "region": Counter(r.get("KhuVuc") for r in real),
    }
