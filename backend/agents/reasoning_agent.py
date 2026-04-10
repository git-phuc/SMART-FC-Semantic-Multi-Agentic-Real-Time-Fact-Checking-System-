"""
Agent 3: Reasoning & Verdict.
Nhận danh sách tóm tắt từ Agent 2 → Lọc bài liên quan → Suy luận → Phán quyết.

Nguyên tắc: Agent 3 chịu trách nhiệm TOÀN BỘ việc phán xét:
1. Lọc bài nào liên quan / reject bài không liên quan
2. Tự đánh giá claim có thể kiểm chứng không
3. Đánh giá credibility nguồn
4. Viết chain_of_thought → suy luận → verdict THẬT / GIẢ / CHƯA XÁC ĐỊNH
"""

import json

from agents.base_agent import BaseAgent
from prompts.reasoning_prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.logger import log_agent_step


class ReasoningAgent(BaseAgent):
    """
    Agent cuối cùng trong pipeline.
    - Nhận danh sách tóm tắt từ Agent 2
    - Tự lọc bài liên quan / không liên quan
    - Tự đánh giá khả năng kiểm chứng của claim
    - Viết chain_of_thought trước khi kết luận (giảm hallucination)
    - Đưa ra verdict: THẬT / GIẢ / CHƯA XÁC ĐỊNH
    """

    def __init__(self):
        super().__init__("ReasoningAgent", "AGENT3", max_prompt_chars=60_000)

    def run(self, state: dict) -> dict:
        """
        Lọc + Suy luận + Phán định cuối cùng.

        Args:
            state: Phải chứa keys: user_input, extracted_info

        Returns:
            State đã cập nhật với: verdict
        """
        user_input = state.get("user_input", "")
        extracted_info = state.get("extracted_info", {})
        crawled_contents = state.get("crawled_contents", [])

        self.add_log(state, "Starting filtering & reasoning process")

        # Chuẩn bị text từ extracted_info
        if extracted_info.get("parse_error"):
            extracted_info_text = extracted_info.get("raw_response", "")
            if crawled_contents:
                extracted_info_text += "\n\n## URLs THẬT (CHỈ dùng các URLs này):\n"
                for c in crawled_contents:
                    extracted_info_text += f"- [{c.get('title', 'N/A')}]({c.get('url', '')})\n"
        else:
            extracted_info_text = json.dumps(extracted_info, ensure_ascii=False, indent=2)

            # Bổ sung danh sách URL thật phòng trường hợp LLM bỏ sót
            if crawled_contents:
                extracted_info_text += "\n\n## DANH SÁCH URL THẬT (chỉ dùng URLs này, KHÔNG tự tạo URL):\n"
                for c in crawled_contents:
                    extracted_info_text += f"- {c.get('title', 'N/A')}: {c.get('url', '')}\n"

        # Gọi LLM để lọc + suy luận
        log_agent_step(self.logger, self.name, "Filtering sources & reasoning (with chain of thought)")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            claim=user_input,
            extracted_info=extracted_info_text,
        )

        llm_response = self.call_llm(SYSTEM_PROMPT, user_prompt)
        verdict = self.parse_json_response(llm_response)

        # Đảm bảo verdict có đủ các fields cần thiết
        verdict = self._validate_verdict(verdict)

        # Log chain_of_thought để dễ debug
        cot = verdict.get("chain_of_thought", "")
        if cot:
            self.logger.info(f"[{self.name}] 🧠 Chain of Thought: {cot[:200]}...")

        # Post-process: thay URLs bịa bằng URLs thật từ crawled_contents
        if crawled_contents:
            verdict = self._fix_urls(verdict, crawled_contents)

        # Thêm vào Agent 3 (ReasoningAgent) ở sau phần parse JSON
        rule_applied = verdict.get("rule_applied", "")
        retry_count = state.get("retry_count", 0)
        cot = verdict.get("chain_of_thought", "")
        
        if rule_applied == "RULE 4" and retry_count <= 1:
            feedback_msg = (
                f"Trường hợp chưa xác định đợt {retry_count}. "
                f"Lý do: {verdict.get('summary', 'Thiếu thông tin')} - "
                f"Suy luận AI: {cot}. "
                f"Đề nghị đổi từ khóa hẹp hơn, hoặc tìm theo chủ thể khác liên quan."
            )
            state["feedback_to_agent1"] = feedback_msg
            self.logger.warning(f"[{self.name}] 🔄 Kích hoạt Feedback Loop (Vòng {retry_count})")
            self.add_log(state, f"Tín hiệu quay xe 🔄: {feedback_msg}")
        else:
            # Nếu đã lặp xong hoặc ra rule khác hợp lệ, xóa feedback đi
            state["feedback_to_agent1"] = ""
            
        state["verdict"] = verdict

        accepted_count = len(verdict.get("filtering", {}).get("sources_accepted", []))
        rejected_count = len(verdict.get("filtering", {}).get("sources_rejected", []))
        is_verifiable = verdict.get("verifiability_assessment", {}).get("is_verifiable", "N/A")

        self.add_log(
            state,
            f"Verdict: {verdict.get('verdict', 'N/A')} "
            f"(Confidence: {verdict.get('confidence_score', 'N/A')}) | "
            f"Sources: {accepted_count} accepted / {rejected_count} rejected | "
            f"Verifiable: {is_verifiable}"
        )

        return state

    def _validate_verdict(self, verdict: dict) -> dict:
        """
        Đảm bảo verdict dict có đủ các fields cần thiết.
        Thêm default values nếu thiếu — bao gồm chain_of_thought.
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
                "step1_filtering": "Không có dữ liệu",
                "step2_verifiability": "Không có dữ liệu",
                "step3_detail_comparison": "N/A",
                "step4_rule_selection": "Không có dữ liệu",
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

        # Map: URL thật → title (lowercase)
        real_urls = {
            c.get("url", ""): c.get("title", "").lower()
            for c in crawled_contents if c.get("url")
        }

        # Map: domain → URL thật
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

                # Chỉ chấp nhận nếu có ít nhất 1 từ khớp
                if best_url and best_score >= 1:
                    assigned_urls.add(best_url)
                    return best_url

            # Không tìm được match → trả rỗng, không gán bừa
            return ""

        for arg in verdict.get("arguments", []):
            if isinstance(arg, dict):
                claimed = arg.get("source_url", "")
                source = arg.get("source_name", "")
                fixed = _find_real_url(claimed, source)
                if fixed != claimed:
                    log_agent_step(
                        self.logger, self.name, "Fixed URL",
                        f"{claimed[:50]} → {fixed[:50] if fixed else '(empty — no match found)'}"
                    )
                arg["source_url"] = fixed

        return verdict