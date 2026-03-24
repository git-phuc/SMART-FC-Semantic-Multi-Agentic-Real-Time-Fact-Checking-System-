"""
Web Search Tool — Dùng Tavily API (primary) + Bing/DDG (fallback).

Tavily ưu điểm:
  - Không bao giờ bị block/rate-limit
  - Kết quả sạch, có snippet chất lượng cao
  - Hỗ trợ filter domain → ưu tiên nguồn .gov.vn, báo lớn
  - Free 1000 req/tháng

Fallback (nếu không có TAVILY_API_KEY):
  - Bing + DuckDuckGo chạy song song
"""

import os
import json
import hashlib
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote_plus
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from dotenv import load_dotenv
from langchain_core.tools import tool  # type: ignore[import-untyped]

from utils.logger import get_logger, log_agent_step

load_dotenv(Path(__file__).parent.parent / ".env")
logger = get_logger("Tools.WebSearch")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ============================================================
# Cache
# ============================================================
CACHE_FILE = Path(__file__).parent.parent / ".search_cache.json"

import time

def _load_cache() -> dict:
    """Load cache và dọn dẹp các entry cũ hơn 24 giờ."""
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            now = time.time()
            clean_data = {}
            # TTL = 24 giờ (86400 giây)
            TTL = 86400

            for k, v in data.items():
                if isinstance(v, dict) and "timestamp" in v:
                    if now - v["timestamp"] < TTL:
                        clean_data[k] = v
                else:
                    # Migration: nếu là format cũ (chỉ có list), giữ lại nhưng gán timestamp hiện tại
                    # Hoặc có thể xóa luôn nếu muốn triệt để dọn data cũ
                    continue 

            return clean_data
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict, key: str, results: list) -> None:
    """Lưu kết quả kèm timestamp vào cache."""
    try:
        cache[key] = {
            "results": results,
            "timestamp": time.time()
        }
        CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass

def _cache_key(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode()).hexdigest()


# ============================================================
# Content Cleaner — loại bỏ rác trước khi đưa vào LLM
# ============================================================
import re

def _clean_content(text: str, max_chars: int = 8000) -> str:
    """
    Làm sạch nội dung raw từ Tavily — chỉ giữ lại plain text bài báo.

    Loại bỏ:
    - Mọi dạng markdown link: [text](url), [![...](...)], ![alt](url)
    - Bullet list là nav links: * [Text](url)
    - URL thuần
    - Base64 images
    - Dòng quá ngắn (menu, nút bấm, breadcrumb)
    - Dòng chỉ là ký tự đặc biệt
    - Text alt ảnh: "Ảnh: xxx", "Photo: xxx"
    """
    if not text:
        return ""

    # Bước 1: Xóa markdown image toàn bộ dạng ![alt](url) và [![...](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Bước 2: Xóa inline links — giữ lại text bên trong [text](url) → text
    text = re.sub(r'\[([^\]]*?)\]\([^)]*?\)', r'\1', text)
    # Bước 3: Xóa HTML entities thông dụng
    text = re.sub(r'&[a-z]+;|&#\d+;', ' ', text)

    lines = text.splitlines()
    clean_lines = []

    for line in lines:
        stripped = line.strip()

        # Bỏ dòng trống — gộp nhiều dòng trống thành 1
        if not stripped:
            if clean_lines and clean_lines[-1] != "":
                clean_lines.append("")
            continue

        # Bỏ URL thuần
        if re.match(r'^https?://', stripped):
            continue

        # Bỏ base64
        if 'data:image' in stripped or 'base64,' in stripped:
            continue

        # Bỏ bullet list ngắn còn sót (nav items: "* Chính trị", "* Kinh tế"...)
        if re.match(r'^\*\s+\S+$', stripped):
            continue

        # Bỏ breadcrumb / path dạng "Văn hóa > Thể thao" hoặc "Văn hóa / Thể thao"
        if re.match(r'^[\w\s]+\s*[›»/|>]\s*[\w\s]+$', stripped) and len(stripped) < 60:
            continue

        # Bỏ dòng chỉ có dấu đặc biệt hoặc số ký tự đặc biệt quá nhiều
        special_ratio = len(re.findall(r'[^\w\s\u00C0-\u024F\u1E00-\u1EFF.,!?:;"\'-]', stripped))
        if special_ratio > len(stripped) * 0.3:
            continue

        # Bỏ dòng quá ngắn không có số (menu, nút bấm)
        if len(stripped) < 25 and not re.search(r'\d', stripped):
            continue

        # Bỏ dòng kiểu caption ảnh: "Ảnh: ...", "Photo: ..."
        if re.match(r'^(Ảnh|Photo|Hình|Caption|Nguồn ảnh)\s*:', stripped, re.IGNORECASE):
            continue

        clean_lines.append(stripped)

    result = "\n".join(clean_lines).strip()
    # Xóa nhiều dòng trống liên tiếp
    result = re.sub(r'\n{3,}', '\n\n', result)

    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n[... nội dung đã được cắt ngắn ...]"

    return result



# ============================================================
# Language Detector
# ============================================================

