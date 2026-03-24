# BÁO CÁO NGHIÊN CỨU KHOA HỌC
**TÊN ĐỀ TÀI:** Xây dựng hệ thống kiểm chứng tin giả tự động đa tác tử dựa trên mô hình RAG thời gian thực và Bộ nhớ ngữ nghĩa hai lớp (Two-Stage Semantic Cache).

**TÊN HỆ THỐNG ĐỀ XUẤT:** SMART-FC (Semantic Multi-Agentic Real-Time Fact-Checking System)

---

## 1. Giới thiệu và Đặt vấn đề

Tin giả (Fake News) đang phát tán với tốc độ chóng mặt nhờ vào sự phát triển của Mạng xã hội. Trong khi đó, việc kiểm chứng tin giả theo cách thủ công tốn rất nhiều thời gian. Các mô hình Ngôn ngữ lớn (LLMs) có khả năng sinh văn bản tốt nhưng thường xuyên gặp vấn đề "Ảo giác" (Hallucination) — tự bịa ra kiến thức nếu không có dữ liệu thực tế.

Nghiên cứu này đề xuất hệ thống **SMART-FC**, một giải pháp kiểm chứng tin giả tự động, kết hợp sức mạnh của hệ thống Đa tác tử (Multi-Agent), mô hình Truy xuất Tăng cường Sinh văn bản (RAG) để đảm bảo tính thời sự của dữ liệu, và kiến trúc Bộ nhớ Ngữ nghĩa (Semantic Cache) tăng cường bởi Nhận dạng Thực thể (NER) giúp tối ưu hóa chi phí điện toán (API cost) và thời gian phản hồi.

---

## 2. Kiến trúc Hệ thống RAG Đa tác tử (Multi-Agentic Real-time RAG)

Hệ thống định nghĩa 3 tác tử trí tuệ nhân tạo độc lập, hoạt động như một dây chuyền RAG hoàn chỉnh:

### 2.1. Agent 1: Tác tử Truy vấn & Tìm kiếm (Retrieval Phase)
- **Nhiệm vụ:** Nhận tin đồn từ người dùng, làm sạch, và tự động thiết kế các bộ từ khóa tìm kiếm (Search Queries) tối ưu nhất nhờ sức mạnh của LLM tốc độ cao (Groq - LLaMA 3.1).
- **Hành động:** Sử dụng Tool `Tavily Search API` để lướt Web thời gian thực (Real-time Web Surfing). Nó truy cập vào 5-6 bài viết từ các trang báo định tuyến uy tín (ví dụ: `GOV`, `VTV`, `Tuổi Trẻ`) và trích xuất hàng chục ngàn ký tự nội dung (Raw Text).

### 2.2. Agent 2: Tác tử Trích xuất thông tin (Augmentation Phase)
- **Nhiệm vụ:** Hoạt động như một bộ lọc (Filter/Extractor). Cỗ máy đọc hiểu hạng nặng (Google Gemini 2.5 Flash) có Context Window lớn sẽ dung nạp mớ nội dung hàng ngàn chữ từ Agent 1.
- **Hành động:** Đối chiếu tin đồn với các bài báo, lập danh sách các thông tin chứng minh hoặc phản bác. Quá trình này giúp "tăng cường" (Augment) kiến thức thực tế cho mô hình, dọn đường cho Agent 3.

### 2.3. Agent 3: Tác tử Khuyếch đại & Suy luận (Generation Phase)
- **Nhiệm vụ:** Tổng hợp chéo các bằng chứng từ Agent 2. 
- **Công nghệ chống Hallucination:** Nghiêm cấm mô hình tự bịa nguồn. Agent 3 được nhồi danh sách các URL thật (crawled_contents). Nhiệm vụ của nó là phát ra phán quyết cuối cùng (THẬT/GIẢ), lập luận bảo vệ kết quả, và gắn Link nguồn trích dẫn thật 100% để tăng độ tín nhiệm cốt lõi.

---

