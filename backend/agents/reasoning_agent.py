"""
Agent 3: Reasoning & Verdict.
Suy luận từ thông tin đã phân tích → Đưa ra phán định thật/giả.
"""

import json

from agents.base_agent import BaseAgent
from prompts.reasoning_agent import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.logger import log_agent_step


class ReasoningAgent(BaseAgent):
    """
    Agent cuối cùng trong pipeline.
    - Nhận extracted info từ Agent 2
    - Cross-reference facts, phân tích logic
    - Đưa ra verdict: THẬT / GIẢ / CHƯA XÁC ĐỊNH
    - Kèm confidence score và giải thích chi tiết
    """

    def __init__(self):
        # LLaMA-3.3-70B có context lớn. Nâng giới hạn text để không làm cụt Extract data của Gemini.
        super().__init__("ReasoningAgent", "AGENT3", max_prompt_chars=60000)

    def run(self, state: dict) -> dict:
        """
        Suy luận và đưa ra phán định cuối cùng.

        Args:
            state: Phải chứa keys: user_input, extracted_info

        Returns:
            State đã cập nhật với: verdict
        """
        user_input = state.get("user_input", "")
        extracted_info = state.get("extracted_info", {})

        self.add_log(state, "Starting reasoning process")

        # Nếu Agent 2 parse error → bổ sung URL thật từ crawled_contents
        # để Agent 3 KHÔNG tự bịa fake URLs
        if extracted_info.get("parse_error"):
            crawled_contents = state.get("crawled_contents", [])
            if crawled_contents:
                real_sources = "\n\n## NGUỒN BÀI BÁO THẬT (URLs đã crawl, PHẢI dùng URLs này):\n"
                for i, c in enumerate(crawled_contents, 1):
                    real_sources += f"- Nguồn {i}: [{c.get('title', 'N/A')}]({c.get('url', '')})\n"
                # Ghép raw_response + URLs thật
                raw = extracted_info.get("raw_response", "")
                extracted_info_text = raw + real_sources
            else:
                extracted_info_text = json.dumps(extracted_info, ensure_ascii=False, indent=2)
        else:
            # Format extracted info cho prompt
            extracted_info_text = json.dumps(extracted_info, ensure_ascii=False, indent=2)

        # Bổ sung danh sách URL thật vào cuối prompt (phòng trường hợp LLM bỏ sót)
        crawled_contents = state.get("crawled_contents", [])
        if crawled_contents and not extracted_info.get("parse_error"):
            urls_appendix = "\n\n## DANH SÁCH URL THẬT (chỉ dùng URLs này, KHÔNG tự tạo URL):\n"
            for c in crawled_contents:
                urls_appendix += f"- {c.get('title', 'N/A')}: {c.get('url', '')}\n"
            extracted_info_text += urls_appendix

        # Gọi LLM để suy luận
        log_agent_step(self.logger, self.name, "Reasoning & generating verdict")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            claim=user_input,
            extracted_info=extracted_info_text,
        )

        llm_response = self.call_llm(SYSTEM_PROMPT, user_prompt)
        verdict = self.parse_json_response(llm_response)

        # Đảm bảo verdict có đủ các fields cần thiết
        verdict = self._validate_verdict(verdict)

        # Post-process: thay URLs bịa bằng URLs thật từ crawled_contents
        crawled_contents = state.get("crawled_contents", [])
        if crawled_contents:
            verdict = self._fix_urls(verdict, crawled_contents)

        state["verdict"] = verdict
        self.add_log(
            state,
            f"Verdict: {verdict.get('verdict', 'N/A')} "
            f"(Confidence: {verdict.get('confidence_score', 'N/A')})"
        )

        return state

    def _validate_verdict(self, verdict: dict) -> dict:
        """
        Đảm bảo verdict dict có đủ các fields cần thiết.
        Thêm default values nếu thiếu.

        Args:
            verdict: Raw verdict dict từ LLM

        Returns:
            Validated verdict dict
        """
        defaults = {
            "verdict": "CHƯA XÁC ĐỊNH",
            "verdict_en": "UNVERIFIED",
            "confidence_score": 0.0,
            "summary": "Không đủ thông tin để đưa ra kết luận.",
            "rule_applied": "Không xác định",
            "arguments": [],
            "reasoning": {
                "evidence_assessment": "Không có đánh giá",
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "logical_analysis": "Không có phân tích",
            },
            "recommendation": "Hãy tìm hiểu thêm từ các nguồn tin chính thống.",
        }

        # Merge defaults cho các fields thiếu
        for key, default_value in defaults.items():
            if key not in verdict:
                verdict[key] = default_value
            elif key == "reasoning" and isinstance(default_value, dict):
                # Merge nested reasoning dict
                for sub_key, sub_default in default_value.items():
                    if sub_key not in verdict[key]:
                        verdict[key][sub_key] = sub_default

        return verdict

    def _fix_urls(self, verdict: dict, crawled_contents: list[dict]) -> dict:
        """
        Thay thế URLs bịa bằng URLs thật từ crawled_contents.
        Tuyệt đối không giữ lại URL nếu nó không tồn tại trong danh sách crawl.
        """
        if not crawled_contents:
            return verdict

        # Xây map: URL thật -> Title
        real_urls = {c.get("url", ""): c.get("title", "").lower() for c in crawled_contents if c.get("url")}
        
        # Xây map: Domain -> URL thật
        from urllib.parse import urlparse
        domains = {}
        for url in real_urls:
            domain = urlparse(url).netloc.replace("www.", "")
            if domain:
                domains[domain] = url

        assigned_urls = set()

        def _find_real_url(claimed_url: str, source_name: str) -> str:
            """Tìm URL thật. Nếu không thấy, cố gắng tìm một URL chưa được dùng làm fallback an toàn."""
            original_claimed_url = claimed_url

            # 1. Match chính xác URL
            if claimed_url in real_urls:
                assigned_urls.add(claimed_url)
                return claimed_url

            # 2. Match theo domain
            claimed_domain = urlparse(claimed_url).netloc.replace("www.", "")
            if claimed_domain and claimed_domain in domains:
                url = domains[claimed_domain]
                assigned_urls.add(url)
                return url

            # 3. Match theo tên báo (source_name) vs Title
            source_lower = source_name.lower() if source_name else ""
            best_url = ""
            best_score = 0
            for url, title in real_urls.items():
                source_words = set(source_lower.split())
                title_words = set(title.split())
                common = len(source_words & title_words)
                if common > best_score:
                    best_score = common
                    best_url = url
            
            if best_url:
                assigned_urls.add(best_url)
                return best_url
                
            # Tôn trọng quyết định của AI nếu nó báo không có nguồn
            if not claimed_url or "không có" in source_lower or "unknown" in source_lower or source_lower == "n/a":
                return ""
                
            # TRƯỜNG HỢP XẤU NHẤT: Bắt buộc nhét URL thật vào để chống ảo giác
            # Ưu tiên lấy URL chưa được gán cho luận điểm nào
            available_urls = [u for u in real_urls.keys() if u not in assigned_urls]
            if available_urls:
                fallback_url = available_urls[0]
            else:
                fallback_url = list(real_urls.keys())[0] if real_urls else original_claimed_url

            assigned_urls.add(fallback_url)
            return fallback_url

        # Fix URLs trong arguments
        for arg in verdict.get("arguments", []):
            if isinstance(arg, dict):
                claimed = arg.get("source_url", "")
                source = arg.get("source_name", "")
                fixed = _find_real_url(claimed, source)
                if fixed and fixed != claimed:
                    log_agent_step(
                        self.logger, self.name, "Fixed URL",
                        f"{claimed[:50]}... → {fixed[:50]}..."
                    )
                arg["source_url"] = fixed

        return verdict
