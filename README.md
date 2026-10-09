# Procurement Intelligence & Negotiation Agent

Ứng dụng hỗ trợ tìm và so sánh nhà cung cấp nội thất từ yêu cầu bằng tiếng Việt, sau đó đề xuất phương án mua và đàm phán.

Ví dụ:

> Tôi cần mua 50 ghế văn phòng, ngân sách 200 triệu đồng, giao trong 14 ngày, ưu tiên giá.

Ứng dụng lọc theo số lượng, ngân sách và thời hạn giao hàng; xếp hạng các phương án phù hợp, kèm giá, nguồn dữ liệu và lý do lựa chọn. Trong cùng cuộc hội thoại, người dùng có thể đổi ngân sách, số lượng hoặc ưu tiên để xem lại kết quả.

## Chức năng

- Tìm nhà cung cấp, so sánh các phương án và xem thông tin từng nhà cung cấp.
- Xếp hạng theo ưu tiên giá, giao hàng, chất lượng hoặc cân bằng.
- Hỏi lại khi thiếu thông tin; giải thích khi không có phương án phù hợp.
- Lưu lịch sử theo phiên, hiển thị số lần gọi mô hình, tool và thời gian xử lý.

Các thay đổi ràng buộc được lấy từ yêu cầu của người dùng. Chốt đơn cần xác nhận.

## Cài đặt

Môi trường đã kiểm tra: Python 3.14. Các lệnh dưới đây dùng PowerShell trên Windows và chạy từ thư mục gốc dự án.

```powershell
git clone https://github.com/TranVu2005/Procurement-Intelligence-Negotiation-Agent.git
cd Procurement-Intelligence-Negotiation-Agent
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env` và điền khóa API. Cấu hình mặc định dùng Gemini:

```dotenv
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_api_key
```

Ứng dụng cũng hỗ trợ các cấu hình sau:

| Nhà cung cấp | `LLM_PROVIDER` | Khóa API | Biến chọn model |
|---|---|---|---|
| Gemini | `gemini` | `GOOGLE_API_KEY` | Cấu hình trong `src/llm.py` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL` |
| NaraRouter | `nararouter` | `NARAROUTER_API_KEY` | `NARAROUTER_MODEL` |

`.env` chỉ lưu trên máy, không đưa lên Git.

## Chạy ứng dụng

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

Mở http://127.0.0.1:8501/ để sử dụng. Nhập yêu cầu mua hàng vào ô chat; kết quả gồm bảng xếp hạng, thông tin nguồn, giải thích điểm số và gợi ý khi không tìm được phương án.

Nếu dùng dòng lệnh:

```powershell
.venv\Scripts\python.exe -m src.agent
```

SQLite được tạo tự động để lưu phiên hội thoại. Log nằm trong `logs/`, báo cáo nằm trong `reports/`.

## Chạy thử và kiểm tra

Có thể chạy thử mà không cần API key bằng chế độ `stub`:

```powershell
$env:AGENT_LLM="stub"
$env:AGENT_STUB_LATENCY_MEAN_S="0"
$env:AGENT_STUB_LATENCY_STDDEV_S="0"
.venv\Scripts\python.exe -m streamlit run app.py
```

Stub trả về dữ liệu trích xuất và câu trả lời cố định. Chế độ này dùng để kiểm tra luồng xử lý, không dùng để đánh giá khả năng hiểu yêu cầu của mô hình. Muốn gọi mô hình thật trở lại, chạy `Remove-Item Env:AGENT_LLM` trước khi khởi động ứng dụng.

Với các biến stub ở trên, chạy toàn bộ test:

```powershell
.venv\Scripts\python.exe -m unittest discover tests "test_*.py"
```

Test gọi API thật được bỏ qua mặc định. Để chạy riêng các test này sau khi đã cấu hình khóa API:

```powershell
Remove-Item Env:AGENT_LLM -ErrorAction SilentlyContinue
$env:RUN_LIVE_TESTS="1"
.venv\Scripts\python.exe -m unittest tests.test_gemini_intent_live tests.test_gemini_memory_live -v
Remove-Item Env:RUN_LIVE_TESTS
```

Đánh giá bộ câu hỏi và đo tải:

```powershell
# Kiểm tra các bước xử lý bằng dữ liệu cố định
.venv\Scripts\python.exe scripts/run_autoeval.py --eval-set tests/eval_set --llm stub --tier pipeline

# Đánh giá mô hình thật, lặp ba lần
.venv\Scripts\python.exe scripts/run_autoeval.py --eval-set tests/eval_set --llm real --tier llm --repeat 3 --sleep-between 4

# Đo tải với mô hình giả lập
.venv\Scripts\python.exe scripts/run_loadtest.py --levels 1,5,10 --requests-per-level 10 --llm stub
```

Kết quả được ghi vào `reports/`. Kết quả stub chỉ phản ánh luồng xử lý; chất lượng ngôn ngữ và thời gian gọi API cần đo bằng mô hình thật.

## Dữ liệu

Dataset hiện có 106 bản ghi: 100 sản phẩm từ nguồn web và 6 bản ghi dùng để kiểm tra tình huống đặc biệt. Dữ liệu được lưu tại `src/tools/mock_data/suppliers.json`, kèm phiên bản và hash trong file `VERSION` cùng thư mục.

Mỗi bản ghi có URL nguồn và danh sách `simulated_fields` để phân biệt số liệu có nguồn với số liệu mô phỏng. Thông tin chưa có bằng chứng, như bảo hành hoặc uy tín, được giữ là `null`.

CSV nguồn và mẫu báo giá nằm trong `src/tools/mock_data/sources/`. Sau khi bổ sung dữ liệu hợp lệ, sinh lại dataset bằng:

```powershell
.venv\Scripts\python.exe generate_mock_data.py
```

Kiểm tra trước khi làm mới nguồn web:

```powershell
.venv\Scripts\python.exe scripts/refresh_sources.py --dry-run
```

Bỏ `--dry-run` để cập nhật từ web. Báo giá B2B cần có ngày, số lượng, kênh nhận báo giá và bằng chứng; chỉ áp dụng tại số lượng ghi trong báo giá. Ba dòng trong `a_b2b_quotes.csv` còn thiếu thông tin này và cần kiểm tra trước khi sử dụng.

## Cấu trúc dự án

| Thành phần | Vai trò |
|---|---|
| `app.py` | Giao diện Streamlit |
| `src/graph.py`, `src/nodes/` | Điều phối các bước xử lý bằng LangGraph |
| `src/perception/` | Trích yêu cầu từ câu nhập |
| `src/memory/` | Lưu và đọc phiên hội thoại bằng SQLite |
| `src/reasoning/` | Lập kế hoạch, lọc, tính điểm và kiểm chứng kết quả |
| `src/tools/` | Truy vấn nhà cung cấp và xử lý dữ liệu nguồn |
| `src/llm.py` | Cấu hình mô hình và chế độ stub |
| `src/eval/`, `tests/` | Chấm kết quả và kiểm thử |
| `scripts/` | Chạy đánh giá, đo tải và cập nhật dữ liệu |

Mô hình xử lý câu nhập và viết phản hồi. Các bước lọc ràng buộc, tính giá, xếp hạng và kiểm chứng được thực hiện bằng Python. Khi chưa tìm được phương án phù hợp, ứng dụng đưa ra gợi ý để người dùng cân nhắc thay đổi yêu cầu.
