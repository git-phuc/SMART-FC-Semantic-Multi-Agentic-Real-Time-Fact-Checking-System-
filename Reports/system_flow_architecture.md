# THIẾT KẾ HỆ THỐNG SMART-FC: TÀI LIỆU KỸ THUẬT CHUYÊN SÂU (DEEP-DIVE ARCHITECTURE)

Tài liệu này bao quát toàn bộ logic kỹ thuật tinh ranh nhất đang chạy ngầm trong hệ thống của bạn. Nó không chỉ mô tả bề nổi, mà còn vẽ ra toàn bộ ngóc ngách của hệ Cache Thực thể, Thuật toán chấm điểm và luồng Xoay vòng LangGraph. Tất cả được phác họa bằng các khối hộp để mang thả vào file báo cáo Word/PDF đảm bảo giữ nguyên định dạng chuyên nghiệp.

---

## 1. SƠ ĐỒ CHUẨN ĐỒ THỊ (FULL SYSTEM FLOWCHART VÀ LUỒNG MULTI-AGENTIC)

Sơ đồ dưới đây bao quát toàn cảnh đường đi của một Claim từ lúc rời tay User đến khi bị phân mảnh bởi ma trận Đa tác tử.

```text
=========================================================================================
                               SMART-FC SYSTEM EXECUTION FLOW                                   
=========================================================================================

[ 👤 USER (Streamlit / CLI) ] ──(Gửi tin đồn)──> [ API / FASTAPI BACKEND ]
                                                        │
                                                        v
            ┌────────────────────────────────────────────────────────────────────────┐
            │ LỚP 1: SBERT + MONGODB SEMANTIC CACHE (BỘ ĐỆM KHÁNG ẢO GIÁC/RAG)       │
            └────────────────────────────────────────────────────────────────────────┘
                │ 1. Vector Search: Biến câu hỏi thành mã Vector 768 chiều (sBERT)
                │ 2. Atlas KNN: Quét lịch sử (Ngưỡng đo độ giống Cosine > 0.82)
                │ 3. Regex Entity Guard: Bắt chính xác từng con số, ngày tháng, tiền tệ.
                │
                ├──────> [CACHE HIT] (Số liệu khớp 100%) ──────> (TRẢ KẾT QUẢ NGAY < 1s) 🟢
                │
                V
          [CACHE MISS] (Trật số liệu, hoặc Câu quá dị chưa ai hỏi)
                │
                v
=========================================================================================
                         LỚP 2: MULTI-AGENT LANGGRAPH PIPELINE (TRUNG TÂM PHÂN TÍCH)
=========================================================================================
                │
                v
      ┌────────────────────────────────────────────────┐
      │ 🤖 AGENT 1: QUERY AGENT (Llama-3.1-8b)        │ <─────────┐ (QUAY LẠI TÌM TỪ KHÓA MỚI)
      └────────────────────────────────────────────────┘          │
        │ • Phân tích Intent (Hoàn cảnh/Mục đích)                 │
        │ • Adaptive Queries (Từ 1 đến 3 từ khóa)                 │
        │                                                         │
        v  [ Bắn Đa Luồng ]                                       │
      ┌────────────────────────────────────────────────┐          │
      │ 🌐 WEB SEARCH ENGINE (Tavily/Bing/DDG)         │          │
      └────────────────────────────────────────────────┘          │
        │ • Khóa tên miền (Chỉ tìm .gov.v và Báo chính thống)     │ [PHỤC HỒI LỖI VÒNG 1]
        │ • API Rotation (Xoay 10 Keys chặn đứng Rate Limit)      │ 
        │ • Chấm điểm toán học W(domain) + W(Relevance / Time)    │
        │                                                         │
        v  [ Dọn rác HTML ]                                       │
      ┌────────────────────────────────────────────────┐          │
      │ 🤖 AGENT 2: EXTRACTOR AGENT (Gemini Flash)    │          │
      └────────────────────────────────────────────────┘          │
        │ • Không bao giờ băm nhỏ bài viết như RAG truyền thống   │
        │ • Tận dụng cửa sổ 1.000.000 Token nuốt gọn 5 link web   │
        │ • Nén gộp lại: 5 bản Tóm tắt lõi hạch (JSON DB)         │
        │                                                         │
        v  [ Nạp 5 bản tóm tắt + Câu gốc ]                        │
      ┌────────────────────────────────────────────────┐          │
      │ ⚖️ AGENT 3: REASONING AGENT (GPT-4o-mini)     │ ─────────┘
      └────────────────────────────────────────────────┘
        │ • Suy Luận Nháp: Chain of Thought (Viết tự luận trước)
        │ • Kiểm duyệt qua Khuôn 4 Luật (Sandbox Rules)
        │
        ├─> [Rule 1: THẬT - Có bằng chứng 100%]
        ├─> [Rule 2: GIẢ - Bị cơ quan chức năng trực tiếp bác bỏ]
        ├─> [Rule 3: KÉM CHÍNH XÁC/BỊA ĐẶT - Gán ghép sai ngữ cảnh]
        │
        └─> [Rule 4: CHƯA XÁC ĐỊNH - Nguồn rác / Lệch pha hoàn toàn]
                  │
                  └─> Kiểm tra (Cờ U-TURN) -> Nếu là Vòng 1 -> Ném "Phản hồi" đảo lên Agent 1 🔄
                  └─> Nếu đã là Vòng 2 -> Bó tay, Trả kết quả TRẮNG (Rule 4) ⚪

=========================================================================================
                                LỚP 3: LƯU TRỮ VÀ XUẤT BẢN
=========================================================================================

[ GÓI QUYẾT ĐỊNH BAO GỒM CHUỖI NHÁP CoT + DANH SÁCH BÁO ] ──> CẤT NGƯỢC VÀO CSDL MONGODB
                                                         ──> VẼ LÊN MÀN HÌNH UI (GIAO DIỆN)
```

