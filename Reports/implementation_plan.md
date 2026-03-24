
# Kế hoạch: Tổng hợp Kiến trúc cho Báo cáo NCKH

## Đề xuất Tên Hệ thống (System Naming)
Để báo cáo NCKH mang tính học thuật và chuyên nghiệp, dưới đây là các đề xuất tên gọi cho dự án:

1. **SMART-FC**: **S**emantic **M**ulti-**A**gentic **R**eal-**T**ime **F**act-**C**hecking System
   *(Hệ thống kiểm chứng tin giả đa tác tử thời gian thực dựa trên ngữ nghĩa)*
2. **NARA-FC**: **N**ER-**A**nhanced **R**AG **A**gentic Fact-Checking Pipeline
   *(Đường ống tác tử kiểm chứng tin giả RAG được tăng cường bởi Nhận dạng Thực thể NER)*

## Cấu trúc Báo cáo NCKH

Báo cáo NCKH sẽ tập trung vào sự kết hợp giữa **Multi-Agent** và mô hình **Retrieval-Augmented Generation (RAG)**, được tăng cường bởi cơ sở dữ liệu Vector và xử lý ngữ nghĩa tự nhiên. 

### 1. Kiến trúc Multi-Agentic RAG Thời gian thực
- **Retrieval (Agent 1 + Tavily):** Tự động phân tích câu hỏi, biến đổi thành các truy vấn tìm kiếm tối ưu và thu thập các bài báo (context) mới nhất từ Internet.
- **Augmentation (Agent 2):** Đọc lược hàng chục ngàn từ ngữ từ các bài báo, trích xuất chính xác thông tin trọng tâm và chắt lọc thành context cô đọng.
- **Generation (Agent 3):** Đọc context, suy luận logic đối chiếu với tin đồn, xuất ra kết luận (Thật/Giả) kèm theo bằng chứng và Link URL minh bạch (chống sinh ảo giác - Hallucination).

### 2. Kiến trúc Bộ nhớ Semantic Cache siêu việt (Vector Search + NER)
- **Chuẩn hóa (Query Normalization):** Sử dụng LLM tốc độ cao (Groq/LLaMA-3) để tóm lược và chuẩn hóa câu hỏi của người dùng, giữ nguyên bản các con số cốt lõi. Bỏ qua các yếu tố cảm xúc, từ đệm.
- **Stage 1 (Cosine Similarity):** Dùng `vietnamese-sbert` mã hóa câu chuẩn hóa thành Vector 768 chiều. Tìm kiếm vector tương đồng trên MongoDB Atlas với threshold `0.80`.
- **Stage 2 (NER Strict Check):** Trích xuất thực thể số (`nums`) từ cả câu gốc lẫn câu chuẩn hóa thông qua biểu thức chính quy và đối chiếu tập hợp con (subset). Đảm bảo không bắt nhầm các tin đồn giống nhau nhưng khác biệt về số liệu.
- **Dynamic Rewrite:** Khi Cache Hit, gọi lại Groq LLM (0.5s) để viết lại văn phong của câu tóm tắt DB theo đúng chủ ngữ và ngữ cảnh của câu truy vấn hiện tại, mang lại trải nghiệm cá nhân hóa đỉnh cao.

### 3. Tối ưu hóa API & Chống Rate Limit
- Triển khai thuật toán **Round-Robin API Key Rotation**. Khi Google Gemini ném lỗi `429 Too Many Requests`, hệ thống ngay lập tức bắt lỗi, hủy phiên làm việc hiện tại, gắn API Key dự phòng mới và chạy tiếp khối lượng công việc đang dang dở mà không cần phải gọi hàm ngủ (`time.sleep`) tốn kém thời gian. 

## Kết quả đạt được (Performance)
- **Cold Start (Cache MISS):** Mất trung bình ~50-60 giây cho một quy trình duyệt hàng trăm nghìn ký tự.
- **Warm Start (Cache HIT):** Mất < 3 giây để truy xuất và viết lại dựa trên kiến thức đã lưu trữ, tối ưu hóa đến 95% chi phí API và Runtime.
