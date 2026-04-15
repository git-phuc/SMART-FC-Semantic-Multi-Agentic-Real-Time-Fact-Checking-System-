# BÁO CÁO KỸ THUẬT HỆ THỐNG SMART-FC
## SEMANTIC MULTI-AGENTIC REAL-TIME FACT-CHECKING SYSTEM

> **Đề tài Nghiên cứu Khoa học (NCKH)**  
> Hệ thống Kiểm chứng Thông tin Tự động Thời gian Thực cho Ngôn ngữ Tiếng Việt  
> Kiến trúc: Autonomous Multi-Agent Pipeline v6.0

---

# CHƯƠNG 1: CƠ SỞ LÝ THUYẾT VÀ TỔNG QUAN NGHIÊN CỨU

## 1.1. Bối cảnh và Động lực Nghiên cứu

### 1.1.1. Hiện trạng Tin giả tại Việt Nam

Sự bùng nổ của mạng xã hội và nền báo chí kỹ thuật số đã tạo ra một bối cảnh thông tin phức tạp, nơi tin giả (Fake News) lan truyền với tốc độ vượt xa khả năng kiểm chứng thủ công của con người. Tại Việt Nam, bài toán này mang những đặc thù riêng biệt:

- **Cơ chế công khai bắt buộc:** Một số nhóm sự kiện — khởi tố, bắt giam, ban hành nghị định, bổ nhiệm quan chức — khi xảy ra bắt buộc phải được đưa tin trong vòng 24 giờ. Điều này tạo ra một **đặc thù suy luận phủ định (Deductive Falsification)**: sự vắng bóng hoàn toàn của thông tin trên hệ thống báo chí chính thống là bằng chứng mạnh cho thấy sự kiện không tồn tại.

- **Dạng tin giả phổ biến nhất:** Nghiên cứu thực nghiệm xác định dạng tin giả nguy hiểm nhất là **"sự kiện thật bọc luận điểm giả" (True Event + False Narrative)**: lấy một sự kiện có thật làm mỏ neo tin cậy, rồi gán ghép thêm các cáo buộc về âm mưu, động cơ không có bằng chứng.

- **Rào cản ngôn ngữ:** Tiếng Việt là ngôn ngữ có cấu trúc phức tạp và thiếu các bộ dữ liệu đánh giá chuẩn (Benchmark Dataset) cho bài toán kiểm chứng thông tin.

### 1.1.2. Hạn chế của Các Phương pháp Truyền thống

| Phương pháp | Hạn chế chính |
|---|---|
| **Kiểm chứng thủ công** | Không thể mở rộng quy mô, độ trễ từ vài giờ đến vài ngày |
| **RAG truyền thống** | Context Swelling: Fixed-size Chunking gây đứt gãy ngữ nghĩa (Coreference Error) |
| **Mô hình phân loại học sâu** | Thiếu khả năng giải thích (Explainability), không cập nhật theo thời gian thực |
| **LLM thuần túy (Zero-shot)** | Hallucination cao, không có nguồn trích dẫn thực tế |

---

## 1.2. Tổng quan Các Công nghệ Nền tảng

### 1.2.1. Mô hình Ngôn ngữ Lớn (Large Language Models)

| Mô hình | Nhà cung cấp | Điểm mạnh được khai thác |
|---|---|---|
| **Llama-3.1-8B-Instant** | Meta / Groq | Độ trễ cực thấp (<1s), phân tích ý định và tạo từ khóa |
| **Gemini-2.5-Flash-Lite** | Google | Cửa sổ ngữ cảnh 1 triệu token, đọc toàn văn tài liệu dài |
| **GPT-4o-Mini** | OpenAI | Năng lực suy luận logic vượt trội, phân tích phức tạp đa chiều |

### 1.2.2. Kiến trúc Đa tác tử (Multi-Agent Architecture)