### 💡 Mô tả & Tác dụng của Hệ thống Thực thi (Execution Flow)
Hệ thống được chẻ ra làm **3 Lớp (Layers)** hoạt động độc lập nhằm mục đích "bóc tách mối quan tâm" (Separation of Concerns). Toàn bộ khối kiến trúc đảm bảo: nhanh nơi cần nhanh, và suy nghĩ thật chậm ở nơi cần dùng não bộ cường độ cao.

1.  **Lớp 1 (Phòng tuyến đầu tiên - SBERT & MongoDB Cache):** Đóng vai trò là một "khiên đỡ đạn" cho hệ thống, đảm bảo phản hồi tức thì với độ trễ chưa tới 1 giây. Việc tra cứu chéo qua lại các luồng thông tin cũ giúp cắt giảm triệt để chi phí gọi Model API (Llama, GPT) nếu câu hỏi lặp lại, mà vẫn tuân thủ định luật kháng ảo giác nhờ lớp lưới Entity Guard.
2.  **Lớp 2 (Trung tâm Multi-Agent LangGraph):** Trái tim của toàn bộ bộ máy, vận hành dựa trên cơ chế đường ống (Pipeline). Ở đây ta có 3 não bộ với 3 năng lực chuyên sâu riêng rẽ. 
    *   **Agent 1 (Query Agent)** không được dùng để suy luận, mà là chiếc radar lùng sục rẽ đa hướng. Khả năng **Adaptive Queries (1-3 truy vấn)** giúp Agent tự lượng sức mình (tin dễ tìm ít, tin khó tìm nhiều) tránh phung phí tài nguyên Internet.
    *   **Agent 2 (Extractor)** như một nhà máy tiêu hóa khổng lồ, lọc bỏ tạp chất HTML, xóe toạc rào cản Token của ChatGPT truyền thống nhờ công nghệ nạp liệu vạch 1 Triệu lượng hạt nhúng của Gemini.
    *   **Agent 3 (Reasoning Agent)** được cách ly hoàn toàn khỏi nhiễu loạn Internet. Nó an tọa ở khâu cuối, giữ sự tập trung tuyệt đối để làm Cán cân Công Lý. Việc cho phép xoay vòng `U-TURN (Feedback Loop)` lấp kín nhược điểm "Cực đoan 1 chiều" của hệ thống phơi sáng AI cũ, giúp AI biết tự nhận sai và tìm lại từ khóa.
3.  **Tác dụng bao trùm:** Xây dựng nên khái niệm tự động hóa 100% (Autonomous Pipeline). Ngay cả khi xảy ra sự cố sập kết nối bên ngoài (bị chặn IP, API nghẽn mạng), khối LangGraph sẽ tự bẻ lái vượt giới hạn truy cập (API Rotation & Engine Fallback) để cứu sống tiến trình kiểm chứng.


---

## 2. KHOA HỌC DỮ LIỆU: MÔ HÌNH CHẤM ĐIỂM TÍN NHIỆM BÁO CHÍ (MULTIVARIATE TRUST SCORING ENGINE)

