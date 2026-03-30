# BÁO CÁO PHƯƠNG PHÁP LUẬN VÀ KIẾN TRÚC CHI TIẾT
**Hệ thống SMART-FC (Semantic Multi-Agentic Real-Time Fact-Checking)**
*Dành cho Nghiên cứu Khoa học (NCKH) chuyên sâu*

---

## 1. GIỚI THIỆU VÀ KIẾN TRÚC TỔNG THỂ
SMART-FC là hệ thống kiểm chứng tin giả tự động đa tác tử dựa trên mô hình **RAG Thời gian thực (Real-time Retrieval-Augmented Generation)** và **Bộ nhớ Ngữ nghĩa Hai lớp (Two-Stage Semantic Cache)**. Điểm đột phá của hệ thống nằm ở việc tích hợp mô hình **Mix-AI (Đa nền tảng LLM)** và **Mô hình Chấm điểm Uy tín Đa biến (Multivariate Credibility Scoring)** nhằm loại trừ thiên kiến thuật toán, ưu tiên nguồn chính thống và tính thời sự.

Hệ thống được thiết kế hoàn toàn tự động để xử lý chu trình khép kín: Nhận tin đồn $\rightarrow$ Tìm kiếm bằng chứng $\rightarrow$ Lọc nhiễu $\rightarrow$ Suy luận logic $\rightarrow$ Đưa ra phán quyết kèm dẫn chứng nguồn.

---

## 2. KIẾN TRÚC ĐA TÁC TỬ (MULTI-AGENT PIPELINE) VÀ SỰ BỐ TRÍ MIX-LLM

Để hệ thống hoạt động với hiệu suất (Runtime) và độ chính xác (Accuracy) cao nhất, dự án từ bỏ thiết kế Single-LLM truyền thống, chuyển sang **Mix-AI Multi-LLM**, phân bổ các mô hình phù hợp nhất cho từng nhiệm vụ (Task Specialization).

### 2.1. Agent 1: Tác tử Phân tích Truy vấn & Tìm kiếm (Retrieval Phase)
- **Nhiệm vụ:** Chuẩn hóa câu hỏi phức tạp của người dùng và thiết kế bộ từ khóa tìm kiếm (Search Query) tối ưu. Giao tiếp với API tìm kiếm (Tavily/Bing) để cào dữ liệu thô (Raw text).
- **Mô hình ứng dụng:** `Groq (LLaMA-3.1-8B-Instant)`.
- **Cơ sở khoa học:** Nhiệm vụ này yêu cầu **Tốc độ phản hồi (Latency)** tính bằng phần nghìn giây. LLaMA 8B chạy trên LPU của Groq đảm bảo việc bóc tách Entity và tạo từ khóa không làm nghẽn cổ chai luồng dữ liệu.

### 2.2. Agent 2: Tác tử Trích xuất Thông tin cốt lõi (Augmentation Phase)
- **Nhiệm vụ:** Nhận một khối lượng văn bản khổng lồ (từ 5-6 bài báo dài, lên tới chục ngàn từ) và đọc hiểu, trích xuất chính xác các bằng chứng ủng hộ hoặc phản bác tin đồn.
- **Mô hình ứng dụng:** `Google Gemini 2.5 Flash`.
- **Cơ sở khoa học:** Agent 2 là một cái "phễu lọc". Nhiệm vụ này đòi hỏi năng lực xử lý Cửa sổ Ngữ cảnh Siêu lớn (Ultra-large Context Window). Gemini Flash với khả năng tiếp nhận đến 1 triệu Token hoàn toàn nuốt trọn toàn bộ văn bản thô mà không mất mát hoặc cắt xén dữ liệu quan trọng.

### 2.3. Agent 3: Tác tử Tối cao - Suy luận & Phán quyết (Generation Phase)
- **Nhiệm vụ:** Tư duy chuỗi logic, đối chiếu chéo các bằng chứng từ Agent 2, chiếu theo thang uy tín để ra quyết định cuối cùng (Verdict) với 3 nhãn: **THẬT / GIẢ / CHƯA XÁC ĐỊNH**.
- **Mô hình ứng dụng:** `Groq (LLaMA-3.3-70B-Versatile)`.
- **Cơ sở khoa học:** Đây là bộ não (Brain) của hệ thống. Đòi hỏi IQ cực cao và sự sắc bén trong suy luận. LLaMA 70B đảm nhiệm việc nhận diện các thủ thuật nhồi nhét tin giả (Perturbation) như thổi phồng số liệu, giật gân, mập mờ bối cảnh.
- **Chống Ảo giác (Anti-Hallucination):** Agent 3 bị cấm tuyệt đối việc tự bịa URL hợp thức hóa câu trả lời. Thuật toán hậu kiểm (Post-processing) của Agent 3 sẽ đối chiếu lại chuỗi URL đầu ra, buộc nó phải khớp 100% với danh sách URL báo chí đã cào được ở Agent 1.

