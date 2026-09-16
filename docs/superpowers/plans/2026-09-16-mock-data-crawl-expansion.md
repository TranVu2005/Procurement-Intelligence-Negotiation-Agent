# Mở rộng crawl-assist cho sources.csv — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mở rộng `scripts/crawl_sources_draft.py` từ 4 lên 7 site nguồn, để
crawl **nhiều dòng nhất có thể** (thay vì 1 dòng đại diện/tổ hợp như hiện
tại) và bù 2 lỗ hổng phân bố hiện tại của `sources_draft.csv` (Đà Nẵng, kệ),
mà không bỏ sót Hà Nội.

**Architecture:** Giữ nguyên 1 file script (không tách package). Mỗi site có
1 parser regex riêng trả về `list[RawProduct]`; hàm `build_rows()` phân loại
bằng `classify()` (không đổi), gom nhóm theo `(TenNCC, KhuVuc, LoaiSanPham)`,
lấy tối đa N=5 dòng/tổ hợp (ưu tiên giá thấp), áp trần 6 dòng/công ty. Site
có nhiều chi nhánh (Xuân Hòa, Tekkashop, kesatngoctin.com) khai `khu_vuc` là
`list[str]`; sản phẩm được chia round-robin theo vùng **trong từng danh
mục** trước khi gom nhóm, để mỗi vùng có cơ hội đại diện ở mọi danh mục thay
vì phụ thuộc vị trí ngẫu nhiên trên trang.

**Tech Stack:** Python 3.14, `requests` (đã có trong venv), `re` (regex thủ
công theo từng site, không dùng `bs4` — chưa cài, không cần cho quy mô
việc này).

## Global Constraints

- Không ghi thẳng vào `src/tools/mock_data/sources.csv` — script chỉ ghi
  `src/tools/mock_data/sources_draft.csv`. Người duyệt tay rồi mới copy vào
  file thật (Task 10 bước 1, `architecture.md` §4.2).
- Cột `nguoi_thu` luôn là chuỗi cố định `"C(script)"` — không giả mạo là
  người tự tay kiểm tra từng trang.
- Mỗi tổ hợp `(TenNCC, KhuVuc, LoaiSanPham)`: tối đa **N = 5 dòng**, ưu tiên
  giá thấp trước (`price is None` xếp cuối, dùng `sorted()` — ổn định, giữ
  đúng thứ tự crawl gốc cho các dòng không giá).
- Trần **6 dòng/công ty** (`TenNCC`), cộng dồn qua mọi danh mục/vùng của
  công ty đó. Khi chạm trần, dừng thêm dòng mới cho công ty đó, in
  `[WARN]` một lần, không dừng cả script.
- Site không xác định được vùng thật (không có địa chỉ chi nhánh rõ trong
  trang) hoặc lỗi SSL khi fetch: **bỏ qua hẳn site đó**, không đoán vùng,
  không tắt xác thực SSL (`verify=False`) để cố lấy bằng được.
- 1 site fetch lỗi (mạng, HTTP lỗi) hoặc parser ra 0 sản phẩm: in
  `[WARN] ...` và bỏ qua site đó, không dừng cả script (`try/except` cô lập
  theo site, đã có sẵn trong `build_rows()`).
- Chạy script trên Windows PowerShell/Bash tool phải set
  `PYTHONIOENCODING=utf-8` trước, nếu không `print()` tiếng Việt sẽ
  `UnicodeEncodeError` (console mặc định dùng cp1252, đã gặp lỗi này khi
  viết bản đầu của script).
- Không commit `src/tools/mock_data/sources_draft.csv` vào git — đây là
  output tái sinh được (chạy lại script là ra), không phải nguồn dữ liệu.
  Chỉ commit thay đổi trong `scripts/crawl_sources_draft.py`.

---

### Task 1: Tổng quát hóa `khu_vuc` thành `str | list[str]`, viết lại `build_rows()` cho N=5/tổ hợp + trần 6/công ty

**Files:**
- Modify: `scripts/crawl_sources_draft.py` (hàm `build_rows()`, các entry
  `SOURCES` của Xuân Hòa và Tekkashop, thêm hàm `split_round_robin()` và
  `_price_sort_key()`)

