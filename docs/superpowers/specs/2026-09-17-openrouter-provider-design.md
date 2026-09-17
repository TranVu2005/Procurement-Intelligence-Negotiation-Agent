# OpenRouter provider cho `src/llm.py`

- Ngày: 2026-09-17
- Owner: Nguoi C (`src/llm.py` thuộc scope C, Decision 3)
- Trạng thái: approved

## Mục tiêu

Cho phép chạy agent (không stub) với model free qua OpenRouter thay vì bắt
buộc `GOOGLE_API_KEY`, để thành viên không có key Gemini vẫn test được luồng
LLM thật.

## Ràng buộc

`AGENT_LLM=stub` đang được dùng khắp nơi: 243 unit test, `scripts/run_autoeval.py
--llm stub`, `scripts/run_loadtest.py`, README, và các file trao đổi trạng thái
của A/B (`B-2026-09-17.md`...). Thay đổi ý nghĩa của biến này là rủi ro cao,
lợi ích thấp — **không đụng vào**.

## Thiết kế

Biến môi trường mới `LLM_PROVIDER=gemini|openrouter` (mặc định `gemini`),
chỉ có tác dụng khi `AGENT_LLM != "stub"`. `AGENT_LLM=stub` vẫn thắng tuyệt
đối như cũ.

```
get_llm(streaming=False, temperature=0.0):
    if AGENT_LLM == "stub": return StubLLM()          # khong doi
    provider = LLM_PROVIDER (default "gemini")
    if provider == "openrouter":
        can OPENROUTER_API_KEY, neu thieu -> EnvironmentError ro rang
        return ChatOpenAI(
            model = OPENROUTER_MODEL (default "google/gemma-4-31b-it:free"),
            api_key = OPENROUTER_API_KEY,
            base_url = "https://openrouter.ai/api/v1",
            temperature, streaming,
        )
    # provider == "gemini": nhanh cu, khong doi
```

Dependency mới: `langchain-openai==1.6.2` (khớp `langchain-core==1.6.2` đang
pin). OpenRouter tương thích OpenAI Chat Completions API nên dùng thẳng
`ChatOpenAI` với `base_url` khác, không cần SDK riêng.

## Model free mặc định

Chọn theo dữ liệu live từ `GET https://openrouter.ai/api/v1/models`, lọc giá
`$0`, kiểm tra 2026-09-17. Default: `google/gemma-4-31b-it:free` (262K
context, đa ngôn ngữ mạnh, cùng họ Google với Gemini đang dùng nên hành vi dễ
so sánh). Ghi thêm 3 lựa chọn thay thế trong README (`z-ai/glm-5.2:free`
context ngắn 32K, `nvidia/nemotron-3-super-120b-a12b:free` lý luận mạnh hơn
nhưng chậm hơn, `openrouter/free` auto-router dùng làm fallback khi bị
rate-limit — free tier OpenRouter giới hạn 20 req/phút, 50 req/ngày không nạp
credit).

## File thay đổi

- `requirements.txt`: thêm `langchain-openai==1.6.2`.
- `src/llm.py`: sửa `get_llm()` như trên.
- `.env.example`: thêm `OPENROUTER_API_KEY=`, `OPENROUTER_MODEL=` (comment
  optional + default).
- `tests/test_llm_factory.py`: test `LLM_PROVIDER=openrouter` trả về
  `ChatOpenAI` đúng `base_url`/`model`; thiếu `OPENROUTER_API_KEY` ->
  `EnvironmentError` nêu rõ tên biến cần set. Không gọi mạng thật.
- `README.md`: thêm mục "Dùng OpenRouter (free)" + bảng model gợi ý.

## Ngoài phạm vi

Không đổi `AGENT_LLM=stub`, không đổi `MODEL_NAME`/nhánh Gemini hiện có,
không thêm provider thứ 3.
