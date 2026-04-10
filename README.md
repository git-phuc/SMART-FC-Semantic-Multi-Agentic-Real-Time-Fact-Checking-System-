# 🤖 SMART-FC: Semantic Multi-Agentic Real-Time Fact-Checking System

SMART-FC là hệ thống xác thực và kiểm chứng thông tin tự động dành cho văn bản ngữ nghĩa tiếng Việt. Hệ thống được phát triển phân lớp theo kiến trúc **Đa tác tử tự trị (Autonomous Multi-Agent Layer)** kết hợp với Mô hình Ngôn ngữ Lớn (LLMs). Quá trình này nhằm tự động hóa quy trình truy xuất nguồn tin, trích xuất dữ kiện, suy luận logic chuyên sâu và thiết lập cơ chế **học tăng cường qua vòng lặp phản hồi tự sửa lỗi (Self-Correction Feedback Loop)**. Đề tài Nghiên cứu Khoa học (NCKH) này hướng tới mục tiêu tối ưu hóa độ chính xác cấu trúc và đảm bảo tính minh bạch logic trong bài toán phân loại tin giả (Fake News Detection).

---

## 🌟 Đóng góp Công nghệ (Phiên bản Kiến trúc v6.0)

1. **Kiến trúc Định tuyến Đa tác tử Dị thể (Heterogeneous Multi-Agent Routing):** 
   - Phân rã quy trình thành 3 luồng tác vụ độc lập: Tác tử **Llama-3.1 (Groq)** chịu trách nhiệm phân tích ý định (Intent Classification); **Google Gemini 1.5** xử lý nén ngữ cảnh tài liệu đa luồng (Massive Context Window); và **OpenAI GPT-4o-mini** thực thi suy luận chuỗi logic vĩ mô.
2. **Hệ thống Caching Ngữ nghĩa Đa tầng (Two-Stage Semantic Cache + NER Guard):**
   - **Lớp 1 (Độ thu hồi - Recall):** Ứng dụng Không gian Vector (Vector Search) bằng mô hình `vietnamese-sbert` phối hợp cùng biểu đồ KNN trên MongoDB Atlas để chỉ mục hóa ngữ pháp.
   - **Lớp 2 (Độ chuẩn xác - Precision):** Ràng buộc đối chiếu chéo thông qua thuật toán Nhận dạng Thực thể (Named Entity Recognition - NER). Cơ chế này trực tiếp loại trừ hiện tượng sai lệch dương (False Positives) bị hình thành do sai số lượng, tiền tệ hoặc mốc thời gian.
3. **Mô hình Phân tích Hệ số tín nhiệm (Multivariate Trust Scoring Engine):**
   - Loại trừ nhiễu thông tin thô (Raw Information Noise) bằng cách quy chuẩn toán học: Kết hợp **Trọng số Tín nhiệm Tên miền (Domain Authority Weighting)** (ưu tiên miền nhà nước `.gov.vn`, cơ quan báo chí trung ương) với **Hàm suy giảm logarit thời gian ($e^{-\lambda t}$)**. Thuật toán tối ưu hóa sự ưu việt của những biến thể thông tin có tính cập nhật và mang độ xác nhận pháp lý cao.
4. **Cơ chế Vòng lặp Phản hồi Tự trị (The U-Turn Feedback Loop):**
   - Chuyển đổi từ mô hình đồ thị luồng đơn tuyến (Linear Pipeline) sang đồ thị chu trình LangGraph (Cyclic Graph). Trong điều kiện dữ liệu truy vấn không bộc lộ trạng thái xác minh rõ ràng (Zero-Ground Truth), hệ thống kích hoạt tín hiệu phản hồi ngược (Backward Feedback Signal), ép Tác tử Truy vấn tái cấu trúc toàn bộ không gian tham số từ khóa.
5. **Suy luận Chuỗi Cấu trúc (Zero-shot Chain of Thought - CoT):**
   - Ép buộc mô hình thiết lập mạng lưới tiền đề (Premise mapping) trước khi thu gọn về miền nhị phân phân loại (Binary Classification). Cấu trúc này mở rộng khả năng kiểm định tính minh bạch thuật toán (Transparency/Explainability) cho Hội đồng Thẩm định.

---

## 🏗️ Sơ đồ Kiến trúc Luồng Thực thi (Execution Pipeline)

