"""
Agent 1: Query Clarifier + Web Crawler.
Nhận input từ user → Phân tích claim → Tạo search queries → Crawl dữ liệu.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base_agent import BaseAgent
from tools.web_search import web_search
from tools.web_scraper import web_scrape
from prompts.query_agent import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.logger import log_agent_step

# Domain không nên scrape (video, social, không có nội dung bài báo)
SKIP_SCRAPE_DOMAINS = [
    "youtube.com", "youtu.be", "facebook.com", "twitter.com",
    "tiktok.com", "instagram.com", "zalo.me",
]


class QueryAgent(BaseAgent):
    """
    Agent đầu tiên trong pipeline.
    - Phân tích claim/thông tin từ user
    - Tạo search queries tối ưu
    - Tìm kiếm trên internet (Tavily: có full content sẵn)
    - Scrape thêm với các URL chưa có content đầy đủ
    """

    def __init__(self):
        super().__init__("QueryAgent", "AGENT1")

    def _should_skip_scrape(self, url: str) -> bool:
        """Kiểm tra xem URL có cần scrape hay không."""
        return any(d in url for d in SKIP_SCRAPE_DOMAINS)

    def _scrape_url(self, result: dict) -> dict | None:
        """
        Scrape 1 URL — dùng trong ThreadPoolExecutor.
        Nếu Tavily đã có full content, bỏ qua scrape.
        """
        url = result.get("url", "")
        if not url:
            return None

        # Nếu Tavily đã cung cấp full content (>500 chars), không cần scrape thêm
        if result.get("has_full_content") and len(result.get("content", "")) > 800:
            log_agent_step(
                self.logger, "QueryAgent", "Using Tavily Content",
                f"Already have {len(result['content'])} chars for {url[:60]}"
            )
            return {
                "url": url,
                "title": result.get("title", ""),
                "content": result.get("content", ""),
                "search_snippet": result.get("snippet", result.get("content", "")[:300]),
                "score": result.get("score", 0.5),
                "source": "tavily_raw",
            }

        # Bỏ qua URL không có nội dung bài báo
        if self._should_skip_scrape(url):
            log_agent_step(self.logger, "QueryAgent", "Skipping", f"Non-article URL: {url[:60]}")
            return None

        # Scrape bình thường
        try:
            scraped = web_scrape.invoke({"url": url})
            if isinstance(scraped, dict):
                content = scraped.get("content", "")
                return {
                    "url": url,
                    "title": scraped.get("title") or result.get("title", ""),
                    "content": content if content else result.get("content", ""),
                    "search_snippet": result.get("snippet", result.get("content", "")[:300]),
                    "score": result.get("score", 0.5),
                    "source": "scraped" if content else "snippet_fallback",
                }
        except Exception as e:
            self.logger.warning(f"Scrape error for {url}: {e}")

        # Fallback — dùng snippet từ search
        return {
            "url": url,
            "title": result.get("title", ""),
            "content": result.get("content", ""),
            "search_snippet": result.get("snippet", ""),
            "score": result.get("score", 0.5),
            "source": "snippet_fallback",
        }

    def run(self, state: dict) -> dict:
        """
        Chạy full pipeline: Clarify → Search (Tavily full content) → Scrape nếu cần.
        """
        user_input = state.get("user_input", "")
        self.add_log(state, f"Received input: {user_input[:100]}...")

        # === Step 1: Phân tích claim và tạo search queries ===
        log_agent_step(self.logger, self.name, "Step 1: Analyzing claim & generating queries")

        user_prompt = USER_PROMPT_TEMPLATE.format(claim=user_input)
        llm_response = self.call_llm(SYSTEM_PROMPT, user_prompt)
        analysis = self.parse_json_response(llm_response)

        search_queries = analysis.get("search_queries", [user_input])
        search_queries = search_queries[:3]    # 3 queries là đủ
        state["claim_analysis"] = analysis
        state["clarified_queries"] = search_queries
        self.add_log(state, f"Generated {len(search_queries)} search queries")

        # === Step 2: Tìm kiếm — Tavily trả về full content sẵn ===
        log_agent_step(self.logger, self.name, "Step 2: Searching the web")

        all_search_results = []
        seen_urls = set()

        def _search_single_query(query: str) -> list:
            """Tìm kiếm 1 query — dùng trong ThreadPoolExecutor."""
            try:
                results = web_search.invoke({"query": query})
                return results if isinstance(results, list) else []
            except Exception as e:
                self.logger.warning(f"Search error for query '{query}': {e}")
                return []

        # Chạy tất cả search queries SONG SONG (thay vì tuần tự)
        with ThreadPoolExecutor(max_workers=len(search_queries)) as executor:
            future_results = list(executor.map(_search_single_query, search_queries))

        # Gộp kết quả + loại bỏ URL trùng
        for results in future_results:
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_search_results.append(r)

        state["search_results"] = all_search_results

        # Log chi tiết — bao nhiêu URL đã có full content từ Tavily
        full_content_count = sum(1 for r in all_search_results if r.get("has_full_content"))
        self.add_log(
            state,
            f"Found {len(all_search_results)} unique results "
            f"({full_content_count} with full content from Tavily)"
        )

        # === Step 3: Lấy top URLs có score cao nhất, bổ sung content nếu cần ===
        log_agent_step(self.logger, self.name, "Step 3: Getting article content")

        # Lọc bỏ URLs vô nghĩa (YouTube, FB...) trước khi sort
        filtered_results = [
            r for r in all_search_results
            if not self._should_skip_scrape(r.get("url", ""))
            or r.get("has_full_content")
        ]

        sorted_results = sorted(
            filtered_results,
            key=lambda x: x.get("score", 0),
            reverse=True,
        )[:5]   # Top 5 — Sau khi lọc YouTube/FB, thực tế khoảng 3-4 cái hữu ích.

        crawled_contents = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._scrape_url, r): r for r in sorted_results}
            for future in as_completed(futures, timeout=25):
                result = future.result()
                if result and result.get("content"):    # Chỉ giữ kết quả có content
                    crawled_contents.append(result)

        # Sort theo score, ưu tiên nguồn có nhiều content nhất trong cùng score
        crawled_contents.sort(
            key=lambda x: (x.get("score", 0), len(x.get("content", ""))),
            reverse=True,
        )

        state["crawled_contents"] = crawled_contents
        total_chars = sum(len(c.get("content", "")) for c in crawled_contents)
        self.add_log(
            state,
            f"Collected content from {len(crawled_contents)} sources "
            f"(total {total_chars:,} chars)"
        )

        return state