**Interfaces:**
- Consumes: `RawProduct` (đã có), `classify()` (đã có, không đổi), `fetch()`
  (đã có, không đổi).
- Produces:
  - `split_round_robin(items: list[RawProduct], regions: list[str]) -> dict[str, list[RawProduct]]`
  - `_price_sort_key(product: RawProduct) -> tuple[bool, int]`
  - `MAX_ROWS_PER_GROUP: int = 5`, `MAX_ROWS_PER_COMPANY: int = 6` (hằng số
    module-level, Task 2-5 không cần biết chi tiết, chỉ cần dòng CSV cuối
    cùng tuân theo 2 giới hạn này).
  - `build_rows()` vẫn trả về `list[dict]` đúng shape cũ (không đổi khóa).

- [ ] **Step 1: Đổi `khu_vuc` của Xuân Hòa và Tekkashop thành list 2 vùng**

Trong `scripts/crawl_sources_draft.py`, sửa 2 entry trong `SOURCES`:

```python
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
```

- [ ] **Step 2: Thêm `split_round_robin()` và `_price_sort_key()` ngay trước `build_rows()`**

```python
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
```

- [ ] **Step 3: Viết lại `build_rows()`**

Thay toàn bộ thân hàm `build_rows()` hiện tại bằng:

```python
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
            if category is None:
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
                    rows.append({
                        "TenNCC": label,
                        "KhuVuc": region,
                        "LoaiSanPham": category,
                        "Gia_niem_yet": product.price if product.price is not None else "",
                        "nguon_url": product.url,
                        "fetched_at": FETCHED_AT,
                        "nguoi_thu": "C(script)",
                    })
                    rows_per_company[label] = rows_per_company.get(label, 0) + 1
                    rows_added_for_source += 1

        print(f"{label}: {len(products)} san pham fetch duoc, "
              f"{len(by_category)} danh muc nhan dien duoc -> {sorted(by_category)}, "
              f"{rows_added_for_source} dong duoc ghi")

    for label in capped_companies:
        print(f"[WARN] {label}: da cham tran {MAX_ROWS_PER_COMPANY} dong/cong ty, "
              f"con san pham chua dung bi bo qua")

    return rows
```

Lưu ý: hàm mới không còn dùng `representative.url or source["urls"][0]` như
bản cũ — mọi parser (kể cả 3 parser mới ở Task 3-5) đều tự set `url` cho
từng `RawProduct`, không cần fallback.

- [ ] **Step 4: Chạy lại script để xác nhận không vỡ**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/crawl_sources_draft.py
```

Expected: chạy hết không lỗi. Dòng log của `Noi That Xuan Hoa` và
`Tekkashop` in ra vẫn có danh mục như cũ. Mở
`src/tools/mock_data/sources_draft.csv`, xác nhận:
- Có dòng `KhuVuc` là cả `Da Nang` lẫn `Ha Noi` cho `Noi That Xuan Hoa` và
  cho `Tekkashop` (trước đây chỉ có `Da Nang`).
- Không dòng nào của `Noi That Hunter`/`Hoa Phat HCM` (vẫn 1 vùng) bị đổi
  `KhuVuc`.
- Tổng số dòng tăng lên (N=5/tổ hợp thay vì 1 dòng/tổ hợp trước đó).

- [ ] **Step 5: Commit**

```bash
git add scripts/crawl_sources_draft.py
git commit -m "$(cat <<'EOF'
feat(data): support multi-region sources and N-per-group sampling

Generalize khu_vuc to str | list[str] so a multi-branch company (Xuan
Hoa, Tekkashop) can contribute rows to more than one region without
duplicate product evidence, and switch build_rows() from one
representative row per group to up to 5, price-ascending, capped at
6 rows per company overall.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `parse_kesatngoctin` — kệ, TP.HCM + Hà Nội

**Files:**
- Modify: `scripts/crawl_sources_draft.py` (thêm hàm `parse_kesatngoctin`,
  thêm 1 entry vào `SOURCES`)