Kiến trúc Đa tác tử là mô hình tổ chức phần mềm trong đó nhiều thực thể AI tự trị (Autonomous Agents) phối hợp để giải quyết bài toán phức tạp. Mỗi agent chuyên môn hóa vào một nhiệm vụ cụ thể, giao tiếp qua **trạng thái chia sẻ (Shared State)** trung tâm.

Ưu điểm so với LLM đơn lẻ:
- **Phân tách mối quan tâm (Separation of Concerns):** Mỗi agent được tối ưu hóa cho đúng nhiệm vụ
- **Khả năng mở rộng (Scalability):** Có thể thay thế hoặc nâng cấp từng agent độc lập
- **Vòng lặp phản hồi (Cyclic Control Flow):** Cho phép agent phản hồi ngược lên các bước trước

### 1.2.3. LangGraph — Bộ khung Đồ thị Tác tử

LangGraph cho phép định nghĩa luồng thực thi của các agent dưới dạng **đồ thị có hướng (Directed Graph)**. Hỗ trợ **đồ thị chu kỳ (Cyclic Graph)** — cho phép reasoning_agent trỏ ngược lại query_agent khi cần, thực hiện U-Turn Feedback Loop.

### 1.2.4. Nguyên lý Anti-Swelling (RAG Cải tiến)

**Context Swelling:** RAG truyền thống băm tài liệu thành các đoạn ~500 từ, gây đứt gãy ngữ nghĩa. Ví dụ: Đoạn 1 lưu _"Ông Nguyễn Văn A là Giám đốc"_, Đoạn 2 lưu _"Hắn ta đã tham ô 100 tỷ"_ — khi chỉ lấy Đoạn 2, AI không biết "hắn ta" là ai.

**Giải pháp Anti-Swelling:** Tận dụng cửa sổ ngữ cảnh 1 triệu token của Gemini Flash để nạp nguyên khối tài liệu. Mô hình đọc toàn văn, giữ nguyên mạch coreference, sau đó nén xuống JSON cô đặc cho Agent 3.

### 1.2.5. Semantic Caching và Named Entity Recognition

**Semantic Caching:** Lưu trữ kết quả dựa trên độ tương đồng ngữ nghĩa (Cosine Similarity) của câu hỏi. Phản hồi < 2 giây cho các claim tương tự.

**Named Entity Recognition (NER):** Nhận dạng thực thể (tên người, tổ chức, số liệu) để đảm bảo hai câu hỏi giống ngữ nghĩa nhưng khác số liệu quan trọng sẽ không được phục vụ từ cache sai.

---

## 1.3. Tổng quan Nghiên cứu Liên quan

| Hướng tiếp cận | Đại diện | Hạn chế |
|---|---|---|
| Phân loại học sâu | BERT, PhoBERT fine-tuning | Thiếu explainability, không cập nhật thời gian thực |
| Kiểm chứng truy xuất | FEVER, KGAT, MultiFC | Phụ thuộc Knowledge Base tĩnh |
| LLM Zero-shot | GPT-4, Gemini trực tiếp | Hallucination cao, không trích dẫn nguồn |
| **Multi-Agent + RAG (SMART-FC)** | **Đề tài này** | **Giải quyết cả 3 hạn chế trên** |

**Ba khoảng trống mà SMART-FC lấp đầy:**
1. Thiếu hệ thống fact-checking thời gian thực cho tiếng Việt với web search + domain knowledge
2. Chưa có cơ chế tự sửa lỗi (Self-Correction) trong pipeline fact-checking
3. Chưa giải quyết dạng tin giả "sự kiện thật bọc luận điểm giả"

---

# CHƯƠNG 2: PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG SMART-FC

## 2.1. Tổng quan Kiến trúc 3 Lớp

