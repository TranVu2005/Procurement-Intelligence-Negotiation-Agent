# RULE CHUNG HỆ THỐNG — Procurement Intelligence & Negotiation Agent (Nội thất)

**Version: v1 · Ngày tạo: 08/9/2026**

Mọi người **bắt buộc đọc và tuân theo** file này khi code. Nếu rule ở đây khác với
những gì đang code, dừng lại và sửa rule (mục 7) trước, không tự ý code lệch rồi
tính sau — lệch từ đầu sẽ vỡ ở lúc tích hợp cuối kỳ.

---

## 1. Ranh giới sở hữu module

| Module                    | Sở hữu bởi | Phạm vi                                                 |
| ------------------------- | ---------- | ------------------------------------------------------- |
| Perception + Memory       | **A**      | Parse input tự nhiên, state schema, SQLite              |
| Reasoning & Planning      | **B**      | Task decomposition, leverage score, re-plan logic       |
| Action/Tool Use + Logging | **C**      | Tool contract, mock dataset, tracing, xử lý lỗi hạ tầng |

**Rule:** muốn sửa field/logic thuộc phần người khác sở hữu → phải hỏi và được
đồng ý trước, không tự ý đổi rồi báo sau.

---

## 2. Data contract (bắt buộc dùng đúng, không tự đổi tên field)

### 2.1 State Schema (A sở hữu — B, C chỉ đọc)

```json
{
  "session_id": "sess_001",
  "created_at": "2026-09-08T10:00:00",
  "updated_at": "2026-09-08T10:05:00",

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
    { "role": "user", "content": "...", "timestamp": "2026-09-08T10:00:00" }
  ],

  "decisions_made": [
    { "supplier_id": "NCC001", "confirmed_at": "2026-09-08T10:04:00" }
  ]
}
```

| Field                    | Kiểu           | Bắt buộc | Ghi chú                                               |
| ------------------------ | -------------- | -------- | ----------------------------------------------------- |
| `product_type`           | string         | có       | enum: ghế văn phòng, bàn làm việc, tủ hồ sơ, kệ, sofa |
| `quantity`               | int            | có       | > 0                                                   |
| `budget_max`             | float (VND)    | có       | tổng ngân sách                                        |
| `delivery_deadline_days` | int            | có       | số ngày kể từ hôm nay                                 |
| `material_preference`    | string \| null | không    | ràng buộc mềm                                         |
| `region_preference`      | string \| null | không    | ràng buộc mềm                                         |
| `min_trust_score`        | float \| null  | không    | ràng buộc mềm, 1–5                                    |

**Quy tắc cập nhật:** khi khách đổi yêu cầu, A **ghi đè** field liên quan, không giữ
song song bản cũ. Mọi field phải truy ngược được về input gốc nào sinh ra nó.

### 2.2 Plan Format (B sở hữu — C đọc để thực thi)

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
      "params": { "product_type": "ghế văn phòng", "material": "gỗ tự nhiên" },
      "reason": "lọc theo ràng buộc cứng/mềm",
      "depends_on": []
    }
  ]
}
```

- `action` **phải trùng tuyệt đối, phân biệt hoa/thường**, với tên tool ở mục 2.3.
- `status` ∈ {`draft`, `executing`, `completed`, `replanned`}.
- Khi re-plan: tạo `plan_id` mới, tăng `replan_count`, điền `replan_reason` — **không sửa đè** plan cũ, để giữ audit trail.

### 2.3 Tool Contract (C sở hữu — B gọi qua LangChain Tool)

Mọi tool lỗi trả **cùng một format**:

```json
{
  "error": true,
  "error_type": "no_match | timeout | invalid_input | tool_unavailable",
  "message": "mô tả ngắn"
}
```

**`search_suppliers`**

- Input: `{"product_type": "string (required)", "material": "string|null", "region": "string|null"}`
- Output: `{"suppliers": [{"MaNCC", "TenNCC", "Gia", "MOQ", "ThoiGianGiao", "DiemUyTin"}]}`

**`get_supplier_detail`**

- Input: `{"supplier_id": "string (required)"}`
- Output: full record 13 field (`MaNCC, TenNCC, LoaiSanPham, ChatLieu, Gia, DonViTinh, MOQ, TonKho, ThoiGianGiao, BaoHanh, ChietKhauTheoSoLuong, DiemUyTin, KhuVuc`)

**`compare_price`**

- Input: `{"supplier_ids": ["string"], "quantity": "int (required)"}`
- Output: `{"comparisons": [{"MaNCC", "unit_price", "discount_applied", "total_price", "meets_moq"}]}`

Nếu 1 supplier_id lỗi → trả lỗi cho riêng phần tử đó, không fail cả response.

---

## 3. Quy tắc chung toàn hệ thống

- Timestamp: luôn ISO 8601 (`YYYY-MM-DDTHH:MM:SS`).
- Tiền tệ: VND, kiểu number thuần, không ký tự "đ"/dấu phẩy.
- Tool luôn trả JSON có cấu trúc, **không trả text tự do**.
- **Không hard-code** input mẫu vào logic xử lý (rubric chấm điểm 0 nếu phát hiện).
- Agent **không được tự ý điền ngầm** thông tin quan trọng còn thiếu — phải hỏi lại người dùng hoặc nêu rõ giả định đang dùng.
- Khi ràng buộc mâu thuẫn (VD: ngân sách không đủ cho MOQ tối thiểu) → phải cảnh báo rõ, không được âm thầm bỏ qua.

## 4. Quy tắc xử lý lỗi & re-plan

- Mọi tool lỗi trả đúng format chuẩn ở mục 2.3.
- B phải re-plan có lý do rõ ràng khi: tool lỗi, state thay đổi, kết quả không thỏa ràng buộc cứng.
- Giới hạn tối đa **3 lần re-plan** cho cùng 1 yêu cầu — quá số này phải trả lời "chưa đủ bằng chứng/cần hỗ trợ thêm", không lặp vô hạn.

## 5. Quy tắc Memory & Session

- Không bao giờ trộn dữ liệu giữa 2 `session_id` khác nhau.
- Khi đổi yêu cầu, ghi đè field liên quan, không giữ song song bản cũ.
- Mọi field trong state phải audit được về nguồn gốc.

## 6. Quy tắc Logging & bảo mật

- Mọi tool call log tối thiểu: `trace_id, timestamp, tool_name, input (đã che field nhạy cảm), status, latency`.
- **Không bao giờ** log API key/secret dưới bất kỳ hình thức nào.
- Hành động hậu quả cao (VD "chốt đơn") bắt buộc có bước confirmation, không tự động thực thi.

## 7. Quy tắc thay đổi rule/schema

- Muốn đổi field, tên action, hoặc bất kỳ mục nào ở trên → sửa trực tiếp trong file này, tăng version (mục "Change log" bên dưới), báo trong group chat, chỉ áp dụng sau khi **cả 3 người xác nhận lại**.
- Không sửa ngầm trong code mà không cập nhật file này — đây là nguồn sự thật duy nhất.

## 8. Quy tắc test/AutoEval

- Mọi tính năng mới khi hoàn thành phải có ít nhất 1 test case tương ứng trong `tests/eval_set/`.
- Không coi tính năng là "xong" nếu chưa chạy qua ít nhất 1 case lỗi liên quan (theo mục 4).