**Interfaces:**
- Consumes: `RawProduct` (Task 1 trở về trước, không đổi).
- Produces: `parse_kesatngoctin(html: str) -> list[RawProduct]`, dùng nội bộ
  bởi `SOURCES`, không hàm nào khác gọi trực tiếp.

Trang danh mục `https://kesatngoctin.com/danh-muc/ke-ho-so` (đã xác minh
bằng `requests` thường, không cần render JS) có sẵn tên + link + giá ngay
trên 1 trang, dạng lặp:

```html
<h3 class="elementor-heading-title elementor-size-default"><a href="https://kesatngoctin.com/san-pham/...">Ten san pham</a></h3>
...
<span class="elementor-heading-title elementor-size-default">Giá: <span class="woocommerce-Price-amount amount">1.090.000&nbsp;...
```

- [ ] **Step 1: Viết `parse_kesatngoctin`**

Thêm vào `scripts/crawl_sources_draft.py`, ngay sau `parse_tekkashop`:

```python
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
```

- [ ] **Step 2: Thêm entry vào `SOURCES`**

Thêm vào cuối danh sách `SOURCES` (sau entry `Tekkashop`):

```python
    {
        "label": "Ngoc Tin",
        "khu_vuc": ["TP.HCM", "Ha Noi"],  # "Chi nhanh TPHCM: 45 duong A8, Binh Tan";
                                            # "Chi Nhanh Ha Noi: 89 D6 Dai Kim, Hoang Mai"
        "urls": ["https://kesatngoctin.com/danh-muc/ke-ho-so"],
        "parser": parse_kesatngoctin,
    },
```

- [ ] **Step 3: Verify bằng lệnh trực tiếp trên site thật**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "
import sys
sys.path.insert(0, 'scripts')
from crawl_sources_draft import fetch, parse_kesatngoctin
html = fetch('https://kesatngoctin.com/danh-muc/ke-ho-so')
products = parse_kesatngoctin(html)
print(len(products))
for p in products[:3]:
    print(p)
"
```

Expected: số sản phẩm > 0 (đã xác minh trước là 9), mỗi dòng có `url` bắt
đầu bằng `https://kesatngoctin.com/san-pham/`, `price` là số nguyên hợp lý
(hàng trăm nghìn đến vài triệu VND), không có dòng `price=None`.

- [ ] **Step 4: Chạy toàn bộ script, kiểm tra output cuối**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/crawl_sources_draft.py
```

Expected: log có dòng `Ngoc Tin: ... danh muc nhan dien duoc -> ['kệ']`. Mở
`sources_draft.csv`, xác nhận có cả dòng `TenNCC=Ngoc Tin, KhuVuc=TP.HCM` và
`TenNCC=Ngoc Tin, KhuVuc=Ha Noi`.

- [ ] **Step 5: Commit**

```bash
git add scripts/crawl_sources_draft.py
git commit -m "$(cat <<'EOF'
feat(data): add kesatngoctin.com parser (ke, TP.HCM + Ha Noi)

Category page already carries name/link/price in one fetch — no
product-page round trip needed. Fills the ke shortfall and adds a
second real Ha Noi + TP.HCM source alongside Xuan Hoa/Tekkashop.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `parse_giakedehangpro` — kệ, Hà Nội

**Files:**
- Modify: `scripts/crawl_sources_draft.py` (thêm hàm `parse_giakedehangpro`,
  thêm 1 entry vào `SOURCES`)

**Interfaces:**
- Consumes: `RawProduct` (không đổi).
- Produces: `parse_giakedehangpro(html: str) -> list[RawProduct]`.

Trang chủ `https://giakedehangpro.com/` liệt kê sản phẩm trực tiếp, có giá
công khai (không phải toàn "Liên hệ" như nhận định ban đầu trong spec —
"Liên hệ" quan sát được trước đó là link menu "Liên hệ", không phải giá sản
phẩm; đã kiểm chứng lại bằng `requests` thật, sẽ sửa spec ở Task 6). Markup:

