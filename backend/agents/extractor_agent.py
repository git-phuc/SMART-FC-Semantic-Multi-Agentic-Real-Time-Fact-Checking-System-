"""
Agent 2: Information Extractor & Summarizer.
Nhận dữ liệu thô từ Agent 1 → Chọn top bài theo Tavily score → Tóm tắt.
"""

from agents.base_agent import BaseAgent
from prompts.extractor_prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.logger import log_agent_step


class ExtractorAgent(BaseAgent):
    """
    Agent thứ hai trong pipeline.
    - Nhận crawled data từ Agent 1 (đã sắp xếp giảm dần theo Tavily score)
    - Chọn top 5 bài có điểm cao nhất để tóm tắt
    - Tóm tắt bằng Gemini
    - Truyền kết quả sang Agent 3
    """

    def __init__(self):
        # Gemini Flash có context 1M token → cho phép nhận toàn bộ nội dung bài báo
        super().__init__("ExtractorAgent", "AGENT2", max_prompt_chars=100_000)

    def run(self, state: dict) -> dict:
        """
        Chọn top sources theo Tavily score + tóm tắt nội dung.

        Args:
            state: Phải chứa keys: user_input, crawled_contents

        Returns:
            State đã cập nhật với: extracted_info
        """
        user_input = state.get("user_input", "")
        crawled_contents = state.get("crawled_contents", [])

        self.add_log(state, f"Received {len(crawled_contents)} sources from Agent 1")

        # Kiểm tra có dữ liệu để xử lý không
        if not crawled_contents:
            self.logger.warning(f"[{self.name}] No crawled data available")
            state["extracted_info"] = {
                "total_sources": 0,
                "sources": [],
                "note": "Không tìm được dữ liệu từ internet để kiểm chứng.",
            }
            self.add_log(state, "No data to process — returning empty")
            return state

        # ── BƯỚC 1: CHỌN TOP 5 THEO TAVILY SCORE ────────────────────────────
        # crawled_contents đã được Agent 1 sort giảm dần theo score → lấy trực tiếp
        log_agent_step(self.logger, self.name, "Step 1: Selecting top 5 sources by Tavily score")

        top_contents = crawled_contents[:5]

        self.add_log(
            state,
            f"Selected top {len(top_contents)} / {len(crawled_contents)} sources "
            f"(score range: {top_contents[0].get('score', 0):.3f} → "
            f"{top_contents[-1].get('score', 0):.3f})"
        )

        # ── BƯỚC 2: TÓM TẮT TOP BÀI BẰNG GEMINI ────────────────────────────
        log_agent_step(self.logger, self.name, "Step 2: Summarizing top sources")

        crawled_data_text = self._format_crawled_data(top_contents)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            claim=user_input,
            crawled_data=crawled_data_text,
            source_count=len(top_contents),
        )

        llm_response = self.call_llm(SYSTEM_PROMPT, user_prompt)
        extracted_info = self.parse_json_response(llm_response)

        state["extracted_info"] = extracted_info
        self.add_log(
            state,
            f"Summarized {len(extracted_info.get('sources', []))} sources"
        )

        return state

    def _format_crawled_data(self, crawled_contents: list) -> str:
        """
        Format crawled data thành text dễ đọc cho LLM prompt.

        Args:
            crawled_contents: List of crawled content dicts (đã sort theo Tavily score)

        Returns:
            Formatted text string
        """
        parts = []
        for i, content in enumerate(crawled_contents, 1):
            url = content.get("url", "N/A")
            title = content.get("title", "N/A")
            text = content.get("content", "N/A")
            score = content.get("score", 0)
            note = content.get("note", "")

            section = f"""### Nguồn {i} (Tavily score: {score:.3f}):
        - **URL**: {url}
        - **Tiêu đề**: {title}
        {f'- **Ghi chú**: {note}' if note else ''}
        - **Nội dung**:
        {text}
        """
            parts.append(section)

        return "\n---\n".join(parts)
