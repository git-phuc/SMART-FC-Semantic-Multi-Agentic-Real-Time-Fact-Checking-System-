"""
Real News Sample Generator (Crawler + LLM Question Generation)
===================================
1. Crawl tin báo mạng (Dân Trí, Tuổi Trẻ, Thanh Niên, VnExpress...)
2. Dùng LLM kiểm duyệt đúng chủ đề Chính trị / Xã hội.
3. Sinh câu hỏi xác minh từ bài báo THẬT (không biến đổi nội dung).
4. Label = "THẬT"

Output: fake_news_mutated.csv
"""

import csv
import os
import sys
import time
import random
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

# ── Load .env ─────────────────────────────────────────────────
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# ── CẤU HÌNH ─────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("AGENT3_API_KEY", "")
BASE_URL       = os.getenv("AGENT3_BASE_URL", "https://api.openai.com/v1")
MODEL          = "gpt-4o-mini"
TARGET_SAMPLES = 200  # Số bài cần có trong file

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "Data", "Posetive", "posetive-news-evaluation.csv")

if not OPENAI_API_KEY:
    print("❌ Không tìm thấy AGENT3_API_KEY. Vui lòng kiểm tra backend/.env")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY, base_url=BASE_URL)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

# ── 1. CẤU HÌNH CRAWLER ─────────────────────────────────────
CRAWL_SOURCES = [
    ("https://vnexpress.net/thoi-su", "https://vnexpress.net"),
    ("https://vnexpress.net/phap-luat", "https://vnexpress.net"),
    ("https://tuoitre.vn/chinh-tri.htm", "https://tuoitre.vn"),
    ("https://tuoitre.vn/phap-luat.htm", "https://tuoitre.vn"),
    ("https://thanhnien.vn/thoi-su.htm", "https://thanhnien.vn"),
    ("https://dantri.com.vn/xa-hoi.htm", "https://dantri.com.vn"),
    ("https://vietnamnet.vn/phap-luat", "https://vietnamnet.vn")
]

def safe_get(url, retries=2, timeout=15):
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r
        except requests.exceptions.Timeout:
            if attempt < retries: time.sleep(2)
        except Exception:
            break
    return None

def extract_article_links(list_url, domain_prefix):
    resp = safe_get(list_url)
    if not resp:
        return set()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if href.startswith("/"):
            href = domain_prefix + href
        elif not href.startswith("http"):
            continue
        if domain_prefix in href and len(href) > 40 and ("-" in href.split("/")[-1] or ".htm" in href):
            links.add(href)
    return links

def extract_article_content(url):
    resp = safe_get(url)
    if not resp:
        return None, None
    soup = BeautifulSoup(resp.text, "html.parser")

    title = None
    for sel in ["h1.title-detail", "h1.article-title", "h1.article__title", "h1.detail-title", "h1"]:
        el = soup.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            break

    if not title or len(title) < 15:
        return None, None

    paragraphs = [p.get_text(strip=True) for p in soup.find_all(["p", "div.content p"]) if len(p.get_text(strip=True)) > 40]
    content = "\n".join(paragraphs[:20])

    if len(content) < 200:
        return None, None

    return title, content


# ── 2. LLM FILTER CHỦ ĐỀ ────────────────────────────────────
FILTER_SYSTEM = """Bạn là chuyên gia phân loại nội dung trong lĩnh vực nghiên cứu truyền thông và khoa học chính trị.

NHIỆM VỤ: Xác định liệu bài báo có thuộc phạm vi nghiên cứu về CHÍNH TRỊ - XÃ HỘI - PHÁP LUẬT VĨ MÔ hay không, dựa trên các tiêu chí học thuật sau:

TIÊU CHÍ CHẤP NHẬN ("YES"):
1. Hoạt động lập pháp và hành pháp: Ban hành, sửa đổi văn bản quy phạm pháp luật; hoạt động của các cơ quan nhà nước cấp trung ương và địa phương; kỷ luật cán bộ, công chức.
2. An ninh công cộng và tư pháp: Các vụ án kinh tế lớn, hoạt động tố tụng, phòng chống tội phạm có tổ chức, an ninh mạng cấp quốc gia.
3. Chính sách xã hội vĩ mô: Quy hoạch hạ tầng, ngân sách công, chính sách đất đai, y tế công cộng, giáo dục diện rộng, thiên tai và ứng phó khủng hoảng.

TIÊU CHÍ LOẠI TRỪ ("NO"):
- Tin tức tội phạm thông thường (trộm cắp, ẩu đả, án mạng đơn lẻ không mang tính hệ thống).
- Nội dung giải trí, văn hóa đại chúng, hoạt động của người nổi tiếng.
- Thông tin đời tư, sức khỏe cá nhân, quan hệ gia đình.
- Quảng cáo thương mại, PR doanh nghiệp, bất động sản.
- Thể thao, e-sports, kết quả thi đấu.
- Tin tức quốc tế không có tác động trực tiếp đến Việt Nam.

YÊU CẦU ĐẦU RA: Chỉ trả về một trong hai giá trị: "YES" hoặc "NO"."""

