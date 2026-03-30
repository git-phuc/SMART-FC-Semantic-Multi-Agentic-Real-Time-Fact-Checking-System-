"""
Web Scraper Tool - Crawl nội dung từ URL.
Hỗ trợ nhiều chiến lược scraping cho báo Việt Nam.
"""

import requests
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from langchain_core.tools import tool  # type: ignore[import-untyped]

from utils.logger import get_logger, log_agent_step

logger = get_logger("Tools.WebScraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

REMOVE_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "iframe", "noscript", "form", "button",
    "figure",  # ảnh caption thường là noise
]

# Các selector đặc trưng của báo Việt Nam
VIET_ARTICLE_SELECTORS = [
    # VnExpress
    {"class": "fck_detail"},
    {"class": "article-body"},
    # Tuổi Trẻ
    {"class": "detail-content"},
    {"class": "content-detail"},
    # Thanh Niên
    {"class": "detail-content-body"},
    # Dân Trí
    {"class": "singular-content"},
    {"class": "news-content"},
    # Generic
    {"itemprop": "articleBody"},
    {"class": "article__body"},
    {"class": "post-content"},
    {"class": "entry-content"},
    {"id": "article-body"},
    {"id": "content"},
]


def _extract_content(soup: BeautifulSoup) -> str:
    """
    Trích xuất nội dung sạch từ HTML.
    Thử nhiều selector theo thứ tự ưu tiên.
    """
    from bs4 import Tag  # type: ignore[import-untyped]

    # Xóa noise trước
    for tag_name in REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            if isinstance(tag, Tag):
                tag.decompose()

    # Thử các selector đặc trưng của báo Việt Nam
    main_content: Tag | None = None
    for selector in VIET_ARTICLE_SELECTORS:
        found = soup.find(attrs=selector)  # type: ignore[arg-type]
        if isinstance(found, Tag):
            main_content = found
            break

    # Fallback: article → main → body
    if main_content is None:
        for fallback in ("article", "main", "body"):
            found = soup.find(fallback)
            if isinstance(found, Tag):
                main_content = found
                break

    if main_content is None:
        return ""

    # Thu thập text từ các đoạn
    paragraphs = main_content.find_all(["p", "h1", "h2", "h3", "h4", "li"])
    text_parts = []
    for p in paragraphs:
        if not isinstance(p, Tag):
            continue
        text = p.get_text(separator=" ", strip=True)
        if text and len(text) > 30:   # Bỏ qua text quá ngắn
            text_parts.append(text)

    content = "\n\n".join(text_parts)

    # Nếu vẫn rỗng, lấy toàn bộ text của main_content
    if not content:
        content = main_content.get_text(separator="\n", strip=True)

    return content


@tool
def web_scrape(url: str) -> dict:
    """
    Crawl và trích xuất nội dung text từ một URL.
    Hỗ trợ các trang báo Việt Nam (VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí...).
    Tự động xử lý encoding tiếng Việt và loại bỏ HTML/scripts/ads.

    Args:
        url: URL cần crawl nội dung

    Returns:
        Dict chứa: url, title, content (clean text), success (bool)
    """
    log_agent_step(logger, "WebScraper", "Scraping", f"URL: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        response.raise_for_status()

        # VnExpress và nhiều báo Việt Nam dùng UTF-8
        if response.encoding and response.encoding.lower() in ("iso-8859-1", "latin-1"):
            # Sai encoding, thử detect lại
            response.encoding = response.apparent_encoding or "utf-8"
        else:
            response.encoding = response.encoding or "utf-8"

        soup = BeautifulSoup(response.text, "html.parser")

        # Lấy title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Trích xuất nội dung
        content = _extract_content(soup)

        # Giới hạn 10000 ký tự — đủ context để LLM suy luận sâu
        if len(content) > 10000:
            content = content[:10000] + "\n\n[... nội dung đã được cắt ngắn ...]"

        log_agent_step(
            logger, "WebScraper", "Done",
            f"Title: {title[:80]} | Content: {len(content)} chars"
        )

        return {"url": url, "title": title, "content": content, "success": True}

    except requests.exceptions.Timeout:
        logger.warning(f"[WebScraper] Timeout: {url}")
        return {"url": url, "title": "", "content": "", "success": False, "error": "Timeout"}

    except requests.exceptions.RequestException as e:
        logger.warning(f"[WebScraper] Error: {url} — {e}")
        return {"url": url, "title": "", "content": "", "success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"[WebScraper] Unexpected error: {e}")
        return {"url": url, "title": "", "content": "", "success": False, "error": str(e)}
