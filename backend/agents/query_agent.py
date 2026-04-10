"""
Agent 1: Query Generator + Web Crawler.
Nhận input từ user → Tạo search queries (1-3) → Crawl dữ liệu thô → Trả về cho Agent 2.

Nguyên tắc: Agent 1 KHÔNG phán xét, KHÔNG phân loại claim.
Nhiệm vụ duy nhất: sinh queries tốt + thu thập dữ liệu đầy đủ nhất có thể.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base_agent import BaseAgent
from tools.web_search import web_search
from tools.web_scraper import web_scrape
from prompts.query_prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from utils.logger import log_agent_step

# Domain không nên scrape (video, social, không có nội dung bài báo)
SKIP_SCRAPE_DOMAINS = [
    "youtube.com", "youtu.be", "facebook.com", "twitter.com",
    "tiktok.com", "instagram.com", "zalo.me",
]


class QueryAgent(BaseAgent):
    """
    Agent đầu tiên trong pipeline.
    - Phân tích claim để xác định từ khóa tìm kiếm
    - Tự quyết định số lượng queries (1-3) theo độ phức tạp của claim
    - Tìm kiếm trên internet (Tavily)
    - Scrape thêm content nếu Tavily chưa đủ

    KHÔNG phán xét, KHÔNG phân loại claim — chỉ thu thập dữ liệu.
    """

    def __init__(self):
        super().__init__("QueryAgent", "AGENT1")

    def _should_skip_scrape(self, url: str) -> bool:
        """Kiểm tra xem URL có cần scrape hay không."""
        return any(d in url for d in SKIP_SCRAPE_DOMAINS)

    def _scrape_url(self, result: dict) -> dict:
        """
        Scrape 1 URL — dùng trong ThreadPoolExecutor.
        Nếu Tavily đã có full content, bỏ qua scrape.
        """
        url = result.get("url", "")
        if not url:
            return {}

        # Nếu Tavily đã cung cấp full content (>800 chars), không cần scrape thêm
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
            return {}

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
        Chạy full pipeline: Analyze → Search (Tavily) → Scrape nếu cần.

        Output state keys được thêm:
            - clarified_queries: list[str]
            - search_results: list[dict]
            - crawled_contents: list[dict]
        """
        user_input = state.get("user_input", "")
        self.add_log(state, f"Received input: {user_input[:100]}...")

        # --- Đọc feedback loop ---
        retry_count = state.get("retry_count", 0)
        feedback = state.get("feedback_to_agent1", "")
        
        # Cập nhật số lần thử
        state["retry_count"] = retry_count + 1

        feedback_section = ""
        if feedback and retry_count > 0:
            self.add_log(state, f"🔄 LẦN LẶP {retry_count + 1} - Nhận Feedback: {feedback}")
            feedback_section = f"\n⚠️ LƯU Ý TỪ LẦN TÌM TRƯỚC ĐÃ THẤT BẠI:\n{feedback}\nHãy rút kinh nghiệm và tạo từ khóa hoàn toàn mới, hoặc đổi hướng tiếp cận.\n"

        # === Step 1: Phân tích claim và tạo search queries (1-3) ===
        log_agent_step(self.logger, self.name, f"Step 1: Analyzing claim & generating queries (Loop {retry_count + 1})")

        user_prompt = USER_PROMPT_TEMPLATE.format(
            claim=user_input, 
            feedback_section=feedback_section
        )
        llm_response = self.call_llm(SYSTEM_PROMPT, user_prompt)
        analysis = self.parse_json_response(llm_response)

        # LLM tự quyết định 1-3 queries — không ép tối đa 5 nữa
        search_queries_raw = analysis.get("search_queries", [])
        
        search_queries = []
        for item in search_queries_raw:
            if isinstance(item, dict) and "query" in item:
                # Bỏ qua query nếu nó trống
                if item["query"].strip():
                    search_queries.append(item["query"].strip())
            elif isinstance(item, str) and item.strip():
                search_queries.append(item.strip())
                
        # Giữ giới hạn trên là 3 để đảm bảo an toàn
        search_queries = search_queries[:3]
        if not search_queries:
            search_queries = [user_input]

        state["clarified_queries"] = search_queries

        # Lưu analysis (chỉ để debug/log)
        complexity = analysis.get("complexity", "N/A")
        complexity_reason = analysis.get("complexity_reason", "")
        state["claim_analysis"] = {
            "original_claim": analysis.get("original_claim", user_input),
            "complexity": complexity,
            "complexity_reason": complexity_reason,
            "analysis": analysis.get("analysis", {}),
        }

        self.add_log(
            state,
            f"Complexity: {complexity} → Generated {len(search_queries)} queries | {complexity_reason}"
        )

        # === Step 2: Tìm kiếm — Tavily trả về full content sẵn ===
        log_agent_step(self.logger, self.name, "Step 2: Searching the web")

        all_search_results = []
        seen_urls = set()

        def _search_single_query(query: str) -> list:
            try:
                results = web_search.invoke({"query": query})
                return results if isinstance(results, list) else []
            except Exception as e:
                self.logger.warning(f"Search error for query '{query}': {e}")
                return []

        # Chạy tất cả search queries SONG SONG
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

        full_content_count = sum(1 for r in all_search_results if r.get("has_full_content"))
        self.add_log(
            state,
            f"Found {len(all_search_results)} unique results "
            f"({full_content_count} with full content from Tavily)"
        )

        # === Step 3: Lấy top URLs theo Tavily score, scrape nội dung nếu cần ===
        log_agent_step(self.logger, self.name, "Step 3: Getting article content")

        filtered_results = [
            r for r in all_search_results
            if not self._should_skip_scrape(r.get("url", ""))
            or r.get("has_full_content")
        ]

        # Lấy top 10 bài có điểm Tavily cao nhất để crawl nội dung
        sorted_results = sorted(
            filtered_results,
            key=lambda x: x.get("score", 0),
            reverse=True,
        )[:10]

        crawled_contents = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._scrape_url, r): r for r in sorted_results}
            for future in as_completed(futures, timeout=25):
                try:
                    result = future.result()
                    if result and result.get("content"):
                        crawled_contents.append(result)
                except Exception as e:
                    original = futures[future]
                    self.logger.warning(
                        f"[{self.name}] Future failed for {original.get('url', 'unknown')[:60]}: {e}"
                    )

        # Sắp xếp lại theo Tavily score (cao → thấp), tie-break bằng độ dài content
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