# 🤖 Multi-Agent Vietnamese Fake News Verification System

Hệ thống multi-agent kiểm chứng tin thật/giả tiếng Việt.  
**Không cần GPU** — gọi API LLM qua internet.  
**Không cần training** — hoạt động bằng prompt engineering.  
**Multi-LLM (Mix-AI)** — mỗi Agent dùng 1 LLM riêng biệt, lách Rate Limit miễn phí.  
**Two-Stage Semantic Cache** — câu hỏi tương tự trả kết quả trong < 2 giây.

---

## 📋 Mục lục

1. [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
2. [Cài đặt nhanh](#-cài-đặt-nhanh)
3. [Cách sử dụng](#-cách-sử-dụng)
4. [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
5. [Multi-LLM Architecture (Mix-AI)](#-multi-llm-architecture-mix-ai)
6. [Chi tiết từng Agent](#-chi-tiết-từng-agent)
7. [Two-Stage Semantic Cache](#-two-stage-semantic-cache)
8. [Search Engine & Nguồn tin](#-search-engine--nguồn-tin)
9. [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
10. [Giải thích từng file](#-giải-thích-từng-file)
11. [Cấu hình LLM cho từng Agent](#-cấu-hình-llm-cho-từng-agent)
12. [Customize cho nghiên cứu](#-customize-cho-nghiên-cứu)
13. [Changelog](#-changelog)

---

## 💻 Yêu cầu hệ thống

| Yêu cầu | Chi tiết |
|----------|----------|
| **GPU** | ❌ Không cần (gọi API cloud) |
| **Python** | >= 3.10 |
| **Internet** | ✅ Cần |
| **API Keys** | Groq + Google Gemini (LLM) · Tavily (Search) · MongoDB Atlas (Cache) |

---

## 🚀 Cài đặt nhanh

```bash
# 1. Cài thư viện
cd e:\Research\Code\NCKH\Multi-Agentic
pip install -r requirements.txt

# 2. Tạo file .env
copy .env.example .env

# 3. Điền API keys vào .env:
#    - AGENT1_API_KEY   : Groq API key      → https://console.groq.com/keys
#    - GEMINI_POOL_KEYS : Cụm thẻ Gemini   → Chống Rate Limit 429 (Mới)
#    - TAVILY_API_KEY   : Tavily key        → Cào web thời gian thực
#    - MONGODB_URI      : MongoDB Atlas URI → Lưu trữ Vector Cache

# 4. Chạy CLI (terminal)
python main.py

# 5. Hoặc chạy Web UI (Streamlit)
streamlit run app.py
```

---

## 🎮 Cách sử dụng

```bash
# Chế độ tương tác (mặc định)
python main.py

# Chạy một lần
python main.py --query "Việt Nam đạt á quân AFF Cup 2024"

# Xuất JSON (dùng cho scripting/API)
python main.py --query "..." --json

# Web UI (Streamlit)
streamlit run app.py
```

---

## 🏗️ Kiến trúc hệ thống

```
                     ┌─────────────────────────────────────────────────┐
                     │          Two-Stage Semantic Cache               │
                     │  (MongoDB Atlas Vector Search + Vietnamese NER) │
                     └──────┬──────────────────────────────┬───────────┘
                            │ HIT → trả kết quả < 2s      │ MISS → chạy pipeline
                            ▼                              ▼
User Input ──▶ Normalizer ──▶ Cache Check ──▶ Agent 1 ──▶ Agent 2 ──▶ Agent 3 ──▶ Verdict
                 (Groq)                        (Groq)     (Gemini)    (Gemini/HF)
                                 │
                                 ├─ Tavily API (primary — nhanh, không bị block)
                                 ├─   General search + Gov-focused search (song song)
                                 └─ Web Scraper fallback (BeautifulSoup)
```

**Cách hoạt động:**
1. **Query Normalizer:** LLM Groq chuẩn hóa tin tức cần kiểm chứng, trích xuất con số cốt lõi.
2. **Semantic Cache** kiểm tra MongoDB — nếu câu tương tự đã hỏi → Groq tự động **Dynamic Rewrite** kết hợp văn phong mới và trả kết quả **trong < 2 giây**.
3. Nếu Cache MISS:
   - **Agent 1 (Groq)** phân tích tin → tạo 3 search queries → Tavily search (2 luồng song song) → lấy full content.
   - **Agent 2 (Gemini)** đọc toàn bộ nội dung (tới 100,000 ký tự) → trích xuất facts → phân loại độ uy tín nguồn (Cấp 1/2/3).
   - **Agent 3 (Gemini/HuggingFace)** suy luận và đưa ra Phán định chính thức (THẬT/GIẢ) kèm Bằng chứng + URL chống Hallucination.
4. Kết quả được **lưu vào Cache** cho lần sau
5. Hiển thị trên terminal (Rich formatting) hoặc Web UI (Streamlit)

---

## 🧠 Multi-LLM Architecture (Mix-AI)

Hệ thống sử dụng **3 nhà cung cấp LLM khác nhau** cho 3 Agent, mỗi model được chọn dựa trên thế mạnh riêng:

| Agent | Provider | Model | Lý do chọn |
|-------|----------|-------|------------|
| **Agent 1** — Query | **Groq** | `llama-3.1-8b-instant` | Tốc độ cực nhanh (~0.5s), chỉ cần sinh keywords |
| **Agent 2** — Extractor | **Google Gemini** | `gemini-2.5-flash` | Context 1M token, đọc 5–10 bài báo dài cùng lúc không nghẽn |
| **Agent 3** — Reasoning | **Google Gemini** | `gemini-2.5-flash` | Khả năng lập luận logic cực mạnh, sinh cấu trúc JSON ổn định |

### Tại sao Mix-AI?
- **Lách Rate Limit miễn phí:** 3 API key từ 3 provider = gấp 3 lần tài nguyên, không bao giờ bị lỗi `429 Too Many Requests`
- **Chuyên biệt hóa:** Model nhỏ nhanh cho việc nhẹ, model to cho việc nặng
- **An toàn:** Không cần tạo nhiều tài khoản ảo (vi phạm ToS), chỉ cần 1 account/provider
- **Không tốn chi phí:** Tất cả đều dùng Free Tier

---

## 🤖 Chi tiết từng Agent

### Agent 1: Query Clarifier + Web Crawler (Groq LLaMA-8B)

| | Chi tiết |
|--|---------|
| **Vai trò** | Phân tích tin → Tìm kiếm → Lấy full content bài báo |
| **LLM** | Groq `llama-3.1-8b-instant` — siêu nhanh, max 1024 tokens output |
| **Bước 1** | LLM phân tích claim → tạo 3 search queries tối ưu |
| **Bước 2** | Tavily search × 2 song song: *general* + *gov-focused* |
| **Bước 3** | Dùng `raw_content` Tavily (đã làm sạch) — không cần scrape lại |
| **Fallback** | Nếu Tavily không có content → scrape bằng BeautifulSoup |
| **Output** | Top 5 bài báo sạch, tổng ~35,000–50,000 chars |

### Agent 2: Information Extractor & Summarizer (Google Gemini Flash)

| | Chi tiết |
|--|---------|
| **Vai trò** | Đọc content → Trích xuất → Đánh giá nguồn → Tóm tắt |
| **LLM** | Google Gemini `gemini-2.5-flash` — context window 1M token |
| **Prompt limit** | **100,000 ký tự** (gấp 8x so với Groq), đọc trọn vẹn mọi bài báo |
| **Xử lý** | Key facts, độ tin cậy nguồn (Cấp 1/2/3), phát hiện mâu thuẫn |
| **Output** | Structured JSON với facts, sources, contradictions, consensus score |

### Agent 3: Reasoning & Verdict (HuggingFace Qwen-72B)

| | Chi tiết |
|--|---------|
| **Vai trò** | Suy luận có luận điểm → Phán định cuối cùng |
| **LLM** | Google Gemini `gemini-2.5-flash` — suy luận logic sâu, ổn định |
| **Verdict** | THẬT · GIẢ · CHƯA XÁC ĐỊNH · MỘT PHẦN ĐÚNG |
| **Output** | Verdict + confidence + **luận điểm chi tiết** (tiêu đề + dẫn chứng + link) + nguồn |

---

## ⚡ Two-Stage Semantic Cache

Hệ thống cache 2 lớp giúp giảm thời gian từ **200–300s xuống < 2s** cho câu hỏi tương tự:

```
User Query → Embedding (vietnamese-sbert) → Vector Search (MongoDB Atlas)
                                                    │
                                    ┌───────────────┴───────────────┐
                                    │ Cosine > 0.90?                │
                                    │  YES → NER Compare            │
                                    │    (Chỉ kiểm tra Con Số)      │
                                    │    Khớp 100%? → CACHE HIT ⚡  │
                                    │    Không khớp? → CACHE MISS   │
                                    │  NO → CACHE MISS              │
                                    └───────────────────────────────┘
```

| Lớp | Mục đích | Công nghệ |
|-----|----------|-----------|
| **Lớp 1 (Recall)** | Tìm câu hỏi tương đồng | MongoDB Atlas Vector Search (cosine > 0.90) |
| **Lớp 2 (Precision)** | Xác nhận chính xác | Trích xuất Subset (dò quét 100% các thông số tiền tệ, thời gian, con số) |

### Cấu hình MongoDB Atlas
1. Tạo cluster miễn phí tại [MongoDB Atlas](https://cloud.mongodb.com)
2. Thêm `MONGODB_URI` vào `.env`
3. Tạo Vector Search Index (`vector_index`) trên collection `FakeNewsDB.CacheLogs`:
```json
{
  "type": "vectorSearch",
  "fields": [
    {
      "path": "vector",
      "type": "vector",
      "numDimensions": 768,
      "similarity": "cosine"
    }
  ]
}
```

### Embedding Model
- `keepitreal/vietnamese-sbert` (768 dimensions)
- Tự động download lần đầu, cache lại cho các lần sau

---

## 🔍 Search Engine & Nguồn tin

### Tavily API (Primary)
- **Không bao giờ bị rate-limit** như Google/Bing scraping
- `include_raw_content=True` → lấy full text bài báo (8,000 chars/nguồn)
- Chạy **2 queries song song** mỗi lần search:
  - **General**: tìm rộng mọi nguồn
  - **Gov-focused**: ưu tiên `.gov.vn`, báo nhà nước

### Thang độ ưu tiên nguồn

| Cấp | Nguồn | Score |
|-----|-------|-------|
| 🏛️ **Cấp 1** — Nhà nước | `baochinhphu.vn`, `chinhphu.vn`, `quochoi.vn`, `mofa.gov.vn`, `nhandan.vn`, `vtv.vn`, `vov.vn`, `*.gov.vn`... | 0.95–0.97 |
| 📰 **Cấp 2** — Báo lớn | `vnexpress.net`, `tuoitre.vn`, `thanhnien.vn`, `dantri.com.vn`, `tienphong.vn`, `laodong.vn`... | 0.90 |
| ⚖️ **Cấp 3** — Pháp luật/an ninh | `cand.com.vn`, `baophapluat.vn`, `anninhthudo.vn`... | 0.85 |
| ❌ **Bị loại** — Tiếng Anh | `espn.com`, `bbc.com`, `reuters.com`, `cnn.com`... | Bị exclude |

### Content Processing Pipeline
```
Tavily raw_content
    │
    ├─ _clean_content():
    │    ├─ Xóa markdown links: ![alt](url), [text](url) → text
    │    ├─ Xóa URL thuần, base64 images
    │    ├─ Xóa nav bullet list: * [Text](url)
    │    ├─ Xóa breadcrumb: Văn hóa › Thể thao
    │    └─ Xóa dòng quá ngắn (menu, nút bấm)
    │
    └─ _is_vietnamese(): Kiểm tra tỷ lệ ký tự tiếng Việt ≥ 3%
         └─ Nếu tiếng Anh → skip, dùng snippet ngắn thay thế
```

---

## 📁 Cấu trúc thư mục

```
Multi-Agentic/
├── .env                  ← API keys (3 LLM + Tavily + MongoDB)
├── .env.example          ← Template cấu hình
├── requirements.txt      ← Thư viện cần cài
├── pyrightconfig.json    ← Config Pyright type-checking
├── main.py               ← Điểm chạy chính (CLI, Rich formatting)
├── app.py                ← Giao diện Web (Streamlit)
│
├── config/
│   └── settings.py       ← get_llm_for_agent() — khởi tạo LLM theo Agent
│
├── agents/
│   ├── base_agent.py     ← Base class: call_llm(), parse_json(), retry logic
│   ├── query_agent.py    ← Agent 1 (AGENT1): Tìm kiếm + Cào nội dung
│   ├── extractor_agent.py← Agent 2 (AGENT2): Trích xuất + Tóm tắt
│   └── reasoning_agent.py← Agent 3 (AGENT3): Suy luận + Phán định
│
├── database/
│   └── mongo_cache.py    ← MongoSemanticCache: Two-Stage Cache
│
├── tools/
│   ├── web_search.py     ← Tavily API + fallback Bing/DDG
│   └── web_scraper.py    ← Crawl fallback (BeautifulSoup)
│
├── prompts/              ← Tách riêng prompts (dễ thí nghiệm)
│   ├── query_agent.py
│   ├── extractor_agent.py
│   └── reasoning_agent.py
│
├── graph/
│   ├── state.py          ← Shared state giữa các agents
│   └── workflow.py       ← LangGraph pipeline + cache integration
│
├── utils/
│   └── logger.py         ← Logging utilities
│
└── .vscode/
    └── settings.json     ← Pylance config
```

---

## 📖 Giải thích từng file

### `config/settings.py` — Cấu hình Multi-LLM
- Hàm `get_llm_for_agent(agent_type)`: đọc biến `.env` theo prefix (`AGENT1_*`, `AGENT2_*`, `AGENT3_*`)
- Dùng `ChatOpenAI(base_url=...)` — hoạt động với mọi provider OpenAI-compatible
- Fallback: nếu chưa có biến `AGENTx_API_KEY`, tự động dùng `LLM_API_KEY` cũ

### `agents/base_agent.py` — Base class
- `__init__(name, agent_type_config, max_prompt_chars)`: khởi tạo LLM riêng cho từng Agent
- `call_llm()`: gửi prompt + auto-truncate theo `max_prompt_chars` + retry with backoff khi bị rate limit
- `parse_json_response()`: parse JSON từ response (xử lý markdown code block)
- `add_log()`: ghi log vào shared state

### `agents/query_agent.py` — Agent 1 (Groq)
- Config: `AGENT1` prefix, `max_prompt_chars=12,000`
- Bước 1: LLM phân tích claim → tạo 3 queries
- Bước 2: Tavily search song song (general + gov-focused)
- Bước 3: Dùng Tavily `raw_content` nếu đủ dài; fallback scrape nếu cần
- Lọc URL YouTube/Facebook/TikTok — không có nội dung bài báo
- Output: `crawled_contents` với tổng ~35–50k chars

### `agents/extractor_agent.py` — Agent 2 (Gemini)
- Config: `AGENT2` prefix, `max_prompt_chars=100,000` (tận dụng context 1M token của Gemini)
- Đọc `crawled_contents` → trích xuất facts → phân loại nguồn → tóm tắt
- Output: `extracted_info` (JSON structured)

### `agents/reasoning_agent.py` — Agent 3 (Gemini Focus)
- Config: `AGENT3` prefix, `max_prompt_chars=12,000` (sử dụng `_fix_urls` chống Hallucinations)
- LLM suy luận → luận điểm + dẫn chứng cụ thể + URL bài báo → verdict
- Output: `verdict` gồm: `summary`, `arguments[]`, `reasoning`, `reliable_sources[]`

### `database/mongo_cache.py` — Semantic Cache
- Class `MongoSemanticCache` — core logic Two-Stage Cache
- `_extract_entities()`: Dò quét con số (Numeric Regex) để tránh False Positives từ địa danh
- `check_cache()`: Stage 1 Vector Search → Stage 2 Numeric compare → HIT/MISS
- `save_to_cache()`: Lưu query + embedding + entities + verdict vào MongoDB
- TTL mặc định 7 ngày

### `tools/web_search.py` — Search Engine
- **Primary**: Tavily API (`search_depth=advanced`, `include_raw_content=True`)
- **Gov search**: Tavily với `include_domains=GOV_DOMAINS + TRUSTED_DOMAINS`
- **Fallback**: Bing + DuckDuckGo (nếu không có Tavily key)
- `_clean_content()`: làm sạch raw HTML/Markdown → plain text
- `_is_vietnamese()`: phát hiện tiếng Anh, loại bỏ khỏi context
- Cache kết quả vào `.search_cache.json` — tránh duplicate request

### `tools/web_scraper.py` — Crawl fallback
- requests + BeautifulSoup, UTF-8 tiếng Việt
- CSS selector riêng cho VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí
- Giới hạn 10,000 ký tự/bài — đủ context mà không quá tải LLM

### `prompts/` — Tách riêng prompt cho từng Agent
- `query_agent.py`: Hướng dẫn LLM phân tích claim và tạo search queries
- `extractor_agent.py`: Hướng dẫn LLM trích xuất facts từ bài báo
- `reasoning_agent.py`: Hướng dẫn LLM viết **luận điểm có cấu trúc** + thang ưu tiên nguồn 3 cấp

### `graph/workflow.py` — LangGraph Pipeline
- `create_workflow()`: Tạo graph `START → Agent1 → Agent2 → Agent3 → END`
- `run_verification()`: Chạy pipeline không cache
- `run_verification_with_cache()`: Chạy pipeline CÓ Two-Stage Semantic Cache

### `main.py` — CLI
- Hiển thị với Rich: verdict panel, luận điểm panels, bảng nguồn có cột "Độ tin cậy"
- 3 mode: interactive / single query (`--query`) / JSON output (`--json`)

### `app.py` — Web UI (Streamlit)
- Giao diện chat để nhập tin đồn cần kiểm chứng
- Hiển thị badge thời gian: ⚡ Cache Hit (xanh) / 🧠 Pipeline (tím)
- Luận điểm & bằng chứng dạng expander, nguồn tham khảo có link

---

## ⚙️ Cấu hình LLM cho từng Agent

File `.env` chứa 3 block cấu hình độc lập, mỗi block gồm 5 biến:

```bash
# ==== AGENT 1 - QUERY (Groq - siêu nhanh) ====
AGENT1_BASE_URL=https://api.groq.com/openai/v1
AGENT1_API_KEY=gsk_your_key
AGENT1_MODEL=llama-3.1-8b-instant
AGENT1_TEMPERATURE=0.1
AGENT1_MAX_TOKENS=1024

# ==== AGENT 2 - EXTRACTOR (Google Gemini - context khổng lồ) ====
AGENT2_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AGENT2_API_KEY=your_gemini_key
AGENT2_MODEL=gemini-2.5-flash
AGENT2_TEMPERATURE=0.1
AGENT2_MAX_TOKENS=4096

# ==== AGENT 3 - REASONING (Google Gemini - suy luận mạnh) ====
AGENT3_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AGENT3_API_KEY=your_gemini_key  # Hoặc dùng GEMINI_POOL_KEYS để tự xoay vòng
AGENT3_MODEL=gemini-2.5-flash
AGENT3_TEMPERATURE=0.1
AGENT3_MAX_TOKENS=2048
```

### Đổi model cho bất kỳ Agent nào
Chỉ cần sửa 3 dòng (`BASE_URL`, `API_KEY`, `MODEL`) trong block tương ứng. Ví dụ đổi Agent 3 sang Groq:
```bash
AGENT3_BASE_URL=https://api.groq.com/openai/v1
AGENT3_API_KEY=gsk_your_key
AGENT3_MODEL=qwen-qwq-32b
```

### Providers hỗ trợ
Mọi provider có OpenAI-compatible API đều dùng được:

| Provider | Base URL | Ghi chú |
|----------|----------|---------|
| **Groq** | `https://api.groq.com/openai/v1` | Miễn phí, siêu nhanh |
| **Google Gemini** | `https://generativelanguage.googleapis.com/v1beta/openai/` | Miễn phí, context 1M token |
| **HuggingFace** | `https://router.huggingface.co/v1/` | Miễn phí, nhiều model lớn |
| **OpenAI** | `https://api.openai.com/v1` | Trả phí |
| **Ollama** | `http://localhost:11434/v1` | Local, miễn phí |

**Không cần sửa code. Đổi `.env` → chạy lại.**

---

## 🔬 Customize cho nghiên cứu

### 1. Đổi prompt (không đụng code)
Mở file trong `prompts/` → sửa → chạy lại.

### 2. Thêm nguồn ưu tiên
Trong `tools/web_search.py`, thêm domain vào `GOV_DOMAINS` hoặc `TRUSTED_DOMAINS`.

### 3. Thêm agent
```python
# 1. Tạo agents/new_agent.py (kế thừa BaseAgent, truyền "AGENT4")
# 2. Tạo prompts/new_agent.py
# 3. Thêm node vào graph/workflow.py
# 4. Thêm AGENT4_* vào .env
```

### 4. Đổi search engine
Trong `tools/web_search.py`:
- Có `TAVILY_API_KEY` → dùng Tavily
- Không có → tự động fallback Bing + DuckDuckGo

### 5. Tinh chỉnh Cache
Trong `database/mongo_cache.py`:
- Ngưỡng similarity: thay đổi `SIMILARITY_THRESHOLD` (mặc định 0.90)
- TTL: thay đổi thời gian hết hạn cache (mặc định 7 ngày)

---

## 📋 Changelog

### v4.0 — NCKH Academic Release (Latest)
- **[NEW]** **Query Normalization Layer:** Thêm Agent tiền trạm gọt dũa tin đồn, tăng cực đỉnh tỷ lệ Vector Search.
- **[NEW]** **API Key Rotation:** Tích hợp `GEMINI_POOL_KEYS` vào `.env`, tự động xoay vòng chặn đứng Rate Limit 429.
- **[NEW]** **Dynamic Summary Rewrite:** Tích hợp Groq tự động viết lại Tóm tắt (Cache Hit) cho thuận văn phong người dùng.
- **[BUGFIX]** **Anti-Hallucination URLs:** Loại bỏ tận gốc vấn đề LLM tự sinh địa chỉ web bịa đặt.
- Cấu trúc file cấu hình chuyển đổi mượt mà giữa HuggingFace truyền thống và Gemini Pool.

---

### v3.0 — 2026-03-24 (Multi-LLM Architecture + Semantic Cache)

#### 🧠 Multi-LLM Architecture (Mix-AI)
- **[NEW]** Mỗi Agent dùng 1 LLM riêng biệt: Groq (Agent 1) · Gemini (Agent 2) · HuggingFace (Agent 3)
- **[NEW]** Hàm `get_llm_for_agent()` đọc biến `.env` theo prefix `AGENT1/2/3`
- **[NEW]** `BaseAgent` nhận `agent_type_config` + `max_prompt_chars` riêng cho từng Agent
- **[NEW]** Agent 2 (Gemini) được mở rộng prompt limit lên **100,000 ký tự** (gấp 8x)
- **[RESULT]** Loại bỏ hoàn toàn lỗi Rate Limit `429`, tài nguyên API tăng gấp 3

#### ⚡ Two-Stage Semantic Cache
- **[NEW]** Class `MongoSemanticCache` — cache 2 lớp (Vector Search + NER)
- **[NEW]** Embedding model `keepitreal/vietnamese-sbert` (768d)
- **[NEW]** Tích hợp `underthesea` NER cho tiếng Việt (PER, LOC, ORG)
- **[NEW]** Hàm `run_verification_with_cache()` trong workflow
- **[NEW]** Streamlit UI hiển thị badge Cache Hit / Pipeline
- **[RESULT]** Thời gian response cho câu hỏi tương tự: **200–300s → < 2s**

#### 🛡️ Type Safety & Code Quality
- **[NEW]** Fix toàn bộ 33 lỗi Pylance/Pyright → **0 errors**
- **[NEW]** `pyrightconfig.json` + `.vscode/settings.json` chuẩn mực
- **[NEW]** Type narrowing với `isinstance(x, Tag)` cho BeautifulSoup

#### 🖥️ Web UI (Streamlit)
- **[NEW]** Tệp `app.py` — giao diện chat kiểm chứng tin tức
- **[NEW]** Preload embedding model + MongoDB connection khi app start
- **[NEW]** Badge thời gian suy luận: ⚡ Cache Hit (xanh) / 🧠 Pipeline (tím)

---

### v2.0 — 2026-03-03 (Cải tiến tốc độ & chất lượng)

#### 🔍 Search Engine — Thay hoàn toàn
- **[NEW]** Tích hợp **Tavily API** làm primary search engine
- **[NEW]** Chạy **2 Tavily searches song song**: general + gov-focused
- **[NEW]** `exclude_domains` loại bỏ báo tiếng Anh ngay từ Tavily
- **[KEEP]** Bing + DuckDuckGo làm fallback

#### 🧹 Content Processing — Làm sạch triệt để
- **[NEW]** `_clean_content()`: xóa markdown links, nav items, URL rác, base64 images
- **[NEW]** `_is_vietnamese()`: phát hiện nội dung tiếng Anh
- **[RESULT]** Tổng context: ~8,000 chars → **~35,000–50,000 chars/lần chạy**

#### 🤖 Agent 1 — Crawler cải tiến
- **[NEW]** Dùng Tavily `raw_content` trực tiếp — giảm scraping
- **[NEW]** Filter URL YouTube/Facebook/TikTok
- **[IMPROVED]** Crawl top 3 → **top 5 URLs**, scrape song song `ThreadPoolExecutor`

#### 🧠 Agent 3 — Reasoning cải tiến
- **[NEW]** Yêu cầu **luận điểm có cấu trúc**: tiêu đề → nội dung → dẫn chứng → URL
- **[NEW]** Thang ưu tiên nguồn 3 cấp: Nhà nước > Báo nhà nước > Báo tư nhân

#### ⚡ Tốc độ
- **Search**: tuần tự → **song song** (~3x nhanh hơn)
- **Scrape**: tuần tự → **song song** + skip nếu Tavily đã có content
- **Tổng thời gian**: ~5–6 phút → **~2 phút**

---

### v1.0 — Phiên bản gốc
- 3 agents cơ bản: Query → Extractor → Reasoning
- Google/Bing/DuckDuckGo scraping
- BeautifulSoup web scraper
- 1 LLM duy nhất cho tất cả agents