```text
                     ┌─────────────────────────────────────────────────────────────┐
                     │          Two-Stage Semantic Cache + NER Guard               │
                     │  (MongoDB Atlas Vector Search + Regex Entity Verification)  │
                     └──────┬────────────────────────────────┬─────────────────────┘
                            │ HIT → Trả kết quả trực tiếp    │ MISS → Tiến trình Pipeline
                            ▼                                ▼
User Input ──▶ Normalizer ──▶ Cache Check ──▶ Agent 1 ──▶ Agent 2 ──▶ Agent 3 ──▶ Verdict & CoT
                                              (Groq)     (Gemini)    (OpenAI)
                                                │           │           │
                          (U-Turn Feedback Loop |───────────┼───────────┘)
                                                │           │
                                                ▼           ▼
                                       ┌──────────────────────────────┐
                                       │ 🌐 Tavily Trust Scoring      │
                                       │ 🗜️ Gemini RAG Anti-Swelling  |
                                       └──────────────────────────────┘
```

---

## 🤖 Ma trận Phân công Tham chiếu (LLM Agents Matrix)

| Tác tử (Agent Node) | Khung hạ tầng LLM | Mô tả Chức năng Nghiên cứu (Research Functionalities) |
|---------------------|---------------|------------------------------------------|
| **1. Agent Truy vấn (Querying)**| `llama-3.1-8b-instant` | Xử lý độ trễ mốc < 1 giây. Thực hiện chức năng phân loại ngôn ngữ học (Linguistics parsing) để định cấu hình tham số tìm kiếm thích nghi (Adaptive Queries) từ 1 đến 3 biến. |
| **2. Agent Trích xuất (Extractor)**| `gemini-2.5-flash-lite`| Ứng dụng Không gian nạp liệu lớn (1 triệu Tokens) làm giải pháp triệt tiêu phương pháp phân mảnh tài liệu cứng (Fixed-size Chunking trong RAG Truyền thống). Ngăn chặn phân tách đứt đoạn câu mạch, loại bỏ dư thừa HTML DOM giữ lại thông tin cốt tủy. |
| **3. Agent Suy luận (Reasoner)**| `gpt-4o-mini` | Tính toán mức độ mâu thuẫn nội tại (Contradiction mapping) theo bảng quyết luật thử nghiệm (4-Rule Sandbox). Mã hóa độc lập quá trình Tự suy ngẫm (CoT) vào đối tượng JSON giúp bảo lưu tiến trình tư duy. |

---

## 📊 Mô hình Đánh giá Thực nghiệm (Evaluation Framework)

Tiến trình đo lường Benchmarking thông qua bộ quy chuẩn định lượng `eval_runner.py`:

1. **Tập Dữ liệu Giả lập Đặc tả (600+ Samples Benchmark Dataset):** Cấu trúc tập kiểm thử tổng hợp quy mô đa miền; bao hàm tin giả cực đoan (thu thập trực tiếp từ Tingia.gov.vn) và bộ khung phân tích sự kiện Chính trị - Xã hội vĩ mô. Áp dụng các kỹ thuật đột biến thông tin (Information Mutation) để ép thử tải độ hội tụ của hệ thống.
2. **Cơ cấu Giả lập Thực nghiệm (CLI Evaluation Engine):**
   - **Xử lý Đa phân luồng Cấp khóa (API Key Rotation Mechanism):** Ứng dụng cấu trúc phân phối Token bảo mật xoay vòng nhằm triệt hạt hiện tượng Nút thắt cổ chai tín hiệu (HTTP 429 Rate Limit Bottleneck).
   - **Cơ chế Khôi phục Dung sai Trễ (In-place Fault Tolerance):** Duy trì cơ chế truyền phát kết quả nguyên tử tại thời gian thực (Atomic Write-to-Disk) lên file CSV. Giảm hao tổn phân chia bộ nhớ RAM, bảo toàn tính liên tục của dữ liệu khi xảy ra hiện tượng Crash mạng diện rộng cục bộ.

---

## 🚀 Huấn luyện và Khởi chạy (Deployment & Environment)

```bash
# 1. Đồng bộ mã nguồn học thuật (Clone Repository)
git clone <repository_url>
cd backend

# 2. Xây dựng phân tầng phụ thuộc lõi (Dependency Install)
pip install -r requirements.txt

# 3. Kích hoạt Môi trường Vi mô (Environment Setup)
# Thiết lập biến tệp `.env` tại phân lớp root backend đính kèm các mã Khóa Định Danh (API Keys).
# Mặc định cấu trúc tệp bị cô lập khỏi luồng tải mã nguồn nhằm đảm bảo chuẩn bảo mật.

# 4. Kích hoạt Tập lệnh Kiểm tra Hệ sinh thái (Evaluation Benchmark Script)
python Evaluation/eval_runner.py

# 5. Khởi động Giao diện Đồ họa Giao tiếp (UI/UX Backend Server)
streamlit run app.py
```
