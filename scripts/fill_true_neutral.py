"""
Tạo dữ liệu Neutral Tinh Khiết (Ground Truth = CHƯA XÁC ĐỊNH)
Kịch bản sinh câu hỏi: Tin đồn tương lai, Động cơ thuyết âm mưu, Tin đồn vi mô.

FIX & CẢI THIỆN:
- Crawl đa nguồn với selector cụ thể hơn
- Prompt được cải thiện để tạo câu hỏi khó tìm kiếm hơn
- Kiểm tra chất lượng câu hỏi trước khi lưu
- Tránh trùng lặp tốt hơn
- Retry logic cho network errors
"""

import csv
import os
import time
import random
import re
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

client = OpenAI(
    api_key=os.getenv("AGENT3_API_KEY"),
    base_url=os.getenv("AGENT3_BASE_URL", "https://api.openai.com/v1"),
)
MODEL = "gpt-4o-mini"

NEUTRAL_FILE = os.path.join(os.path.dirname(__file__), "..", "Evaluation", "neutral-news-evaluation.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TARGET = 300

# ──────────────────────────────────────────────
# PROMPT ĐÃ CẢI THIỆN
# ──────────────────────────────────────────────
MUTATION_PROMPT = """Bạn là chuyên gia tạo bài test cho hệ thống fact-checking trí tuệ nhân tạo.
Mục tiêu: Đọc bài báo gốc về ĐỜI SỐNG / XÃ HỘI, sau đó TẠO RA một Câu hỏi tin đồn (rất đời thường, lặt vặt) mà BẮT BUỘC KẾT QUẢ TÌM KIẾM GOOGLE SẼ CHẢ AI THÈM KIỂM CHỨNG.

BỐI CẢNH BẮT BUỘC: 
- PHẢI dùng Tên riêng, Địa danh, hoặc chi tiết có thật từ bài báo.
- Dịch chuyển câu chuyện thành ĐỜI SỐNG DÂN CƯ, mâu thuẫn chung cư, chuyện hàng xóm lặt vặt. Hệ thống fact-checking chính trị thường "mù" với thể loại tin đồn xóm làng này.

CÁCH TẠO TIN ĐỒN:
1. Tranh cãi tiền nong cá nhân, mâu thuẫn bãi đậu xe, chó mèo cắn nhau giữa các nhân vật trong bài.
2. Tiếng chửi bới, tiếng khóc lúc nửa đêm không ai ghi âm lại.
3. Bí mật gia đình, ly hôn ngầm, xích mích mẹ chồng nàng dâu.

LUẬT QUAN TRỌNG NHẤT:
- Câu hỏi tập trung vào chi tiết sinh hoạt CỰC KỲ ĐỜI THƯỜNG.
- Bắt đầu bằng: "Trong group cư dân có đồn rằng..." hoặc "Mấy bà hàng xóm bàn tán rằng..."
- Kết thúc bằng: "Xin hệ thống kiểm chứng giúp tôi thông tin này THẬT, GIẢ hay CHƯA XÁC ĐỊNH?"
- Đóng vai một người dân nhiều chuyện.

CHỈ TRẢ VỀ DUY NHẤT 1 CÂU HỎI HOÀN CHỈNH. KHÔNG GHI THÊM GÌ KHÁC."""


# ──────────────────────────────────────────────
CRAWL_SOURCES = [
    # TRANG ĐỜI SỐNG, CỘNG ĐỒNG, GIÁO DỤC, SỨC KHỎE NHÀ ĐẤT
    ("https://vnexpress.net/doi-song", "https://vnexpress.net", "h1", "p.description, p.Normal, p"),
    ("https://vnexpress.net/giao-duc", "https://vnexpress.net", "h1", "p.description, p.Normal, p"),
    ("https://dantri.com.vn/doi-song.htm", "https://dantri.com.vn", "h1", "p"),
    ("https://dantri.com.vn/van-hoa.htm", "https://dantri.com.vn", "h1", "p"),
    ("https://vietnamnet.vn/doi-song", "https://vietnamnet.vn", "h1", "p"),
    ("https://vietnamnet.vn/giao-duc", "https://vietnamnet.vn", "h1", "p"),
    ("https://tuoitre.vn/nhip-song-tre.htm", "https://tuoitre.vn", "h1", "p"),
    ("https://tuoitre.vn/giao-duc.htm", "https://tuoitre.vn", "h1", "p"),
]

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def safe_get(url, retries=2, timeout=12):
    """HTTP GET với retry và timeout."""
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(2)
        except Exception:
            break
    return None


def extract_article_links(list_url, domain_prefix):
    """Crawl trang danh sách bài, trả về set URLs bài viết."""
    resp = safe_get(list_url)
    if not resp:
        return set()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Chuẩn hóa URL tương đối
        if href.startswith("/"):
            href = domain_prefix + href
        elif not href.startswith("http"):
            continue
        # Lọc bài viết (độ dài đủ, đúng domain, có slug chữ)
        if domain_prefix in href and len(href) > 45 and "-" in href.split("/")[-1]:
            links.add(href)
    return links


def extract_article_content(url):
    """Crawl bài viết, trả về (title, content) hoặc (None, None)."""
    resp = safe_get(url)
    if not resp:
        return None, None
    soup = BeautifulSoup(resp.text, "html.parser")

    # Thử nhiều selector title phổ biến
    title = None
    for sel in ["h1.title-detail", "h1.article-title", "h1.article__title",
                "h1.detail-title", "h1.title-page-detail", "h1"]:
        el = soup.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            break

    if not title or len(title) < 15:
        return None, None

    # Lấy nội dung đoạn văn
    paragraphs = [p.get_text(strip=True) for p in soup.find_all(["p", "div.content p", "div.article-content p", "div.detail-content p", "div.article__detail p"]) if len(p.get_text(strip=True)) > 30]
    content = "\n".join(paragraphs[:25])

    if len(content) < 200:
        return None, None

    return title, content


def is_valid_question(q):
    """Kiểm tra chất lượng câu hỏi sinh ra."""
    if not q or len(q) < 80:
        return False
    # Phải có trigger phrase ngụ ý rò rỉ nội bộ hoặc đồn thổi dân cư
    triggers = ["tôi nghe", "tin đồn", "rò rỉ", "nghe đồn", "nội bộ", "người quen", "đồn", "bàn tán", "cư dân", "hàng xóm"]
    if not any(t in q.lower() for t in triggers):
        return False
    # Phải có câu kết
    endings = ["thật, giả hay chưa xác định", "thật hay giả hay chưa xác định",
               "thông tin này là", "xác minh", "kiểm chứng", "chưa xác định"]
    if not any(e in q.lower() for e in endings):
        return False
    return True


def gen_question(title, content):
    """Gọi GPT-4o-mini để sinh câu hỏi CHƯA XÁC ĐỊNH."""
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": MUTATION_PROMPT},
                {"role": "user", "content": f"Tiêu đề bài báo: {title}\n\nNội dung:\n{content[:3000]}"},
            ],
            max_tokens=500,
            temperature=0.85,   # Giảm từ 0.9 → ít hallucinate hơn nhưng vẫn sáng tạo
        )
        q = r.choices[0].message.content.strip().strip('"').strip("'")
        return q if is_valid_question(q) else None
    except Exception as e:
        print(f"    ⚠️ GPT error: {e}")
        return None


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("=" * 65)
    print("🔄  SINH DỮ LIỆU NEUTRAL (CHƯA XÁC ĐỊNH) — SMART-FC EVAL")
    print("=" * 65)

    # ── Đọc file hiện tại ──
    if not os.path.exists(NEUTRAL_FILE):
        print(f"❌ Không tìm thấy: {NEUTRAL_FILE}")
        return

    with open(NEUTRAL_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fnames = list(reader.fieldnames)
        neu_rows = list(reader)

    # ── Giữ nguyên toàn bộ file hiện tại (55 mẫu) để crawl thêm cho đầy 100 ──
    kept = []
    for r in neu_rows:
        # Nếu có câu hỏi thì giữ hết
        if r.get("question", "").strip():
            # GIỮ NGUYÊN HOÀN TOÀN TẤT CẢ GIÁ TRỊ, KHÔNG XÓA NỮA!
            kept.append(r)
            
    print(f"🧹 Dọn file CSV: Giữ lại {len(kept)} mẫu cũ.")
    need = TARGET - len(kept)
    print(f"📊 Cần tạo thêm: {need} mẫu\n")

    if need <= 0:
        print("✅ Đã đủ số lượng, không cần tạo thêm.")
        return

    # ── Tập hợp title đã có để tránh trùng ──
    existing_titles = {r.get("title", "").strip().lower() for r in kept}

    # ── Crawl links từ tất cả nguồn ──
    print("🕷️  BƯỚC 1: Thu thập links bài viết...")
    all_links = []  # [(url, domain_prefix)]
    for list_url, domain, *_ in CRAWL_SOURCES:
        links = extract_article_links(list_url, domain)
        for lnk in links:
            all_links.append((lnk, domain))
        print(f"    {domain.split('//')[1][:20]:20s} → {len(links)} links")
        time.sleep(0.5)

    random.shuffle(all_links)
    print(f"    → Tổng: {len(all_links)} links (đã shuffle)\n")

    # ── Sinh câu hỏi ──
    print("🤖  BƯỚC 2: Crawl bài + Sinh câu hỏi CHƯA XÁC ĐỊNH...")
    new_rows = []
    attempts = 0
    max_attempts = len(all_links)

    for url, domain in all_links:
        if len(new_rows) >= need:
            break
        if attempts >= max_attempts:
            break
        attempts += 1

        title, content = extract_article_content(url)
        if not title:
            continue
        if title.strip().lower() in existing_titles:
            continue

        print(f"  [{len(new_rows)+1}/{need}] Đang xử lý: {title[:55]}...")

        q = gen_question(title, content)
        if not q:
            print(f"         ⚠️ Câu hỏi sinh ra không hợp lệ, bỏ qua.")
            time.sleep(0.5)
            continue

        row = {fn: "" for fn in fnames}
        row.update({
            "index": "",                  # Re-index sau
            "title": title,
            "question": q,
            "Link bài gốc": url,
            "label": "CHƯA XÁC ĐỊNH",    # Ground truth cứng
            "mutation_level": 2,          # Mức độ khó
        })
        new_rows.append(row)
        existing_titles.add(title.strip().lower())
        print(f"         ✅ OK — {len(q)} ký tự")
        time.sleep(0.4)  # Rate limit OpenAI

    # ── Ghi kết quả ──
    if not new_rows:
        print("\n❌ Không sinh được bài mới nào. Kiểm tra network hoặc API key.")
        return

    final_rows = kept + new_rows
    # Re-index từ 1
    for i, r in enumerate(final_rows, 1):
        r["index"] = i

    with open(NEUTRAL_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fnames)
        w.writeheader()
        w.writerows(final_rows)

    print(f"\n{'='*65}")
    print(f"✅ Hoàn thành! Đã tạo {len(new_rows)} mẫu mới.")
    print(f"📊 Tổng Neutral: {len(final_rows)}/{TARGET}")
    print(f"📄 File: {NEUTRAL_FILE}")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()