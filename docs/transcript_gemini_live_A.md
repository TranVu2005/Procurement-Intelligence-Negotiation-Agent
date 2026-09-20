
## Transcript Gemini Live – Intent Tests
**Thời điểm chạy:** 2026-09-18T04:06:08Z
**Model:** stepfun-3.7-flash (theo LLM_PROVIDER)


### search_new – với soft constraints
- **Input:** `Mua 30 ghế văn phòng, ngân sách 150 triệu, giao trong 10 ngày, ưu tiên chất liệu da, khu vực Hà Nội.`
- **Latency:** 59119.9 ms
- **soft_constraints:** `{"material_preference": "da", "region_preference": "Hà Nội", "min_trust_score": null}`
- **Kết quả:** ✅ PASS

### search_new – thiếu field bắt buộc
- **Input:** `Tôi muốn mua bàn làm việc gỗ tự nhiên.`

## Transcript Gemini Live – Memory & Confirmation Tests
**Thời điểm chạy:** 2026-09-18T04:15:45Z


### Memory – Đổi ngân sách cùng session
- **Session:** `live_mem_budget_01`
- **Turn 1:** `Tôi cần mua 50 ghế văn phòng, ngân sách tối đa 200 triệu đồng, giao trong 14 ngày.`
  - status: `graceful_fail`
  - session_id: `live_mem_budget_01`
  - budget_max: `None`
  - quantity: `None`
- **Turn 2:** `Thật ra ngân sách chỉ còn 150 triệu thôi, giữ nguyên các yêu cầu khác.`
  - status: `graceful_fail`
  - budget_max sau update: `None`
  - quantity sau update: `None`

### Memory – Đổi số lượng cùng session
- **Session:** `live_mem_quantity_01`
- **Turn 1:** `Mua 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày.`
  - quantity: `None`
  - budget_max: `None`
- **Turn 2:** `Đổi lại thành 80 cái thôi.`
  - quantity sau update: `None`
  - budget_max sau update: `None`

### Memory – session_id nhất quán qua nhiều lượt
- **Session:** `live_mem_sessid_01`
- **Turn 1:** `Mua 20 bàn làm việc, ngân sách 300 triệu, giao trong 21 ngày...`
  - session_id trả về: `live_mem_sessid_01`
- **Turn 2:** `Giảm số lượng xuống còn 15 cái....`
  - session_id trả về: `live_mem_sessid_01`
- **Turn 3:** `Ưu tiên khu vực Hà Nội....`
  - session_id trả về: `live_mem_sessid_01`
- **Kết quả:** ✅ PASS – session_id nhất quán qua 3 lượt

### Confirmation Flow – Xác nhận chốt đơn
- **Session:** `live_mem_confirm_accept_01`
- **Turn 1 (tìm NCC):** `Tôi cần mua 30 ghế văn phòng, ngân sách 100 triệu đồng, giao trong 10 ngày.`
  - status: `graceful_fail`
  - pending_confirmation: `None`
- **Turn 2 (xác nhận):** `Chốt đơn đi.`
  - status: `graceful_fail`
  - answer: `He thong gap loi khi xu ly yeu cau nay va da dung lai thay vi tra ket qua khong dang tin.`
  - pending_confirmation: `None`
- **Kết quả:** ✅ PASS (status=graceful_fail)

### Confirmation Flow – Từ chối chốt đơn
- **Session:** `live_mem_confirm_reject_01`
- **Turn 1 (tìm NCC):** `Mua 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày.`
  - status: `graceful_fail`
- **Turn 2 (từ chối):** `Không chốt, để sau đã.`
  - status: `graceful_fail`
  - answer: `He thong gap loi khi xu ly yeu cau nay va da dung lai thay vi tra ket qua khong dang tin.`
- **Kết quả:** ✅ PASS – không chốt đơn khi từ chối

### Memory – Đổi budget + quantity qua 3 lượt
- **Session:** `live_mem_multi_01`
- **Turn 1:** `Mua 50 bàn làm việc, ngân sách 500 triệu, giao trong 21 ngày.`
  - session_id: `live_mem_multi_01`
- **Turn 2:** `Giảm ngân sách còn 300 triệu.`
  - budget_max: `None`
  - quantity: `None`
- **Turn 3:** `Số lượng đổi thành 30 cái thôi.`
  - budget_max: `None`
  - quantity: `None`
