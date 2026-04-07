# 🤖 SMART-FC: Semantic Multi-Agentic Real-Time Fact-Checking System

Hệ thống xác thực tiền kiểm và kiểm chứng tin tức đa trung tâm dành cho văn bản tiếng Việt. Được phát triển dựa trên kiến trúc **Multi-Agent** kết hợp các Mô hình Ngôn ngữ Lớn (LLMs) thế hệ mới nhằm tự động hóa quy trình phân loại nguồn tin, trích xuất dữ kiện và suy luận logic. Đây là kết quả của đề tài Nghiên cứu Khoa học (NCKH) nhằm cung cấp giải pháp kiểm chứng tin giả với độ chính xác cao và thời gian phản hồi theo thời gian thực (Real-time).

---

## 🌟 Chức năng nổi bật (Cập nhật phiên bản v5.0)

1. **Kiến trúc Tri-Agent Đa Hình (Heterogeneous LLM Routing):** 
   - Chuyên biệt hóa 3 luồng tác vụ độc lập với 3 nền tảng LLM khác nhau: **Groq** (truy xuất nhanh), **Google Gemini** (sức chứa ngữ cảnh lớn), và **OpenAI** (suy luận logic) nhằm tối đa hóa tốc độ và độ tin cậy.
2. **Bảo lưu ngữ nghĩa đa tầng (Two-Stage Semantic Caching):**
   - **Lớp 1 (Recall):** Tìm kiếm vector nhúng (Vector Search) bằng `keepitreal/vietnamese-sbert` thông qua MongoDB Atlas.
   - **Lớp 2 (Precision):** Triển khai Named Entity Recognition (NER) nhằm đối chiếu khắt khe các thực thể số, thời gian, tên riêng.
   - Thời gian truy vấn cho các tin tức trùng lặp được tối ưu xuống mức dưới 2 giây.
3. **Trình truy xuất Dữ liệu Thông minh (Asynchronous Web Crawler):**
   - Xử lý đồng thời 3 luồng tìm kiếm định danh (Chính thống `gov`, `nhandan.vn` và đa phương tiện) thông qua chuẩn API Tavily.
   - Áp dụng cơ chế Fallback (dự phòng) qua Bing & DuckDuckGo nếu xuất hiện tình huống Time-out rớt mạng ở mức 15 giây.

---

## 🏗️ Kiến trúc luồng xử lý (Workflow Architecture)

Sơ đồ quy trình tương tác cốt lõi của hệ thống SMART-FC Pipeline:

```text
                     ┌─────────────────────────────────────────────────┐
                     │          Two-Stage Semantic Cache               │
                     │  (MongoDB Atlas Vector Search + Vietnamese NER) │
                     └──────┬──────────────────────────────┬───────────┘
                            │ HIT → trả kết quả < 2s       │ MISS → chạy pipeline
                            ▼                              ▼
User Input ──▶ Normalizer ──▶ Cache Check ──▶ Agent 1 ──▶ Agent 2 ──▶ Agent 3 ──▶ Verdict
                 (Groq)                        (Groq)     (Gemini)    (OpenAI)
                                                 │
                                                 ├─ Tavily API (Primary Search)
                                                 ├─ Định truy vết Nguồn Chính thống (Gov-focused)
                                                 └─ Web Scraper fallback (Bing/DuckDuckGo)
```

---

## 🤖 Tổ hợp Mô hình Ngôn ngữ (Agent Models)

Hệ thống được thiết kế theo hướng chuyên biệt hóa (Tri-Agent), mỗi LLM phụ trách một giai đoạn tương ứng với lợi thế kỹ thuật cốt lõi:

| Đặc vụ (Agent) | Nền tảng (Provider) | Lõi mô hình (LLM Model) | Chức năng kiểm thử NCKH |
|----------------|---------------------|-------------------------|-------------------------|
| **Agent 1: Query** | Groq | `llama-3.1-8b-instant` | Tối ưu hóa độ trễ API (< 1s), sinh cấu trúc từ khóa chuyên biệt. |
| **Agent 2: Extractor**| Google | `gemini-2.5-flash-lite` | Xử lý Context Window khổng lồ (1M Tokens), trích xuất khối lượng văn bản báo chí thô. |
| **Agent 3: Reasoner** | OpenAI | `gpt-4o-mini` | Tính chính xác logic cao, sinh chuỗi đầu ra JSON vững chắc (Zero-Hallucination). |

---

