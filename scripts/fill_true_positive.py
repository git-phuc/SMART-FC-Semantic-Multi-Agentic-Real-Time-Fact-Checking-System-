import csv
import os
import time
import random
import re
import requests
import json
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

# TẠO FILE MỚI, KHÔNG ĐỤNG VÀO FILE CŨ
NEW_POSITIVE_FILE = os.path.join(os.path.dirname(__file__), "..", "Evaluation", "posetive-news-evaluation-new.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

TARGET = 100

MUTATION_PROMPT = """Bạn là chuyên gia tạo bộ dữ liệu chuẩn (Ground Truth) cho hệ thống Fact-checking.
Mục tiêu: Đọc bài báo. Xét duyệt (Lọc) lấy tin Chính trị/Xã hội/Pháp luật Việt Nam. Sau đó TẠO RA 1 câu hỏi mang nhãn THẬT (Positive) với mức độ khó (1, 2, 3).

BƯỚC 1: LỌC NỘI DUNG (FILTERING)
Bài báo PHẢI thuộc lĩnh vực: Chính trị, Xã hội, Pháp luật, An ninh Quốc phòng, hoặc Điều hành Nhà nước Việt Nam.
Nếu là tin Giải trí, Showbiz, Thể thao, Quốc tế vô thưởng vô phạt, hoặc quảng cáo doanh nghiệp -> Trả về JSON: {"status": "REJECT", "reason": "Không thuộc lĩnh vực chính trị xã hội"}

BƯỚC 2: TẠO CÂU HỎI NHÃN "THẬT" (POSITIVE) CHÍNH XÁC 100%
Hãy chọn ngẫu nhiên một trong 3 mức độ khó sau để đặt câu hỏi (Đảm bảo dữ liệu đa dạng khó-dễ):
- Mức 1 (Dễ): Hỏi về sự kiện cốt lõi, tiêu đề chính của bài. Người bình thường chỉ cần đọc lướt tiêu đề là biết đúng. 
  (VD: "Anh ơi kiểm chứng giúp em có phải kỳ họp Quốc hội sáng nay vừa bế mạc không? Thật, giả hay chưa xác định?")
- Mức 2 (Trung bình): Hỏi về một CHI TIẾT CỤ THỂ (ngân sách dự chi, số liệu thống kê, tên quan chức phụ xử lý). AI phải đọc sâu vào thân bài mới thấy.
  (VD: "Em nghe đồn ngân sách cấp cho dự án cầu X là 1.500 tỷ đồng, thông tin này thật hay giả vậy?")
- Mức 3 (Khó): Lấy một điểm nhỏ giấu kỹ trong bài (một quy định ngách, một câu phát biểu nhỏ giọt cuối bài). Dạng này kiểm tra khả năng Context cực sâu của AI.

LUẬT BẮT BUỘC KHI TẠO CÂU HỎI:
- Mọi chi tiết (số liệu, tên, luật) trong câu hỏi PHẢI ĐÚNG HOÀN TOÀN so với bài báo. Tuyệt đối không thay đổi thông tin.
- Cuối câu hỏi luôn chêm mồi là đi hỏi AI: "Tin này Thật, giả hay chưa xác định?"

BƯỚC 3: TRẢ VỀ DUY NHẤT 1 KHỐI JSON:
{
  "status": "ACCEPT",
  "difficulty_level": <1, 2, hoac 3>,
  "question": "<CÂU HỎI ĐƯỢC TẠO>"
}
KHÔNG GHI THÊM BẤT CỨ TEXT NÀO NGOÀI JSON!"""

# CÁC NGUỒN CRAWL - BÁO CÁO CHÍNH THỐNG VÀ UY TÍN NHẤT VIỆT NAM VỀ CHÍNH TRỊ - XÃ HỘI
CRAWL_SOURCES = [
    ("https://baochinhphu.vn/chinh-tri.htm", "https://baochinhphu.vn", "h1", "p"),
    ("https://baochinhphu.vn/thoi-su.htm", "https://baochinhphu.vn", "h1", "p"),
    ("https://nhandan.vn/chinhtri/", "https://nhandan.vn", "h1", "p, div.detail-content-body p"),
    ("https://www.qdnd.vn/chinh-tri", "https://www.qdnd.vn", "h1", "p"),
    ("https://www.qdnd.vn/xa-hoi", "https://www.qdnd.vn", "h1", "p"),
    ("https://tuoitre.vn/chinh-tri.htm", "https://tuoitre.vn", "h1", "p"),
    ("https://thanhnien.vn/thoi-su.htm", "https://thanhnien.vn", "h1", "p"),
    ("https://vnexpress.net/thoi-su", "https://vnexpress.net", "h1", "p.description, p.Normal, p"),
    ("https://vnexpress.net/phap-luat", "https://vnexpress.net", "h1", "p.description, p.Normal, p")
]

def safe_get(url, retries=2, timeout=15):
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
        # Lọc các link URL có vẻ giống bài báo (độ dài đủ, chứa domain)
        if domain_prefix in href and len(href) > 45 and ("-" in href.split("/")[-1] or re.search(r"\d{5,}", href)):
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

    paragraphs = [p.get_text(strip=True) for p in soup.find_all(["p", "div.content p"]) if len(p.get_text(strip=True)) > 30]
    content = "\n".join(paragraphs[:25])

    if len(content) < 200:
        return None, None

    return title, content

def is_valid_question(q):
    if not q or len(q) < 50:
        return False
    endings = ["thật, giả hay chưa xác định", "thật hay giả", "chưa xác định"]
    if not any(e.lower() in q.lower() for e in endings):
        return False
    return True

def gen_question(title, content):
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": MUTATION_PROMPT},
                {"role": "user", "content": f"Tiêu đề: {title}\n\nNội dung:\n{content[:3000]}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=600,
            temperature=0.7,
        )
        resp_text = r.choices[0].message.content.strip()
        data = json.loads(resp_text)
        
        if data.get("status") != "ACCEPT":
            return None, None
            
        q = data.get("question", "")
        level = data.get("difficulty_level", 1)
        
        return q, level if is_valid_question(q) else (None, None)
    except Exception as e:
        print(f"    ⚠️ GPT error: {e}")
        return None, None

def main():
    print("=" * 65)
    print("🔄  SINH 100 DỮ LIỆU POSITIVE (THẬT) KÈM MỨC ĐỘ KHÓ 1-2-3 ")
    print("=" * 65)

    need = TARGET
    
    # Chuẩn bị file CSV mới
    fieldnames = ['index', 'title', 'question', 'Link bài gốc', 'label', 'mutation_level', 'Decision', 'output_1', 'link_1', 'output_2', 'link_2', 'output_3', 'link_3', 'label_model']
    
    new_rows = []
    existing_titles = set()

    print("🕷️  BƯỚC 1: Thu thập links bài báo chính thống...")
    all_links = []
    for list_url, domain, *_ in CRAWL_SOURCES:
        links = extract_article_links(list_url, domain)
        for lnk in links:
            all_links.append((lnk, domain))
        print(f"    {domain.split('//')[1][:20]:20s} ({list_url.split('/')[-1] or list_url.split('/')[-2]}) → {len(links)} links")
        time.sleep(0.5)

    random.shuffle(all_links)
    print(f"    → Tổng: {len(all_links)} links (đã shuffle)\n")

    print("🤖  BƯỚC 2: Crawl bài + Sinh câu hỏi thật (Lọc Policy + Level Khó)...")
    attempts = 0
    max_attempts = len(all_links)

    for url, domain in all_links:
        if len(new_rows) >= need:
            break
        if attempts >= max_attempts:
            break
        attempts += 1

        title, content = extract_article_content(url)
        if not title or title.strip().lower() in existing_titles:
            continue

        print(f"  [{len(new_rows)+1}/{need}] Đang xử lý: {title[:55]}...")

        q, level = gen_question(title, content)
        if not q:
            print(f"         ⚠️ Câu hỏi ko hợp lệ hoặc bị AI lọc bỏ, skip.")
            time.sleep(0.5)
            continue

        row = {fn: "" for fn in fieldnames}
        row.update({
            "index": len(new_rows) + 1,
            "title": title,
            "question": q,
            "Link bài gốc": url,
            "label": "THẬT",  # Nhãn cố định THẬT
            "mutation_level": level,  # Mức độ khó (1,2,3)
        })
        new_rows.append(row)
        existing_titles.add(title.strip().lower())
        print(f"         ✅ TẠO OK (Level {level}) — {len(q)} ký tự")
        time.sleep(0.4)

    if not new_rows:
        print("\n❌ Không sinh được bài mới nào.")
        return

    with open(NEW_POSITIVE_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(new_rows)

    print(f"\n{'='*65}")
    print(f"✅ Hoàn thành! Đã tạo {len(new_rows)} mẫu Positive mới.")
    print(f"📄 File lưu tại: {NEW_POSITIVE_FILE}")
    print(f"{'='*65}")

if __name__ == "__main__":
    main()
