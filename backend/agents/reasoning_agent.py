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
        super().__init__("ReasoningAgent", "AGENT3")

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
            "reliable_sources": [],
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
        Dùng text matching giữa source_name (LLM output) và title (crawled).
        """
        # Xây map: tên nguồn (lowercase) → URL thật
        real_urls = {}
        for c in crawled_contents:
            url = c.get("url", "")
            title = c.get("title", "").lower()
            if url:
                real_urls[url] = title
                # Trích domain làm key phụ
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace("www.", "")
                if domain:
                    real_urls.setdefault(f"domain:{domain}", url)

        def _find_real_url(claimed_url: str, source_name: str) -> str:
            """Tìm URL thật gần nhất với URL/source_name mà LLM đưa ra."""
            # Nếu URL đã có trong crawled → giữ nguyên
            if claimed_url in real_urls:
                return claimed_url

            # Tìm bằng domain match
            if claimed_url:
                from urllib.parse import urlparse
                claimed_domain = urlparse(claimed_url).netloc.replace("www.", "")
                domain_key = f"domain:{claimed_domain}"
                if domain_key in real_urls:
                    return real_urls[domain_key]

            # Tìm bằng tên nguồn match với title bài báo
            source_lower = source_name.lower() if source_name else ""
            best_url = ""
            best_score = 0
            for url, title in real_urls.items():
                if url.startswith("domain:"):
                    continue
                # Đếm từ chung giữa source_name và title
                source_words = set(source_lower.split())
                title_words = set(title.split())
                common = len(source_words & title_words)
                if common > best_score:
                    best_score = common
                    best_url = url

            return best_url if best_score > 0 else ""

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
                arg["source_url"] = fixed or claimed

        # Fix URLs trong reliable_sources
        for src in verdict.get("reliable_sources", []):
            if isinstance(src, dict):
                claimed = src.get("url", "")
                source = src.get("name", "")
                fixed = _find_real_url(claimed, source)
                if fixed and fixed != claimed:
                    log_agent_step(
                        self.logger, self.name, "Fixed source URL",
                        f"{claimed[:50]}... → {fixed[:50]}..."
                    )
                src["url"] = fixed or claimed

        return verdict