```
==========================================================================
                 SMART-FC SYSTEM — 3-LAYER ARCHITECTURE
==========================================================================

[ USER (Streamlit / API) ] --(Gửi claim)--> [ FastAPI BACKEND ]
                                                     |
                                                     v
    +----------------------------------------------------------+
    |  LỚP 1: SEMANTIC CACHE (MongoDB + SBERT + NER)           |
    |  Phòng tuyến đầu tiên — Phản hồi trong < 2 giây          |
    +----------------------------------------------------------+
                | HIT --> Trả kết quả ngay
                | MISS -->
                v
    +----------------------------------------------------------+
    |  LỚP 2: MULTI-AGENT LANGGRAPH PIPELINE                   |
    |  Agent 1 (Groq) -> Agent 2 (Gemini) -> Agent 3 (GPT)    |
    |  Với U-Turn Feedback Loop tự trị                          |
    +----------------------------------------------------------+
                |
                v
    +----------------------------------------------------------+
    |  LỚP 3: LƯU TRỮ VÀ XUẤT BẢN                              |
    |  MongoDB Cache + Streamlit UI + API Response              |
    +----------------------------------------------------------+
```

---

## 2.2. LỚP 1: Hệ thống Caching Ngữ nghĩa Hai Tầng

### 2.2.1. Tầng 1: Vector Search (Độ thu hồi — Recall)

Mô hình `vietnamese-sbert` chuyển đổi mỗi claim thành vector 768 chiều. Lập chỉ mục trong MongoDB Atlas với cấu trúc **KNN Search**. Ngưỡng: Cosine Similarity > 0.82 → đánh dấu "nghi ngờ trùng", chuyển sang Tầng 2.

### 2.2.2. Tầng 2: NER Entity Guard (Độ chuẩn xác — Precision)

```
Câu cũ:  "Tài xế BMW tông 15 chiếc xe máy"
Câu mới: "Tài xế BMW tông tận 50 chiếc xe máy"
→ Cosine Similarity: ~98% (gần giống nhau)
→ NER Guard: 15 ≠ 50 → MISMATCH → Bắt buộc chạy lại pipeline
```

Sử dụng Regex Pattern Matching trích xuất thực thể số. Nếu bất kỳ thực thể số nào lệch → Cache MISS bắt buộc.

### 2.2.3. Quick Rewrite khi Cache HIT

Groq (Llama) viết lại nhanh phần `summary` phù hợp cách diễn đạt người hỏi, giữ nguyên kết luận và bằng chứng. Tốn thêm ~2 giây.

---

## 2.3. LỚP 2: Multi-Agent LangGraph Pipeline

### 2.3.1. Trạng thái Chia sẻ (Shared State)

```python
class VerificationState(TypedDict):
    user_input: str           # Claim gốc từ người dùng
    clarified_queries: list   # Các từ khóa tìm kiếm (Agent 1)
    crawled_contents: list    # Nội dung bài báo + Trust Score (Agent 1)
    extracted_info: dict      # JSON tóm tắt cô đặc (Agent 2)
    verdict: dict             # Phán quyết cuối cùng (Agent 3)
    agent_logs: list          # Nhật ký thực thi từng bước
    retry_count: int          # Bộ đếm vòng lặp phản hồi
    feedback_to_agent1: str   # Tín hiệu phản hồi Agent 3 → Agent 1
```

### 2.3.2. Sơ đồ Đồ thị LangGraph

```
START
  |
  v
+-------------------------------+
| query_agent (Agent 1)          |<---- (U-Turn Feedback Loop)
| Groq / Llama-3.1-8B            |               ^
+-------------------------------+               |
  |                                             |
  v                                             |
+-------------------------------+               |
| extractor_agent (Agent 2)      |               |
| Google Gemini 2.5 Flash Lite   |               |
+-------------------------------+               |
  |                                             |
  v                                             |
+-------------------------------+               |
| reasoning_agent (Agent 3)      |-(feedback!="")-+
| OpenAI GPT-4o-mini             |
+-------------------------------+
  | (feedback="")
  v
 END → Cache + Frontend
```