Không phải tờ báo nào nhả về từ Google/Tavily cũng được cho nạp trực tiếp vào mồm AI. AI rất ngây thơ, nên chúng ta tự xây dựng công cụ trừng phạt Toán học dằn mặt các trang web bẩn và báo lá cải trước khi AI kịp nhìn phân tích nguồn.

- **Công thức Toán học Cốt lõi:**  
  Thuật toán chấm điểm Uy tín (Credibility Score) được tính qua mô hình trọng số đa biến (Multivariate Weighted Model):  
  $$C(doc) = \min(1.0, W_{domain} + (W_{relevance} \times W_{time\_decay}))$$

  Trong đó:
  - $W_{domain}$: Trọng số tiên nghiệm của tên miền (Dictionary-based Priority - Lọc qua ma trận Domain).
  - $W_{relevance}$: Base score từ Search Engine thể hiện độ khớp ngữ nghĩa (Cosine Similarity từ Tavily, mặc định $\approx 0.75$).
  - $W_{time\_decay}$: Hệ số suy giảm giá trị thông tin theo hàm e mũ: $e^{-\lambda \cdot t}$ (Với $\lambda = 0.02$, $t$ là số ngày kể từ khi xuất bản bài báo). Được sinh ra để dìm các tin tức lỗi thời.

```text
=========================================================================================
             MÔ HÌNH CHẤM ĐIỂM UY TÍN BÁO CHÍ (MULTIVARIATE TRUST SCORING ENGINE)
=========================================================================================

[ WEB SEARCH RESULTS ] ──> Bao gồm URLs gốc, Nội dung, và Ngày đăng (t)
       │
       v
┌──────────────────────────────────────────────────────────┐
│ 1. BỘ PHÂN LOẠI QUYỀN LỰC TÊN MIỀN (Domain Authority - W_domain)
├──────────────────────────────────────────────────────────┤
│ 👑 Bậc 1 (+0.45): Nhóm Đảng, Chính phủ (baochinhphu.vn, quochoi.vn)
│ 🥇 Bậc 2 (+0.40): Thông tấn xư, Báo chủ lực nhà nước (vtv.vn, vov.vn, nhandan.vn)
│ 🥈 Bậc 3 (+0.25 - 0.35): Các Bộ Ban Ngành, Báo lớn (tuoitre.vn, mps.gov.vn)
│ 💩 Bậc Bét (+0.0) : Web rác, blog ẩn danh, diễn đàn
└──────────────────────────────────────────────────────────┘
       + (Cộng với)
┌──────────────────────────────────────────────────────────┐
│ 2. BỘ BÓP NGHẸT THỜI GIAN (Exponential Time Decay - W_time_decay)
├──────────────────────────────────────────────────────────┤
│ Hoạt động theo hàm suy giảm vật lý: e^(-0.02 * t)
│ Nhỏ biểu thức (W_relevance * e^(-0.02*t))
│ - Tin của 5 năm trước (t lớn) -> Bị giảm triệt để giá trị relevance.
│ - Tin nóng sáng hôm nay (t ~ 0) -> Giữ nguyên uy lực 100%.
└──────────────────────────────────────────────────────────┘
       │
       v
  [ GIAO THOA TOÁN HỌC ]  =  W_domain + (W_relevance * W_time_decay)
       │
       v
   [ LẬP BẢNG XẾP HẠNG TRƯỚC KHI ĐƯA VÀO AGENT 2 ]
   1. Cổng Thông tin Điện tử Chính Phủ (Score: 0.98) 🟢
   2. Báo Tuổi Trẻ (Score: 0.85) 🟢
   ...
   100. Blog Rác Vớ Vẩn (Score: 0.12) 🔴 ---> [BỊ HỆ THỐNG LOẠI BỎ CỨNG RẮN TRƯỚC KHI ĐỌC]
```

### 💡 Mô tả Toán học & Tác dụng của Hệ Cân Bằng (Trust Scoring)