---

## 3. MÔ HÌNH CHẤM ĐIỂM UY TÍN ĐA BIẾN (MULTIVARIATE CREDIBILITY SCORING)

Một trong những đóng góp học thuật quan trọng nhất của hệ thống là việc chuyển hóa ranh giới ưu tiên bài báo từ **Lập trình Cứng (Rule-based Hardcoding)** sang **Tối ưu hóa Toán học Đa biến (Multivariate Optimization)**.

Để phân định xem bài báo nào được cung cấp cho con AI đọc làm bằng chứng, điểm uy tín tổng hợp $\mathcal{C}(doc)$ của một bài báo được tính toán qua phương trình hội tụ 3 thành tố:

$$ \mathcal{C}(doc) = \mathcal{W}_{domain} + (\lambda \cdot \mathcal{S}_{relevance} \cdot e^{-\kappa \cdot \Delta t}) $$

*(Chú ý: Hệ thống chuẩn hóa kết quả cuối cùng qua hàm $min(1.0, \mathcal{C})$ nhằm xác định mức trần 1.0 tuyệt đối).*

#### 3.1. $\mathcal{W}_{domain}$: Trọng số Tiên nghiệm Tên Miền (Domain Prior Trust)
Đây là "Bão lãnh uy tín" mang tính răn đe. Hệ thống thiết lập một Từ điển Trọng số (Dictionary Weights Matrix) phân tầng báo chí Việt Nam:
1. **Mức 0.45 (Chỉ thị tối cao):** Cổng chính phủ (`chinhphu.vn`), Quốc hội (`quochoi.vn`), Văn kiện Đảng.
2. **Mức 0.40 (Thông tấn quốc gia):** Báo Nhân Dân, VTV, VOV, TTXVN.
3. **Mức 0.35 (Bộ Ban Ngành):** `mps.gov.vn` (Công an), `mofa.gov.vn` (Ngoại giao)...
4. **Mức 0.20 - 0.30:** Báo pháp luật, báo điện tử đại chúng (`tuoitre.vn`, `vnexpress.net`)...

**Ý nghĩa logic:** Bài báo xuất phát từ Cổng Chính phủ mang giá trị cốt lõi, dù hành văn khô khan (dẫn đến $\mathcal{S}_{relevance}$ đánh giá thấp) nhưng nhờ điểm cộng $\mathcal{W}_{domain} = 0.45$, nó luôn nổi lên đầu (Top 1 Search) để tạo tiền đề cho RAG đập tan tin giả.

#### 3.2. $\mathcal{S}_{relevance}$: Độ Liên Quan Ngữ Nghĩa (Semantic Relevance)
- Tỉ số do Engine AI của Tavily/Bing đo đạc (Cosine Similarity/BM25) đo lường sự trùng khớp ý nghĩa giữa câu tin đồn và nội dung tài liệu tìm được. Giá trị $0.0 \leq \mathcal{S} \leq 1.0$.
- Giúp hệ thống loại bỏ những bài báo uy tín cao nhưng lạc đề (mismatch context).

#### 3.3. $e^{-\kappa \cdot \Delta t}$: Lõi Phân rã Thời gian (Exponential Time Decay)
- Tính chất cốt lõi của tin giả là **"Tính thời sự" (Freshness)**. Một sự thật năm 2018 chưa chắc đúng ở 2024.
- Hàm mũ suy giảm: Sử dụng $\Delta t$ (số ngày kể từ khi xuất bản bài báo). Nếu bài báo quá cũ, hàm suy giảm tiến về $0$, kéo sụp phần bù điểm của $\mathcal{S}_{relevance}$. 
- **Ý nghĩa logic:** Nếu có 2 bài báo nói về cùng mức lương cơ sở (năm 2023 và năm 2024). Bài 2023 sẽ bị trừng phạt điểm nặng nề bởi $\Delta t$ lớn, nhường chỗ cho bài 2024 có $\Delta t \approx 0$ lọt vào mắt Agent. Từ đó hệ thống SMART-FC luôn nạp được **Chân lý mới nhất (The Most Updated Fact)** để đối đáp.

