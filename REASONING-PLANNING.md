# Reasoning & Planning — thiết kế cho buổi họp 10/09

**Owner:** Người B  
**Phạm vi:** đọc state của A, lập kế hoạch và ra quyết định; chỉ gọi tool theo contract của C.

## 1. Luồng xử lý

```text
Structured state (A)
        |
        v
validate_state --------------------------> thiếu/sai dữ liệu: hỏi lại, không tự điền
        |
        v
search_suppliers (tool C)
        |
        v
filter_hard_constraints ----------------> không còn ứng viên: chẩn đoán + re-plan
        |
        v
compare_price (tool C)
        |
        v
rank_candidates + leverage_score
        |
        v
generate_recommendation
        |
        v
verify_output ---------------------------> sai constraint/tổng tiền: re-plan
        |
        v
Recommendation + evidence + negotiation strategy
```

Re-plan luôn tạo `plan_id` mới, ghi `replan_reason`, tăng `replan_count` và dừng sau
tối đa 3 lần. Khi quá giới hạn, agent graceful-fail và nói rõ chưa đủ bằng chứng hoặc
cần người dùng điều chỉnh yêu cầu.

## 2. Input của planner

Planner dùng nguyên state schema trong `SYSTEM-RULES.md`:

- Bắt buộc: `session_id`, `product_type`, `quantity`, `budget_max`,
  `delivery_deadline_days`.
- Tùy chọn: `material_preference`, `region_preference`, `min_trust_score`.
- Không tự suy đoán field bắt buộc còn thiếu.

## 3. Output của planner

`make_plan(state)` trả đúng plan contract:

```json
{
  "plan_id": "plan_<unique-id>",
  "session_id": "sess_001",
  "status": "draft",
  "replan_count": 0,
  "replan_reason": null,
  "workflow": [
    {"name": "validate_state", "kind": "reasoning"},
    {"name": "search_suppliers", "kind": "tool"}
  ],
  "steps": [
    {
      "step_id": 1,
      "action": "search_suppliers",
      "params": {
        "product_type": "ghế văn phòng",
        "material": "gỗ tự nhiên",
        "region": "Hà Nội"
      },
      "reason": "Tìm ứng viên trước khi kiểm tra các ràng buộc",
      "depends_on": []
    }
  ]
}
```

Chỉ tool call thực sự mới nằm trong `steps`. Các bước suy luận nằm trong `workflow`,
vì rule chung quy định `steps[*].action` phải trùng chính xác tên tool của C.

`compare_price` chưa được đưa ngay vào executable steps vì `supplier_ids` chỉ tồn tại
sau khi `search_suppliers` trả kết quả. Orchestrator phải lấy ID thật từ tool output rồi
mới tạo call, không dùng ID giả hoặc hard-code.

## 4. Quy tắc lọc và xếp hạng

Ràng buộc cứng được kiểm tra trước khi chấm điểm:

1. Sản phẩm đúng loại.
2. `quantity >= MOQ` và `quantity <= TonKho`.
3. Tổng giá sau chiết khấu không vượt `budget_max`.
4. `ThoiGianGiao <= delivery_deadline_days`.

Ứng viên vi phạm một ràng buộc cứng không được xếp hạng như phương án hợp lệ. Có thể
giữ lại trong danh sách phương án thay thế nhưng phải ghi rõ điều kiện bị vi phạm.

Ràng buộc mềm dùng để xếp hạng/trade-off: chất liệu, khu vực, uy tín, bảo hành. Trọng
số leverage score sẽ được chốt ở deliverable kế tiếp sau khi A/B/C thống nhất ý nghĩa
và miền giá trị của các field.

## 5. Các nhánh re-plan bắt buộc

| Tình huống | Nguyên nhân được ghi | Hướng thay thế |
|---|---|---|
| Hết hàng | `stock_below_quantity` | chia đơn, giảm số lượng đợt đầu hoặc NCC khác |
| MOQ quá cao | `quantity_below_moq` | gom đơn, thương lượng MOQ hoặc NCC khác |
| Tất cả giao trễ | `delivery_deadline_unmet` | nới deadline, giao nhiều đợt hoặc NCC gần hơn |
| Không đúng vật liệu | `material_not_found` | hỏi người dùng có chấp nhận vật liệu gần nhất |
| Tool lỗi | `timeout/tool_unavailable` | retry có giới hạn, fallback hoặc graceful failure |

## 6. Kịch bản ráp thử trong họp

Input: mua 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày; ưu tiên gỗ tự
nhiên, Hà Nội và uy tín từ 4.0.

1. A trả structured state đúng schema.
2. B gọi `make_plan(state)` và tạo call `search_suppliers`.
3. C chạy tool và trả supplier records có nguồn gốc từ mock dataset.
4. B lọc MOQ/tồn kho/ngân sách/deadline trước, sau đó mới so sánh ràng buộc mềm.
5. Nếu không có ứng viên, B tạo plan mới có lý do; không sửa đè plan cũ.
6. Log của C chứng minh input, tool call, output, latency và trạng thái.

## 7. Chạy kiểm tra phần B

Từ thư mục gốc repository:

```bash
python -m unittest discover -s tests -p "test_planner.py" -v
```
