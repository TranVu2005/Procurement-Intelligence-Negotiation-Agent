# Thiết kế: mở rộng crawl-assist cho `sources.csv` (Task 10)

Ngày: 2026-09-16
Trạng thái: đã duyệt qua brainstorming, chờ viết implementation plan
Người sở hữu: Nguoi C (data collection thuộc Đợt 3, `src/tools/mock_data/`)

## 1. Bối cảnh

Task 10 của kế hoạch C ([docs/superpowers/plans/2026-09-14-role-c-implementation.md](../plans/2026-09-14-role-c-implementation.md))
yêu cầu `src/tools/mock_data/sources.csv` — dữ liệu **thật do người thu tay**,
đạt ngưỡng phân bố ở `architecture.md` §4.3 (mỗi `LoaiSanPham` ≥8, mỗi `KhuVuc`
≥5, tổng 50-55 dòng). Hiện trạng: file này **chưa tồn tại**; `suppliers.json`
mới có 32 record thường (không tính EDGE), thiếu nặng ở Đà Nẵng (0), kệ (3/8),
bàn làm việc (5/8).

Phiên làm việc trước đã:
- Khảo sát khả năng crawl các site bán nội thất thật (có giá công khai, danh
  mục sản phẩm rõ), thay vì chỉ đọc blog liệt kê không có giá/danh mục.
- Viết bản nháp `scripts/crawl_sources_draft.py`, crawl thành công 4 site
  (noithathunter.com, hoaphathcm.vn, xuanhoa.vn, tekkashop.com.vn), sinh
  `src/tools/mock_data/sources_draft.csv` (8 dòng).