---

### 2.3.3. AGENT 1: Query Agent (Groq / Llama-3.1-8B)

**Vai trò:** Radar tìm kiếm thông minh — phân tích claim, sinh từ khóa thích nghi, thực thi tìm kiếm, và chấm điểm tín nhiệm nguồn.

**Bước 1 — Phân tích Intent & Sinh Adaptive Queries:**
Xác định Subject, Event, Figures. Adaptive Query Count: đơn giản → 1 query; phức tạp → 2-3 queries.

**Bước 2 — Web Search + API Rotation Pool:**
Pool 5+ Tavily API keys xoay vòng tự động. Engine Fallback: Tavily → Bing → DuckDuckGo.

**Bước 3 — Multivariate Trust Scoring Engine:**

```
C(doc) = min(1.0, W_domain + W_relevance × exp(-λ × t))
```

Trong đó:
- W_domain: Trọng số tên miền theo bảng phân cấp 4 bậc:
  - Bậc 1 (+0.45): baochinhphu.vn, quochoi.vn, *.gov.vn
  - Bậc 2 (+0.40): vtv.vn, vov.vn, nhandan.vn
  - Bậc 3 (+0.25–0.35): tuoitre.vn, vnexpress.net, dantri.com.vn
  - Bậc Bét (+0.0): Blog, diễn đàn, mạng xã hội
- W_relevance: Điểm liên quan từ Tavily
- exp(-λ×t): Hàm suy giảm thời gian (λ=0.02, t=số ngày)

**Bước 4 — Web Crawling:**
Ưu tiên nội dung từ Tavily Content. Fallback sang WebScraper với timeout 15 giây/URL.

---

### 2.3.4. AGENT 2: Extractor Agent (Google Gemini 2.5 Flash Lite)

**Vai trò:** Nhà máy lọc thô theo triết lý Anti-Swelling.

**Bước 1 — Top-K Source Filtering:**
Chọn Top 5 nguồn có Trust Score cao nhất từ crawled_contents.

**Bước 2 — Data Formatting & Prompt Structuring:**
1. Data Unpacking: Giải nén dict các trường
2. Context Serialization: Nối 5 văn bản thành cuộn Markdown có ranh giới
3. Dynamic Prompt Injection: Nhúng vào template với {claim}, {crawled_data}, {source_count}=5

**Bước 3 — Holistic Extraction & Anti-Swelling:**
Toàn bộ khối văn bản (~50,000–100,000 ký tự) nạp vào Gemini Flash — không có bước chunking. Zero-Judgment Constraint: tuyệt đối không phán xét Thật/Giả.

Output JSON chuẩn hóa:
```json
{
  "total_sources": 5,
  "sources": [{
    "source_url": "https://...",
    "source_name": "VnExpress",
    "title": "Tiêu đề bài báo",
    "summary": "Tóm tắt 3-5 câu trung thực",
    "key_facts": ["Fact 1", "Fact 2", "Fact 3"],
    "has_content": true
  }]
}
```

---

### 2.3.5. AGENT 3: Reasoning Agent (OpenAI GPT-4o-Mini)

**Vai trò:** Cơ quan phán quyết trung tâm — suy luận đa tầng và đưa ra phán quyết minh bạch.

**Bước 1 — State Ingestion & Evidence Preparation:**
Tiếp nhận extracted_info, bổ sung URL Whitelist. LLM bị ràng buộc chỉ được dùng URL từ danh sách thật.

**Bước 2 — Multi-Layer Reasoning (Khung Tư duy 4 Lớp):**

- **Layer 1 — Source Credibility Filtering:**
  Phân loại nguồn theo thang 4 cấp. Loại bỏ nguồn Cấp 4 và nguồn chỉ trùng keyword.

