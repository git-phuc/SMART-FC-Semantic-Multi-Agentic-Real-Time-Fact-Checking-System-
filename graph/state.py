"""
State definition cho LangGraph workflow.
Định nghĩa shared state chứa toàn bộ dữ liệu pipeline.
"""

from typing import TypedDict, Any


class VerificationState(TypedDict, total=False):
    """
    Shared state cho toàn bộ verification pipeline.
    Mỗi agent đọc và ghi vào state này.

    Attributes:
        user_input: Thông tin gốc từ user cần kiểm chứng
        claim_analysis: Kết quả phân tích claim từ Agent 1 (JSON dict)
        clarified_queries: Danh sách search queries đã tạo (Agent 1)
        search_results: Kết quả tìm kiếm từ internet (Agent 1)
        crawled_contents: Nội dung đã crawl từ các URL (Agent 1)
        extracted_info: Thông tin đã trích xuất và tóm tắt (Agent 2)
        verdict: Phán định cuối cùng (Agent 3)
        agent_logs: Log từng bước xử lý (tất cả agents)
    """

    # Input
    user_input: str

    # Agent 1 outputs
    claim_analysis: dict[str, Any]
    clarified_queries: list[str]
    search_results: list[dict[str, Any]]
    crawled_contents: list[dict[str, Any]]

    # Agent 2 outputs
    extracted_info: dict[str, Any]

    # Agent 3 outputs
    verdict: dict[str, Any]

    # Shared logging
    agent_logs: list[str]
