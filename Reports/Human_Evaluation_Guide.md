# HƯỚNG DẪN ĐÁNH GIÁ BỞI CON NGƯỜI (HUMAN EVALUATION)
## Hệ thống SMART-FC — Semantic Multi-Agentic Real-Time Fact-Checking

---

## 1. MỤC TIÊU

Đánh giá chất lượng đầu ra của hệ thống SMART-FC thông qua nhận định trực tiếp của con người. Khác với đánh giá tự động (chỉ so khớp nhãn đúng/sai), Human Evaluation đo được **chất lượng lập luận**, **mức độ thuyết phục**, và **tính hữu ích của nguồn trích dẫn** — những yếu tố mà máy không tự chấm được.

---

## 2. GIẢI THÍCH THUẬT NGỮ

### 2.1. Thang Likert (Likert Scale)
Là thang đo mức độ được sử dụng phổ biến trong nghiên cứu khoa học. Thay vì chỉ hỏi "Đúng hay Sai?", thang Likert cho phép người đánh giá thể hiện mức độ chi tiết hơn theo các bậc từ thấp đến cao.

Trong nghiên cứu này sử dụng **thang 5 bậc (5-point Likert Scale)**:

| Điểm | Ý nghĩa |
|------|---------|
| 1 | Rất kém |
| 2 | Kém |
| 3 | Trung bình |
| 4 | Tốt |
| 5 | Xuất sắc |

### 2.2. Mean (Điểm trung bình)
Là giá trị trung bình cộng của tất cả điểm số trên toàn bộ mẫu đánh giá. Công thức:

$$\text{Mean} = \frac{\sum_{i=1}^{N} S_i}{N}$$

Trong đó $N$ = số mẫu (90), $S_i$ = điểm của mẫu thứ $i$.

### 2.3. Standard Deviation — SD (Độ lệch chuẩn)
Đo mức độ phân tán của điểm số xung quanh giá trị trung bình. SD nhỏ nghĩa là các điểm số tập trung gần nhau (đánh giá nhất quán). SD lớn nghĩa là điểm số dao động mạnh (chất lượng không đồng đều).

$$SD = \sqrt{\frac{\sum_{i=1}^{N} (S_i - \text{Mean})^2}{N}}$$

---

## 3. THIẾT KẾ THÍ NGHIỆM

### 3.1. Chọn mẫu đánh giá
Lấy ngẫu nhiên **90 mẫu** từ bộ dữ liệu SMART-600, phân bổ đều theo nhãn:

| Nhãn hệ thống | Số mẫu |
|---------------|--------|
| Supported (THẬT) | 30 |
| Refuted (GIẢ) | 30 |
| Unverified (CHƯA XÁC ĐỊNH) | 30 |
| **Tổng** | **90** |

### 3.2. Người đánh giá
- Số lượng: **1 người đánh giá độc lập**.
- Yêu cầu: Có khả năng đọc hiểu tin tức tiếng Việt, theo dõi thời sự cơ bản.

> **Ghi chú cho báo cáo:** *"Do giới hạn nguồn lực, Human Evaluation được thực hiện bởi 1 chuyên gia đánh giá độc lập trên 90 mẫu ngẫu nhiên phân tầng."*

### 3.3. Dữ liệu cung cấp cho người đánh giá
Với mỗi mẫu, người đánh giá nhận được:
1. **Tin đồn gốc (Claim):** Nội dung tin tức cần kiểm chứng.
2. **Phán quyết của hệ thống (Verdict):** THẬT / GIẢ / CHƯA XÁC ĐỊNH.
3. **Chuỗi lập luận (Chain-of-Thought):** Đoạn văn giải thích quá trình điều tra.
4. **Khuyến nghị:** Lời khuyên hệ thống đưa ra cho người đọc.

---

## 4. BA TIÊU CHÍ ĐÁNH GIÁ VÀ THANG ĐIỂM CHI TIẾT

### 4.1. Tiêu chí 1: Độ chính xác Phán quyết (Verdict Accuracy)

**Câu hỏi dành cho người đánh giá:** *"Phán quyết (THẬT / GIẢ / CXĐ) có chính xác so với thực tế không?"*

| Điểm | Mô tả |
|------|-------|
| **1 — Sai hoàn toàn** | Phán quyết ngược hẳn với thực tế. VD: Tin rõ ràng GIẢ nhưng hệ thống nói THẬT. |
| **2 — Sai đáng kể** | Phán quyết không đúng nhưng không hoàn toàn ngược. VD: Tin GIẢ nhưng hệ thống nói CXĐ (bỏ lỡ bằng chứng bác bỏ). |
| **3 — Chấp nhận được** | Phán quyết hợp lý trong bối cảnh thông tin hạn chế. VD: Hệ thống nói CXĐ cho tin mà ngay cả người đánh giá cũng khó kết luận. |
| **4 — Chính xác** | Phán quyết đúng với thực tế, có cơ sở rõ ràng. |
| **5 — Chính xác tuyệt đối** | Hoàn toàn chính xác, phản ánh đúng bản chất sự kiện kể cả chi tiết tinh tế (VD: phát hiện đúng phần bịa đặt trong tin "nửa thật nửa giả"). |

---

### 4.2. Tiêu chí 2: Chất lượng Lập luận (Reasoning Quality)

**Câu hỏi dành cho người đánh giá:** *"Chuỗi lập luận (Chain-of-Thought) có logic, mạch lạc và thuyết phục không?"*