- **Layer 2 — Claim Context Classification:**
  - Nhà nước/Pháp lý → Vắng bóng = bằng chứng phủ định (Deductive Falsification)
  - Xã hội/Học thuật → Vắng bóng = bình thường, không suy diễn

- **Layer 3 — Evidence Cross-Referencing + Verify Every Assertion:**

  Cấp 1 — Factual Core Verification: Đối chiếu sự kiện nền (tên, chức danh, số liệu) với nguồn uy tín.

  Cấp 2 — Narrative Layer Verification (Nguyên lý then chốt):
  ```
  Ví dụ:
  "Ông A tái đắc cử"            → [Sự kiện nền] → Báo xác nhận → CÓ THẬT
  "...do khuất tất, âm mưu"     → [Diễn giải]   → Bằng chứng?  → KHÔNG CÓ
  → Verdict: GIẢ (Rule 3), KHÔNG PHẢI THẬT
  ```

  Deductive Falsification: Sự kiện thuộc cơ chế công khai bắt buộc, vắng bóng trên báo Cấp 1-2-3 → bằng chứng phủ định.

- **Layer 4 — Chain-of-Thought + Self-Consistency Check:**
  Viết chuỗi tự luận, sau đó đọc lại: "Verdict có nhất quán với phân tích không?"

**Hệ thống 4 Quy tắc Phán quyết:**

| Rule | Nhãn | Điều kiện |
|---|---|---|
| RULE 1 | THẬT | ≥1 nguồn Cấp 1 hoặc ≥2 nguồn Cấp 2-3 xác nhận trực tiếp |
| RULE 2 | GIẢ | Bác bỏ trực tiếp HOẶC Deductive Falsification |
| RULE 3 | GIẢ — Sai lệch | Chi tiết sai bản chất HOẶC narrative bịa đặt không có bằng chứng |
| RULE 4 | CHƯA XÁC ĐỊNH | Không đủ bằng chứng |

**Bước 3 — Output Validation & Schema Enforcement:**
- Schema Validation + Default Fallback
- Instruction-at-Generation-Point: ràng buộc nhúng trực tiếp vào trường verdict của JSON template
- Assertion Verification Field: ép model viết all_verified: true/false ngay trước verdict
- URL Rectification (3-Tier): Exact Match → Domain Match → Title-Keyword Match

**Bước 4 — Self-Directed Feedback Loop:**

| Điều kiện | Quyết định |
|---|---|
| Đã chốt Rule 1, 2, 3 với bằng chứng rõ | request_deep_search: false |
| Chốt Rule 4 + nhận ra keyword có thể lệch hướng | request_deep_search: true, ghi suggested_search_angle |
| retry_count ≥ MAX_RETRIES = 2 | Cưỡng chế dừng (Hard Ceiling), tối đa 1 lần lookback |

**Bước 5 — State Finalization & Verdict Forwarding:**
LangGraph should_continue() đọc feedback_to_agent1:
- Khác rỗng → Route về query_agent (Agent 1)
- Rỗng → Route tới END → Lưu Cache → Trả về Frontend

---

## 2.4. Output Cuối cùng (Final Verdict Object)

```json
{
  "chain_of_thought": "Chuỗi tự luận 4-8 câu mô tả hành trình điều tra",
  "assertion_verification": {
    "event_claim": "Sự kiện nền có được xác nhận không?",
    "narrative_claim": "Diễn giải đi kèm có bằng chứng không?",
    "all_verified": false
  },
  "verdict": "THẬT / GIẢ / CHƯA XÁC ĐỊNH",
  "verdict_en": "SUPPORTED / REFUTED / UNVERIFIED",
  "confidence_score": 0.91,
  "rule_applied": "RULE 3",
  "rule_explanation": "Sự kiện có tồn tại nhưng narrative bịa đặt không có bằng chứng",
  "summary": "Tóm tắt 2-3 câu cho người đọc",
  "arguments": [{"title": "...", "content": "...", "evidence": "...", "source_url": "..."}],
  "divergence_found": true,
  "divergence_details": "Mô tả chi tiết sai lệch nếu có",
  "recommendation": "Khuyến nghị hành động cho người dùng"
}
```

