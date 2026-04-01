# 🤖 SMART-FC: Semantic Multi-Agentic Real-Time Fact-Checking System

Hệ thống xác thực tiền kiểm và kiểm chứng tin tức đa trung tâm dành cho văn bản tiếng Việt. Được phát triển dựa trên kiến trúc **Multi-Agent** kết hợp các Mô hình Ngôn ngữ Lớn (LLMs) thế hệ mới nhằm tự động hóa quy trình phân loại nguồn tin, trích xuất dữ kiện và suy luận logic. Đây là kết quả của đề tài Nghiên cứu Khoa học (NCKH) nhằm cung cấp giải pháp kiểm chứng tin giả với độ chính xác cao và thời gian phản hồi theo thời gian thực (Real-time).

---

## 🌟 Chức năng nổi bật (Cập nhật phiên bản v5.0)

1. **Kiến trúc Tri-Agent Đa Hình (Heterogeneous LLM Routing):** 
   - Hệ thống được cấu trúc hóa theo 3 luồng tác vụ độc lập, tận dụng tối đa lợi thế của các nhà cung cấp APIs khác nhau:
     - **Query Generator (Agent 1):** Tích hợp `llama-3.1-8b-instant` (Groq) nhằm tối ưu hóa độ trễ sinh từ khóa tìm kiếm (dưới 1s).
     - **Information Extractor (Agent 2):** Sử dụng `gemini-2.5-flash-lite` với bộ nhớ ngữ cảnh cực lớn (1M Tokens) nhằm phân tích chuyên sâu các dữ liệu báo chí chưa qua chọn lọc.
     - **Logical Reasoner (Agent 3):** Vận hành trên `gpt-4o-mini` (OpenAI) để thực hiện đánh giá độ uy tín (Reliability Matrix) và xử lý JSON đầu ra với tính nhất quán cao, giảm thiểu triệt để hiện tượng AI sinh ảo giác (Hallucination).
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

## 💡 Giải pháp Tối ưu hóa Kỹ thuật (Technical Optimizations & Tips)

Quá trình phát triển hệ thống áp dụng nhiều kỹ thuật xử lý (Tricks/Tips) nhằm vượt qua các rào cản từ API bên thứ ba, đảm bảo hệ thống có thể chạy diện rộng (Scale) hiệu quả phục vụ công tác báo cáo khoa học.

1. **Auto-Routing & Xoay vòng Khóa bảo mật (API Key Rotation):**
   - Cơ chế nhận diện tự động nhà cung cấp thông qua biến `BASE_URL`, cho phép tráo đổi linh hoạt giữa các dòng AI (OpenAI, Gemini, Groq) mà không làm vỡ cấu trúc LangChain. Thư viện tự trỏ đúng luồng (Endpoints).
   - Tích hợp vòng lặp `POOL_KEYS` để xoay vòng thẻ sử dụng cho nhóm Cloud Free Tier (Gemini), tự động phân tải lách lỗi nghẽn cổ chai (HTTP Error 429 Too Many Requests).
2. **Kỹ thuật ngắt chùm chống quá tải (Batch-Sleep Evaluator):**
   - Mã nguồn `eval_runner.py` được thiết kế dưới định dạng phân mảng nhỏ (Chunking - Batch size = 4). Hệ thống bắt buộc "ngủ" (Sleep) 180 giây giữa mỗi chùm để giải phóng băng thông từ máy chủ LLMs. Kỹ thuật này ngăn chặn lỗi chặn IP (IP Banned) khi đo kiểm bộ dữ liệu hàng trăm câu (Dataset NCKH).
3. **Quản lý Time-out Kép dự phòng (Web Search Handlers):**
   - Mô-đun thu thập dữ liệu (Crawling) chạy qua 3 Thread bất đồng bộ song song. Áp dụng giới hạn `timeout=15s` cứng cho thư viện API Tavily.
   - Nếu tắc nghẽn cáp quang, hệ thống không bị treo lơ lửng mà kích hoạt Fallback Cơ sở (Bing/DuckDuckGo kết hợp BeautifulSoup scraper) để vượt cửa ải ngay tắp lự.
4. **Resiliency Extraction (Trích xuất bền vững dữ kiện JSON):**
   - Thu thập chuỗi (String) từ Model không thể đảm bảo cấu trúc hoàn hảo. Hệ thống cấu hình hàm `parse_json_response()` xử lý Expression để loại bỏ các thẻ Markdown rác (như ` ```json...``` `) bọc ngoài mảng phân tích, chặn đứt gãy lỗi Parse mã nguồn Python.
5. **Ghi đè bảo toàn nguyên vẹn (In-place Caching & Checkpoints):**
   - Đảm bảo cơ chế Resume (Khôi phục) số liệu. Tệp nhật ký `.csv` được cập nhật lưu trực tiếp vào ổ đĩa sau mỗi nhịp thay vì treo trên bộ nhớ RAM. Nếu sập nguồn hoặc đóng máy, thành quả nghiên cứu không bị bốc hơi và hệ thống có khả năng đánh giá tiếp từ dòng Data lỗi cuối cùng.

