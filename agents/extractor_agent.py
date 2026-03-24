"""
Agent 2: Information Extractor & Summarizer.
Nhận dữ liệu thô từ Agent 1 → Trích xuất thông tin quan trọng → Tóm tắt.
"""

import json

from agents.base_agent import BaseAgent
from prompts.extractor_agent import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.logger import log_agent_step


class ExtractorAgent(BaseAgent):
    """
    Agent thứ hai trong pipeline.
    - Nhận crawled data từ Agent 1
    - Trích xuất key facts từ mỗi nguồn
    - Đánh giá độ tin cậy nguồn tin
    - Phát hiện mâu thuẫn giữa các nguồn
    - Tạo structured summary
    """

    def __init__(self):
        # Gemini Flash có context 1M token → cho phép nhận toàn bộ nội dung bài báo
        super().__init__("ExtractorAgent", "AGENT2", max_prompt_chars=100_000)

    def run(self, state: dict) -> dict:
        """
        Trích xuất và tóm tắt thông tin từ crawled data.

        Args:
            state: Phải chứa keys: user_input, claim_analysis, crawled_contents

        Returns:
            State đã cập nhật với: extracted_info
        """
        user_input = state.get("user_input", "")
        claim_analysis = state.get("claim_analysis", {})
        crawled_contents = state.get("crawled_contents", [])

        self.add_log(state, f"Processing {len(crawled_contents)} sources")

        # Kiểm tra có dữ liệu để xử lý không
        if not crawled_contents:
            self.logger.warning(f"[{self.name}] No crawled data available")
            state["extracted_info"] = {
                "claim_being_verified": user_input,
                "sources_analysis": [],
                "consensus_points": [],
                "contradiction_points": [],
                "overall_summary": "Không tìm được dữ liệu từ internet để kiểm chứng.",
            }
            self.add_log(state, "No data to process - returning empty analysis")
            return state

        # Format crawled data cho prompt
        crawled_data_text = self._format_crawled_data(crawled_contents)
        claim_analysis_text = json.dumps(claim_analysis, ensure_ascii=False, indent=2)

        # Gọi LLM để phân tích
        log_agent_step(self.logger, self.name, "Extracting & summarizing information")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            claim=user_input,
            claim_analysis=claim_analysis_text,
            crawled_data=crawled_data_text,
        )

        llm_response = self.call_llm(SYSTEM_PROMPT, user_prompt)
        extracted_info = self.parse_json_response(llm_response)

        state["extracted_info"] = extracted_info
        self.add_log(
            state,
            f"Extracted info from {len(extracted_info.get('sources_analysis', []))} sources. "
            f"Consensus: {len(extracted_info.get('consensus_points', []))} points, "
            f"Contradictions: {len(extracted_info.get('contradiction_points', []))} points"
        )

        return state

    def _format_crawled_data(self, crawled_contents: list[dict]) -> str:
        """
        Format crawled data thành text dễ đọc cho LLM prompt.

        Args:
            crawled_contents: List of crawled content dicts

        Returns:
            Formatted text string
        """
        parts = []
        for i, content in enumerate(crawled_contents, 1):
            url = content.get("url", "N/A")
            title = content.get("title", "N/A")
            text = content.get("content", "N/A")
            note = content.get("note", "")

            section = f"""### Nguồn {i}:
- **URL**: {url}
- **Tiêu đề**: {title}
{f'- **Ghi chú**: {note}' if note else ''}
- **Nội dung**:
{text}
"""
            parts.append(section)

        return "\n---\n".join(parts)
