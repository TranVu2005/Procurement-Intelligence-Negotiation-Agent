# Kế hoạch dự án — Procurement Intelligence & Negotiation Agent (Nội thất)
### AI Guru AEF1 — cập nhật sau buổi họp 1 (08/9)

**Nhóm:** A (Perception + Memory) · B (Reasoning & Planning) · C (Action/Tool Use + Logging)
**Thời gian còn lại:** 08/9 → 18/9 · **Báo cáo/demo:** 18–19/9

## Quyết định đã chốt ở buổi họp 1
| Câu hỏi | Quyết định |
|---|---|
| Phạm vi ngành hàng | Giới hạn **1 ngành: Nội thất** (bàn, ghế, tủ, kệ...) |
| Chiến lược đàm phán | Mix: **leverage score** (định lượng) + giải thích định tính đi kèm |
| Nguồn dữ liệu tuần đầu | **Mock dataset**, web search thật để sau |
| Framework | **LangChain** (AgentExecutor + Tool) |
| Lưu state | **SQLite** |
| Edge case | Theo bộ AutoEval trong docx nhóm đã có + bổ sung case đặc thù ngành nội thất |

**Giả định mock dataset** (câu 3–4 chưa chốt số liệu cụ thể): ~15–20 nhà cung cấp, field: `MaNCC, TenNCC, LoaiSanPham, ChatLieu, Gia, DonViTinh, MOQ, TonKho, ThoiGianGiao(ngày), BaoHanh(tháng), ChietKhauTheoSoLuong, DiemUyTin(1-5), KhuVuc`. Chỉnh lại nếu nhóm muốn khác trước khi C bắt tay dựng dataset.

**Edge case đặc thù ngành nội thất cần thêm vào AutoEval** (ngoài các case chung: happy path / thiếu-mơ hồ thông tin / mâu thuẫn ràng buộc / tool lỗi / adversarial):
- Hết hàng / NCC ngừng kinh doanh sản phẩm được hỏi
- MOQ của NCC lớn hơn số lượng khách yêu cầu
- Thời gian giao của mọi NCC đều vượt deadline khách đưa ra
- Chất liệu/kích thước yêu cầu không tồn tại trong catalog nào
- Ngân sách đủ số lượng nhưng không đủ chất lượng/chất liệu mong muốn

---

## Việc cần làm NGAY — Thứ Ba 08/9 (trong ngày hôm nay)

| Người | Việc cần làm | Hạn |
|---|---|---|
| Cả 3 | Dựng khung repo dùng chung, cài LangChain + SQLite driver | Tối 08/9 |
| Cả 3 | Viết lại 3 hợp đồng giao diện (state schema, plan format, tool contract) với field cụ thể ngành nội thất, ký xác nhận | Tối 08/9 |
| **C** | Phác thảo danh sách field mock dataset (bảng trên), gửi A/B góp ý | Tối 08/9 |
| **A + B** | Phản hồi góp ý field dataset của C | Sáng 09/9 |
| Cả 3 | Bổ sung 5 edge case đặc thù nội thất vào file AutoEval docx | 09/9 |

---

## Buổi họp 2 — Thứ Năm 10/9

| Người | Việc cần hoàn thành trước họp | Hạn nộp |
|---|---|---|
| **A** | Schema SQLite hoàn chỉnh (session, constraints cứng/mềm, lịch sử hội thoại) | Tối 09/9 |
| **A** | Parser nhận input tự nhiên → structured state: loại sản phẩm, số lượng, chất liệu, ngân sách, deadline giao hàng; tách rõ ràng buộc cứng/mềm | **Sáng 10/9 (trước họp)** |
| **B** | Sơ đồ phân rã nhiệm vụ dạng LangChain chain (tìm NCC → lọc ràng buộc cứng → so sánh → tính leverage score → đề xuất + chiến lược đàm phán) — bản thiết kế | **Sáng 10/9 (trước họp)** |
| **C** | Mock dataset nội thất hoàn chỉnh (15–20 NCC) | Tối 09/9 |
| **C** | 2 LangChain Tool: `search_suppliers`, `get_supplier_detail` chạy trên mock data + logging cơ bản | **Sáng 10/9 (trước họp)** |

**Agenda:** ráp thử 1 câu hỏi mẫu end-to-end; đối chiếu field giữa parser (A), plan (B) và dataset (C); chỉnh lại hợp đồng giao diện nếu lệch.

---

## Buổi họp 3 — Thứ Bảy 12/9

