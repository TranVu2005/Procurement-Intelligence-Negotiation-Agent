# Hợp đồng giao diện — Procurement Intelligence & Negotiation Agent (Nội thất)

Tài liệu này là **nguồn sự thật duy nhất** về dữ liệu trao đổi giữa 3 module. Khi code,
không ai được tự ý đổi field/tên mà không cập nhật lại file này và báo 2 người còn lại.

---

## 1. State Schema (A sở hữu — B, C chỉ đọc)

Lưu trong SQLite, expose ra dạng dict/JSON khi A truyền cho B/C dùng.

```json
{
  "session_id": "sess_001",
  "created_at": "2026-09-08T10:00:00",
  "updated_at": "2026-09-08T10:05:00",

  "intent": "search_new",
  "supplier_ids": ["NCC001", "NCC002"],
  "supplier_id": null,

  "hard_constraints": {
    "product_type": "ghế văn phòng",
    "quantity": 50,
    "budget_max": 200000000,
    "delivery_deadline_days": 14
  },

  "soft_constraints": {
    "material_preference": "gỗ tự nhiên",
    "region_preference": null,
    "min_trust_score": 4.0
  },

  "conversation_history": [
    {"role": "user", "content": "Tôi cần mua 50 ghế văn phòng...", "timestamp": "2026-09-08T10:00:00"},
    {"role": "agent", "content": "Đã ghi nhận yêu cầu...", "timestamp": "2026-09-08T10:00:05"}
  ],

  "decisions_made": [
    {"supplier_id": "NCC001", "confirmed_at": "2026-09-08T10:04:00"}
  ]
}
```

**Quy tắc field:**

| Field | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `intent` | string | có | `search_new` \| `compare_specific` \| `supplier_detail` \| `out_of_scope` — do Perception ghi, B/C đọc để định tuyến |
| `supplier_ids` | list[string] | không | danh sách MaNCC khi intent=`compare_specific`; `[]` nếu không có |
| `supplier_id` | string \| null | không | MaNCC cụ thể khi intent=`supplier_detail`; `null` nếu không có |
| `product_type` | string | có\* | enum gợi ý: ghế văn phòng, bàn làm việc, tủ hồ sơ, kệ, sofa... (\*bắt buộc khi `search_new`) |
| `quantity` | int | có\* | > 0, nếu ≤0 → lỗi validate ở Perception (\*bắt buộc khi `search_new` hoặc `compare_specific`) |
| `budget_max` | float (VND) | có\* | tổng ngân sách, không phải đơn giá (\*bắt buộc khi `search_new`) |
| `delivery_deadline_days` | int | có\* | số ngày kể từ hôm nay (\*bắt buộc khi `search_new`) |
| `material_preference` | string \| null | không | ràng buộc mềm |
| `region_preference` | string \| null | không | ràng buộc mềm |
| `min_trust_score` | float \| null | không | ràng buộc mềm, 1–5 |
| `decisions_made` | list | không | lịch sử lựa chọn đã chốt, dùng để tránh hỏi lại |

**Quy tắc cập nhật:** khi khách đổi yêu cầu, A **ghi đè** field liên quan trong
`hard_constraints`/`soft_constraints`, không giữ song song bản cũ — B/C luôn đọc bản
mới nhất từ `updated_at`.

---

## 2. Plan Format (B sở hữu — C đọc để thực thi)

```json
{
  "plan_id": "plan_001",
  "session_id": "sess_001",
  "status": "executing",
  "replan_count": 0,
  "replan_reason": null,
  "steps": [
    {
      "step_id": 1,
      "action": "search_suppliers",
      "params": {"product_type": "ghế văn phòng"},
      "reason": "tìm rộng theo loại sản phẩm; chất liệu và khu vực được chấm như ưu tiên mềm ở bước sau",
      "depends_on": []
    },
    {
      "step_id": 2,
      "action": "compare_price",
      "params": {"supplier_ids": ["NCC001", "NCC002"], "quantity": 50},
      "reason": "tính leverage score dựa trên giá sau chiết khấu",
      "depends_on": [1]
    }
  ]
}
```

**Quy tắc:**
- `action` **phải trùng tuyệt đối** với tên tool trong mục 3 — B không được tự đặt tên action mới mà không báo C.
- `status` nhận 1 trong: `draft` / `executing` / `completed` / `replanned`.
- Khi re-plan (hết hàng, MOQ vượt, tool lỗi...), B tạo `plan_id` mới, tăng `replan_count`, điền `replan_reason` — không sửa đè lên plan cũ (để có thể truy vết lại như rubric yêu cầu).

---

## 3. Tool Contract (C sở hữu — B gọi qua LangChain Tool)

Mọi tool trả lỗi theo **cùng một format** để B xử lý re-plan thống nhất:
```json
{"error": true, "error_type": "no_match | timeout | invalid_input | tool_unavailable", "message": "mô tả ngắn"}
```