def _is_vietnamese(text: str, min_ratio: float = 0.03) -> bool:
    """
    Kiem tra text co phai tieng Viet khong.
    Tieng Viet co nhieu ky tu Unicode rieng trong khoang U+1E00-U+1EFF.
    min_ratio: ty le toi thieu 3% ky tu Viet -> khong the la tieng Anh thuan.
    """
    if not text:
        return False
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha < 50:
        return True   # qua ngan, khong danh gia
    viet_chars = sum(1 for c in text if '\u1e00' <= c <= '\u1eff' or c in '\u0111\u0110')
    return (viet_chars / total_alpha) >= min_ratio


# Domain chi tieng Anh -- khong co gia tri cho tin Viet
ENGLISH_ONLY_DOMAINS = [
    "espn.com", "bbc.com", "reuters.com", "apnews.com",
    "theguardian.com", "nytimes.com", "cnn.com", "foxnews.com",
    "goal.com", "transfermarkt.com", "sportfive.com",
]


# ============================================================
# Nguon uy tin -- uu tien trong Tavily + scoring
# ============================================================
GOV_DOMAINS = [
    # Chính phủ & cơ quan nhà nước
    "baochinhphu.vn",     # Báo Chính Phủ
    "chinhphu.vn",        # Cổng TTĐT Chính Phủ
    "quochoi.vn",         # Quốc Hội Việt Nam ← quan trọng
    "mofa.gov.vn",        # Bộ Ngoại Giao ← quan trọng cho tin quốc tế
    "mps.gov.vn",         # Bộ Công An
    "mic.gov.vn",         # Bộ TT&TT
    "moh.gov.vn",         # Bộ Y tế
    "moet.gov.vn",        # Bộ GD&ĐT
    "most.gov.vn",        # Bộ KH&CN
    "tdtdt.gov.vn",       # Cục Thể dục thể thao
    # Báo chí chính thống nhà nước
    "nhandan.vn",         # Nhân Dân — báo Đảng trung ương
    "tapchicongsan.org.vn", # Tạp chí Cộng Sản
    "vtv.vn",             # VTV — Đài truyền hình quốc gia
    "vov.vn",             # VOV — Đài Tiếng nói VN
    "vietnamplus.vn",     # Vietnam+ — TTXVN
    "vnanet.vn",          # Thông tấn xã VN
]

TRUSTED_DOMAINS = [
    # Báo điện tử lớn
    "vnexpress.net",
    "tuoitre.vn",
    "thanhnien.vn",
    "dantri.com.vn",
    "tienphong.vn",       # Tiền Phong
    "laodong.vn",         # Lao Động
    "zingnews.vn",        # Zing News
    # Báo chính trị/pháp luật
    "phapluat.vn",
    "baophapluat.vn",     # Báo Pháp Luật VN
    "anninhthudo.vn",     # An Ninh Thủ Đô
    "cand.com.vn",        # Công An Nhân Dân
    # Tham khảo
    "vi.wikipedia.org",
    "thethaovanhoa.vn",
]

def _score_result(url: str, base_score: float = 0.75) -> float:
    """Tính score dựa trên domain của URL."""
    if any(d in url for d in GOV_DOMAINS):
        return 0.97  # Nguồn chính phủ — cao nhất
    if any(d in url for d in TRUSTED_DOMAINS):
        return 0.90  # Báo lớn uy tín
    if ".gov.vn" in url or ".edu.vn" in url:
        return 0.95  # Bất kỳ .gov.vn nào
    return base_score


# ============================================================
# PRIMARY: Tavily Search API
# ============================================================

def search_tavily(query: str, num_results: int = 5,
                  include_domains: list[str] | None = None) -> list[dict]:
    """
    Tavily Search API với raw_content — lấy toàn bộ nội dung bài báo.
    include_domains: giới hạn tìm kiếm trong domain cụ thể (optional).
    """
    if not TAVILY_API_KEY:
        return []

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": num_results,
        "include_answer": False,
        "include_raw_content": True,
        "include_images": False,
        "exclude_domains": ENGLISH_ONLY_DOMAINS,  # Loai tru site chi tieng Anh
    }
    if include_domains:
        payload["include_domains"] = include_domains

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning(f"[Tavily] Error: {e}")
        return []

    results = []
    for r in data.get("results", []):
        url = r.get("url", "")
        # raw_content là full text bài, content là snippet
        raw = r.get("raw_content", "") or ""
        snippet = r.get("content", "") or ""
        # Dung raw neu dai hon 500 chars va la tieng Viet
        cleaned_raw = _clean_content(raw) if len(raw) > 500 else ""
        # Bo content tieng Anh -- khong phu hop voi he thong tin Viet
        if cleaned_raw and not _is_vietnamese(cleaned_raw):
            logger.debug(f"[Tavily] Skip English content: {url[:60]}")
            cleaned_raw = ""   # dung snippet ngan thay the
        full_content = cleaned_raw if cleaned_raw else snippet
        results.append({
            "title": r.get("title", ""),
            "url": url,
            "content": full_content,
            "snippet": snippet[:500],    # snippet ngắn, chỉ lưu 500 chars
            "has_full_content": bool(cleaned_raw),
            "score": _score_result(url, base_score=r.get("score", 0.75)),
        })
    return results