---

## 2.5. Bộ Công cụ Đánh giá (Evaluation Framework)

**eval_runner.py:**
- Auto-Resume: Bỏ qua mẫu đã có kết quả
- Atomic Write: Ghi từng kết quả ngay vào CSV, không mất dữ liệu khi crash
- Anti-Spam: Nghỉ 90 giây sau mỗi 6 mẫu tránh Rate Limit
- API Rotation: Xoay vòng pool key Tavily (5 keys) và Gemini (8 keys)

---

# CHƯƠNG 3: KẾT QUẢ THỬ NGHIỆM VÀ ĐÁNH GIÁ

## 3.1. Thiết lập Thực nghiệm

### 3.1.1. Môi trường Thực nghiệm

| Thành phần | Thông số |
|---|---|
| Agent 1 | Llama-3.1-8B-Instant / Groq API / Pool 4 keys |
| Agent 2 | Gemini-2.5-Flash-Lite / Google AI API / Pool 8 keys |
| Agent 3 | GPT-4o-Mini / OpenAI API |
| Search Engine | Tavily Primary / Pool 5 keys / Bing Fallback |
| Database Cache | MongoDB Atlas M0 |
| Embedding Model | vietnamese-sbert (HuggingFace) |

### 3.1.2. Cấu trúc Bộ Dữ liệu

**Bộ dữ liệu tiêu cực (Negative — Tin GIẢ): 200 mẫu**

Kỹ thuật Information Mutation:
- Sai lệch số liệu: Thay đổi con số thống kê, tiền tệ, số người
- Gán ghép chức danh: Thay sai quân hàm, chức vụ
- Thêm narrative bịa: Gán thêm âm mưu, động cơ không có căn cứ
- Sai lệch thời gian: Thay đổi ngày tháng, khung thời gian
- Lệch địa danh: Thay cơ quan, địa phương xử lý vụ việc

**Bộ dữ liệu tích cực (Positive — Tin THẬT): 200 mẫu**
Thu thập từ tin tức chính thống, reformulate thành câu hỏi kiểm chứng 100–200 từ.

---

## 3.2. Kết quả Thực nghiệm

### 3.2.1. Kết quả trên Bộ Dữ liệu Tiêu cực (200 mẫu GIẢ)

| Phán quyết | Số lượng | Tỷ lệ |
|---|---|---|
| **GIẢ (Đúng ✅)** | **195** | **97.5%** |
| THẬT (Sai ❌) | 5 | 2.5% |
| CHƯA XÁC ĐỊNH | 0 | 0% |

### 3.2.2. Phân tích 5 Mẫu Phân loại Sai

Toàn bộ 5 mẫu sai đều thuộc dạng **"True Event + False Narrative"**:

| IDX | Sự kiện nền (Thật) | Narrative bịa (không có bằng chứng) |
|---|---|---|
| 52 | Xã Kiều Phú nông thôn mới | "Chiêu trò bưng bít thông tin" |
| 54 | VTV, VOV chuyển về Trung ương Đảng | "Kiểm soát truyền thông, ngăn ý kiến trái chiều" |
| 57 | Ông Nguyễn Khắc Toàn tái đắc cử | "Khuất tất mờ ám, quân cờ thế lực" |
| 67 | Bảo tàng 1.000 tỷ phê duyệt | "Chiêu trò che giấu lợi ích nhóm" |
| 70 | Phá dỡ KS Điện lực Hồ Gươm | "Kế hoạch bí mật, thao túng bất động sản" |

**Pattern lỗi:** AI chỉ verify sự kiện nền (CÓ THẬT) rồi dừng lại, không tiếp tục xác minh lớp diễn giải/cáo buộc.

