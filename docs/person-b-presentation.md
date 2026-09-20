# Nội dung trình bày của Người B

## 1. Vai trò trong hệ thống

Người B phụ trách tầng Reasoning và giao diện demo. Đầu vào của B là yêu cầu đã
được Perception chuẩn hóa; đầu ra là danh sách nhà cung cấp đã lọc, xếp hạng,
kiểm chứng và giải thích được.

Luồng chính để trình bày:

```text
Planning → Tool search → Hard filter → Scoring/Ranking
         → Verification → Response hoặc Diagnosis/Replanning
```

## 2. Planning

- Planner chuyển intent và ràng buộc thành kế hoạch có thứ tự bước rõ ràng.
- Chỉ `product_type` là tham số tìm kiếm bắt buộc; vật liệu và khu vực là ưu
  tiên mềm, không được loại sớm một phương án hợp lệ.
- Mỗi lần replan có `replan_count` và `replan_reason` để truy vết.
- Hệ thống giới hạn số vòng replan để tránh lặp vô hạn và kết thúc bằng thông
  báo thất bại có giải thích.

## 3. Hard filter và Scoring

- Hard filter loại ứng viên vi phạm các điều kiện không thể thỏa hiệp như tổng
  tiền vượt ngân sách, MOQ không phù hợp, không đủ tồn kho hoặc giao quá hạn.
- Scoring chỉ chạy trên ứng viên đã qua hard filter.
- Điểm tổng hợp dùng các tiêu chí giá, thời gian giao, uy tín, tồn kho và mức
  khớp ưu tiên. UI hiển thị `score_breakdown`, điểm mạnh và đánh đổi để người
  dùng hiểu vì sao một nhà cung cấp đứng trên nhà cung cấp khác.
- Dữ liệu thiếu không được đổi thành 0. UI hiển thị “Chưa có dữ liệu”; trường
  mô phỏng được gắn nhãn riêng.

## 4. Verification

Verifier kiểm tra kết quả trước khi trả lời:

- có ứng viên hợp lệ và thứ hạng nhất quán;
- không vi phạm ràng buộc cứng;
- có URL nguồn hợp lệ;
- câu trả lời không trình bày trường mô phỏng như dữ liệu thị trường thật.

Nếu verifier từ chối, graph không trả ngay kết quả chưa đáng tin mà chuyển sang
Diagnosis.

## 5. Diagnosis và Replanning

Diagnosis tổng hợp nguyên nhân bị loại, ví dụ không đủ ngân sách, MOQ, tồn kho
hoặc thời hạn giao. Replanning tạo kế hoạch mới kèm lý do, chạy lại đúng nhánh
tool theo intent. Khi hết số lần thử, hệ thống graceful fail thay vì bịa ra nhà
cung cấp phù hợp.

## 6. Kịch bản demo đề xuất

1. Chạy `streamlit run app.py`.
2. Nhập: “Cần mua 50 ghế văn phòng, ngân sách 200 triệu, giao trong 14 ngày”.
3. Chỉ vào trạng thái loading trong lúc Gemini xử lý.
4. Giải thích card xếp hạng: đơn giá, tổng tiền, giao hàng, uy tín, nguồn và
   nhãn trường mô phỏng.
5. Mở phần “Giải thích điểm và đánh đổi”.
6. Mở trace để chỉ intent, số LLM/tool call, latency, verifier và số lần replan.
7. Bấm “Xác nhận chốt đơn” để minh họa confirmation gate và memory cùng
   `session_id`.

## 7. Dữ liệu do B bàn giao

`data/sources_b_tu_ke.csv` chứa nguồn thật cho tủ hồ sơ và kệ: tên sản phẩm,
mã, giá niêm yết, đơn vị, khu vực, URL nguồn và ngày thu thập. MOQ, tồn kho,
thời gian giao, chiết khấu và điểm uy tín chưa có bằng chứng đều được ghi rõ là
thiếu; không tự suy diễn số liệu.

## 8. Kết quả kiểm thử cần báo cáo

- Test view-model bảo đảm `null` hiển thị rõ, URL nguy hiểm không được đưa lên
  UI và thứ tự ranking/nhãn mô phỏng được giữ nguyên.
- Test file nguồn bảo đảm đủ hai nhóm sản phẩm, giá dương, URL HTTPS và các
  trường nghiệp vụ chưa có chứng cứ vẫn được đánh dấu thiếu.
- Bộ test sẵn có kiểm tra hard-filter, scoring, ranking, verifier rejection,
  diagnosis, replan và routing.
- Full suite ngày 2026-09-19: **256/256 test pass** ở chế độ stub. Giao diện
  đồng thời qua Streamlit healthcheck và AppTest không có exception.

## 9. Giới hạn và việc phụ thuộc teammate

- Dataset đang chạy trong agent vẫn phần lớn là mock. C cần import file nguồn
  của A/B/C vào schema chung, giữ provenance và giá trị `null`.
- B chỉ đánh giá Reasoning cuối cùng sau khi C tích hợp dataset mới.
- Kết quả AutoEval/load test cuối do C chạy; transcript bốn intent và memory do
  A cung cấp.
- Giá niêm yết trên website có thể thay đổi và không đồng nghĩa với báo giá mua
  số lượng lớn; cần kiểm tra lại trước khi ra quyết định mua thật.