---

## 4. BỘ NHỚ NGỮ NGHĨA HAI LỚP (TWO-STAGE SEMANTIC CACHE)

Để giải quyết bài toán Chi phí API (Cost) và Độ trễ (Latency) trong môi trường thực tiễn (Production-ready), SMART-FC tích hợp hệ thống Data-Caching thông minh, rút ngắn thời gian phản hồi từ **~60 giây xuống còn < 2 giây**.

### 4.1. Normalize Layer (Tầng chuẩn hóa)
Sử dụng LLM siêu tốc bóc tách vỏ bọc từ ngữ của tin đồn (các từ cảm thán, thêm thắt), chỉ giữ lại **khung sườn sự kiện** và **bảo toàn 100% các con số**.

### 4.2. Stage 1: Vector Search (Tìm kiếm Vectơ - Không gian ngữ nghĩa)
Tin đồn chuẩn hóa được chuyển đổi thành Tín hiệu Vector liên tục (768 chiều) thông qua thuật toán `vietnamese-sbert`. 
MongoDB Atlas Vector Search quét tập dữ liệu bằng `Cosine Similarity`. Nếu điểm tương đồng chạm **ngưỡng an toàn tuyệt đối là 0.80**, hệ thống kích hoạt Stage 2. (Ngưỡng 0.8 giúp hệ thống dung thứ cho các cách diễn đạt đồng nghĩa nhưng từ chối các tin đồn lạc đề).

### 4.3. Stage 2: NER Strict Check (Kiểm tra Thắng-Thua bằng Thực thể)
Tin giả tiếng Việt thường sử dụng thủ thuật thay đổi con số (Ví dụ: Sự thật phạt 5 triệu $\rightarrow$ Tin giả phạt 50 triệu). Độ tương đồng Cosine của 2 câu này cực kỳ sát nhau vì chỉ lệch 1 chữ số.
Hệ thống sử dụng các thuật toán Regex để trích xuất `nums` (Tiền tệ, Thời gian). Bắt buộc số liệu trong câu hỏi mới phải **hoàn toàn bù đắp (subset match)** số liệu trong lịch sử truy vấn. Nếu sai lệch, xóa bỏ Cache Hit $\rightarrow$ ép luồng Agent chạy lại tìm kiếm thực tế để tránh sai sót.

### 4.4. Dynamic Rewrite (Viết lại Tóm tắt Tự động)
Nếu Cache Hit ở cả 2 bước, thay vì xuất ra lời tóm tắt khô cứng trong DB, hệ thống sẽ đẩy câu trả lời và câu hỏi của người dùng vào `Groq LLaMA 8B` (tốn ~0.8 giây) để điều chỉnh chủ ngữ, vị ngữ khớp hoàn hảo với văn phong người hỏi. Mang lại trải nghiệm cá nhân hóa đỉnh cao.

---

## 5. CƠ CHẾ CHỐNG LỖI VÀ XOAY VÒNG TÀI NGUYÊN (RELIABILITY & API ROTATION)

Trong quá trình thu thập thông tin quy mô lớn, các nhà cung cấp AI thường giới hạn băng thông (Rate-Limit HTTP 429).
Hệ thống xử lý **Queue Bloat (nghẽn cổ chai)** bằng kỹ thuật **Round-Robin Key Pool**. Thay vì dùng Sleep (ngủ đông bắt trải nghiệm người dùng chờ 60 giây), class `BaseAgent` chủ động bắt Timeout Exception, lập tức vứt bỏ Key bị cấm tạm thời, "bốc" Key dự phòng thứ hai từ không gian lưu trữ `.env` và tái kích hoạt Request bị treo ở giây thứ 60, tạo nên một đường ống trơn tru không có điểm Gãy (Zero-point Failure).

---
*(Bản quyền thiết kế hệ thống SMART-FC. Tài liệu mô tả kỹ thuật phục vụ thẩm định NCKH)*
