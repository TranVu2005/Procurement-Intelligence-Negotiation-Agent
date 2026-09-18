# PHÂN CÔNG CÔNG VIỆC CÒN LẠI – 2026-09-17

## 1. Trạng thái hiện tại

- Core agent đã chạy end-to-end bằng Gemini thật.
- Full test: **247/247 pass**, 1 integration test được skip.
- Luồng `search_new` đã tìm, lọc, xếp hạng và xác minh được nhà cung cấp.
- Dataset hiện có 38 bản ghi và đã có URL nguồn, nhưng phần lớn trường nghiệp vụ vẫn là dữ liệu mô phỏng.
- Giao diện hiện tại mới là CLI, chưa có giao diện web phục vụ demo.

## 2. Những nhóm việc còn lại

1. Thu thập và tích hợp dữ liệu thật.
2. Sửa routing còn lỗi trong graph.
3. Xây dựng giao diện demo.
4. Test Gemini thật, memory và confirmation flow.
5. Chạy AutoEval, load test và hoàn thiện báo cáo.

## 3. Phân công cho A – Perception và Memory

### Việc cần làm

1. Test Gemini thật đủ bốn intent:
   - `search_new`;
   - `compare_specific`;
   - `supplier_detail`;
   - `out_of_scope`.
2. Test hội thoại nhiều lượt:
   - thay đổi ngân sách;
   - thay đổi số lượng;
   - giữ đúng `session_id`;
   - xác nhận chốt đơn;
   - từ chối chốt đơn.
3. Kiểm tra parser khi dữ liệu có trường `null` hoặc thiếu trường không bắt buộc.
4. Thu thập dữ liệu thật cho:
   - ghế văn phòng;
   - bàn làm việc.

### Sản phẩm bàn giao

- Commit test cho bốn intent và memory.
- Transcript chạy Gemini thật.
- Danh sách lỗi perception/memory còn tồn tại.
- File dữ liệu nguồn của ghế văn phòng và bàn làm việc.

## 4. Phân công cho B – Reasoning, UI và kiểm thử tích hợp

### Việc cần làm

1. Xây dựng giao diện demo có:
   - giao diện chat;
   - trạng thái loading khi chờ Gemini;
   - lịch sử hội thoại;
   - bảng hoặc card nhà cung cấp;
   - giá, tổng tiền, thời gian giao và điểm uy tín;
   - link nguồn có thể bấm;
   - nhãn phân biệt dữ liệu thật và dữ liệu mô phỏng;
   - nút xác nhận chốt đơn;
   - phần metric/trace thu gọn.
2. Kiểm tra Reasoning trên dataset mới:
   - hard-filter;
   - scoring;
   - ranking;
   - verifier;
   - diagnosis và replan.
3. Viết test cho:
   - dữ liệu thiếu hoặc `null`;
   - dữ liệu có nguồn;
   - tính đúng đắn của xếp hạng;
   - kết quả bị verifier từ chối.
4. Thu thập dữ liệu thật cho:
   - tủ hồ sơ;
   - kệ.
5. Chuẩn bị phần thuyết trình Planning, Scoring, Verification và Replanning.

### Sản phẩm bàn giao

- Giao diện demo chạy được với `run_request()`.
- Test và kết quả kiểm tra Reasoning.
- File dữ liệu nguồn của tủ hồ sơ và kệ.
- Nội dung trình bày phần của B.

## 5. Phân công cho C – Data, Tools, Graph và Evaluation

### Việc cần làm

1. Sửa routing sau `replan`:
   - `search_new` → `tool_search`;
   - `compare_specific` → `tool_compare`;
   - `supplier_detail` → `tool_detail`;
   - intent ngoài phạm vi không được gọi tool.
2. Thêm regression test để compare/detail không rơi sang search sau replan.
3. Hoàn thiện pipeline dữ liệu thật:
   - crawler hoặc importer;
   - chuẩn hóa về schema chung;
   - `source_url`;
   - `collected_at` hoặc `last_checked`;
   - đánh dấu trường mô phỏng;
   - giữ `null` nếu không có dữ liệu thật, không tự bịa số liệu.
4. Thu thập dữ liệu thật cho sofa.
5. Tích hợp toàn bộ dữ liệu của A, B và C vào tools.
6. Tạo file version dữ liệu:

   ```text
   src/tools/mock_data/VERSION
   ```

7. Chạy AutoEval bằng Gemini thật.
8. Chạy load test và xuất báo cáo vào `reports/`.

### Sản phẩm bàn giao

- Commit sửa graph và regression test.
- Dataset đã chuẩn hóa.
- Dataset version.
- Báo cáo AutoEval và load test.
- File dữ liệu nguồn của sofa.

## 6. Schema tối thiểu cho dữ liệu thật

Mỗi bản ghi tối thiểu cần có:

```text
supplier_id
supplier_name
product_type
product_name
price
unit
region
source_url
collected_at
```

Các trường MOQ, tồn kho, thời gian giao, bảo hành, chiết khấu và điểm uy tín chỉ được coi là dữ liệu thật khi có nguồn kiểm chứng. Nếu không có nguồn thì phải để `null` hoặc ghi rõ là dữ liệu mô phỏng.

## 7. Việc cả nhóm cùng hoàn thành

1. Cập nhật README và architecture theo trạng thái mới.
2. Sửa số lượng test từ 243 thành 247.
3. Viết rõ dữ liệu nào là thật, dữ liệu nào là mô phỏng.
4. Chuẩn bị slide gồm:
   - bài toán và phạm vi;
   - kiến trúc LangGraph;
   - vai trò A/B/C;
   - Perception → Planning → Tools → Verification → Response;
   - memory và confirmation gate;
   - nguồn dữ liệu;
   - kết quả test và AutoEval;
   - latency và load test;
   - hạn chế và hướng phát triển.
5. Chuẩn bị kịch bản demo và diễn tập trước buổi báo cáo.

## 8. Thứ tự thực hiện

1. C sửa routing và chốt schema dữ liệu.
2. A, B và C thu thập dữ liệu theo nhóm sản phẩm được giao.
3. C tích hợp dữ liệu vào tools.
4. B làm giao diện song song bằng contract hiện tại.
5. A test bốn intent và memory.
6. B kiểm tra scoring và verifier trên dữ liệu mới.
7. C chạy AutoEval và load test.
8. Cả nhóm cập nhật tài liệu, làm slide và diễn tập demo.

## 9. Phụ thuộc cần lưu ý

- B có thể bắt đầu làm giao diện ngay, không cần chờ dataset hoàn chỉnh.
- B cần chờ dataset tích hợp của C để chạy đánh giá Reasoning cuối cùng.
- C cần dữ liệu nguồn của A và B trước khi tạo dataset hoàn chỉnh.
- Cả nhóm cần kết quả AutoEval và load test trước khi chốt báo cáo.