| Điểm | Mô tả |
|------|-------|
| **1 — Vô nghĩa** | Lập luận rời rạc, mâu thuẫn, hoặc không liên quan đến tin đồn. |
| **2 — Yếu** | Có đề cập sự kiện nhưng hời hợt, nhảy thẳng sang kết luận mà không giải thích. |
| **3 — Trung bình** | Có cấu trúc cơ bản, đúng sự kiện, nhưng thiếu chiều sâu hoặc bỏ sót khía cạnh quan trọng. |
| **4 — Tốt** | Logic, mạch lạc, đề cập đầy đủ các khía cạnh chính. Người đọc hiểu được tại sao hệ thống kết luận như vậy. |
| **5 — Xuất sắc** | Chặt chẽ, phân tích đa chiều, chỉ ra cả bằng chứng ủng hộ lẫn phản đối. Hoàn toàn thuyết phục. |

---

### 4.3. Tiêu chí 3: Tính liên quan của Nguồn trích dẫn (Source Relevance)

**Câu hỏi dành cho người đánh giá:** *"Các nguồn báo chí trích dẫn có liên quan trực tiếp đến sự kiện không?"*

| Điểm | Mô tả |
|------|-------|
| **1 — Không liên quan** | Nguồn hoàn toàn lệch đề, nói về sự kiện khác. URL hỏng hoặc không tồn tại. |
| **2 — Gián tiếp** | Cùng chủ đề chung nhưng không đề cập trực tiếp sự kiện cụ thể trong tin đồn. |
| **3 — Một phần** | Một số nguồn liên quan, một số không. Hoặc nguồn đề cập sự kiện nhưng thiếu chi tiết cốt lõi. |
| **4 — Tốt** | Đa số nguồn đề cập đúng sự kiện, đúng nhân vật, đúng thời điểm. Bằng chứng hữu ích. |
| **5 — Hoàn hảo** | Tất cả nguồn nói trực tiếp về sự kiện. Bằng chứng rõ ràng, nguồn uy tín. |

---

## 5. CẤU TRÚC CỘT TRONG FILE DỮ LIỆU

### 5.1. Các cột có sẵn (từ hệ thống)

| Cột | Mô tả |
|-----|-------|
| `index` | Số thứ tự mẫu |
| `title` | Tiêu đề bài báo gốc |
| `question` | Tin đồn / Claim cần kiểm chứng |
| `label` | Nhãn gốc (Ground Truth) |
| `Output` | Phán quyết hệ thống (THẬT / GIẢ / CXĐ) |
| `Chain-of-Thought` | Chuỗi lập luận hệ thống tạo ra |
| `Khuyến Nghị` | Khuyến nghị cho người dùng |
| `pred` | Nhãn dự đoán dạng mã hóa |

### 5.2. Các cột cần thêm (cho Human Evaluation)

| Cột | Mô tả |
|-----|-------|
| `H_Verdict` | Chấm Độ chính xác phán quyết (1–5) |
| `H_Reasoning` | Chấm Chất lượng lập luận (1–5) |
| `H_Source` | Chấm Tính liên quan nguồn (1–5) |
| `H_Note` | Ghi chú lý do (bắt buộc khi cho điểm 1–2) |

---

## 6. CÁCH TÍNH KẾT QUẢ

### 6.1. Điểm trung bình mỗi tiêu chí
Với mỗi tiêu chí, tính Mean trên toàn bộ 90 mẫu:

$$\text{Mean} = \frac{\sum_{i=1}^{90} S_i}{90}$$

### 6.2. Phân tích theo nhóm nhãn
Tách riêng điểm trung bình theo từng nhãn để phát hiện hệ thống mạnh/yếu ở nhóm nào:

| Tiêu chí | Supported (30 mẫu) | Refuted (30 mẫu) | Unverified (30 mẫu) | Tổng (90 mẫu) |
|----------|--------------------|--------------------|---------------------|---------------|
| Verdict Accuracy | ? / 5.0 | ? / 5.0 | ? / 5.0 | ? / 5.0 |
| Reasoning Quality | ? / 5.0 | ? / 5.0 | ? / 5.0 | ? / 5.0 |
| Source Relevance | ? / 5.0 | ? / 5.0 | ? / 5.0 | ? / 5.0 |

---

## 7. BẢNG KẾT QUẢ BÁO CÁO (TEMPLATE)

### 7.1. Tổng quan

| Tiêu chí | Mean ± SD | Đánh giá |
|----------|-----------|----------|
| Verdict Accuracy | ? ± ? / 5.0 | ? |
| Reasoning Quality | ? ± ? / 5.0 | ? |
| Source Relevance | ? ± ? / 5.0 | ? |

### 7.2. Thang diễn giải điểm trung bình

| Khoảng điểm | Đánh giá tổng thể |
|-------------|-------------------|
| 4.5 – 5.0 | Xuất sắc |
| 4.0 – 4.4 | Tốt |
| 3.0 – 3.9 | Chấp nhận được |
| 2.0 – 2.9 | Cần cải thiện |
| 1.0 – 1.9 | Không đạt yêu cầu |

---

## 8. LƯU Ý KHI THỰC HIỆN

1. **Không xem nhãn gốc trước:** Người đánh giá chỉ đọc Claim + Output hệ thống, chấm điểm xong rồi mới được so với nhãn gốc (label).
2. **Chấm theo thứ tự ngẫu nhiên:** Không chấm lần lượt 30 mẫu THẬT rồi 30 mẫu GIẢ (dễ bị thiên vị). Trộn ngẫu nhiên 90 mẫu trước khi chấm.
3. **Ghi chú bắt buộc khi cho 1–2 điểm:** Giúp phân tích lỗi (Error Analysis) sau này.
4. **Nghỉ giữa chừng:** Nên chia thành 2–3 lượt chấm (mỗi lượt 30–45 mẫu) để tránh mệt mỏi ảnh hưởng chất lượng đánh giá.
