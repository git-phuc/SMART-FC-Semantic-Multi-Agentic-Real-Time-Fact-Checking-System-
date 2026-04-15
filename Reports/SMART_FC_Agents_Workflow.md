# Cấu Trúc và Luồng Xử Lý Của Hệ Thống Multi-Agent SMART-FC

Tài liệu này mô tả chi tiết quy trình xử lý thông tin (từ khi nhận tin đồn đến khi ra phán quyết) thông qua luồng chạy (workflow) tự động của hệ thống SMART-FC do 3 tác tử (Agents) đảm nhiệm, được phối hợp chặt chẽ bởi **LangGraph**.

---

## 1. TỔNG QUAN LUỒNG CHẠY (WORKFLOW) TRÊN LANGGRAPH
Hệ thống sử dụng kiến trúc StateGraph (máy trạng thái) để dẫn dắt luồng thông tin theo một chiều và có khả năng rẽ nhánh vòng lặp: 
`START → Query Agent (A1) → Extractor Agent (A2) → Reasoning Agent (A3) → Kiểm tra Điểu kiện → (Vòng lại A1 hoặc END)`

* **Cơ chế semantic-cache tiền trạm:** Trước khi đẩy vào đồ thị LangGraph, hệ thống sẽ chạy qua 2 vòng (Vector Search + NER cache) vào cơ sở dữ liệu. 
   - Nếu HIT: Lấy đáp án cũ, dùng LLM siêu tốc gọt lại văn phong cho hợp câu hỏi (mất ~1-2s). Trả kết quả ngay.
   - Nếu MISS: Khởi động đường ống Graph đầy đủ (~200s). Cuối cùng lưu kết quả vào cache.
* **Vòng lặp thông minh (Agentic Feedback Loop):** Khác với các hệ thống Pipeline xưa thường chạy một mạch đụng tường là chốt, hệ thống này cho phép Agent cuối cùng (A3) có quyền "chê" dữ liệu chưa đủ chứng minh. Tín hiệu này định hướng A1 đổi từ khóa search lại.

---

## 2. QUY TRÌNH HOẠT ĐỘNG CHI TIẾT TỪNG AGENT

### AGENT 1: Query Agent (Trinh sát & Thu thập dữ liệu)
Đóng vai trò như một thám tử đi tìm kiếm thông tin thô từ Internet. Tôn chỉ hoạt động là **tuyệt đối không phán xét tính đúng sai của claim**, chỉ tập trung sinh ra các "lưới" từ khóa phù hợp để vợt dữ liệu.

* **Bước 1 (Phân tích mức độ phức tạp & Lập chiến lược truy vấn):** 
  * AI tiếp nhận "tin đồn" (claim) đầu vào, đánh giá xem dạng này phức tạp cỡ nào.
  * Tùy độ rắc rối, AI sẽ xuất ra cùng lúc từ 1 đến 3 câu truy vấn (search queries) chứa các từ khóa bao phủ vấn đề.
  * *Lưu ý vòng lặp:* Đọc biến trạng thái `feedback_to_agent1`, nếu A3 ở lượt trước mắng "nhầm hướng rồi, tìm thiếu góc nhìn X", thì A1 trong quá trình tạo truy vấn mới sẽ được bơm thẳng đoạn chỉ đạo này vào bộ não để dẹp bỏ những phán đoán cũ, nhắm đúng "góc nhìn X" đó.
* **Bước 2 (Tìm kiếm web cực tốc bằng Multi-Threading):**
  * Dùng kĩ năng `ThreadPoolExecutor` để lấy bộ 1-3 queries bung ra công cụ Tavily Search đồng thời. Sau đó gom tất lưới lại, loại bỏ các đường link trùng lặp (duplication removal).
  * Check xem nếu API của Tavily đủ uy tín trích hẳn một bức tường rào toàn rễ chữ (`has_full_content`), A1 sẽ thu thập lấy text ngay lập tức mà khỏi cần mò mẫm vô link.
* **Bước 3 (Spider Crawl tàn khốc):**
  * Lọc bớt các domain không thể bóc như Youtube, Zalo, Tiktok... (vì toàn video hay bị chặn bắt dữ liệu).
  * Rút ra bảng xếp hạng dựa vào *Tavily Score*, lấy đúng **10 bài viết tín nhất** để cho vào hàng đợi (Queue).
  * Chạy song song thọc thẳng vào 10 URLs đó (thông qua Web Scraper Tool) để móc lõi từng dòng văn bản (paragraph) bên trong mang về. Cuối cùng đóng cái túi búa xua (chứa chữ thô + URL gốc) chuyển sang A2.