- Phát hiện và sửa 1 bug phân loại danh mục (sản phẩm ghép như "Bàn làm việc
  ... có tủ" bị bắt nhầm thành tủ hồ sơ) — chuyển từ luật ưu tiên cố định
  sang chọn theo từ khóa xuất hiện sớm nhất trong tên sản phẩm.
- Dùng Playwright MCP khảo sát nhanh 4 site ứng viên còn lại (tìm link danh
  mục, đọc địa chỉ chi nhánh), rồi verify từng site bằng `requests` tĩnh để
  xác nhận có crawl được bằng code không (xem §3) — 3/4 dùng được, 1 loại.

Thiết kế này mở rộng script đó để thu thập **nhiều nhất có thể** trong giới
hạn nguồn đã biết, thay vì chỉ đủ ngưỡng tối thiểu.

## 2. Mục tiêu và phi mục tiêu

**Mục tiêu:**
- Mở rộng `scripts/crawl_sources_draft.py` để crawl 7 site (4 đã có parser +
  3 ứng viên mới đã khảo sát xong ở §3), tối đa hóa số dòng thu được trong
  giới hạn lấy mẫu ở §4.
- Bù cụ thể 2 lỗ hổng vùng/danh mục hiện tại: Đà Nẵng (0 → nhiều hơn), kệ
  (3/8 → gần/đủ 8), đồng thời không bỏ sót Hà Nội (dùng lại nhánh Hà Nội có
  sẵn của các công ty đa chi nhánh — Xuân Hòa, Tekkashop, kesatngoctin.com —
  thay vì tìm site mới).
- Giữ nguyên vòng duyệt tay: script chỉ ghi `sources_draft.csv`, không ghi
  thẳng `sources.csv` thật.

**Phi mục tiêu (ngoài phạm vi thiết kế này):**
- Không tự động merge draft vào `sources.csv` thật — vẫn là copy tay của
  người, theo đúng Task 10 bước 1.
- Không chỉnh sửa `generate_mock_data.py` — đó là việc riêng của Task 10 sau
  khi `sources.csv` thật đã có, không thuộc thiết kế này.
- Không tìm kiếm site mới ngoài 3 ứng viên đã xác định dùng được
  (kesatngoctin.com, giakedehangpro.com, noithatlinco.com — tongkhogiake.com
  đã khảo sát và loại, xem §3) — nếu sau khi crawl hết 7 site vẫn thiếu
  ngưỡng, việc tìm thêm site là một vòng lặp riêng, không nằm trong thiết kế
  này.
- Không đặt số dòng tổng cố định trước — kết quả phụ thuộc site nào crawl
  được, site nào không (xem §6 rủi ro).

## 3. Nguồn dữ liệu

| Site | Vùng | Danh mục dự kiến | Trạng thái parser |
|---|---|---|---|
| noithathunter.com | Đà Nẵng | ghế văn phòng, bàn làm việc, tủ hồ sơ | Đã có (`parse_hunter`) |
| hoaphathcm.vn | TP.HCM | kệ | Đã có (`parse_hoaphathcm`) |
| xuanhoa.vn | Đà Nẵng + Hà Nội | bàn làm việc, tủ hồ sơ, ghế văn phòng | Đã có (`parse_xuanhoa`), cần sửa để tách 2 vùng |
| tekkashop.com.vn | Đà Nẵng + Hà Nội | ghế văn phòng | Đã có (`parse_tekkashop`), cần sửa để tách 2 vùng |
| kesatngoctin.com | TP.HCM + Hà Nội (2 chi nhánh ghi rõ địa chỉ) | kệ | Đã khảo sát — static, 2 bước (trang danh mục lấy tên/link, trang sản phẩm mới có giá `woocommerce-Price-amount`); parser chưa viết |
| giakedehangpro.com | Hà Nội (444 Phúc Diễn, Nam Từ Liêm) | kệ | Đã khảo sát — static, 1 bước, **không có giá công khai** (toàn "Liên hệ"); parser chưa viết |
| noithatlinco.com | TP.HCM (112A Lê Thúc Hoạch, Tân Phú) | sofa | Đã khảo sát — static, JSON nhúng sẵn trong HTML (`name`/`price`/`urlPart`), dễ viết parser nhất trong tất cả các site; parser chưa viết |

**Loại khỏi danh sách: tongkhogiake.com.** Hai lý do: (1) lỗi
`SSL: CERTIFICATE_VERIFY_FAILED` khi fetch bằng `requests` mặc định, phải
tắt xác thực chứng chỉ (`verify=False`) mới qua được; (2) địa chỉ công ty
thật nằm ở Lâm Đồng (ngoài 3 vùng mục tiêu) — các cụm từ "Hà Nội"/"Hồ Chí
Minh"/"Nha Trang" xuất hiện trong trang chỉ là landing page SEO theo tỉnh,
không phải chi nhánh thật, nên không dùng làm `KhuVuc` được theo nguyên tắc
dưới đây.

Với 3 site còn lại (chưa viết parser, nhưng đã xác nhận vùng thật + xác nhận
crawl được bằng `requests` tĩnh, không cần render JS): nếu lúc viết parser
phát sinh thêm chỗ không xác định được `KhuVuc`, **bỏ qua phần đó**, không
gán phỏng đoán. Lý do: `SYSTEM-RULES.md` cấm agent tự điền thông tin còn
thiếu; một dòng dữ liệu "thật" mà tự đoán vùng thì không còn là dữ liệu
thật.

## 4. Chính sách lấy mẫu

- Mỗi tổ hợp `(TenNCC, KhuVuc, LoaiSanPham)`: lấy tối đa **N = 5 dòng**, chọn
  theo giá tăng dần (ưu tiên sản phẩm có giá thật thấp nhất trước — vẫn là
  bằng chứng giá xác thực, không phải lý do nghiệp vụ).
- Trần **6 dòng/công ty** tính trên toàn bộ các tổ hợp của công ty đó. Khi
  chạm trần, dừng thêm dòng mới cho công ty đó và in log rõ số sản phẩm còn
  lại chưa dùng (không âm thầm bỏ).
- Với site có 2 vùng (Xuân Hòa, Tekkashop): fetch trang **một lần**, sau đó
  chia danh sách sản phẩm đã phân loại thành 2 tập con không giao nhau theo
  vòng round-robin theo đúng thứ tự khai trong `SOURCES[i]["khu_vuc"]`
  (sản phẩm thứ lẻ → phần tử đầu của list, thứ chẵn → phần tử thứ hai) rồi
  mới gom nhóm theo tổ hợp. Mục đích: một sản phẩm cụ thể không bị gán làm
  bằng chứng cho 2 dòng khác vùng cùng lúc.
- Không đặt tổng số dòng cố định trước; kết quả phụ thuộc số site crawl được
  và số danh mục nhận diện được trên mỗi site.

## 5. Kiến trúc script

Giữ nguyên 1 file `scripts/crawl_sources_draft.py` (không tách package) —
đây là công cụ dùng vài lần cho việc thu thập dữ liệu, không phải code chạy
runtime của agent, tách package là over-engineering so với quy mô việc.
Cấu trúc hiện có (fetch → parser riêng từng site → `classify()` → gom nhóm →
ghi CSV) được giữ nguyên, chỉ mở rộng các phần sau:

- **`RawProduct`**: không đổi (`name`, `url`, `price`).
- **`classify()`**: không đổi — luật chọn từ khóa xuất hiện sớm nhất trong
  tên đã đúng, đã kiểm chứng qua bug ở phiên trước.
- **`SOURCES`**: field `khu_vuc` đổi kiểu từ `str` sang `str | list[str]`.
  Khi là `list`, hàm gom nhóm biết phải chia round-robin trước (xem §4).
- **3 parser mới**: `parse_kesatngoctin` (2 bước: trang danh mục lấy
  tên/link, trang sản phẩm lấy giá — WooCommerce), `parse_giakedehangpro`
  (1 bước, không giá), `parse_noithatlinco` (1 bước, trích JSON nhúng sẵn
  trong HTML thay vì regex theo class CSS — cấu trúc đã xác nhận ở §3, không
  cần dò lại).
- **`build_rows()`**: thêm bộ đếm `rows_per_company: dict[str, int]` để áp
  trần 6 dòng/công ty; thêm logic chia vùng round-robin khi `khu_vuc` là
  list; đổi từ lấy 1 đại diện/tổ hợp sang lấy tối đa N=5, sắp theo giá tăng
  dần trước, dòng không có giá xếp sau theo đúng thứ tự crawl gốc (trường
  hợp toàn bộ tổ hợp không có giá, như Xuân Hòa — lấy N sản phẩm đầu tiên
  theo thứ tự crawl, không có tiêu chí sắp nào khác để dùng).
- **`main()`**: sau khi ghi CSV, in thêm bảng tổng hợp phân bố của riêng
  draft này (đếm theo `LoaiSanPham` và `KhuVuc`) kèm ghi chú rõ đây là số
  của draft, chưa cộng phần `sources.csv` thật đã có sẵn (nếu có).

### Xử lý lỗi

Giữ nguyên pattern try/except hiện tại quanh từng site trong vòng lặp
`build_rows()`: 1 site fetch lỗi (mạng, bị chặn, HTTP lỗi) hoặc parser ra 0
sản phẩm thì in cảnh báo (`[WARN] ...`) và bỏ qua site đó, không dừng cả
script. Site không xác định được vùng (xem §3) cũng in `[WARN]` và bỏ qua
theo cùng cơ chế.

### Luồng dữ liệu

```
fetch(url) -> html
  -> parser rieng tung site(html) -> list[RawProduct]
  -> classify(product.name) -> LoaiSanPham | None (loai None)
  -> neu khu_vuc la list: chia round-robin theo vung
  -> gom nhom theo (TenNCC, KhuVuc, LoaiSanPham)
  -> lay toi da N=5, uu tien gia thap, ap tran 6 dong/cong ty
  -> ghi src/tools/mock_data/sources_draft.csv
  -> in bang tong hop phan bo (LoaiSanPham x KhuVuc) cua draft
```

## 6. Rủi ro

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| Site đã khảo sát cấu trúc HTML thay đổi giữa lúc khảo sát và lúc viết parser (trang thương mại cập nhật theme) | Parser viết theo cấu trúc cũ không khớp nữa | Try/except cô lập theo site (§5); nếu 1-2 site thất bại, các site còn lại vẫn chạy và ghi được phần của mình |
| Site không có địa chỉ vùng rõ ràng, hoặc lỗi SSL cert khi fetch (đã gặp ở tongkhogiake.com) | Không có `KhuVuc` đáng tin, hoặc không fetch được | Bỏ qua site đó hoàn toàn (§3), không đoán vùng và không tắt xác thực SSL để cố lấy bằng được |
| Sau khi crawl hết 7 site vẫn chưa đạt ngưỡng kệ/Đà Nẵng | `sources.csv` thật (sau khi người duyệt) có thể vẫn thiếu, cần thêm site hoặc nhập tay bù | Bảng tổng hợp cuối script (§5) cho thấy ngay chỗ còn thiếu để quyết định vòng tiếp theo — không nằm trong scope thiết kế này |
| Trần 6 dòng/công ty cắt bớt đúng lúc công ty đó đang bù đúng danh mục thiếu | Dataset không tối ưu bù lỗ hổng dù có đủ sản phẩm | Chấp nhận trade-off đã chọn ở Phần A (ưu tiên đa dạng công ty hơn tối đa hoá theo lỗ hổng); log rõ số bị cắt để người tự quyết định nới trần nếu cần |

## 7. Xác minh sau khi implement

Không phải unit test theo nghĩa `unittest` (đây là script thu thập dữ liệu
một lần, không phải logic agent) — xác minh bằng cách chạy thực tế:

1. `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/crawl_sources_draft.py`
   chạy hết không crash, mỗi site fetch lỗi/rỗng phải có dòng `[WARN]` tương
   ứng chứ không im lặng.
2. Mở `sources_draft.csv`, kiểm tra bằng mắt: không dòng nào company vượt 6
   dòng; không dòng nào trùng `nguon_url` giữa 2 `KhuVuc` khác nhau của cùng
   1 công ty (kiểm tra round-robin không bị lỗi).
3. Bảng tổng hợp cuối script khớp với đếm thủ công từ chính file CSV vừa
   ghi (sanity check logic gom nhóm không lệch với logic in báo cáo).
