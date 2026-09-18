"""Crawl-assist cho sources.csv (Task 10, architecture.md muc 4.2).

Fetch 7 trang ban noi that that da khao sat (co gia cong khai hoac danh muc
ro rang), tu dong doan LoaiSanPham tu ten san pham, roi xuat toi da 5 dong
moi to hop (cong ty, khu vuc, danh muc) - uu tien gia thap, tran 6 dong/cong
ty - kem link san pham cu the lam bang chung gia.

KHONG ghi thang vao src/tools/mock_data/sources.csv. Day chi la NHAP -
nguoi phai mo file draft, kiem tra tung dong (dung khu vuc? dung danh muc?
gia con hop ly khong?), roi moi copy vao sources.csv that (Task 10 buoc 1).
Cot `nguoi_thu` danh dau ro la "C(script)" de khong gia mao la nguoi tu tay
kiem tra tung trang - dung tinh than "khu vuc do script gan, chua nguoi xac
nhan" da thao luan.

Chay: .venv/Scripts/python.exe scripts/crawl_sources_draft.py
Ket qua: src/tools/mock_data/sources_draft.csv
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.dataset_builder import SOURCE_COLUMNS  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
TIMEOUT_S = 15
FETCHED_AT = date.today().isoformat()

OUT_PATH = Path(__file__).parent.parent / "src" / "tools" / "mock_data" / "sources_draft.csv"

# San pham ngoai pham vi B2B van phong (truong hoc, gia dinh, kho, dich vu) - loai truoc khi phan loai
_EXCLUDE_KEYWORDS = (
    "học sinh", "ký túc xá", "mầm non", "giường",
    "lắp đặt", "nhà bếp", "siêu thị", "gia dụng", "bàn bệt",
)

# Gia duoi muc nay la dich vu/phu kien/gia hien thi loi, khong phai 1 san pham noi that
MIN_PRICE_VND = 50_000

# Ten san pham VN dat danh tu chinh o dau ("Ban lam viec co tu...", "Tu tai
# lieu..."). Uu tien co dinh sai vi hang lam-viec-co-tu se bi bat nham thanh
# "tu" du no la cai ban. Dung vi tri xuat hien SOM NHAT cua tu khoa trong ten.
_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sofa": ("sofa",),
    "tủ hồ sơ": ("tủ",),
    "kệ": ("kệ",),
    "ghế văn phòng": ("ghế",),
    "bàn làm việc": ("bàn",),
}


def classify(name: str) -> str | None:
    lowered = name.lower()
    if any(bad in lowered for bad in _EXCLUDE_KEYWORDS):
        return None
    # "Bo ghe sofa ..." la sofa: "ghe" dung truoc nhung sofa moi la danh muc that
    if "sofa" in lowered:
        return "sofa"
    best_category, best_pos = None, len(lowered) + 1
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            pos = lowered.find(kw)
            if pos != -1 and pos < best_pos:
                best_category, best_pos = category, pos
    return best_category


@dataclass
class RawProduct:
    name: str
    url: str
    price: int | None  # None = khong cong bo gia tren trang


def is_usable(product: RawProduct) -> bool:
    """Khong co gia van giu (nguoi duyet quyet); gia qua thap thi loai."""
    return product.price is None or product.price >= MIN_PRICE_VND


def to_source_row(label: str, region: str, category: str, product: RawProduct) -> dict:
    """1 dong draft theo dung schema src/tools/mock_data/sources/*.csv."""
    row = {column: "" for column in SOURCE_COLUMNS}
    row.update({
        "supplier_name": label,
        "product_type": category,
        "product_name": product.name,
        "price": product.price if product.price is not None else "",
        "unit": "bo" if "bộ" in product.name.lower() else "cai",
        "region": region,
        "source_url": product.url,
        "collected_at": FETCHED_AT,
        "collected_by": "C(script)",
        "note": "chua duyet tay",
    })
    return row


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# 4 parser rieng cho 4 site - moi site 1 kieu markup, khong co parser chung.
# ---------------------------------------------------------------------------

def parse_hunter(html: str) -> list[RawProduct]:
    """noithathunter.com - WooCommerce. Gia = so cuoi trong khoi (sale > regular)."""
    titles = list(re.finditer(r'class="name product-title"><a href="([^"]+)">([^<]+)</a>', html))
    products = []
    for i, match in enumerate(titles):
        url, name = match.group(1), match.group(2).strip()
        window_end = titles[i + 1].start() if i + 1 < len(titles) else match.end() + 1500
        window = html[match.end():window_end]
        amounts = re.findall(r'amount">([\d,]+)<', window)
        price = int(amounts[-1].replace(",", "")) if amounts else None
        products.append(RawProduct(name=name, url=url, price=price))
    return products


def parse_hoaphathcm(html: str) -> list[RawProduct]:
    """hoaphathcm.vn - markup rieng, gia dang '1.234.000 VNĐ' (dau cham = phan cach nghin)."""
    pattern = re.compile(
        r'class="sp__item" title="([^"]+)".*?href="(san-pham/[^"]+)".*?sp__price_new">([\d.]+)\s*VNĐ',
        re.DOTALL,
    )
    products = []
    for name, rel_url, price_text in pattern.findall(html):
        price = int(price_text.replace(".", ""))
        products.append(RawProduct(name=name.strip(), url=f"https://hoaphathcm.vn/{rel_url}", price=price))
    return products


def parse_xuanhoa(html: str) -> list[RawProduct]:
    """xuanhoa.vn - khong cong bo gia cong khai ('Giá tham khảo: Liên hệ')."""
    seen: set[str] = set()
    products = []
    for rel_url, name in re.findall(r'href="(/sp/[^"]+)">([^<]+)</a>', html):
        name = name.strip()
        if not name or rel_url in seen:
            continue
        seen.add(rel_url)
        products.append(RawProduct(name=name, url=f"https://xuanhoa.vn{rel_url}", price=None))
    return products


def parse_tekkashop(html: str) -> list[RawProduct]:
    """tekkashop.com.vn - Shopify. data-ori-price DAU TIEN trong khoi = gia hien tai
    (theme hien "Regular price" nhung la gia sau giam; so thu 2 moi la gia goc bi gach).
    URL san pham nam TRUOC ten trong markup (<a class="full-unstyled-link" boc ca card)."""
    titles = list(re.finditer(r'card-information__text h5">\s*([^\n<]+?)\s*</span>', html))
    base = "https://tekkashop.com.vn"
    products = []
    for i, match in enumerate(titles):
        name = match.group(1).strip()
        window_end = titles[i + 1].start() if i + 1 < len(titles) else match.end() + 1500
        window = html[match.end():window_end]
        prices = re.findall(r"data-ori-price='([\d,]+)\.\d+'", window)
        price = int(prices[0].replace(",", "")) if prices else None

        preceding = html[max(0, match.start() - 2000):match.start()]
        url_matches = re.findall(r'href="([^"]+)"\s+class="full-unstyled-link"', preceding)
        url = base + url_matches[-1] if url_matches else base
        products.append(RawProduct(name=name, url=url, price=price))
    return products


def parse_kesatngoctin(html: str) -> list[RawProduct]:
    """kesatngoctin.com - trang danh muc da co gia san (khong can fetch
    tung trang san pham). Gia dang '1.090.000' (dau cham = phan cach nghin)."""
    pattern = re.compile(
        r'<a href="(https://kesatngoctin\.com/san-pham/[^"]+)">([^<]+)</a>'
        r'.*?woocommerce-Price-amount amount">([\d.]+)&nbsp;',
        re.DOTALL,
    )
    products = []
    for url, name, price_text in pattern.findall(html):
        products.append(RawProduct(name=name.strip(), url=url, price=int(price_text.replace(".", ""))))
    return products


def parse_giakedehangpro(html: str) -> list[RawProduct]:
    """giakedehangpro.com - gia cong khai dang '1.830.000₫' (co the la gia
    sale, la gia dau tien gap - dung lam gia hien tai). Loc trung link theo
    url vi <a> bao anh va <a> bao ten cung tro toi 1 san pham."""
    pattern = re.compile(
        r'<a href="(/[^"]+)" title="([^"]+)">.*?<span class="price">([\d.]+)₫</span>',
        re.DOTALL,
    )
    seen: set[str] = set()
    products = []
    base = "https://giakedehangpro.com"
    for rel_url, name, price_text in pattern.findall(html):
        if rel_url in seen:
            continue
        seen.add(rel_url)
        products.append(RawProduct(name=name.strip(), url=base + rel_url, price=int(price_text.replace(".", ""))))
    return products


def parse_noithatlinco(html: str) -> list[RawProduct]:
    """noithatlinco.com - JSON san co nhung trong HTML (khong phai regex
    theo class CSS). Gia la so nguyen thuan, khong co dau phan cach."""
    pattern = re.compile(r'"price":(\d+),.*?"urlPart":"([^"]+)".*?"name":"([^"]+)"')
    base = "https://www.noithatlinco.com"
    products = []
    for price_text, url_part, name in pattern.findall(html):
        products.append(RawProduct(name=name.strip(), url=f"{base}/{url_part}", price=int(price_text)))
    return products


# ---------------------------------------------------------------------------
# Cau hinh 4 nguon: url fetch, parser, TenNCC, KhuVuc gan san (co ly do).
# ---------------------------------------------------------------------------

SOURCES = [
    {
        "label": "Noi That Hunter",
        "khu_vuc": "Da Nang",  # dia chi showroom: 123 Luong Truc Dam, Hoa Minh, Lien Chieu, Da Nang
        "urls": [f"https://noithathunter.com/danh-muc/noi-that-van-phong/page/{p}/" for p in (1, 2, 3)],
        "parser": parse_hunter,
    },
    {
        "label": "Hoa Phat HCM",
        "khu_vuc": "TP.HCM",  # dia chi: 55 Bach Dang, P.15, Binh Thanh, TP.HCM
        "urls": ["https://hoaphathcm.vn/san-pham/ke-sat-45"],
        "parser": parse_hoaphathcm,
    },
    {
        "label": "Noi That Xuan Hoa",
        "khu_vuc": ["Da Nang", "Ha Noi"],  # "Van phong mien Trung: So 169, Nguyen Chanh, Da Nang";
                                             # "Van phong mien Bac: So 7, Pho Yen The, Ha Noi"
        "urls": ["https://xuanhoa.vn/cmsp/noi-that-van-phong"],
        "parser": parse_xuanhoa,
    },
    {
        "label": "Tekkashop",
        "khu_vuc": ["Da Nang", "Ha Noi"],  # kho: "Da Nang: Lo 37, Duong so 2, KCN An Don";
                                             # "Ha Noi: Lo B2-2-4, KCN Thang Long, Bac Tu Liem"
        "urls": ["https://tekkashop.com.vn/collections/ghe-van-phong"],
        "parser": parse_tekkashop,
    },
    {
        "label": "Ngoc Tin",
        "khu_vuc": ["TP.HCM", "Ha Noi"],  # "Chi nhanh TPHCM: 45 duong A8, Binh Tan";
                                            # "Chi Nhanh Ha Noi: 89 D6 Dai Kim, Hoang Mai"
        "urls": ["https://kesatngoctin.com/danh-muc/ke-ho-so"],
        "parser": parse_kesatngoctin,
    },
    {
        "label": "Gia Ke De Hang Pro",
        "khu_vuc": "Ha Noi",  # "444 phuc Dien, Nam Tu Liem, Ha Noi"; "mien phi noi thanh Ha Noi"
        "urls": ["https://giakedehangpro.com/"],
        "parser": parse_giakedehangpro,
    },
    {
        "label": "Noi That Linco",
        "khu_vuc": "TP.HCM",  # "112A Le Thuc Hoach, Tan Quy, Tan Phu, HCM"
        "urls": ["https://www.noithatlinco.com/sofa-v%C4%83n-ph%C3%B2ng"],
        "parser": parse_noithatlinco,
    },
]


MAX_ROWS_PER_GROUP = 5
MAX_ROWS_PER_COMPANY = 6


def split_round_robin(items: list[RawProduct], regions: list[str]) -> dict[str, list[RawProduct]]:
    """Chia san pham da phan loai cho nhieu vung theo vong tron, giu nguyen
    thu tu crawl trong tung vung. 1 san pham chi thuoc DUNG 1 vung."""
    buckets: dict[str, list[RawProduct]] = {region: [] for region in regions}
    for i, item in enumerate(items):
        buckets[regions[i % len(regions)]].append(item)
    return buckets


def _price_sort_key(product: RawProduct) -> tuple[bool, int]:
    """Gia thap truoc; khong co gia xep cuoi, giu nguyen thu tu crawl goc
    (sorted() on dinh, nen cac phan tu co cung key giu nguyen thu tu vao)."""
    return (product.price is None, product.price or 0)


def build_rows() -> list[dict]:
    rows: list[dict] = []
    rows_per_company: dict[str, int] = {}
    capped_companies: set[str] = set()

    for source in SOURCES:
        label = source["label"]
        products: list[RawProduct] = []
        for url in source["urls"]:
            try:
                html = fetch(url)
            except requests.RequestException as exc:
                print(f"[WARN] fetch that bai {url}: {exc}")
                continue
            products.extend(source["parser"](html))

        if not products:
            print(f"[WARN] {label}: khong fetch duoc san pham nao, bo qua")
            continue

        by_category: dict[str, list[RawProduct]] = {}
        for product in products:
            category = classify(product.name)
            if category is None or not is_usable(product):
                continue
            by_category.setdefault(category, []).append(product)

        khu_vuc = source["khu_vuc"]
        regions = khu_vuc if isinstance(khu_vuc, list) else [khu_vuc]

        rows_added_for_source = 0
        for category, items in by_category.items():
            buckets = split_round_robin(items, regions) if len(regions) > 1 else {regions[0]: items}
            for region, region_items in buckets.items():
                ranked = sorted(region_items, key=_price_sort_key)
                for product in ranked[:MAX_ROWS_PER_GROUP]:
                    if rows_per_company.get(label, 0) >= MAX_ROWS_PER_COMPANY:
                        capped_companies.add(label)
                        break
                    rows.append(to_source_row(label, region, category, product))
                    rows_per_company[label] = rows_per_company.get(label, 0) + 1
                    rows_added_for_source += 1

        print(f"{label}: {len(products)} san pham fetch duoc, "
              f"{len(by_category)} danh muc nhan dien duoc -> {sorted(by_category)}, "
              f"{rows_added_for_source} dong duoc ghi")

    for label in capped_companies:
        print(f"[WARN] {label}: da cham tran {MAX_ROWS_PER_COMPANY} dong/cong ty, "
              f"con san pham chua dung bi bo qua")

    return rows


def print_distribution(rows: list[dict]) -> None:
    by_category = Counter(r["product_type"] for r in rows)
    by_region = Counter(r["region"] for r in rows)
    print("\nPhan bo cua rieng draft nay (CHUA cong sources.csv that neu da co san):")
    print(f"  Theo LoaiSanPham: {dict(by_category)}")
    print(f"  Theo KhuVuc: {dict(by_region)}")


def main() -> None:
    rows = build_rows()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SOURCE_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} dong nhap -> {OUT_PATH}")
    print_distribution(rows)
    print("\nDay la NHAP: kiem tra tung dong (region/product_type/gia) tren trang that, "
          "doi collected_by thanh nguoi da duyet, xoa note, roi chep vao "
          "src/tools/mock_data/sources/<nhom>.csv.")


if __name__ == "__main__":
    main()
