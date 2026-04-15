"""
Agent 3: Reasoning & Verdict.
Phiên bản v3 — Agentic Feedback Loop:
  - Không còn `if rule_applied == "RULE 4" and retry_count <= 1` cứng.
  - Đọc `feedback_signal` từ model để quyết định có trigger loop không.
  - Model tự quyết định khi nào cần search lại và tìm theo hướng nào.
"""

import json

from agents.base_agent import BaseAgent
from prompts.reasoning_prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.logger import log_agent_step


class ReasoningAgent(BaseAgent):
    """
    Agent cuối cùng trong pipeline.
    - Nhận danh sách tóm tắt từ Agent 2
    - Tự lọc nguồn → đọc bối cảnh → đối chiếu bằng chứng → suy luận
    - Đưa ra verdict: THẬT / GIẢ / CHƯA XÁC ĐỊNH
    - Tự quyết định có cần yêu cầu Agent 1 search lại không (feedback_signal)
    """

    def __init__(self):
        super().__init__("ReasoningAgent", "AGENT3", max_prompt_chars=60_000)

    def run(self, state: dict) -> dict:
        """
        Suy luận + Phán định + Phát tín hiệu feedback nếu cần.

        Args:
            state: Phải chứa keys: user_input, extracted_info

        Returns:
            State đã cập nhật với: verdict, feedback_to_agent1
        """
        user_input = state.get("user_input", "")
        extracted_info = state.get("extracted_info", {})
        crawled_contents = state.get("crawled_contents", [])

        self.add_log(state, "Starting reasoning process")

        # Chuẩn bị text từ extracted_info
        extracted_info_text = self._prepare_extracted_text(extracted_info, crawled_contents)

        # Gọi LLM suy luận
        log_agent_step(self.logger, self.name, "Reasoning with chain of thought")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            claim=user_input,
            extracted_info=extracted_info_text,
        )

        llm_response = self.call_llm(SYSTEM_PROMPT, user_prompt)
        verdict = self.parse_json_response(llm_response)

        # Validate và fill defaults
        verdict = self._validate_verdict(verdict)

        # Log chain_of_thought để debug
        cot = verdict.get("chain_of_thought", "")
        if cot:
            self.logger.info(f"[{self.name}] 🧠 Chain of Thought: {cot[:300]}...")

        # Fix URLs bịa → URLs thật
        if crawled_contents:
            verdict = self._fix_urls(verdict, crawled_contents)

        # === ĐỌC FEEDBACK SIGNAL TỪ MODEL ===
        # Thay vì code cứng "if RULE 4 and retry_count <= 1",
        # giờ agent lắng nghe quyết định của model.
        feedback_signal = verdict.get("feedback_signal", {})
        request_deep_search = feedback_signal.get("request_deep_search", False)
        suggested_angle = feedback_signal.get("suggested_search_angle", "")
        signal_reason = feedback_signal.get("reason", "")

        retry_count = state.get("retry_count", 0)
        MAX_RETRIES = 2  # Hard ceiling để tránh infinite loop trong mọi trường hợp

        if request_deep_search and retry_count < MAX_RETRIES:
            feedback_msg = (
                f"Agent 3 yêu cầu tìm kiếm lại. "
                f"Lý do: {signal_reason}. "
                f"Góc độ tìm kiếm đề xuất: {suggested_angle}"
            )
            state["feedback_to_agent1"] = feedback_msg
            self.logger.warning(
                f"[{self.name}] 🔄 Kích hoạt Feedback Loop theo yêu cầu model "
                f"(Vòng {retry_count + 1}/{MAX_RETRIES}): {suggested_angle[:100]}"
            )
            self.add_log(state, f"🔄 Model yêu cầu search lại: {feedback_msg}")
        else:
            if request_deep_search and retry_count >= MAX_RETRIES:
                self.logger.warning(
                    f"[{self.name}] ⛔ Model muốn search lại nhưng đã đạt MAX_RETRIES ({MAX_RETRIES}). "
                    f"Chốt verdict hiện tại."
                )
            # Xóa feedback — pipeline kết thúc ở đây
            state["feedback_to_agent1"] = ""

        state["verdict"] = verdict

        # Log tóm tắt kết quả
        accepted_count = len(verdict.get("filtering", {}).get("sources_accepted", []))
        rejected_count = len(verdict.get("filtering", {}).get("sources_rejected", []))
        claim_context = verdict.get("verifiability_assessment", {}).get("claim_context", "N/A")

        self.add_log(
            state,
            f"Verdict: {verdict.get('verdict', 'N/A')} "
            f"(Confidence: {verdict.get('confidence_score', 'N/A')}) | "
            f"Rule: {verdict.get('rule_applied', 'N/A')} | "
            f"Sources: {accepted_count} accepted / {rejected_count} rejected | "
            f"Context: {claim_context[:60]} | "
            f"Deep search: {request_deep_search}"
        )

        return state

    def _prepare_extracted_text(self, extracted_info: dict, crawled_contents: list) -> str:
        """
        Chuẩn bị text từ extracted_info để đưa vào prompt.
        Bổ sung danh sách URL thật để model không tự tạo URL.
        """
        if extracted_info.get("parse_error"):
            text = extracted_info.get("raw_response", "")
        else:
            text = json.dumps(extracted_info, ensure_ascii=False, indent=2)

        # Luôn bổ sung danh sách URL thật — phòng tránh hallucination URL
        if crawled_contents:
            text += "\n\n## DANH SÁCH URL THẬT (chỉ dùng các URLs này, KHÔNG tự tạo URL):\n"
            for c in crawled_contents:
                text += f"- {c.get('title', 'N/A')}: {c.get('url', '')}\n"

        return text

    def _validate_verdict(self, verdict: dict) -> dict:
        """
        Đảm bảo verdict có đủ fields cần thiết.
        Thêm defaults nếu thiếu — bao gồm feedback_signal và claim_context mới.
        """
        defaults = {
            "chain_of_thought": "",
            "filtering": {
                "total_sources_received": 0,
                "sources_accepted": [],
                "sources_rejected": [],
                "top_sources_for_arguments": [],
            },
            "verifiability_assessment": {
                "is_verifiable": False,
                "claim_context": "Không xác định được bối cảnh",
                "reasoning": "Không đủ thông tin để đánh giá",
            },
            "verdict": "CHƯA XÁC ĐỊNH",
            "verdict_en": "UNVERIFIED",
            "confidence_score": 0.0,
            "summary": "Không đủ thông tin để đưa ra kết luận.",
            "rule_applied": "RULE 4",
            "rule_explanation": "Không có nguồn trực tiếp liên quan",
            "divergence_found": False,
            "divergence_details": None,
            "arguments": [],
            "reasoning": {
                "layer1_filtering": "Không có dữ liệu",
                "layer2_context": "Không có dữ liệu",
                "layer3_evidence": "Không có dữ liệu",
                "layer4_verdict": "Không có dữ liệu",
            },
            "feedback_signal": {
                "request_deep_search": False,
                "suggested_search_angle": None,
                "reason": "Verdict đã đủ tự tin",
            },
            "recommendation": "Hãy tìm hiểu thêm từ các nguồn tin chính thống.",
        }

        for key, default_value in defaults.items():
            if key not in verdict:
                verdict[key] = default_value
            elif isinstance(default_value, dict) and isinstance(verdict.get(key), dict):
                for sub_key, sub_default in default_value.items():
                    if sub_key not in verdict[key]:
                        verdict[key][sub_key] = sub_default

        return verdict

    def _fix_urls(self, verdict: dict, crawled_contents: list) -> dict:
        """
        Thay thế URLs bịa bằng URLs thật từ crawled_contents.
        Chỉ fallback khi thực sự không tìm được match — không gán bừa.
        """
        from urllib.parse import urlparse

        real_urls = {
            c.get("url", ""): c.get("title", "").lower()
            for c in crawled_contents if c.get("url")
        }

        domains = {}
        for url in real_urls:
            domain = urlparse(url).netloc.replace("www.", "")
            if domain:
                domains[domain] = url

        assigned_urls: set = set()

        def _find_real_url(claimed_url: str, source_name: str) -> str:
            # 1. Match chính xác
            if claimed_url in real_urls:
                assigned_urls.add(claimed_url)
                return claimed_url

            # 2. Match theo domain
            claimed_domain = urlparse(claimed_url).netloc.replace("www.", "") if claimed_url else ""
            if claimed_domain and claimed_domain in domains:
                url = domains[claimed_domain]
                assigned_urls.add(url)
                return url

            # 3. Match theo tên báo vs title bài
            source_lower = (source_name or "").lower().strip()
            if source_lower and source_lower not in ("", "n/a", "unknown"):
                best_url, best_score = "", 0
                source_words = set(source_lower.split())
                for url, title in real_urls.items():
                    title_words = set(title.split())
                    common = len(source_words & title_words)
                    if common > best_score:
                        best_score = common
                        best_url = url

                if best_url and best_score >= 1:
                    assigned_urls.add(best_url)
                    return best_url

            return ""

        for arg in verdict.get("arguments", []):
            if isinstance(arg, dict):
                claimed = arg.get("source_url", "")
                source = arg.get("source_name", "")
                fixed = _find_real_url(claimed, source)
                if fixed != claimed:
                    log_agent_step(
                        self.logger, self.name, "Fixed URL",
                        f"{claimed[:50]} → {fixed[:50] if fixed else '(empty)'}"
                    )
                arg["source_url"] = fixed

        return verdict