Thuật toán chấm điểm được thiết lập nhằm xóa sạch rủi ro False Positive (Xác nhận sai vì đọc nhầm báo bịa đặt).
*   **Trọng số Tên Miền (Domain Authority Weighting):** Đây là màng lọc chính trị. Với tư cách một phần mềm truy xét Fake News trong không gian mạng Việt Nam, việc dựa hoàn toàn vào AI là thiếu cơ sở pháp lý. Bằng cách nhồi sẵn sổ tay phân bậc Domain, hệ thống luôn lấy "Tiếng nói từ báo Đảng, Nhà Nước" làm ưu tiên tối thượng (`+0.45`). Các web vô danh hoặc web chui sẽ phải chịu hệ số cộng 0.
*   **Cơ chế Bóp Nghẹt Thời Gian (Exponential Time Decay):** Hàm suy giảm logarit $e^{-\lambda \cdot t}$ bắt chước nguyên lý phân rã vật lý hạt nhân. Điểm độc đáo nằm ở việc: Hai người cùng tên A, cùng bị đi tù do ăn trộm, nhưng một vụ xảy ra vào 2012, một vụ xảy ra mới sáng hôm qua 2026. Công cụ Tavily thông thường sẽ trả về lộn xộn cả 2. Việc áp dụng hàm phân rã mũi tên triệt tiêu bớt sức mạnh của bài báo xuất bản 14 năm trước, tự ép những tin tức nóng hổi trồi lên top.
*   **Tác dụng cốt lõi:** Khi Agent 1 tìm kiếm cụm từ nhạy cảm *"Chủ tịch nước từ chức"*, rất nhiều web cá độ bóng đá dùng SEO lậu để cướp Top 1 Google. Nếu để Agent 2 đọc bừa cái content rác rưởi ấy, hậu quả đầu ra sai lệch sẽ không cách nào cứu giãn. Toán học đã bóp méo bảng xếp hạng, dọn đường cho Agent 2 cắn lấy đoạn text tinh khiết và uy nghi nhất!


---

## 3. TRIẾT LÝ RAG "ANTI-SWELLING" (HIỆN TƯỢNG PHỊNH TRƯỚNG NGỮ CẢNH)

Đây là một sự biến thể đảo ngược nhằm khắc phục cái gai lớn mà kiến trúc **RAG (Retrieval-Augmented Generation)** kinh điển gặp phải khi tiếp xúc văn bản quá dài.

### 💡 Vấn đề "Mù Ngữ Cảnh" của RAG Cũ:
Hệ RAG truyền thống phải dùng "dao" chặt bài báo (Chunking process) thành từng phân khúc theo độ dài cố định là 500 từ. 
> Ví dụ, Đoạn 1 lưu trữ: _"Nguyễn Văn A là giám đốc lừng lẫy."_
> Sang đoạn thẻ 2, câu truyện viết: _"Hắn ta đã tham ô 100 tỷ đồng và bị truy nã."_
Nếu máy tìm kiếm nhúng RAG chỉ móc trúng lên khúc Đoạn 2 ném cho mô hình AI, AI lập tức dính ảo giác ngắt mạch vì nó không truy ngược lại được danh tính từ _"Hắn ta"_ (Sự kiện tách bến đứt gãy ngữ cảnh).

### 💡 Giải pháp Anti-Swelling (Siêu ngậm khối) và Tác dụng: 
Nhờ lợi dụng sức chứa Hố Đen **1.000.000 Token của Gemini Flash Lite**, chúng ta cự tuyệt hoàn toàn lệnh cắt Chunking rườm rà và chậm chạp! 
*   **Cơ chế ngấm toàn phần (Holistic Reading):** Gemini hút ráo toàn bộ tinh hoa từ 1 hoặc 5 trang báo 20.000 từ. Việc đọc văn bản 1 mảng liền mạch giúp nó kết nối triệt để các đại từ nhân xưng và móc nối các phân đoạn câu phức tạp.
*   **Tác dụng tuyệt đỉnh:** Nó tự động "Tiết ra" 200 chữ nén đặc nhất (Đóng mác chuẩn Extractor Mode) cho con chip não xịn nhất GPT-4o-mini thưởng thức. Giải pháp trung gian này vừa tiết kiệm được cả triệu lượng token rác gây phung phí API đắt đỏ của GPT-4, vừa né được dớp "Cắt Nhầm Văn Bản" băm lỗ chỗ của RAG thời tiền sử. Mang lại bảng Data vô trùng cho Agent 3 hoạt động.


---

## 4. CHI TÚI THẦN BẢO VỆ: BỘ CACHE KHÁNG ẢO GIÁC (SEMANTIC CACHE + N.E.R)

Nơi mà DB MongoDB trở thành Trí Khôn nhân tạo vòng ngoài, vừa tối ưu tốc độ x10 lần, vừa sở hữu thiết kế "Rào chắn hai điểm va chạm".

