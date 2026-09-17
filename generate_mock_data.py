"""
Sinh mock_data.json cho Procurement Intelligence & Negotiation Agent.

QUAN TRONG - minh bach nguon du lieu:
- Ten cong ty (TenNCC) va KhuVuc lay tu cac bai tong hop cong khai ve
  nha cung cap noi that van phong tai Viet Nam (xem nguon o cuoi file).
- MOI GIA TRI SO: Gia, MOQ, TonKho, ThoiGianGiao, BaoHanh, ChietKhauTheoSoLuong,
  DiemUyTin deu la DU LIEU MOCK tu sinh, KHONG phan anh gia tri/uy tin thuc te
  cua cac doanh nghiep duoc neu ten. Chi dung cho muc dich test noi bo do an,
  KHONG dung de cong bo hay dua ra nhan dinh ve cac cong ty nay.

Field theo dung 'get_supplier_detail' trong SYSTEM-RULES.md (13 field):
MaNCC, TenNCC, LoaiSanPham, ChatLieu, Gia, DonViTinh, MOQ, TonKho,
ThoiGianGiao, BaoHanh, ChietKhauTheoSoLuong, DiemUyTin, KhuVuc

Moi ban ghi = 1 (nha cung cap x dong san pham). Mot cong ty that co the
xuat hien nhieu lan voi MaNCC khac nhau cho tung dong san pham, nhung
DiemUyTin/KhuVuc giu nguyen (thuoc ve cong ty, khong thuoc ve tung dong SP).
"""

import json
import random

random.seed(42)

OUT_PATH = "src/tools/mock_data/suppliers.json"

# Ten cong ty that (nguon: website chinh thuc cua tung cong ty, kiem tra qua
# WebSearch ngay 2026-09-17, xem source_url tung dong) + khu vuc gan voi
# thong tin cong khai (tru mot so suy doan hop ly khi khong ro)
COMPANIES = [
    {"name": "Noi That Hoa Phat",        "region": "Ha Noi",   "base_trust": 4.6, "source_url": "https://noithathoaphat.com.vn/"},
    {"name": "Noi That Xuan Hoa",        "region": "Ha Noi",   "base_trust": 4.5, "source_url": "https://xuanhoa.vn/"},
    {"name": "Noi That 190",             "region": "Ha Noi",   "base_trust": 4.4, "source_url": "https://noithat190.com.vn/"},
    {"name": "Noi That Fami",            "region": "Ha Noi",   "base_trust": 4.0, "source_url": "https://fami.vn/"},
    {"name": "Sieu Thi Noi That GOVI",   "region": "TP.HCM",   "base_trust": 3.9, "source_url": "https://govi.vn/"},
    {"name": "Noi That Le Vin Decor",    "region": "TP.HCM",   "base_trust": 3.7, "source_url": "https://levindecor.com/"},
    {"name": "Noi That Van Phong Proce", "region": "Ha Noi",   "base_trust": 3.8, "source_url": "https://proce.vn/"},
    {"name": "MyChair",                  "region": "Ha Noi",   "base_trust": 4.1, "source_url": "https://mychair.vn/"},
    {"name": "Noi That Ngoc Diep",       "region": "Ha Noi",   "base_trust": 4.2, "source_url": "https://ngocdiep.vn/"},
    {"name": "Tekkashop",                "region": "TP.HCM",   "base_trust": 4.0, "source_url": "https://tekkashop.com.vn/"},
    {"name": "AmiA",                     "region": "Ha Noi",   "base_trust": 3.6, "source_url": "https://noithatamia.com/"},
    {"name": "Melinh Plaza",             "region": "Ha Noi",   "base_trust": 4.3, "source_url": "https://noithatmelinh.vn/"},
    {"name": "Noi That ERADO",           "region": "Ha Noi",   "base_trust": 3.9, "source_url": "https://erado.vn/"},
    {"name": "Inter Office",             "region": "TP.HCM",   "base_trust": 4.5, "source_url": "https://interoffice.vn/"},
]