def search_tavily_gov(query: str) -> list[dict]:
    """
    Tavily search tập trung vào nguồn chính phủ và báo chính thống.
    Chạy song song với search_tavily general.
    """
    return search_tavily(
        query,
        num_results=4,
        include_domains=GOV_DOMAINS + TRUSTED_DOMAINS,
    )


# ============================================================
# FALLBACK: Bing + DDG (chạy song song)
# ============================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
}

def _safe_get(url: str, timeout: int = 10, **kwargs):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, **kwargs)
        return r if r.status_code == 200 else None
    except Exception:
        return None


def search_bing(query: str, num_results: int = 5) -> list[dict]:
    from bs4 import Tag  # type: ignore[import-untyped]

    url = f"https://www.bing.com/search?q={quote_plus(query)}&cc=VN&setlang=vi-VN"
    resp = _safe_get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for li in soup.find_all("li", class_="b_algo"):
        if not isinstance(li, Tag):
            continue
        h2 = li.find("h2")
        if not isinstance(h2, Tag):
            continue
        a = h2.find("a")
        if not isinstance(a, Tag):
            continue
        href = str(a.get("href", ""))
        if not href.startswith("http") or " " in href or "bing.com/ck/" in href:
            continue
        title = a.get_text(strip=True)
        snippet_tag = li.find("p") or li.find("div", class_="b_caption")
        snippet_text = snippet_tag.get_text(strip=True) if isinstance(snippet_tag, Tag) else ""
        results.append({"title": title, "url": href, "content": snippet_text,
                        "score": _score_result(href, 0.75)})
        if len(results) >= num_results:
            break
    return results


def search_ddg(query: str, num_results: int = 5) -> list[dict]:
    from bs4 import Tag  # type: ignore[import-untyped]

    resp = _safe_get("https://html.duckduckgo.com/html/", params={"q": query})
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for div in soup.find_all("div", class_="result"):
        if not isinstance(div, Tag):
            continue
        a = div.find("a", class_="result__a")
        if not isinstance(a, Tag):
            continue
        href = str(a.get("href", ""))
        if not href.startswith("http"):
            continue
        title = a.get_text(strip=True)
        snip = div.find("a", class_="result__snippet")
        snippet = snip.get_text(strip=True) if isinstance(snip, Tag) else ""
        results.append({"title": title, "url": href, "content": snippet,
                        "score": _score_result(href, 0.70)})
        if len(results) >= num_results:
            break
    return results


def search_fallback(query: str, num_results: int = 5) -> list[dict]:
    """Bing + DDG chạy song song — dùng khi không có Tavily."""
    all_results, seen_urls = [], set()
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(search_bing, query, num_results): "bing",
            ex.submit(search_ddg, query, num_results): "ddg",
        }
        for future in as_completed(futures, timeout=12):
            for r in (future.result() or []):
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:num_results]


# ============================================================
# LANGCHAIN TOOL
# ============================================================

@tool
def web_search(query: str) -> list[dict]:
    """
    Tìm kiếm thông tin trên internet để kiểm chứng tin tức.

    - Dùng Tavily API (nếu có TAVILY_API_KEY) — nhanh, ổn định, không bị block
    - Fallback sang Bing + DuckDuckGo (chạy song song) nếu không có Tavily
    - Tự động ưu tiên nguồn chính phủ (.gov.vn) và báo lớn
    - Cache kết quả tránh request trùng

    Args:
        query: Câu truy vấn tìm kiếm

    Returns:
        Danh sách [{title, url, content, score}], score cao = nguồn uy tín hơn
    """
    log_agent_step(logger, "WebSearch", "Searching", f"Query: {query}")

    # Kiểm tra cache
    cache = _load_cache()
    key = _cache_key(query)
    if key in cache:
        cached_entry = cache[key]
        cached_results = cached_entry.get("results", [])
        log_agent_step(logger, "WebSearch", "Cache Hit", f"{len(cached_results)} results")
        return cached_results

    # Chọn search engine
    if TAVILY_API_KEY:
        # Chạy 2 Tavily search song song:
        # 1. General → tìm rộng mọi nguồn
        # 2. Focused → ưu tiên .gov.vn + báo lớn (đảm bảo luôn có nguồn chính phủ)
        all_results, seen_urls = [], set()
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_general = ex.submit(search_tavily, query, 5)
            f_gov     = ex.submit(search_tavily_gov, query)
            for future in as_completed([f_general, f_gov], timeout=20):
                for r in (future.result() or []):
                    if r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_results.append(r)
        # Ưu tiên gov.vn lên đầu
        all_results.sort(key=lambda x: x["score"], reverse=True)
        results = all_results[:6]
        engine = "Tavily (general + gov)"
    else:
        results = search_fallback(query, num_results=5)
        engine = "Bing+DDG"

    log_agent_step(logger, "WebSearch", f"{engine}", f"Found {len(results)} results")

    if results:
        _save_cache(cache, key, results)

    return results
