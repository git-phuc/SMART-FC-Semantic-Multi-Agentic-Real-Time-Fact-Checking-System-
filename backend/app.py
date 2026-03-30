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


_preload_cache()  # Chạy 1 lần khi app khởi động, cache lại cho các lần sau

# === Custom CSS ===
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .inference-badge {
        display: inline-block;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 700;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid rgba(255,255,255,0.2);
    }
    .badge-cache {
        background: linear-gradient(135deg, #00b894, #00cec9);
        color: white;
    }
    .badge-pipeline {
        background: linear-gradient(135deg, #6c5ce7, #a29bfe);
        color: white;
    }
    .verdict-box {
        padding: 20px;
        border-radius: 12px;
        border-left: 8px solid;
        margin-bottom: 20px;
        background-color: rgba(128, 128, 128, 0.05);
    }
    .verdict-THẬT { border-color: #00b894; }
    .verdict-GIẢ { border-color: #d63031; }
    .verdict-CHƯA_XÁC_ĐỊNH { border-color: #fdcb6e; }
    .verdict-title {
        font-size: 1.6rem;
        font-weight: 800;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# === Giao diện Sidebar ===
with st.sidebar:
    st.markdown("### 🧬 Về SMART-FC")
    st.caption("Semantic Multi-Agentic Real-Time Fact-Checking. Khung hệ thống điểm chuẩn kiểm chứng thông tin tự động tiếng Việt.")
    
    st.divider()
    st.markdown("### 🧠 Kiến trúc Mix-LLM")
    st.info("Trình truy vấn: **LLaMA-3.1-8B**")
    st.info("Trình trích xuất: **Gemini-2.5-Flash**")
    st.warning("Trình suy luận: **LLaMA-3.3-70B**")
    
    st.divider()
    st.markdown("### ⚡ Công nghệ Tăng tốc")
    st.success("✔ Two-Stage Semantic Cache")
    st.success("✔ MongoDB Vector Search")
    st.success("✔ Round-Robin API Rotation")

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
    if verdict_text == "THẬT": v_class = "THẬT"
    elif verdict_text == "GIẢ": v_class = "GIẢ"

    st.markdown(f'''
    <div class="verdict-box verdict-{v_class}">
        <div class="verdict-title">Phán định: <span style="color: {color};">{verdict_text}</span></div>
        <div style="font-size: 1.1em; opacity: 0.8;">Độ tin cậy: <strong>{confidence:.1%}</strong></div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.info(verdict_data.get("summary", "Không có tóm tắt."))

    arguments = verdict_data.get("arguments", [])
    if arguments:
        st.divider()
        st.markdown("#### 📝 Luận điểm & Bằng chứng")
        for i, arg in enumerate(arguments, 1):
            with st.expander(f"{i}. {arg.get('title', 'Luận điểm')}", expanded=True):
                st.write(arg.get("content", ""))
                if arg.get("evidence"):
                    st.caption(f"Trích dẫn: {arg.get('evidence')}")
                if arg.get("source_url"):
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
                elif elapsed < 40:
                    log_container.markdown("⚖️ **[Agent 3 — ReasoningAgent]** Đang suy luận, đối chiếu các nguồn và xây dựng luận điểm...")
                else:
                    log_container.markdown("✍️ **[Agent 3 — ReasoningAgent]** Sắp xong rồi, đang đưa ra phán quyết cuối cùng...")
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