## 3. Kiến trúc Bộ nhớ Ngữ nghĩa Hai lớp (Two-Stage Semantic Cache)

Để giải quyết vấn đề LLM API chạy quá chậm (~60s) và tốn kém chi phí nhồi Token cho cùng một tin đồn bị xào xáo lại từ ngữ, hệ thống ứng dụng mô hình RAG Database (Vector Search) nội bộ kết hợp xử lý thuật toán NER cứng.

### 3.1. Normalize Layer (Tầng chuẩn hóa động)
- Chuyển đổi tin đồn phức tạp thành một lõi thông tin cô đọng bằng LLM (giữ nguyên con số, ngày tháng). 
- Bắt buộc lưu Entity từ cả câu gốc lẫn câu chuẩn hóa để bảo toàn 100% các con số (Nums) không bị rơi rụng.

### 3.2. Stage 1: Vector Search (Tìm kiếm ngữ nghĩa không gian Vectors)
- Câu hỏi chuẩn hóa được chuyển đổi thành Tọa độ Vector 768 chiều bằng `vietnamese-sbert`.
- Sử dụng **MongoDB Atlas Vector Search** chạy thuật toán `Cosine Similarity`. Nếu điểm tương đồng >= `0.80`, tài liệu được đưa sang Lớp 2.

### 3.3. Stage 2: NER Strict Check (Kiểm tra chéo Thực thể khắt khe)
- Tách bóc các con số, tiền tệ, ngày tháng (Nums) bằng Regex. 
- Bắt buộc cụm số liệu của người dùng mới phải là **tập con (Subset)** của tin đồn trong lịch sử. Điều này chống lại hiện tượng "Tương đồng ngữ nghĩa nhưng sai bét về con số" (VD: Phạt 5 triệu vs Phạt 50 triệu).

### 3.4. Dynamic Rewrite (Viết lại Tóm tắt tự động)
- Khi Cache Hit thành công, thay vì in lại tóm tắt cứng nhắc của DB cổ, hệ thống ném thẳng câu hỏi mới của User và tóm tắt DB vào LLaMA-8B.
- Trả ra một câu tóm tắt đã được đổi chủ ngữ/vị ngữ sao cho mướt và khớp hoàn hảo với văn phong của người hỏi chỉ trong 0.8 giây, mang lại trải nghiệm UX đỉnh cao.

---

## 4. Cơ chế chống sập hệ thống (API Key Rotation)

Một đặc điểm giới hạn kỹ thuật của các hãng AI là Rate Limit (429 Error). Khi cào dữ liệu lớn, Gemini API miễn phí dễ dàng từ chối phục vụ.
- **Giải pháp truyền thống:** Sleep (Ngủ đông) 60-90 giây, gây đình trệ toàn bộ trải nghiệm người dùng cuối.
- **Cơ chế áp dụng (Round-Robin API Pool):** Xây dựng kho chứa nhiều API Keys. Nếu Model sinh ra lỗi 429, Class [BaseAgent](file:///e:/Research/Code/NCKH/Multi-Agentic/agents/base_agent.py#17-221) chủ động "đá" key hỏng ra, nạp Key dự phòng thứ 2 vào Object Langchain và quất lại tác vụ tức thì mà không cần bất kỳ sự gián đoạn thời gian nào.

---

## 5. Kết luận và Đóng góp hướng nghiên cứu

Hệ thống **SMART-FC** minh chứng được khả năng tư duy chuỗi (Chain-of-thought) ưu việt của mô hình Multi-Agent khi kết hợp RAG. Đồng thời, cấu trúc Vector Semantic Search 2 lớp giúp hệ thống đưa mô hình vào thực tiễn với chi phí tối thiểu, xử lý tin giả lặp lại với thời gian phản hồi **giảm từ 60 giây xuống còn dưới 3 giây**. Đây là một bước đệm hoàn hảo để mở rộng cho các hệ thống Tự động hóa Dịch vụ công hoặc Tổng đài Cảnh báo Tin giả quốc gia tương lai.