```html
<a href="/ke-de-file-tai-lieu-dai-1-8m-x-sau-0-4m-x-cao-2m-6-tang" title="Kệ để file tài liệu (...)">
  ...
</a>
...
<div class="price-box price-loop-style">
    <span class="special-price"><span class="price">1.830.000₫</span></span>
    <span class="old-price"><span class="price">1.960.000₫</span></span>
</div>
```

Trang cũng có các link điều hướng không phải sản phẩm (menu, `/checkout`,
...) — không lọc riêng trong parser, để `classify()` ở `build_rows()` tự
loại (tên các link đó không chứa từ khóa danh mục nào).

- [ ] **Step 1: Viết `parse_giakedehangpro`**

Thêm vào `scripts/crawl_sources_draft.py`, ngay sau `parse_kesatngoctin`:

```python
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
```

- [ ] **Step 2: Thêm entry vào `SOURCES`**

```python
    {
        "label": "Gia Ke De Hang Pro",
        "khu_vuc": "Ha Noi",  # "444 phuc Dien, Nam Tu Liem, Ha Noi"; "mien phi noi thanh Ha Noi"
        "urls": ["https://giakedehangpro.com/"],
        "parser": parse_giakedehangpro,
    },
```

- [ ] **Step 3: Verify bằng lệnh trực tiếp trên site thật**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "
import sys
sys.path.insert(0, 'scripts')
from crawl_sources_draft import fetch, parse_giakedehangpro
html = fetch('https://giakedehangpro.com/')
products = parse_giakedehangpro(html)
print(len(products))
for p in products[:5]:
    print(p)
"
```

Expected: số sản phẩm > 50 (đã xác minh trước ra 113, kể cả vài dòng không
liên quan như '/checkout' sẽ tự bị lọc ở bước `classify()`, không phải ở
đây). Không có `url` trùng lặp trong danh sách in ra.

- [ ] **Step 4: Chạy toàn bộ script, kiểm tra output cuối**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/crawl_sources_draft.py
```

Expected: log có dòng `Gia Ke De Hang Pro: ... -> ['kệ']` (hoặc thêm danh
mục khác nếu site cũng có sản phẩm khớp từ khóa khác — không sao, cứ giữ
nguyên, không lọc cứng theo danh mục dự kiến). Mở `sources_draft.csv`, xác
nhận có dòng `TenNCC=Gia Ke De Hang Pro, KhuVuc=Ha Noi` với `Gia_niem_yet`
có giá trị số thật (không rỗng).

- [ ] **Step 5: Commit**

```bash
git add scripts/crawl_sources_draft.py
git commit -m "$(cat <<'EOF'
feat(data): add giakedehangpro.com parser (ke, Ha Noi)

Homepage lists products with a real public price (price-box /
special-price markup) — the "no public price" note from the design
spec was based on a menu link false-positive, corrected here.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `parse_noithatlinco` — sofa, TP.HCM

**Files:**
- Modify: `scripts/crawl_sources_draft.py` (thêm hàm `parse_noithatlinco`,
  thêm 1 entry vào `SOURCES`)

**Interfaces:**
- Consumes: `RawProduct` (không đổi).
- Produces: `parse_noithatlinco(html: str) -> list[RawProduct]`.

Trang `https://www.noithatlinco.com/sofa-v%C4%83n-ph%C3%B2ng` nhúng sẵn 1
khối JSON trong HTML (nền tảng dạng Wix/Ecwid), mỗi sản phẩm có 3 khóa liền
kề theo đúng thứ tự `price`, `urlPart`, `name`:

```
"price":9600000,...,"urlPart":"bộ-ghế-sofa-da-simili-cao-cấp-kt37-noha-màu-xanh-lá",...,"name":"Bộ ghế sofa da simili cao cấp KT37 Noha màu xanh lá"
```

Giá ở đây là số nguyên thuần, không có dấu phân cách — không cần `.replace()`
như các site khác.

- [ ] **Step 1: Viết `parse_noithatlinco`**

Thêm vào `scripts/crawl_sources_draft.py`, ngay sau `parse_giakedehangpro`:

```python
def parse_noithatlinco(html: str) -> list[RawProduct]:
    """noithatlinco.com - JSON san co nhung trong HTML (khong phai regex
    theo class CSS). Gia la so nguyen thuan, khong co dau phan cach."""
    pattern = re.compile(r'"price":(\d+),.*?"urlPart":"([^"]+)".*?"name":"([^"]+)"')
    base = "https://www.noithatlinco.com"
    products = []
    for price_text, url_part, name in pattern.findall(html):
        products.append(RawProduct(name=name.strip(), url=f"{base}/{url_part}", price=int(price_text)))
    return products
```

- [ ] **Step 2: Thêm entry vào `SOURCES`**

```python
    {
        "label": "Noi That Linco",
        "khu_vuc": "TP.HCM",  # "112A Le Thuc Hoach, Tan Quy, Tan Phu, HCM"
        "urls": ["https://www.noithatlinco.com/sofa-v%C4%83n-ph%C3%B2ng"],
        "parser": parse_noithatlinco,
    },
```

- [ ] **Step 3: Verify bằng lệnh trực tiếp trên site thật**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "
import sys
sys.path.insert(0, 'scripts')
from crawl_sources_draft import fetch, parse_noithatlinco
html = fetch('https://www.noithatlinco.com/sofa-v%C4%83n-ph%C3%B2ng')
products = parse_noithatlinco(html)
print(len(products))
for p in products[:3]:
    print(p)
"
```

Expected: số sản phẩm > 0 (đã xác minh trước ra 72), mỗi `name` chứa chữ
"sofa" hoặc "ghế", `price` là số nguyên trong khoảng vài triệu VND.

- [ ] **Step 4: Chạy toàn bộ script, kiểm tra output cuối**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/crawl_sources_draft.py
```

Expected: log có dòng `Noi That Linco: ... -> ['sofa']`. Mở
`sources_draft.csv`, xác nhận có dòng `TenNCC=Noi That Linco, KhuVuc=TP.HCM,
LoaiSanPham=sofa`.

- [ ] **Step 5: Commit**