| Người | Việc cần hoàn thành trước họp | Hạn nộp |
|---|---|---|
| **A** | Multi-turn: cập nhật/ghi đè state đúng khi khách đổi yêu cầu (không giữ đồng thời state cũ+mới) | 11/9 |
| **A** | Input validation: sản phẩm không có trong catalog, số lượng ≤0, ngân sách không hợp lệ | **Sáng 12/9 (trước họp)** |
| **B** | Công thức leverage score (trọng số: giá, MOQ, thời gian giao, bảo hành, điểm uy tín) | 11/9 |
| **B** | Hàm sinh giải thích định tính đi kèm điểm số + xử lý trade-off khi ràng buộc mềm xung đột | **Sáng 12/9 (trước họp)** |
| **C** | Tool `compare_price` / tính chiết khấu theo số lượng | 11/9 |
| **C** | Xử lý lỗi tool gracefully (NCC không tồn tại, field thiếu) + logging đầy đủ trace ID | **Sáng 12/9 (trước họp)** |

**Agenda:** demo full happy path — kiểm tra leverage score có thực sự bám dữ liệu (giá/MOQ/uy tín) chứ không phải giải thích chung chung.

---

## Buổi họp 4 — Thứ Ba 15/9

| Người | Việc cần hoàn thành trước họp | Hạn nộp |
|---|---|---|
| **A** | Session isolation (state reset đúng giữa các phiên, không rò dữ liệu) | **13/9** |
| **B** | Re-plan cho các case: hết hàng, MOQ > yêu cầu, mọi NCC đều trễ deadline — sinh phương án thay thế có nguyên nhân rõ, không lặp vô hạn | **14/9** |
| **C** | Retry/backoff/fallback khi tool lỗi (mô phỏng timeout/HTTP lỗi) | 13/9 |
| **C** | Cơ chế confirmation trước khi "chốt đơn" giả lập; rà log không lộ dữ liệu nhạy cảm | **14/9** |
| Cả 3 | Dựng bộ test hoàn chỉnh trong AutoEval (đủ case đã liệt kê), gán pass/fail rõ ràng | **Sáng 15/9 (trước họp)** |

**Agenda:** demo 2 luồng bắt buộc theo rubric 2.2.1 (thành công + có sự cố/re-plan); review bộ test cùng nhau, đảm bảo không case nào "hard-code theo test".

---

## Buổi họp 5 — Thứ Năm 17/9

| Người | Việc cần hoàn thành trước họp | Hạn nộp |
|---|---|---|
| Cả 3 | Chạy AutoEval, báo cáo 5 chỉ số: Task Success, Constraint Satisfaction, Tool Call Success, Citation/Evidence Correctness, Failure Recovery | 16/9 |
| Cả 3 | Performance test (TTFT, latency P50/P95, throughput) + load test nếu hạ tầng cho phép | 16/9 |
| Cả 3 | Cost/resource: số lần gọi LLM/tool trung bình, token, cost/request | 16/9 |
| Cả 3 | Phân tích lỗi có chiều sâu (failure mode, nguyên nhân gốc, giới hạn hệ thống) | **Sáng 17/9 (trước họp)** |
| Cả 3 | Bản nháp báo cáo + slide | **Sáng 17/9 (trước họp)** |

**Agenda:** chốt số liệu cuối; luyện vấn đáp chéo (mỗi người hỏi-đáp phần của 2 người kia); phân vai trình bày.

---

## 18/9 — Tổng duyệt cuối (buffer, không họp chính thức)

| Người | Việc cần làm | Hạn |
|---|---|---|
| Cả 3 | Đóng băng code, chạy lại toàn bộ bộ test một lần cuối | Sáng 18/9 |
| Cả 3 | Duyệt lại 2 kịch bản demo bắt buộc | Trưa 18/9 |
| Cả 3 | Rà báo cáo/slide — mọi khẳng định phải truy được tới input/state/tool call/nguồn | Chiều 18/9 |
| Từng người | Chuẩn bị phần trình bày đóng góp cá nhân | Tối 18/9 |

---

## Rủi ro cần né để không bị "điểm 0 toàn mục"
- **Perception:** không hard-code input, không tự điền ngầm thông tin, không lặng lẽ bỏ qua ràng buộc mâu thuẫn.
- **Memory:** không lẫn dữ liệu giữa các phiên; giải thích được state đến từ đâu.
- **Action/Tool Use:** không lộ secret/API key trong log; hành động hậu quả cao phải có xác nhận.
- **Feedback/Evaluation:** không chỉ trình bày vài transcript chọn tay — phải có oracle pass/fail rõ ràng cho từng case.