### 3.2.3. Quy trình Khắc phục (3 cải tiến Prompt Engineering)

| Cải tiến | Vị trí | Cơ chế |
|---|---|---|
| Verify Every Assertion | Section II | Dạy nguyên lý "Claim = Sự kiện + Diễn giải, phải verify cả hai" |
| Narrative Layer Check | Layer 3 | "Claim khẳng định thêm điều gì ngoài sự kiện?" |
| Assertion Field + Instruction-at-Generation-Point | JSON template | Ép model viết all_verified: true/false → tự khóa verdict |

### 3.2.4. Phân tích Trường hợp Thành công

**Case 1 — Deductive Falsification:**
> Claim: "Bộ trưởng Y tế Nguyễn Thanh Long khẳng định vaccine COVID gây ung thư tại Quốc hội tháng 3/2026"
- Layer 2: Sự kiện thuộc cơ chế công khai bắt buộc
- Kết quả: Vắng bóng hoàn toàn trên báo Cấp 1-3
- **Verdict: GIẢ (Rule 2), Confidence: 0.90**

**Case 2 — Divergence Chi tiết:**
> Claim: "Toà tuyên phạt bị cáo Trần Văn Quân nhận hối lộ 900 triệu đồng"
- Layer 3: Báo Tuổi Trẻ ghi 800 triệu, không phải 900 triệu
- **Verdict: GIẢ (Rule 3), divergence_details rõ ràng**

---

## 3.3. Phân tích Hiệu năng Pipeline

### 3.3.1. Thời gian Xử lý

| Thành phần | Thời gian trung bình |
|---|---|
| Cache HIT | < 2 giây |
| Agent 1 (Groq/Llama) | 3–8 giây |
| Tavily Search (2 queries song song) | 5–12 giây |
| Agent 2 (Gemini Flash) | 8–15 giây |
| Agent 3 (GPT-4o-Mini) | 40–80 giây |
| **Tổng Pipeline (Cache MISS)** | **60–120 giây** |

### 3.3.2. Tỷ lệ Thành công API

| API | Pool Size | Tỷ lệ Thành công |
|---|---|---|
| Tavily Search | 5 keys | ~98% |
| Gemini (Agent 2) | 8 keys | ~99% |
| Groq (Agent 1) | 4 keys | ~97% |

---

## 3.4. Hạn chế Nhận diện

| Hạn chế | Nguyên nhân |
|---|---|
| Sự kiện rất mới (<24h) thường CHƯA XÁC ĐỊNH | Tavily chưa index kịp |
| Sự kiện học thuật / nội bộ doanh nghiệp | Không có nguồn báo chí xác nhận |
| Độ trễ cao (60–120s) | GPT-4o-Mini xử lý prompt dài |

---

# CHƯƠNG 4: KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

## 4.1. Tổng kết Đóng góp Kỹ thuật

| # | Đóng góp | Mô tả |
|---|---|---|
| 1 | Heterogeneous Multi-Agent Pipeline | 3 LLM chuyên biệt phối hợp |
| 2 | Anti-Swelling RAG Philosophy | Loại bỏ Fixed-size Chunking, 1M-token context |
| 3 | Verify Every Assertion | Giải quyết dạng True Event + False Narrative |
| 4 | U-Turn Feedback Loop | Self-Correction đầu tiên cho fact-checking tiếng Việt |
| 5 | Two-Stage Semantic Cache + NER Guard | <2s phản hồi, độ chính xác thực thể cao |
| 6 | Multivariate Trust Scoring Engine | Domain Authority + Exponential Time Decay |

## 4.2. Đánh giá Ưu / Nhược điểm

