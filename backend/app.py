import streamlit as st
import time
import threading
from graph.workflow import run_verification_with_cache as run_verification

# === Cấu hình trang (PHẢI ĐẶT ĐẦU TIÊN) ===
st.set_page_config(
    page_title="Hệ thống Kiểm chứng Tin tức",
    page_icon="🔍",
    layout="centered"
)


# === Preload cache (embedding model + MongoDB) lúc app start ===
@st.cache_resource(show_spinner="🔄 Đang khởi tạo hệ thống (load model + kết nối DB)...")
def _preload_cache():
    """Load embedding model + MongoDB connection 1 lần duy nhất."""
    from database.mongo_cache import get_cache
    return get_cache()


_preload_cache()

# === Custom CSS ===
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Inter', sans-serif;
    }
    
    /* Nền Darkmode Cinematic */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* Giao diện huy hiệu thời gian (Glassmorphism) */
    .inference-badge {
        display: inline-block;
        padding: 6px 18px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 700;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
        letter-spacing: 0.5px;
    }
    .badge-cache {
        background: linear-gradient(135deg, rgba(0,230,118,0.2), rgba(29,233,182,0.4));
        color: #00e676;
        border-color: rgba(0, 230, 118, 0.4);
    }
    .badge-pipeline {
        background: linear-gradient(135deg, rgba(108,92,231,0.2), rgba(162,155,254,0.4));
        color: #a29bfe;
        border-color: rgba(162, 155, 254, 0.4);
    }
    
    /* Khung kết quả chính (Verdict Box Cinematic) */
    .verdict-box {
        padding: 25px;
        border-radius: 16px;
        border-left: 8px solid;
        margin-bottom: 25px;
        margin-top: 10px;
        background: rgba(22, 27, 34, 0.8);
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        backdrop-filter: blur(12px);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .verdict-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.6);
    }
    .verdict-THẬT { border-color: #00e676; }
    .verdict-GIẢ { border-color: #ff1744; }
    .verdict-CHƯA_XÁC_ĐỊNH { border-color: #ffeb3b; }
    
    /* Tiêu đề kết quả */
    .verdict-title {
        font-family: 'Outfit', sans-serif;
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    .verdict-score {
        font-size: 1.1em;
        opacity: 0.85;
        font-weight: 300;
    }

    /* Chain of Thought box */
    .cot-box {
        background: rgba(108, 92, 231, 0.08);
        border: 1px solid rgba(162, 155, 254, 0.25);
        border-radius: 10px;
        padding: 14px 18px;
        font-size: 0.92em;
        line-height: 1.7;
        color: #b8b4d8;
        font-style: italic;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# === Giao diện Sidebar ===
with st.sidebar:
    st.markdown("## 🧬 SMART-FC v5.0")
    st.caption("Hệ thống điểm chuẩn kiểm chứng thông tin tự động tiếng Việt (NCKH). Vận hành dựa trên nền tảng Multi-Agentic thời gian thực.")
    
    st.divider()
    st.markdown("### 🤖 Tri-Agent Mix-AI")
    st.info("⚡ T.Truy vấn: **Groq Llama-3.1**")
    st.success("🧠 T.Trích xuất: **Gemini 2.5 Flash Lite**")
    st.error("⚖️ T.Suy luận: **OpenAI GPT-4o-Mini**")
    
    st.divider()
    st.markdown("### ⚡ Công nghệ Nền tảng")
    st.success("✔ Lớp đệm Vector-NER Cache kép")
    st.success("✔ Luân chuyển API Round-Robin chống Rate limit")
    st.success("✔ Web Crawler Bất đồng bộ (Tavily Fallback)")

# === Giao diện chính ===
st.title("🤖 SMART-FC: Hệ thống Kiểm chứng Tin giả")
st.markdown("Hệ thống kiểm chứng tự động Đa tác tử. Hãy nhập văn bản hoặc tin đồn cần xác minh vào khung chat bên dưới.")

# Khởi tạo lịch sử chat
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Chào bạn! Hãy nhập tin tức hoặc tin đồn bạn muốn kiểm chứng."}
    ]


# ============================================================
# Hàm render thời gian suy luận
# ============================================================
def render_inference_time(time_taken: float, from_cache: bool = False):
    """Hiển thị badge thời gian suy luận."""
    if from_cache:
        badge_class = "badge-cache"
        label = f"⚡ Cache Hit — {time_taken:.2f}s"
    else:
        badge_class = "badge-pipeline"
        if time_taken >= 60:
            minutes = int(time_taken // 60)
            seconds = time_taken % 60
            label = f"🧠 Pipeline — {minutes}m {seconds:.1f}s"
        else:
            label = f"🧠 Pipeline — {time_taken:.1f}s"

    st.markdown(
        f'<span class="inference-badge {badge_class}">{label}</span>',
        unsafe_allow_html=True,
    )


# ============================================================
# Hàm render kết quả verdict
# ============================================================
def render_verdict(verdict_data: dict, time_taken: float = 0.0, from_cache: bool = False):
    # Hiển thị thời gian suy luận
    if time_taken > 0:
        render_inference_time(time_taken, from_cache)

    verdict_text = verdict_data.get("verdict", "CHƯA XÁC ĐỊNH")
    confidence = verdict_data.get("confidence_score", 0.0)

    color_map = {
        "THẬT": "#00b894",
        "GIẢ": "#d63031",
        "CHƯA XÁC ĐỊNH": "#fdcb6e"
    }
    color = color_map.get(verdict_text, "gray")

    v_class = "CHƯA_XÁC_ĐỊNH"
    if verdict_text == "THẬT":
        v_class = "THẬT"
    elif verdict_text == "GIẢ":
        v_class = "GIẢ"

    # Verdict box chính
    st.markdown(f'''
    <div class="verdict-box verdict-{v_class}">
        <div class="verdict-title">PHÁN ĐỊNH: <span style="color: {color};">{verdict_text}</span></div>
        <div class="verdict-score">Điểm tin cậy (Confidence): <strong style="color: {color};">{confidence:.1%}</strong></div>
    </div>
    ''', unsafe_allow_html=True)

    # Tóm tắt phán quyết
    st.info(verdict_data.get("summary", "Không có tóm tắt."))

    # ── Chain of Thought (mới) ────────────────────────────────
    chain_of_thought = verdict_data.get("chain_of_thought", "").strip()
    if chain_of_thought:
        with st.expander("🧠 Chuỗi suy luận của AI (Chain of Thought)", expanded=False):
            st.markdown(
                f'<div class="cot-box">{chain_of_thought}</div>',
                unsafe_allow_html=True,
            )

    # ── Luận điểm & Bằng chứng ───────────────────────────────
    raw_arguments = verdict_data.get("arguments", [])
    valid_arguments = [arg for arg in raw_arguments if arg.get("source_url", "").strip()]
    display_arguments = valid_arguments[:3]

    if display_arguments:
        st.divider()
        st.markdown("#### 📝 Luận điểm & Bằng chứng")
        for i, arg in enumerate(display_arguments, 1):
            with st.expander(f"{i}. {arg.get('title', 'Luận điểm')}", expanded=True):
                st.write(arg.get("content", ""))
                if arg.get("evidence"):
                    st.caption(f"Trích dẫn: {arg.get('evidence')}")
                st.markdown(f"Đọc thêm: [{arg.get('source_name', 'Nguồn')}]({arg.get('source_url')})")

    if verdict_data.get("recommendation"):
        st.success(verdict_data.get("recommendation"))


# ============================================================
# Hiển thị lịch sử tin nhắn
# ============================================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if isinstance(msg["content"], dict):
            render_verdict(
                msg["content"],
                time_taken=msg.get("time_taken", 0.0),
                from_cache=msg.get("from_cache", False),
            )
        else:
            st.markdown(msg["content"])


# ============================================================
# Xử lý khi người dùng nhập tin
# ============================================================
if prompt := st.chat_input("Nhập tin đồn bạn muốn kiểm chứng..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        final_state_container = {}

        def run_pipeline(user_input, output_dict):
            try:
                output_dict["state"] = run_verification(user_input)
            except Exception as e:
                import traceback
                output_dict["error"] = str(e)
                output_dict["traceback"] = traceback.format_exc()

        pipeline_thread = threading.Thread(target=run_pipeline, args=(prompt, final_state_container))
        pipeline_thread.start()

        start_time = time.time()

        with st.status("🔍 Đang kiểm chứng thông tin...", expanded=True) as status_box:
            log_container = st.empty()

            while pipeline_thread.is_alive():
                elapsed = time.time() - start_time
                if elapsed < 5:
                    log_container.markdown("⏳ **[Agent 1 — QueryAgent]** Đang phân tích tin và tạo từ khóa tìm kiếm...")
                elif elapsed < 12:
                    log_container.markdown("🌐 **[Agent 1 — WebSearch]** Đang tìm kiếm trên Internet (Tavily API) và làm sạch nội dung...")
                elif elapsed < 25:
                    log_container.markdown("🧠 **[Agent 2 — ExtractorAgent]** Đang đọc hàng chục ngàn từ và trích xuất chứng cứ...")
                elif elapsed < 50:
                    log_container.markdown("⚖️ **[Agent 3 — ReasoningAgent]** Đang suy luận, đối chiếu các nguồn và xây dựng luận điểm...")
                elif elapsed < 90:
                    log_container.markdown("🤔 **Thinking...** Agent 3 đang phân tích sâu hoặc yêu cầu Agent 1 tìm kiếm thêm nguồn...")
                else:
                    mins = int(elapsed // 60)
                    log_container.markdown(f"🧠 **Deep Thinking... ({mins}m+)** Pipeline đang chạy vòng lặp phản hồi — tìm thêm bằng chứng để đưa ra phán quyết chính xác nhất...")
                time.sleep(0.5)

            pipeline_thread.join()

        # Xử lý kết quả SAU KHI status block đã đóng
        time_taken = time.time() - start_time

        if "error" in final_state_container:
            st.error(f"❌ Đã có lỗi: {final_state_container['error']}")
            with st.expander("🔍 Chi tiết lỗi (debug)", expanded=False):
                st.code(final_state_container.get("traceback", "Không có traceback"))
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ Lỗi hệ thống: {final_state_container['error']}",
            })
        elif "state" in final_state_container:
            final_state = final_state_container["state"]
            verdict_data = final_state.get("verdict", {})
            from_cache = final_state.get("from_cache", False)

            render_verdict(verdict_data, time_taken=time_taken, from_cache=from_cache)

            st.session_state.messages.append({
                "role": "assistant",
                "content": verdict_data,
                "time_taken": time_taken,
                "from_cache": from_cache,
            })
        else:
            st.warning("⚠️ Pipeline kết thúc nhưng không có kết quả. Vui lòng thử lại.")