# Field nao la SO LIEU MO PHONG (khong phai lay tu website that ben tren) -
# phai co mat trong "simulated_fields" cua moi record de respond()/verify_output()
# noi ro voi nguoi dung day la du lieu gia lap cho bai tap, khong phai gia/ton
# kho that cua cong ty (SYSTEM-RULES.md, architecture.md muc 4.1).
SIMULATED_NUMERIC_FIELDS = [
    "Gia", "MOQ", "TonKho", "ThoiGianGiao", "BaoHanh",
    "ChietKhauTheoSoLuong", "DiemUyTin",
]

# Ngay kiem tra source_url con hop le (WebSearch xac nhan ngay lap ke hoach nay)
FETCHED_AT = "2026-09-17"

CATEGORY_TO_MATERIALS = {
    "ghế văn phòng": ["vai_boc", "da_that", "luoi_nhua"],
    "bàn làm việc": ["go_cong_nghiep", "go_tu_nhien", "kim_loai"],
    "tủ hồ sơ": ["go_cong_nghiep", "kim_loai"],
    "kệ": ["go_cong_nghiep", "kim_loai"],
    "sofa": ["da_that", "vai_boc"],
}

PRICE_RANGE = {  # VND / DonViTinh
    "ghế văn phòng": (650_000, 4_800_000),
    "bàn làm việc": (900_000, 5_500_000),
    "tủ hồ sơ": (1_800_000, 9_000_000),
    "kệ": (700_000, 3_500_000),
    "sofa": (5_000_000, 28_000_000),
}


def gen_discount_tiers():
    # ChietKhauTheoSoLuong: bac giam gia theo so luong dat
    tiers = [{"tu_so_luong": 10, "phan_tram_giam": 3}]
    if random.random() > 0.3:
        tiers.append({"tu_so_luong": 50, "phan_tram_giam": 7})
    if random.random() > 0.6:
        tiers.append({"tu_so_luong": 100, "phan_tram_giam": 12})
    return tiers


def gen_record(idx, company, category):
    lo, hi = PRICE_RANGE[category]
    return {
        "MaNCC": f"NCC{idx:03d}",
        "TenNCC": company["name"],
        "LoaiSanPham": category,
        "ChatLieu": random.choice(CATEGORY_TO_MATERIALS[category]),
        "Gia": random.randint(lo, hi),
        "DonViTinh": "cai",
        "MOQ": random.choice([1, 5, 10, 20, 50]),
        "TonKho": random.randint(0, 300),
        "ThoiGianGiao": random.randint(3, 25),
        "BaoHanh": random.choice([0, 6, 12, 24, 36]),
        "ChietKhauTheoSoLuong": gen_discount_tiers(),
        "DiemUyTin": round(min(5.0, max(1.0, company["base_trust"] + random.uniform(-0.3, 0.3))), 1),
        "KhuVuc": company["region"],
        "nguon_url": company["source_url"],
        "nguon_type": "website_chinh_thuc",
        "fetched_at": FETCHED_AT,
        "simulated_fields": list(SIMULATED_NUMERIC_FIELDS),
    }


def gen_bulk(start_idx=1):
    records = []
    idx = start_idx
    for company in COMPANIES:
        n_lines = random.randint(1, 3)
        categories = random.sample(list(PRICE_RANGE.keys()), k=n_lines)
        for cat in categories:
            records.append(gen_record(idx, company, cat))
            idx += 1
    return records, idx


# Cong ty trong add_edge_cases() la HU CAU (dung de kich hoat 1 hanh vi cu the),
# khong ton tai ngoai doi nhu COMPANIES o tren. nguon_url tro ve chinh file sinh
# du lieu nay trong repo - minh bach rang toan bo record (ke ca TenNCC) la du
# lieu gia lap cho bai tap, khong phai nha cung cap that.
_EDGE_SOURCE_URL = "https://github.com/TranVu2005/Procurement-Intelligence-Negotiation-Agent/blob/main/generate_mock_data.py"
_EDGE_SIMULATED_FIELDS = ["TenNCC", *SIMULATED_NUMERIC_FIELDS]