def is_valid_topic(title, content):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": FILTER_SYSTEM},
                {"role": "user", "content": f"Tiêu đề: {title}\nNội dung (tóm tắt): {content[:800]}"}
            ],
            max_tokens=10,
            temperature=0.0
        )
        res = response.choices[0].message.content.strip().upper()
        return "YES" in res
    except Exception as e:
        print(f"      ⚠️ Lỗi LLM filter: {e}")
        return False


# ── 3. SINH CÂU HỎI TỪ BÀI THẬT ────────────────────────────
QUESTION_SYSTEM = """Bạn là người dùng mạng xã hội đang thắc mắc về một tin đọc được.

NHIỆM VỤ: Viết 1 tin nhắn hỏi AI xác minh, giống như người thật nhắn tin — ngắn gọn, tự nhiên, đúng chất "người dùng bình thường".

YÊU CẦU:
- Độ dài: 80–150 ký tự (KHÔNG được dài hơn).
- Đề cập 1–2 chi tiết cụ thể trong bài (con số, tên, ngày).
- Giọng tò mò, bình thường, không văn vẻ.
- Kết bằng: "thật không?" hoặc "đúng không?" hoặc "có thật không vậy?".
- Chỉ trả về đúng 1 câu hỏi duy nhất, không giải thích."""

QUESTION_USER = """Bài: {title}
Nội dung: {content}"""


def call_llm(system: str, user: str) -> str | None:
    for _ in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=0.7,
                max_tokens=200
            )
            res = r.choices[0].message.content.strip()
            return res.strip('"').strip("'")
        except Exception:
            time.sleep(10)
    return None

def is_valid_question(q):
    if not q or len(q) < 20: return False
    endings = ["thật không", "đúng không", "có thật không vậy", "thật hay giả", "chưa xác định"]
    return any(e.lower() in q.lower() for e in endings)


# ── 4. MAIN WORKFLOW ─────────────────────────────────────────
def main():
    print("=" * 65)
    print("🔄 CRAWL & GENERATE REAL NEWS SAMPLES (REPAIR MISSING)")
    print("=" * 65)

    fieldnames = ["index", "title", "question", "Link bài viết", "label",
                  "Decision", "output_1", "link_1", "output_2", "link_2", "output_3", "link_3", "label_model"]

    rows = []
    existing_links = set()
    
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                fieldnames = reader.fieldnames
            for row in reader:
                rows.append(row)
                link = row.get("Link bài viết") or row.get("Link bài gốc", "")
                if link:
                    existing_links.add(link)
    
    # Tìm các dòng bị trống (thiếu question/title)
    missing_indices = []
    for i, row in enumerate(rows):
        q = row.get("question", "").strip()
        if not q or q.lower() == "nan":
            missing_indices.append(i)
            
    if not missing_indices:
        print(f"✅ Hoàn hảo! Không có dòng nào thiếu trong tổng số {len(rows)} samples.")
        return
        
    print(f"⚠️ Phát hiện {len(missing_indices)} dòng bị trống. Sẽ tự động crawl nội dung lấp đầy...")

    # Quét links
    print("\n🕷️ BƯỚC 1: Thu thập links bài báo...")
    all_links = []
    for list_url, domain in CRAWL_SOURCES:
        links = extract_article_links(list_url, domain)
        for lnk in links:
            if lnk not in existing_links:
                all_links.append(lnk)
        print(f"    {domain.split('//')[1][:15]:15s} → quét được {len(links)} links")
        time.sleep(1)

    random.shuffle(all_links)
    print(f"    → Tổng links hợp lệ mới: {len(all_links)}\n")

    filled_count = 0

    for url in all_links:
        if not missing_indices:
            break

        title, content = extract_article_content(url)
        if not title: continue

        if not is_valid_topic(title, content):
            continue

        print(f"[{filled_count+1}/{len(missing_indices)}] ✅ THẬT | {title[:55]}...")

        q = call_llm(
            QUESTION_SYSTEM,
            QUESTION_USER.format(title=title, content=content[:2000])
        )
        if not is_valid_question(q):
            print("         ⚠️ Lỗi sinh câu hỏi, skip.")
            continue

        # Lấy index dòng bị thiếu đầu tiên
        target_i = missing_indices.pop(0)
        
        # Cập nhật row
        row = rows[target_i]
        row["title"] = title
        row["question"] = q
        row["Link bài viết"] = url
        row["label"] = "THẬT"
        
        filled_count += 1
        print(f"         💬 Đã điền vào thẻ index {row.get('index', target_i+1)}: {q}\n")

        # Ghi lưu ngay vào file
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    print(f"\n{'='*65}")
    print(f"✅ Hoàn thành! Đã điền thêm {filled_count} mẫu bị thiếu.")
    print(f"📄 File lưu tại: {OUTPUT_FILE}")
    print(f"{'='*65}")

if __name__ == "__main__":
    main()