## 📋 Mục lục
1. [🌟 Chức năng nổi bật](#-chức-năng-nổi-bật-cập-nhật-phiên-bản-v50)
2. [🏗️ Kiến trúc luồng xử lý (Workflow Architecture)](#-kiến-trúc-luồng-xử-lý-workflow-architecture)
3. [🤖 Tổ hợp Mô hình Ngôn ngữ (Agent Models)](#-tổ-hợp-mô-hình-ngôn-ngữ-agent-models)
4. [📊 Benchmark Dataset & Evaluation Pipeline](#-benchmark-dataset--evaluation-pipeline)
5. [💻 Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
6. [🚀 Hướng dẫn Cài đặt & Triển khai](#-hướng-dẫn-cài-đặt--triển-khai-đám-mây)
7. [💡 Giải pháp Tối ưu hóa Kỹ thuật](#-giải-pháp-tối-ưu-hóa-kỹ-thuật-tips--tricks)

---

## 📊 Benchmark Dataset & Evaluation Pipeline

Nhằm phục vụ cho việc đánh giá khách quan độ chính xác của hệ thống, một mô-đun **Evaluation** độc lập đã được thiết kế:

### 1. Tập dữ liệu đánh giá FAKE NEWS (100 Samples Benchmark)
Tập dữ liệu "GIẢ" được thiết kế công phu và cực kỳ sát thực tế, tập trung khai thác các luận điệu xuyên tạc, chống phá chính quyền và tin đồn thất thiệt:
- **Crawled Data (Xấp xỉ 34%):** Các bài báo giả, tin đồn thất thiệt ở thế giới thực được Crawler thu thập tự động từ chuyên trang bóc phốt của *Cổng thông tin điện tử Đảng Cộng Sản, Báo Quân Đội Nhân Dân (qdnd.vn), Báo Công An Nhân Dân (cand.com.vn)* và *tingia.gov.vn*.
- **AI-Mutated Data (Xấp xỉ 66%):** Dữ liệu đột biến sinh ra từ AI. Thay vì dùng tin giả dễ vạch trần, chúng tôi đưa tin CHUẨN vào cho các mô hình (LLMs) tự động chế tác (*Mutate*) thành các kịch bản chống phá tinh vi với 3 mức độ (từ dễ đến cực khó). 

### 2. Giao diện Đánh giá tự động (CLI Eval Runner)
- Công cụ `eval_runner.py` gọi luồng Pipeline thô (loại bỏ cơ chế Cache để AI phải làm việc hoàn toàn độc lập).
- Được thiết kế với giao diện Terminal hiện đại (sử dụng thư viện `rich`), hiển thị trực quan tiến trình (Spinner), tô màu phán quyết (Verdict) và thời gian phản hồi ở chuẩn hình ảnh xuất bản NCKH.
- Cơ chế **Auto-Resume & In-place Saving**: Tự động lưu tiến trình từng bài. Nếu bị giới hạn Rate-limit hoặc ngắt mạng, có thể chạy lại lệnh mà không phải test lại những file đã chấm điểm.

---

## 💻 Yêu cầu hệ thống

| Môi trường vận hành | Yêu cầu kỹ thuật |
|--------------------|-----------------|
| **Hệ điều hành** | Chạy độc lập qua Cloud (Streamlit Community/Vercel) hoặc Localhost |
| **Phần cứng** | Không yêu cầu cấu hình Local GPU (Tác vụ Model suy luận xử lý trên Cloud API) |
| **Môi trường Code** | `Python >= 3.10` |
| **Thẻ khai báo (Dependencies)** | Theo tệp định kiểu `requirements.txt` chuyên dụng cho Cloud Deployment. |
| **Bảo mật APIs** | Đòi hỏi cung cấp Keys định danh: Groq, Google Generative AI, OpenAI, Tavily Search. |
| **Cơ sở Dữ liệu** | MongoDB Atlas (Hỗ trợ Vectorize Indexing). |

---

## 🚀 Hướng dẫn Cài đặt & Triển khai Đám mây

### Chạy cục bộ (Local Development)
```bash
# 1. Kéo mã nguồn về thư mục làm việc
cd backend

# 2. Cài đặt các thư viện lõi hệ thống
pip install -r requirements.txt

# 3. Tạo tệp cấu hình biến môi trường
Mở thư mục gốc, tạo tệp `.env` và thiết lập các Token bảo mật (Keys). 
Tệp này đã được thiết lập vô hiệu hóa (ignored) trên hệ thống Git để bảo vệ mã xác thực.

# 4. Thi hành ứng dụng trên nền tảng Web Streamlit
streamlit run app.py
```

---

## 💡 Giải pháp Tối ưu hóa Kỹ thuật (Tips & Tricks)

Quá trình chạy nghiệm thu NCKH áp dụng các kỹ thuật quản trị hiệu năng sau để đảm bảo hệ thống tự hành và không sinh lỗi:

- **Xoay vòng Khóa API (Key Rotation):** Ứng dụng mảng tuần hoàn `POOL_KEYS` tự động đổi API Key (điển hình là Gemini) để vượt rào (Bypass) giới hạn Rate Limit 429.
- **Hệ điều tốc Đánh giá Lô (Batch Sleep):** Tích hợp vòng lặp trong `eval_runner.py` (cấu hình `Batch=4`, trễ `180s`) giúp xả Cache máy chủ, chống chặn IP khi đẩy Test với bộ Dataset quy mô lớn.
- **Dự phòng Web Time-out (Search Fallback):** Ép giới hạn thời gian phản hồi API (`timeout=15s`) khi chạy Crawler bất đồng bộ. Tự động bẽ nhánh sang phương án Scraper cổ điển (Bing/DDG) nếu mạng kết nối Mỹ gặp sự cố vỡ gói tin.
- **Bộ lọc Trích xuất thuần (JSON Clean-parse):** Áp dụng Regular Expression (Regex) dọn sạch mọi thẻ Markdown nhiễu (` ```json `) bọc ngoài mảng phân tích do LLMs sinh ra, bảo vệ luồng Parse độc lập của Python.
- **Tiến trình Ghi đè Tức thời (In-place Saving):** Cấu hình mô-đun Auto-resume ghi đè dữ liệu trực tiếp lên File `.csv` gốc theo từng dòng. Không lưu trên RAM để chống tổn thất tài nguyên khi Server sập đột ngột.

