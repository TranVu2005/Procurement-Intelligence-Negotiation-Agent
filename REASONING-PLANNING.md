# Reasoning & Planning — trạng thái triển khai

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

## 2. Input và intent của planner

Planner dùng nguyên state schema trong `SYSTEM-RULES.md`:

- Với `search_new`: bắt buộc `session_id`, `product_type`, `quantity`, `budget_max`,
  `delivery_deadline_days`.
- Với `compare_specific`: bắt buộc `session_id`, `quantity` và danh sách
  `supplier_ids`.
- Với `supplier_detail`: bắt buộc `session_id` và `supplier_id`.
- Với `out_of_scope`: chỉ cần `session_id`; planner không tạo tool call mua hàng.
- Tùy chọn: `material_preference`, `region_preference`, `min_trust_score`.
- Không tự suy đoán field bắt buộc còn thiếu.

## 3. Output của planner

`make_plan(state, intent=...)` trả plan theo đúng intent:

```json
{
  "plan_id": "plan_<unique-id>",
  "session_id": "sess_001",
  "intent": "search_new",
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
        "product_type": "ghế văn phòng"
      },
      "reason": "Tìm ứng viên trước khi kiểm tra các ràng buộc",
      "depends_on": []
    }
  ]
}
```

Chỉ tool call thực sự mới nằm trong `steps`. Các bước suy luận nằm trong `workflow`,
vì rule chung quy định `steps[*].action` phải trùng chính xác tên tool của C.

Chất liệu và khu vực là ràng buộc mềm nên plan tìm rộng theo loại sản phẩm; chúng được
dùng để xếp hạng và giải thích trade-off, không được âm thầm biến thành điều kiện loại.

Với `search_new`, `compare_price` chưa được đưa ngay vào executable steps vì
`supplier_ids` chỉ tồn tại sau khi `search_suppliers` trả kết quả. Orchestrator phải lấy
ID thật từ tool output rồi mới tạo call, không dùng ID giả hoặc hard-code. Với
`compare_specific`, planner nhận ID do A trích xuất và tạo trực tiếp bước
`compare_price`.

## 4. Quy tắc lọc và xếp hạng

Ràng buộc cứng được kiểm tra trước khi chấm điểm:

1. Sản phẩm đúng loại.
2. `quantity >= MOQ` và `quantity <= TonKho`.
3. Tổng giá sau chiết khấu không vượt `budget_max`.
4. `ThoiGianGiao <= delivery_deadline_days`.

Ứng viên vi phạm một ràng buộc cứng không được xếp hạng như phương án hợp lệ. Có thể
giữ lại trong danh sách phương án thay thế nhưng phải ghi rõ điều kiện bị vi phạm.

Ràng buộc mềm dùng để xếp hạng/trade-off: chất liệu, khu vực, uy tín, bảo hành. Trọng
số leverage score hiện dùng: giá 30%, MOQ 15%, giao hàng 20%, bảo hành 15%, uy tín
20%. Mỗi thành phần được chuẩn hóa về 0–100 và được trả kèm breakdown để audit.
Nếu bảo hành/uy tín bị thiếu, giá trị giữ nguyên là `null`; công thức tái chuẩn hóa trên
các trọng số còn bằng chứng thay vì tự điền một con số giả.

Nếu hai bản ghi cùng tên nhà cung cấp và cùng loại sản phẩm nhưng có giá/thông số mâu
thuẫn, kết quả chuyển sang `evidence_conflict` và không chọn nhà cung cấp cho tới khi
nguồn được xác minh.

Mỗi ứng viên được xếp hạng còn có chiến lược đàm phán gồm mức chiết khấu mục tiêu,
đòn bẩy có bằng chứng (sản lượng/MOQ, số phương án thay thế, bảo hành, uy tín), nhượng
bộ có thể chấp nhận và guardrail không vượt ngân sách/không tự động chốt đơn.

## 5. Chẩn đoán, xác minh và re-plan

`diagnose(rejected_suppliers)` gom các mã vi phạm hard constraint, đếm số nhà cung
cấp bị ảnh hưởng và tạo `replan_reason` có cấu trúc. Lý do này được chuyển cho
`make_replan`; plan mới luôn có ID mới và tăng `replan_count`.

`verify_output(ranked, req, tool_results)` là cổng cuối trước khi trả lời người dùng.
Kết quả gồm `passed`, danh sách `violations` và danh sách `claims`. Nó kiểm tra lại:

- hard constraints và phép tính tổng tiền;
- nhà cung cấp được đề xuất có thật trong tool output;
- claim quan trọng có evidence và `nguon_url` để trích dẫn.

Nếu verdict không đạt, agent phải diagnose/re-plan hoặc graceful-fail; không được trình
bày một phương án chưa xác minh như kết quả chắc chắn.

### Các nhánh re-plan bắt buộc

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
python -m unittest discover -s tests -p "test_scoring.py" -v
python -m unittest discover -s tests -p "test_verification.py" -v
python -m unittest discover -s tests -p "test_reasoning_tools_integration.py" -v
python -m scripts.demo_e2e
```