```bash
git add scripts/crawl_sources_draft.py
git commit -m "$(cat <<'EOF'
feat(data): add noithatlinco.com parser (sofa, TP.HCM)

Parses the embedded product JSON directly instead of HTML class
selectors — simplest of the 7 sources.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Bảng tổng hợp phân bố cuối script + cập nhật docstring

**Files:**
- Modify: `scripts/crawl_sources_draft.py` (module docstring, `main()`)

**Interfaces:**
- Consumes: `rows: list[dict]` do `build_rows()` trả về (không đổi shape).
- Produces: không có hàm mới — chỉ thêm output ra console.

- [ ] **Step 1: Thêm import `Counter`**

Ở đầu file, thêm vào khối import hiện có:

```python
from collections import Counter
```

- [ ] **Step 2: Cập nhật module docstring**

Sửa dòng đầu docstring (hiện đang nói "Fetch 4 trang"):

```python
"""Crawl-assist cho sources.csv (Task 10, architecture.md muc 4.2).

Fetch 7 trang ban noi that that da khao sat (co gia cong khai hoac danh muc
ro rang), tu dong doan LoaiSanPham tu ten san pham, roi xuat toi da 5 dong
moi to hop (cong ty, khu vuc, danh muc) - uu tien gia thap, tran 6 dong/cong
ty - kem link san pham cu the lam bang chung gia.
```

(Giữ nguyên phần còn lại của docstring — đoạn nói về `sources_draft.csv` là
nháp và `nguoi_thu` không đổi.)

- [ ] **Step 3: Thêm `print_distribution()` và gọi trong `main()`**

Thêm hàm mới ngay trước `main()`:

```python
def print_distribution(rows: list[dict]) -> None:
    by_category = Counter(r["LoaiSanPham"] for r in rows)
    by_region = Counter(r["KhuVuc"] for r in rows)
    print("\nPhan bo cua rieng draft nay (CHUA cong sources.csv that neu da co san):")
    print(f"  Theo LoaiSanPham: {dict(by_category)}")
    print(f"  Theo KhuVuc: {dict(by_region)}")
```

Sửa `main()` để gọi hàm này sau khi ghi CSV:

```python
def main() -> None:
    rows = build_rows()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} dong nhap -> {OUT_PATH}")
    print_distribution(rows)
    print("\nDay la NHAP: mo file, kiem tra tung dong (KhuVuc/LoaiSanPham/gia) "
          "truoc khi copy vao src/tools/mock_data/sources.csv that.")
```

- [ ] **Step 4: Chạy script, xác nhận bảng tổng hợp in đúng**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/crawl_sources_draft.py
```

Expected: 2 dòng cuối in ra `Theo LoaiSanPham: {...}` và `Theo KhuVuc:
{...}`. Đếm tay số dòng trong `sources_draft.csv` theo `LoaiSanPham` (VD
`grep -c ',kệ,' sources_draft.csv` sau khi trừ dòng header) phải khớp con số
script in ra cho `'kệ'`.

- [ ] **Step 5: Commit**

```bash
git add scripts/crawl_sources_draft.py
git commit -m "$(cat <<'EOF'
feat(data): print draft distribution summary after each crawl run

Lets the reviewer see LoaiSanPham/KhuVuc coverage of this draft
immediately, without opening the CSV and counting by hand.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Sửa ghi chú sai trong spec, chạy toàn bộ 7 site, xác minh cuối

**Files:**
- Modify: `docs/superpowers/specs/2026-09-16-mock-data-crawl-expansion-design.md`
  (§3 — sửa ghi chú "không có giá công khai" của giakedehangpro.com)

**Interfaces:** Không có — task xác minh + sửa tài liệu, không đổi code.

- [ ] **Step 1: Sửa dòng sai trong spec §3**

Trong file spec, tìm dòng:

```
| giakedehangpro.com | Hà Nội (444 Phúc Diễn, Nam Từ Liêm) | kệ | Đã khảo sát — static, 1 bước, **không có giá công khai** (toàn "Liên hệ"); parser chưa viết |
```

Sửa thành:

```
| giakedehangpro.com | Hà Nội (444 Phúc Diễn, Nam Từ Liêm) | kệ | Đã crawl (`parse_giakedehangpro`) — static, 1 bước; **có giá công khai** (nhận định "không có giá" lúc khảo sát là sai, do đọc nhầm link menu "Liên hệ" với giá sản phẩm — đã sửa khi viết implementation plan) |
```

- [ ] **Step 2: Chạy toàn bộ script lần cuối, xác minh theo đúng spec §7**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/crawl_sources_draft.py
```

Kiểm tra đủ 3 điều spec §7 đã nêu:
1. Chạy hết không crash; mọi site fetch lỗi/rỗng (nếu có) phải có dòng
   `[WARN]` tương ứng, không im lặng.
2. Mở `src/tools/mock_data/sources_draft.csv` bằng mắt: không công ty nào
   vượt quá 6 dòng (`grep -c ",<TenNCC>," sources_draft.csv` cho từng công
   ty trong cột `TenNCC`); không có 2 dòng cùng `TenNCC` khác `KhuVuc` mà
   trùng `nguon_url`.
3. Bảng tổng hợp cuối script (Task 5) khớp với đếm tay từ chính file CSV.

- [ ] **Step 3: Xác nhận log liệt kê đủ 7 site**

Trong output console, xác nhận có đúng 7 dòng log dạng
`<TenNCC>: N san pham fetch duoc, ...`, tương ứng: Noi That Hunter, Hoa Phat
HCM, Noi That Xuan Hoa, Tekkashop, Ngoc Tin, Gia Ke De Hang Pro, Noi That
Linco. Không có site nào bị `[WARN] ... khong fetch duoc san pham nao` —
nếu có, dừng lại kiểm tra nguyên nhân (site đổi cấu trúc, mạng lỗi) trước
khi coi Task này xong.

- [ ] **Step 4: Commit sửa spec**

```bash
git add docs/superpowers/specs/2026-09-16-mock-data-crawl-expansion-design.md
git commit -m "$(cat <<'EOF'
docs(spec): correct giakedehangpro.com price note after implementation

Confirmed during Task 3 implementation: the site does publish real
prices (price-box/special-price markup); the earlier "no public
price" note in the design spec mistook a menu link for a product
price.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
