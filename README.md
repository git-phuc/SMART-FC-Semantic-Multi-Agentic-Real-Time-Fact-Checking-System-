# 🤖 SMART-FC: Semantic Multi-Agentic Real-Time Fact-Checking System

Hệ thống xác thực tiền kiểm và kiểm chứng tin tức đa trung tâm dành cho văn bản tiếng Việt. Được phát triển dựa trên kiến trúc **Multi-Agent** kết hợp các Mô hình Ngôn ngữ Lớn (LLMs) thế hệ mới nhằm tự động hóa quy trình phân loại nguồn tin, trích xuất dữ kiện và suy luận logic. Đây là kết quả của đề tài Nghiên cứu Khoa học (NCKH) nhằm cung cấp giải pháp kiểm chứng tin giả với độ chính xác cao và thời gian phản hồi theo thời gian thực (Real-time).

---

## 🌟 Chức năng nổi bật (Cập nhật phiên bản v5.0)

1. **Kiến trúc Tri-Agent Đa Hình (Heterogeneous LLM Routing):** 
   - Hệ thống được cấu trúc hóa theo 3 luồng tác vụ độc lập, tận dụng tối đa lợi thế của các nhà cung cấp APIs khác nhau:
   
| Đặc vụ (Agent) | Nền tảng (Provider) | Lõi mô hình (LLM Model) | Chức năng kiểm thử NCKH |
|----------------|---------------------|-------------------------|-------------------------|
| **Agent 1: Query** | Groq | `llama-3.1-8b-instant` | Tốc độ chớp nhoáng (< 1s), sinh cấu trúc từ khóa chuyên biệt. |
| **Agent 2: Extractor**| Google | `gemini-2.5-flash-lite` | Xử lý Context Window khổng lồ (1M Tokens), trích xuất chuyên sâu dữ kiện báo chí thô. |
| **Agent 3: Reasoner** | OpenAI | `gpt-4o-mini` | Tính chính xác logic cao, chốt JSON kết luận với độ tin cậy và Zero-Hallucination. |
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

## 📋 Mục lục
1. [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
2. [Hướng dẫn Cài đặt & Triển khai Đám mây](#-hướng-dẫn-cài-đặt--triển-khai-đám-mây)

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