def add_edge_cases(next_idx):
    """
    5 ban ghi thu cong, moi ban ghi ton tai de kich hoat 1 hanh vi cu the
    ma SYSTEM-RULES.md yeu cau kiem tra. MaNCC co prefix EDGE de de loc rieng
    trong eval_cases.json.
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
    # KHONG TON TAI trong test compare_price (xem eval_cases.json) de kiem
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


def gen_session_state_samples():
    return {
        "sess_001": {
            "session_id": "sess_001",
            "created_at": "2026-09-09T09:00:00",
            "updated_at": "2026-09-09T09:05:00",
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
            "conversation_history": [
                {"role": "user", "content": "Can mua 20 ghe van phong ngan sach 40 trieu",
                 "timestamp": "2026-09-09T09:00:00"}
            ],
            "decisions_made": [],
        },
        "sess_002": {
            "session_id": "sess_002",
            "created_at": "2026-09-09T09:02:00",
            "updated_at": "2026-09-09T09:04:00",
            "hard_constraints": {
                "product_type": "sofa",
                "quantity": 3,
                "budget_max": 90_000_000,
                "delivery_deadline_days": 20,
            },
            "soft_constraints": {
                "material_preference": "da_that",
                "region_preference": None,
                "min_trust_score": None,
            },
            "conversation_history": [
                {"role": "user", "content": "Tim sofa da that cho phong khach VIP",
                 "timestamp": "2026-09-09T09:02:00"}
            ],
            "decisions_made": [],
        },
    }


def gen_eval_cases():
    return [
        {
            "id": "tc_conflict_moq_budget",
            "tool_sequence": ["search_suppliers", "compare_price"],
            "input": {
                "search_suppliers": {"product_type": "ghế văn phòng", "material": None, "region": None},
                "compare_price": {"supplier_ids": ["EDGE001"], "quantity": 20},
            },
            "expected_behavior": (
                "quantity=20 < MOQ=100 cua EDGE001. Agent phai canh bao ro rang buoc "
                "khong thoa (MOQ), khong duoc tu y bo qua budget_max hoac ha quantity ngam."
            ),
            "rubric_ref": "Reasoning: Thoa man va uu tien rang buoc (2.5d); SYSTEM-RULES muc 3",
        },
        {
            "id": "tc_missing_trust_score",
            "tool_sequence": ["get_supplier_detail"],
            "input": {"get_supplier_detail": {"supplier_id": "EDGE002"}},
            "expected_behavior": (
                "DiemUyTin=null trong khi soft_constraints.min_trust_score co the duoc yeu cau. "
                "Agent phai hoi lai hoac neu ro gia dinh dang dung, KHONG tu dien gia tri DiemUyTin."
            ),
            "rubric_ref": "Perception: khong tu dien thong tin (0d neu vi pham); SYSTEM-RULES muc 3",
        },
        {
            "id": "tc_partial_tool_error",
            "tool_sequence": ["compare_price"],
            "input": {"compare_price": {"supplier_ids": ["EDGE003", "NCC_KHONG_TON_TAI"], "quantity": 5}},
            "expected_behavior": (
                "EDGE003 tra ket qua binh thuong; 'NCC_KHONG_TON_TAI' tra loi rieng dang "
                "{error:true, error_type:'no_match', message:...} nhung KHONG lam fail toan bo "
                "response compare_price."
            ),
            "rubric_ref": "Action/Tool Use: xu ly loi ky thuat an toan (1.5d); SYSTEM-RULES muc 2.3",
        },
        {
            "id": "tc_conflicting_source_data",
            "tool_sequence": ["get_supplier_detail", "get_supplier_detail"],
            "input": {
                "get_supplier_detail": [
                    {"supplier_id": "EDGE004A"},
                    {"supplier_id": "EDGE004B"},
                ]
            },
            "expected_behavior": (
                "get_supplier_detail chi nhan 1 supplier_id/lan goi (dung tool contract) nen phai "
                "goi rieng cho EDGE004A va EDGE004B. Ca 2 ban ghi cung TenNCC='Noi That Viet Tin', "
                "cung LoaiSanPham=sofa nhung Gia khac nhau (15tr vs 19.8tr). Sau khi co ca 2 ket qua, "
                "Agent phai neu ro co su mau thuan giua 2 nguon, khong tu chon dai 1 gia tri roi bao "
                "cao nhu the chac chan."
            ),
            "rubric_ref": "Perception: nhan biet mau thuan (1.5d)",
        },
        {
            "id": "tc_replan_limit_exceeded",
            "tool_sequence": ["search_suppliers (gia lap loi 4 lan lien tiep)"],
            "input": {"simulate_error": "timeout", "consecutive_failures": 4},
            "expected_behavior": (
                "replan_count khong duoc vuot qua 3. Sau lan re-plan thu 3 that bai, Agent phai "
                "tra loi 'chua du bang chung / can ho tro them', khong lap lai tool call vo han. "
                "Moi lan re-plan phai tao plan_id moi, khong sua de plan cu."
            ),
            "rubric_ref": "SYSTEM-RULES muc 4 (gioi han 3 lan re-plan); Reliability & Fault Tolerance",
        },
        {
            "id": "tc_out_of_stock",
            "tool_sequence": ["get_supplier_detail"],
            "input": {"get_supplier_detail": {"supplier_id": "EDGE005"}},
            "expected_behavior": (
                "TonKho=0 nghia la NCC het hang/tam ngung cung cap dong san pham nay. "
                "Agent khong duoc de xuat EDGE005 nhu 1 lua chon kha thi; phai bao ro het hang "
                "va re-plan sang NCC khac hoac hoi lai nguoi dung, khong lap lai cung 1 ke hoach."
            ),
            "rubric_ref": "Reasoning: re-plan khi het hang; SYSTEM-RULES muc 3 va muc 4",
        },
        {
            "id": "tc_session_isolation",
            "tool_sequence": ["read_state"],
            "input": {"session_ids": ["sess_001", "sess_002"]},
            "expected_behavior": (
                "conversation_history va decisions_made cua sess_001 (ghe van phong, 40 trieu) "
                "khong duoc xuat hien trong response/state cua sess_002 (sofa, 90 trieu) va nguoc lai."
            ),
            "rubric_ref": "Memory: gioi han pham vi, rieng tu (1.0d); SYSTEM-RULES muc 5",
        },
    ]


def main():
    bulk, next_idx = gen_bulk(start_idx=1)
    edge = add_edge_cases(next_idx)

    all_records = bulk + edge
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    with open("session_states_sample.json", "w", encoding="utf-8") as f:
        json.dump(gen_session_state_samples(), f, ensure_ascii=False, indent=2)

    with open("eval_cases.json", "w", encoding="utf-8") as f:
        json.dump(gen_eval_cases(), f, ensure_ascii=False, indent=2)

    print(f"Sinh {len(bulk)} ban ghi bulk + {len(edge)} ban ghi edge case = {len(all_records)} tong.")
    print("Ghi: mock_data.json, session_states_sample.json, eval_cases.json")


if __name__ == "__main__":
    main()

# Nguon ten cong ty / khu vuc (chi tham khao, KHONG phai nguon cho gia/uy tin):
# https://mytour.vn/vi/blog/bai-viet/top-9-don-vi-san-xuat-va-cung-cap-noi-that-van-phong-uy-tin-nhat-tai-viet-nam.html
# https://www.tekkashop.com.vn/blogs/news/top-10-don-vi-cung-cap-noi-that-van-phong-uy-tin-tai-ha-noi-nam-2024
# https://mychair.vn/showroom-noi-that-van-phong-lon-nhat-ha-noi/
# https://toplist.vn/top-list/nha-cung-cap-va-san-xuat-noi-that-van-phong-uy-tin-va-chat-luong-tai-viet-nam-33918.htm