### `search_suppliers`
- **Input:** `{"product_type": "string (required)", "material": "string | null", "region": "string | null"}`
- **Output:**
```json
{"suppliers": [
  {"MaNCC": "NCC001", "TenNCC": "Nội Thất Hòa Phát", "Gia": 850000, "MOQ": 20,
   "ThoiGianGiao": 10, "DiemUyTin": 4.5,
   "nguon_url": "https://...", "nguon_type": "public_listing",
   "fetched_at": "2026-09-13", "simulated_fields": ["Gia", "MOQ", "TonKho"]}
]}
```
(chỉ trả field tóm tắt, không trả full record). Bốn trường nguồn luôn có mặt; nếu bản ghi gốc
thiếu, `nguon_url`/`nguon_type`/`fetched_at` là `null` và `simulated_fields` là `[]` — không được
làm crash response (Quyết định 2, architecture.md §8.2).

### `get_supplier_detail`
- **Input:** `{"supplier_id": "string (required)"}`
- **Output:** toàn bộ 13 field gốc của NCC (MaNCC, TenNCC, LoaiSanPham, ChatLieu, Gia, DonViTinh, MOQ, TonKho, ThoiGianGiao, BaoHanh, ChietKhauTheoSoLuong, DiemUyTin, KhuVuc) cộng bốn trường nguồn (`nguon_url`, `nguon_type`, `fetched_at`, `simulated_fields`) đã có sẵn trên bản ghi gốc — tool này không cần sửa để lộ chúng ra.

### `compare_price`
- **Input:** `{"supplier_ids": ["string", "..."], "quantity": "int (required)"}`
- **Output:**
```json
{"comparisons": [
  {"MaNCC": "NCC001", "unit_price": 850000, "discount_applied": "5%", "total_price": 40375000,
   "meets_moq": true, "nguon_url": "https://...", "simulated_fields": ["Gia", "MOQ", "TonKho"]}
]}
```

**Quy tắc:** nếu 1 supplier_id không tồn tại hoặc dataset thiếu field → trả lỗi theo format chung ở trên cho riêng phần tử đó, không làm fail cả response. Phần tử không lỗi mang thêm `nguon_url` và
`simulated_fields` để mọi claim về `total_price` truy được về nguồn. Phần tử lỗi giữ nguyên shape
lỗi chuẩn, không có hai trường này.

### `confirm_order` — đã cập nhật vai trò (buổi họp 4, 15/9)
- **Vai trò mới**: node `confirm_gate` (pipeline, không phải LLM-callable tool) — chặn lại chờ người dùng xác nhận tường minh (architecture.md §3.5).
- **Input/Output giữ nguyên** như cũ.

### Quyết định §8.1 (tất cả đã đồng ý)
`material` và `region` bị bỏ hoàn toàn khỏi `plan.steps[0].params` (không truyền `None`, không truyền gì). Soft preferences được đọc từ `soft_constraints` bởi `evaluate_candidates()` sau khi search xong. A đã cập nhật `tests/test_integration_ab.py` theo.

- **Input:** `{"supplier_id": "string (required)", "quantity": "int (required)", "confirmed": "bool (required)"}`
- **Output nếu `confirmed=true` và hợp lệ:**
```json
{"order_confirmed": true, "supplier_id": "NCC001", "quantity": 50, "confirmed_at": "2026-09-15T09:00:00"}
```
- **Output nếu `confirmed=false`/thiếu:** lỗi theo format chung, `error_type: "invalid_input"`.

**Quy tắc:** đây là GATE cho hành động hậu quả cao (SYSTEM-RULES.md mục 3) — tool **không bao giờ** tự
suy ra `confirmed=true`; B/agent chỉ được truyền `confirmed=true` sau khi người dùng đã xác nhận rõ
ràng trong hội thoại. Tool này **không** ghi vào `decisions_made` (thuộc `src/memory`, Nguoi A sở hữu) —
chỉ trả kết quả xác nhận/từ chối, việc ghi state là bước riêng sau đó của agent/A.

### Retry/backoff cho lỗi tạm thời (nội bộ C, không phải tool mới)
`src/tools/retry.py::call_with_retry()` bọc quanh 1 lệnh gọi tool, tự retry (backoff mũ 2, tối đa 2 lần)
khi `error_type` là `timeout` hoặc `tool_unavailable`. Lỗi xác định (`no_match`, `invalid_input`) KHÔNG
retry. Không đổi input/output của 3 tool hiện có — B có thể chọn gọi tool trực tiếp hoặc qua
`call_with_retry(tool_func, ...)`, không bắt buộc phải cập nhật gì ở B nếu chưa dùng.

---

## Bảng ký xác nhận

Mỗi người đọc kỹ phần mình sẽ dùng nhiều nhất (A đọc kỹ mục 1, B đọc kỹ mục 2, C đọc kỹ mục 3) nhưng **cả 3 đều phải xác nhận cả 3 mục**, vì cả 3 module đọc-ghi chéo nhau.

| Người | Đã đọc | Đồng ý | Đề xuất sửa (nếu có) | Ngày ký |
|---|---|---|---|---|
| A | ☑ | ☑ | Đồng ý quyết định §8.1: bỏ material/region khỏi plan.steps[0].params; bổ sung `intent`, `supplier_ids`, `supplier_id` vào §1 (17/9/2026) | 15/9/2026 |
| B | ☑ | ☑ | Đồng ý §8.1; đã nối node reasoning thật và cập nhật ví dụ plan/test theo contract | 16/9/2026 |
| C | ☑ | ☑ | | 18/9/2026 |

> Sau khi cả 3 tick xong, coi đây là bản khóa (frozen) cho buổi họp 2 (10/9). Muốn đổi field sau mốc này phải báo cả nhóm trước khi sửa code.