```text
=========================================================================================
  HỆ THỐNG PHÒNG NGỰ KÉP TẠI BỘ ĐỆM: VECTOR MATCHING + NAMED ENTITY RECOGNITION (NER)
=========================================================================================
                                         
   [ CÂU HỎI MỚI ĐẾN TỪ USER ] ───> ("Ông A bị bắt vì tham ô 15 tỷ đồng")
          │
      (Chia Thành 2 Luồng Phân Tích Song Song)
          │
          ├─────────────────────────────────────────────────┐
          v                                                 v
 ┌──────────────────────────┐                   ┌──────────────────────────┐
 │ LUỒNG 1: Vectorization   │                   │ LUỒNG 2: NER Extraction  │
 │ (SBERT Semantic Model)   │                   │ (Regex Scanner Rules)    │
 └──────────────────────────┘                   └──────────────────────────┘
          │ Đẩy Lên Mạng HuggingFace                      │ Bóc Tách Từng Chữ 
          v                                               v
  [ Vector 768 Chiều Không Gian ]                 [ Gắp Lấy Thực Thể Khóa ]
  [0.12, -0.4, 0.88, 0.99, ...]                   - Biến Tiền Tệ: "15 tỷ đồng"
          │                                       - Biến Nhân Vật: "Ông A"
          │                                                 │
          v                                                 │
 ┌──────────────────────────┐                               │
 │ MONGODB ATLAS KNN SEARCH │                               │
 │ (Tìm hàng xóm gần nhất)  │                               │
 └──────────────────────────┘                               │
          │                                                 │
          v                                                 │
 [ Tìm Thấy Dấu Vết Trong Lịch Sử! ]                        │
 Câu Cũ: "Ông A bị bắt vì tham ô 2 tỷ"                      │
 👉 Cosine Similarity: 98% (Vì cực giống ngữ nghĩa)         │
          │                                                 │
          v                                                 v
     ┌────────────────────────────────────────────────────────────┐
     │  CỬA ẢI KIỂM CHUẨN THỰC THỂ KÉP (CROSS-ENTITY VALIDATION)  │
     └────────────────────────────────────────────────────────────┘
                            │ Check đối sánh chéo 1:1 :
                            │ Số bên cũ: "15 tỷ"  <======>  Số bên mới: "2 tỷ"
                            │ ❌ BÁO ĐỘNG MISMATCH! (Lệch cực nặng hệ số lõi)
                            │
        ┌───────────────────┴────────────────────┐
        v                                        v
[ KHỚP LÕI TOÀN BỘ HAI BÊN ]             [ LỆCH THỰC THỂ CỐT LÕI MỘT BÊN ]
        │                                        │
        v                                        v
  ( CACHE HIT )                            ( CACHE MISS )
Bốc thẳng dữ liệu cũ,                Xé bỏ lệnh gọi Cache, dập cầu dao báo sai!
Đáp vào mặt Frontend sau 2s.         Bóp còi gọi Bộ Đội Agent LangGraph xuất quân để xác thực!
```

### 💡 Mô tả Giải pháp "Chồng lấn NER" và Tác dụng Thực Tiễn
Lý do căn bản khiến chúng ta không thể ném hoàn toàn niềm tin vào 1 cụm Vector Search là bài toán đòn bẩy độ giống nhau (Cosine Threshold). Nỗi nhức nhối hiện hình khi một tờ báo có bài: _"Tài xế BMW tông 15 chiếc xe máy"_, còn ngày hôm sau kẻ xấu lại tung Fake News ác ý câu y hệt nhưng đổi biến: _"Tài xế BMW tông tận 50 chiếc xe máy, chính quyền che dấu!"_
Nếu chỉ dựa vào Vector, máy học hiểu nhầm đây chỉ là sai sót đánh máy hoặc dị bản cách chia động từ từ đồng nghĩa. Nó chỉ mặt **similarity là 99%** và móc CSDL đáp ra chữ ĐÚNG LÀ SỰ THẬT cho Fake News.

*   **Tác Dụng Bịt Lỗ Hổng Ảo Giác (Anti-Hallucination Barrier):** Hệ thống phái riêng Nhánh số 2 đi chạy máy dò quét xuyên thủng để lọc nhể từng hạt chữ số có mặt mòi cấu trúc "Tiền tệ, Ngày tháng, Khối lượng đo". Sau khi luồng Vector vác bài cũ tới cửa ngõ, hai bộ Entities đặt đè lên nhau. Chênh lệch **số 15 và số 50** lập tức đứt gãy khớp chéo $\rightarrow$ Cửa ải nhận diện được bẫy lừa người dùng, từ đó quyết định đập vỡ cọc CSDL cũ bắt AI phải lặn lội tự truy xuất tin mới toanh từ Internet. Đây là bảo ngọc minh chứng độ vững như thạch của hệ thống truy vấn NCKH.