### AGENT 2: Extractor Agent (Đọc hiểu thông sâu & Chắt lọc dữ liệu)
Lý do có A2 là vì nạp cả cục văn bản khổng lồ từ chục website vào não lõi (A3) thì sẽ sinh ảo giác (Hallucination) mất tập trung. A2 là một biên tập viên tóm tắt bài giỏi.

* **Bước 1 (Lựa chọn tinh hoa thay vì số lượng):** A2 có lòng tham mức độ, nó chỉ lấy thẳng **Top 5 nguồn** đạt tiêu chí cao nhất mà A1 vừa bàn giao lại.
* **Bước 2 (Xử lý tập trung và Trích xuất tin tức):**
  * Chuyển hóa 5 mớ hỗn mang thành định dạng cực kì rõ rệt: `### Nguồn 1: (Title... Content...)` v.v.
  * Gọi một LLM có ngữ cảnh siêu khủng (Max context Tokens lớn như Gemini Flash). Nó dặn LLM: "Hãy đọc và lọc lấy đúng chi tiết liên quan đến tin đồn người dùng đưa, cái gì không liên quan vứt hết!".
  * Đầu ra không còn mớ hỗn độn thô ráo, mà là các thông tin tinh luyện cực kì sát với ý bài.

### AGENT 3: Reasoning Agent (Toà án Tối cao Suy luận & Phán Quyết)
Đây là hạt nhân của toàn khối. A3 đảm nhiệm chức năng lập luận từng bước (Chain-of-Thought / CoT), lật vấn đề theo nhiều chiều rồi hẵng dập búa.

* **Bước 1 (Đóng khung bằng chứng tránh Ảo giác URL):** 
  * A3 đọc bản Text cô đọng mà A2 đệ lên.
  * Để A3 không dùng trí tưởng tượng bịa ra một trang báo ma (lỗi cố hữu của AI), Code đã áp dụng thiết chế kẹp tay: Ép vào bên dưới prompt nguyên một **DANH SÁCH URL THẬT**. Hàm nội bộ `_fix_urls` sẽ luôn kiểm định: "AI tung ra Link này, Link này có nằm trong tập A1 cào về không?". Không có thì map tự động lại về nguồn thật đã cào hoặc vứt, không được bịa.
* **Bước 2 (Chuỗi lập luận lõi - Reasoning Framework theo 4 Layers):**
  1. *Layer 1:* Lọc xem trong số báo cáo của A2, link nào dùng được, link nào rác bỏ đi.
  2. *Layer 2:* Đánh giá bối cảnh thực sự của loại tin đồn này là gì. 
  3. *Layer 3:* Xác định những "Evidence" (Bằng chứng trích xuất trực tiếp từ báo chí) nào đấu đá trực tiếp vào chi tiết trong claim.
  4. *Layer 4:* Chốt lại thành một bảng giải thích tường tận.
* **Bước 3 (Agentic Feedback - Trọng tài Yêu cầu VAR):**
  * **Critical Feature:** Nếu A3 thấy ở Bước 2, kết quả toàn là "báo chí không nhắc đến rành mạch" hoặc đánh mâu thuẫn... thay vì hấp tấp phán "CHƯA XÁC ĐỊNH", A3 có quyền kích hoạt biến nội bộ `feedback_signal = request_deep_search (True)`. 
  * Khi cờ bật lên, kèm theo lời giải thích "Lý do: Góc tìm kiếm bị trượt vấn đề, Hãy dùng gợi ý góc xoay này:...", file Graph (ở `Should_Continue`) sẽ bẻ cung đường lùi thẳng về **A1** để cày lại từ đầu. Hệ thống giới hạn vòng lặp (MAX_RETRIES = 2) để Graph không chạy liên tục vô hạn.
* **Kết thúc Phán quyết:** Sau khi đã đủ vững tâm hoặc hết lượt VAR, nó đập búa Label: `THẬT`, `GIẢ`, hoặc `CHƯA XÁC ĐỊNH` đi kèm chỉ số tự tin hoàn mỹ và cung cấp 3 lý luận / 3 Link báo chứng minh trực tiếp ra màn hình.
