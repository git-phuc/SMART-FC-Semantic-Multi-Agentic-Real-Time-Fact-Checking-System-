"""
LangGraph Workflow - Orchestrator kết nối 3 agents thành pipeline.
Định nghĩa graph: START → Agent1 → Agent2 → Agent3 → END
"""

from langgraph.graph import StateGraph, START, END  # type: ignore[import-untyped]
from langgraph.graph.state import CompiledStateGraph  # type: ignore[import-untyped]

from graph.state import VerificationState
from agents.query_agent import QueryAgent
from agents.extractor_agent import ExtractorAgent
from agents.reasoning_agent import ReasoningAgent
from utils.logger import get_logger

logger = get_logger("Graph.Workflow")


def create_workflow() -> CompiledStateGraph:
    """
    Tạo LangGraph workflow với 3 nodes (3 agents).

    Flow:
        START → query_agent → extractor_agent → reasoning_agent → END

    Returns:
        Compiled StateGraph sẵn sàng chạy
    """
    # Khởi tạo agents
    query_agent = QueryAgent()
    extractor_agent = ExtractorAgent()
    reasoning_agent = ReasoningAgent()

    # Tạo graph
    workflow = StateGraph(VerificationState)

    # Thêm nodes (mỗi node là một agent)
    workflow.add_node("query_agent", query_agent.run)
    workflow.add_node("extractor_agent", extractor_agent.run)
    workflow.add_node("reasoning_agent", reasoning_agent.run)

    # Kết nối các nodes theo thứ tự
    workflow.add_edge(START, "query_agent")
    workflow.add_edge("query_agent", "extractor_agent")
    workflow.add_edge("extractor_agent", "reasoning_agent")
    workflow.add_edge("reasoning_agent", END)

    # Compile graph
    app = workflow.compile()

    logger.info("[Workflow] Graph compiled: START → Agent1 → Agent2 → Agent3 → END")
    return app


def run_verification(claim: str) -> dict:
    """
    Chạy toàn bộ verification pipeline cho một claim.

    Args:
        claim: Thông tin/tin tức cần kiểm chứng

    Returns:
        Final state dictionary chứa toàn bộ kết quả
    """
    logger.info(f"[Workflow] Starting verification for: {claim[:100]}...")

    # Tạo workflow
    app = create_workflow()

    # Tạo initial state
    initial_state = {
        "user_input": claim,
        "agent_logs": [],
    }

    # Chạy pipeline
    final_state = app.invoke(initial_state)

    logger.info("[Workflow] Verification complete!")
    return final_state


def run_verification_with_cache(claim: str) -> dict:
    """
    Chạy verification pipeline CÓ Two-Stage Semantic Cache.

    Flow:
        1. Check cache (Vector Search + NER) → nếu HIT, trả kết quả ngay (~1-2s)
        2. Nếu MISS → chạy full pipeline 3 agents (~200s)
        3. Sau khi pipeline xong → lưu kết quả vào cache

    Args:
        claim: Thông tin/tin tức cần kiểm chứng

    Returns:
        Final state dictionary chứa toàn bộ kết quả
    """
    import time

    # --- Lấy singleton cache (embedder chỉ load 1 lần) ---
    from database.mongo_cache import get_cache
    cache = get_cache()

    # --- Stage 1 + 2: Check cache ---
    if cache:
        try:
            start_cache = time.time()
            cache_result = cache.check_cache(claim)
            cache_time = time.time() - start_cache

            if cache_result.get("hit"):
                logger.info(
                    f"[Workflow] ⚡ CACHE HIT! "
                    f"score={cache_result.get('score', 0):.4f} | "
                    f"time={cache_time:.2f}s | "
                    f"cached_query=\"{cache_result.get('cached_query', '')[:60]}...\""
                )
                # Inject original cached query into verdict for UI transparency
                verdict_data = cache_result["data"]
                
                # --- Quick Rewrite (Groq): Sửa ngữ cảnh của Summary cho khớp với câu hỏi của User ---
                try:
                    from config.settings import get_llm_for_agent
                    from langchain_core.messages import HumanMessage  # type: ignore[import-untyped]
                    fast_llm = get_llm_for_agent("AGENT1")
                    original_summary = verdict_data.get("summary", "")
                    
                    rewrite_prompt = (
                        f"Viết lại đoạn tóm tắt kết quả kiểm chứng dưới đây sao cho các từ ngữ/chủ ngữ giống trực tiếp với lời văn của tin đồn mà người dùng vừa hỏi.\n"
                        f"TUYỆT ĐỐI GIỮ NGUYÊN ý nghĩa, kết luận và các bằng chứng.\n"
                        f"KHÔNG giải thích thêm, chỉ trả về đoạn văn tóm tắt viết lại.\n\n"
                        f"Tin đồn của người dùng: \"{claim}\"\n"
                        f"Tóm tắt cũ (cần viết lại): \"{original_summary}\"\n\n"
                        f"Tóm tắt mới:"
                    )
                    rewrite_res = fast_llm.invoke([HumanMessage(content=rewrite_prompt)])
                    new_summary = str(rewrite_res.content).strip().strip('"')
                    if new_summary:
                        verdict_data["summary"] = new_summary
                        logger.info(f"[Workflow] Dùng Groq viết lại summary thành công ({time.time() - start_cache:.2f}s)")
                except Exception as rewrite_err:
                    logger.warning(f"[Workflow] Lỗi rewrite summary: {rewrite_err}")

                verdict_data["cached_query"] = claim  # Trả lại câu của user, không báo câu DB nữa

                # Trả state giống format của pipeline
                return {
                    "user_input": claim,
                    "verdict": verdict_data,
                    "agent_logs": [
                        f"[Cache] ⚡ Cache HIT trong {cache_time:.2f}s "
                        f"(similarity={cache_result.get('score', 0):.4f})"
                    ],
                    "from_cache": True,
                }
            else:
                logger.info(f"[Workflow] Cache MISS ({cache_time:.2f}s) — running full pipeline")
        except Exception as e:
            logger.warning(f"[Workflow] Cache check error: {e}")

    # --- Cache MISS: chạy full pipeline ---
    final_state = run_verification(claim)

    # --- Lưu kết quả vào cache ---
    if cache and final_state.get("verdict"):
        try:
            cache.save_to_cache(claim, final_state["verdict"])
            final_state.setdefault("agent_logs", []).append(
                "[Cache] 💾 Đã lưu kết quả vào MongoDB Cache"
            )
        except Exception as e:
            logger.warning(f"[Workflow] Cache save error: {e}")

    return final_state