| Khía cạnh | Ưu điểm | Nhược điểm |
|---|---|---|
| Chất lượng | Minh bạch CoT, explainable AI | False Negative với dạng narrative tinh vi |
| Tốc độ | <2s với Cache HIT | 60–120s với Cache MISS |
| Chi phí | Cache giảm 60–70% API calls | GPT-4o-Mini tốn kém |
| Độ bền | Fault tolerance, Atomic Write, API Rotation | Phụ thuộc nhiều API bên thứ 3 |
| Phạm vi | Phủ rộng tin tức chính trị-xã hội VN | Hạn chế với sự kiện học thuật / nội bộ |

## 4.3. Hướng Phát triển Tương lai

### Ngắn hạn (3–6 tháng)
1. **Fine-tuning LLM tiếng Việt:** Thay GPT-4o-Mini bằng Qwen-2.5-72B fine-tuned trên dữ liệu fact-checking tiếng Việt.
2. **Knowledge Graph tin tức Việt Nam:** Đồ thị tri thức từ báo chí, tra cứu trực tiếp quan hệ thực thể.
3. **Streaming Response:** Server-Sent Events (SSE) hiển thị tiến trình thời gian thực.

### Trung hạn (6–12 tháng)
4. **Active Learning từ phản hồi người dùng:** RLHF cải thiện liên tục.
5. **Đa ngôn ngữ:** Hỗ trợ Khmer, Lào, tiếng Anh cho khu vực Đông Nam Á.
6. **Browser Extension:** Kiểm chứng văn bản trên web bằng highlight + click.

### Dài hạn (12+ tháng)
7. **Early Warning System:** Active monitoring tự phát hiện tin giả viral, cảnh báo chủ động.
8. **Multimodal Fact-Checking:** Mở rộng kiểm chứng sang hình ảnh (deepfake), video, audio.

---

## 4.4. Kết luận

SMART-FC đã chứng minh tính khả thi của kiến trúc Đa tác tử tự trị cho bài toán kiểm chứng thông tin tiếng Việt thời gian thực. Hệ thống phân rã bài toán phức tạp thành ba nhiệm vụ chuyên biệt — Tìm kiếm thông minh, Nén ngữ cảnh Anti-Swelling, và Suy luận đa tầng — mỗi nhiệm vụ được thực thi bởi LLM phù hợp nhất.

Nguyên lý **Verify Every Assertion** và triết lý **Anti-Swelling** giải quyết trực tiếp hai điểm yếu lớn nhất của hệ thống fact-checking hiện có: xu hướng chỉ xác minh sự kiện nền mà bỏ qua lớp diễn giải bịa đặt, và vấn đề đứt gãy ngữ nghĩa khi xử lý tài liệu dài.

Kết quả thực nghiệm bước đầu đạt **97.5% accuracy** trên bộ dữ liệu 200 mẫu tin GIẢ, với cơ chế giải thích minh bạch qua Chain-of-Thought giúp người dùng không chỉ biết kết quả mà còn hiểu **tại sao** hệ thống đưa ra phán quyết đó.

---

## TÀI LIỆU THAM KHẢO

1. Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020.
2. Wei, J., et al. (2022). *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*. NeurIPS 2022.
3. Yao, S., et al. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models*. ICLR 2023.
4. OpenAI (2024). *GPT-4 Technical Report*. arXiv:2303.08774.
5. Team, G. (2024). *Gemini: A Family of Highly Capable Multimodal Models*. arXiv:2312.11805.
6. Touvron, H., et al. (2023). *Llama 2: Open Foundation and Fine-Tuned Chat Models*. arXiv:2307.09288.
7. Reimers, N., & Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks*. EMNLP 2019.
8. Thorne, J., et al. (2018). *FEVER: A large-scale dataset for Fact Extraction and VERification*. NAACL 2018.
9. Nguyen, D. Q., et al. (2020). *PhoBERT: Pre-trained language models for Vietnamese*. EMNLP 2020.
10. Baly, R., et al. (2018). *Predicting Factuality of Reporting and Bias of News Media Sources*. EMNLP 2018.
