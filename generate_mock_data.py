"""Sinh suppliers.json va VERSION tu CSV nguon va 6 fixture EDGE.

Gia san pham co nguon duoc giu nguyen. Cac truong nghiep vu mo phong
va fixture EDGE duoc danh dau bang simulated_fields/nguon_type.
"""

from datetime import date
from pathlib import Path

from src.tools.dataset_builder import (
    build_source_records,
    distribution,
    read_source_rows,
    write_dataset,
)

OUT_PATH = "src/tools/mock_data/suppliers.json"
SOURCES_DIR = Path("src/tools/mock_data/sources")
VERSION_PATH = Path("src/tools/mock_data/VERSION")

SIMULATED_NUMERIC_FIELDS = [
    "Gia", "MOQ", "TonKho", "ThoiGianGiao", "BaoHanh",
    "ChietKhauTheoSoLuong", "DiemUyTin",
]
FETCHED_AT = "2026-09-17"

# Fixture EDGE co y la du lieu gia lap, khong phai bao gia that.
_EDGE_SOURCE_URL = "https://github.com/TranVu2005/Procurement-Intelligence-Negotiation-Agent/blob/main/generate_mock_data.py"
_EDGE_SIMULATED_FIELDS = ["TenNCC", *SIMULATED_NUMERIC_FIELDS]


def add_edge_cases(next_idx):
    """
    6 ban ghi thu cong, moi ban ghi ton tai de kich hoat 1 hanh vi cu the
    ma SYSTEM-RULES.md yeu cau kiem tra. MaNCC co prefix EDGE de de loc rieng
    trong tests/eval_set/.
    """
    edge_source = {
        "nguon_url": _EDGE_SOURCE_URL,
        "nguon_type": "du_lieu_test_gia_lap",
        "fetched_at": FETCHED_AT,
        "simulated_fields": list(_EDGE_SIMULATED_FIELDS),
    }
    records = []

    # EDGE 1 - ngan sach khong du cho MOQ (dung cho case "rang buoc mau thuan")
    # Gia cao + MOQ lon => tong don toi thieu rat lon, de test canh bao mau thuan
    records.append({
        "MaNCC": "EDGE001", "TenNCC": "Noi That Cao Cap Kim Long",
        "LoaiSanPham": "ghế văn phòng", "ChatLieu": "da_that",
        "Gia": 4_500_000, "DonViTinh": "cai", "MOQ": 100, "TonKho": 150,
        "ThoiGianGiao": 20, "BaoHanh": 24,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 100, "phan_tram_giam": 5}],
        "DiemUyTin": 4.2, "KhuVuc": "Ha Noi", **edge_source,
    })

    # EDGE 2 - thieu DiemUyTin (null) trong khi de bai co the yeu cau
    # min_trust_score => Agent KHONG duoc tu dien, phai hoi lai / neu gia dinh
    records.append({
        "MaNCC": "EDGE002", "TenNCC": "Noi That Thanh Cong Moi",
        "LoaiSanPham": "bàn làm việc", "ChatLieu": "go_cong_nghiep",
        "Gia": 1_450_000, "DonViTinh": "cai", "MOQ": 10, "TonKho": 80,
        "ThoiGianGiao": 7, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 10, "phan_tram_giam": 4}],
        "DiemUyTin": None, "KhuVuc": "Da Nang", **edge_source,
    })

    # EDGE 3 - MaNCC nay CO TON TAI nhung se duoc dung ket hop voi 1 ma
    # KHONG TON TAI trong test compare_price (xem tests/eval_set/) de kiem
    # tra loi cuc bo, khong fail ca response.
    records.append({
        "MaNCC": "EDGE003", "TenNCC": "Noi That Song Hong",
        "LoaiSanPham": "tủ hồ sơ", "ChatLieu": "kim_loai",
        "Gia": 2_300_000, "DonViTinh": "cai", "MOQ": 5, "TonKho": 40,
        "ThoiGianGiao": 10, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 5, "phan_tram_giam": 2}],
        "DiemUyTin": 3.8, "KhuVuc": "TP.HCM", **edge_source,
    })

    # EDGE 4 - 2 ban ghi CUNG TenNCC nhung DU LIEU MAU THUAN (gia khac nhau
    # cho cung 1 dong san pham) => test phat hien mau thuan nguon du lieu
    records.append({
        "MaNCC": "EDGE004A", "TenNCC": "Noi That Viet Tin",
        "LoaiSanPham": "sofa", "ChatLieu": "da_that",
        "Gia": 15_000_000, "DonViTinh": "bo", "MOQ": 1, "TonKho": 10,
        "ThoiGianGiao": 15, "BaoHanh": 24,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 5, "phan_tram_giam": 5}],
        "DiemUyTin": 4.0, "KhuVuc": "Ha Noi", **edge_source,
    })
    records.append({
        "MaNCC": "EDGE004B", "TenNCC": "Noi That Viet Tin",
        "LoaiSanPham": "sofa", "ChatLieu": "da_that",
        "Gia": 19_800_000, "DonViTinh": "bo", "MOQ": 1, "TonKho": 10,
        "ThoiGianGiao": 15, "BaoHanh": 24,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 5, "phan_tram_giam": 5}],
        "DiemUyTin": 4.0, "KhuVuc": "Ha Noi", **edge_source,
    })

    # EDGE 5 - TonKho=0 (het hang / NCC tam ngung cung cap dong san pham nay).
    # Khong the phat hien qua search_suppliers/compare_price (2 tool nay khong
    # tra field TonKho theo contract) - chi lo ra khi goi get_supplier_detail.
    # Dung cho buoi hop 4: B phai re-plan thay vi de xuat NCC nay.
    records.append({
        "MaNCC": "EDGE005", "TenNCC": "Noi That Kho Rong",
        "LoaiSanPham": "kệ", "ChatLieu": "go_cong_nghiep",
        "Gia": 1_200_000, "DonViTinh": "cai", "MOQ": 10, "TonKho": 0,
        "ThoiGianGiao": 14, "BaoHanh": 12,
        "ChietKhauTheoSoLuong": [{"tu_so_luong": 10, "phan_tram_giam": 3}],
        "DiemUyTin": 3.5, "KhuVuc": "Ha Noi", **edge_source,
    })

    # EDGE 6 - khong phai du lieu san pham, ma la 2 session state mau dung
    # rieng cho test "session isolation" (rule 5). Luu tach o file khac.
    return records



def generate_dataset(sources_dir=SOURCES_DIR, data_path=OUT_PATH, version_path=VERSION_PATH,
                     built_on=None):
    """Sinh dataset + VERSION tu nguon, khong ghi file demo ngoai pham vi refresh."""
    edge = add_edge_cases(1)
    sourced = build_source_records(read_source_rows(Path(sources_dir).glob("*.csv")))
    records = edge + sourced
    version = write_dataset(records, data_path, version_path, built_on or date.today().isoformat())
    return records, version



def main():
    records, version = generate_dataset()
    edge_count = sum(record["MaNCC"].startswith("EDGE") for record in records)
    dist = distribution(records)
    print(f"Sinh {edge_count} edge + {len(records) - edge_count} nguon that = {len(records)} ban ghi.")
    print(f"dataset_version = {version}")
    print(f"Nguon that theo LoaiSanPham: {dict(dist['product_type'])}")
    print(f"Nguon that theo KhuVuc: {dict(dist['region'])}")


if __name__ == "__main__":
    main()
