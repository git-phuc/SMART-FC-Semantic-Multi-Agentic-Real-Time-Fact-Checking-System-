"""
Fake News Generator (Crawler + LLM Mutation)
===================================
1. Crawl tin báo mạng (Dân Trí, Tuổi Trẻ, Thanh Niên, VnExpress...)
2. Dùng LLM kiểm duyệt đúng chủ đề Chính trị / Xã hội.
3. Biến đổi bài báo THẬT thành phiên bản GIẢ ở 3 mức độ khó.
4. Dùng GPT-4o-mini để sinh câu hỏi kiểm chứng.

Output: fake_news_mutated.csv
"""

import csv
import os
import sys
import time
import random
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv

# ── Load .env ─────────────────────────────────────────────────
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# ── CẤU HÌNH ─────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("AGENT3_API_KEY", "")
BASE_URL       = os.getenv("AGENT3_BASE_URL", "https://api.openai.com/v1")
MODEL          = "gpt-4o-mini"
TARGET_SAMPLES = 200  # Số bài cần crawl

# Output: bài báo GIẢ đã mutation + câu hỏi
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "Data", "Negative", "negative-news-evaluation.csv")

if not OPENAI_API_KEY:
    print("❌ Không tìm thấy AGENT3_API_KEY. Vui lòng kiểm tra backend/.env")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY, base_url=BASE_URL)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

# ── 1. CẤU HÌNH CRAWLER (TRANG BÁO ĐẠI CHÚNG VIỆT NAM) ─────────
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
        # Lọc URL có vẻ giống bài báo (chứa domain, độ dài vừa đủ, chứa số ID hoặc -)
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


# ── 2. XÁC NHẬN CHỦ ĐỀ CHÍNH TRỊ / XÃ HỘI BẰNG LLM ─────────────
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
    """Sử dụng LLM để lọc bài viết có đúng chủ đề không."""
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


# ── 3. PHÂN BỔ MUTATION LEVEL ──────────────────────────────────
def assign_levels(total: int) -> list[int]:
    """Phân bổ level: 30% L1, 40% L2, 30% L3"""
    if total <= 0: return []
    n_l1 = max(1, round(total * 0.30))
    n_l3 = max(1, round(total * 0.30))
    n_l2 = total - n_l1 - n_l3
    levels = [1] * n_l1 + [2] * n_l2 + [3] * n_l3
    random.shuffle(levels)
    return levels


# ── 4. PROMPT MUTATION BÀI BÁO (THẬT → GIẢ) ────────────────────
MUTATION_SYSTEM = """Bạn là chuyên gia tạo dữ liệu đánh giá tin giả.
NHIỆM VỤ: Đọc bài báo gốc và tạo ra một phiên bản GIẢ (mutated) dựa theo mức độ được yêu cầu.

YÊU CẦU:
1. Bạn phải cố tình làm SAI LỆCH thông tin (thay số liệu, đảo ngược kết quả, đổi tên cơ quan, tự chế quy định mới, v.v.).
2. Trích xuất chính xác "câu khẳng định sai lệch" (fabricated_claim) mà bạn vừa chế ra. Đây chính là "hạt nhân" tin giả để làm mồi sinh câu hỏi.

TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON sau, KHÔNG kèm giải thích:
{
  "fake_content": "<Đoạn bài báo đã bị xào nấu thành tin sai sự thật>",
  "fabricated_claim": "<Câu tóm tắt đúng chi tiết nòng cốt bịa đặt. Ví dụ: 'Bộ CA sẽ cấm nhận tiền bảo lãnh' hoặc 'Ngân hàng Nhà nước phá sản'>"
}"""

MUTATION_PROMPTS = {
    1: """LEVEL 1 — SAI LỆCH RÕ RÀNG (Thay đổi các số liệu khổng lồ, sửa hẳn kết luận cốt lõi của bài báo gốc).
Tiêu đề gốc: {title}
Nội dung gốc: {content}""",

    2: """LEVEL 2 — SAI LỆCH CHỦ THỂ (Văn phong trung lập, nhưng sửa tên cơ quan ra quyết định, sửa mức phạt, ngày tháng hiệu lực).
Tiêu đề gốc: {title}
Nội dung gốc: {content}""",

    3: """LEVEL 3 — SAI LỆCH CỰC VI (Giữ nguyên gốc 95%, chỉ chọc 1 lỗ sai: sửa 1 con số giấu kín, hoặc 1 quy định ngách đan xen bên trong).
Tiêu đề gốc: {title}
Nội dung gốc: {content}"""
}


# ── 5. PROMPT SINH CÂU HỎI MẠNG XÃ HỘI TỪ BẢN GIẢ ────────────────
QUESTION_SYSTEM = """Bạn đóng vai một người dùng mạng đang yêu cầu hệ thống kiểm chứng một sự kiện đang lan truyền.

NHIỆM VỤ: Dựa vào "Nội dung bài báo GIẢ" và "Ý chính bịa đặt", hãy tạo MỘT Câu Hỏi Kiểm Chứng phức tạp và đầy đủ bối cảnh (100 - 300 từ).

QUY TRÌNH & NGUYÊN TẮC:
1. BỐI CẢNH: Tóm tắt lại câu chuyện bịa đặt như thể bạn vừa đọc được nó trên mạng. Phải chèn ĐẦY ĐỦ các thông tin trọng yếu: tên cơ quan, tên người, nội dung sự kiện, các con số hay quy định sai lệch. Không được viết hời hợt vài chữ.
2. BIỂU ĐẠT: Hãy trình bày như một người đang tóm tắt lại tin đồn: "Gần đây trên mạng có thông tin cho rằng...", "Tôi có đọc được một bài báo viết về việc..."
3. TRUY VẤN: Ở phần cuối, đặt câu hỏi yêu cầu xác minh rõ ràng tính đúng sai của thông tin đó. 
4. TUYỆT ĐỐI không được trả lời thay! Chỉ đóng vai người đặt câu hỏi. Không chèn markdown.

ĐẦU RA: Trả về DUY NHẤT một đoạn văn hoàn chỉnh chứa toàn bộ thông tin trên."""

QUESTION_USER = """Nội dung bài báo GIẢ (bối cảnh bịa đặt):
{fake_content}

Ý chính bịa đặt (cốt lõi sai trái):
{fabricated_claim}"""


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
                max_tokens=2000
            )
            res = r.choices[0].message.content.strip()
            return res.strip('"').strip("'")
        except Exception:
            time.sleep(10)
    return None

def is_valid_question(q):
    if not q or len(q) < 50: return False
    endings = ["thật", "giả", "xác định", "đúng", "không", "nhỉ", "vậy"]
    return any(e.lower() in q.lower() for e in endings)


# ── 6. MAIN WORKFLOW ───────────────────────────────────────────
def main():
    print("=" * 65)
    print("🔄 CRAWL & GENERATE FAKE NEWS (LEVEL 1-2-3)")
    print("=" * 65)

    need = TARGET_SAMPLES
    new_rows = []
    
    # ── Đọc các link cũ đã sinh để tránh trùng
    existing_links = set()
    max_index = 0
    total_existing_rows = 0
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                existing_links.add(row.get("Link bài gốc", ""))
                if row.get("title", "").strip():
                    total_existing_rows += 1
                try: max_index = max(max_index, int(row.get("index", 0)))
                except: pass

    need = TARGET_SAMPLES - total_existing_rows
    if need <= 0:
        print(f"🎉 Đã đủ {TARGET_SAMPLES} samples trong CSV GIẢ! Không cần chạy thêm.")
        return
        
    print(f"📊 Đã có {total_existing_rows} samples. Cần thu thập thêm {need} bài nữa (bắt đầu từ index {max_index + 1}).")

    # ── Quét các Link ─────────────────────────────────────────
    print(f"🕷️ BƯỚC 1: Thu thập links bài báo ĐẠI CHÚNG...")
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

    # ── Mở file Ghi ───────────────────────────────────────────
    levels = assign_levels(need)
    level_names = {1: "🟢 Kích động (1)", 2: "🟡 Sửa số (2)", 3: "🔴 Sửa nhỏ (3)"}
    
    fieldnames = ["index", "title", "question", "Link bài viết", "Link bài gốc", "label", "mutation_level", "Decision", "output_1", "link_1", "output_2", "link_2", "output_3", "link_3", "label_model"]
    mode = "a" if os.path.exists(OUTPUT_FILE) else "w"
    
    with open(OUTPUT_FILE, mode, newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w": w.writeheader()

        for url in all_links:
            if len(new_rows) >= need: break
            
            # Đọc nội dung bài
            title, content = extract_article_content(url)
            if not title: continue

            # LLM Filter Chủ đề
            if not is_valid_topic(title, content):
                continue
                
            level = levels[len(new_rows)]
            print(f"[{len(new_rows)+1}/{need}] {level_names[level]} | {title[:50]}...")
            
            # Mutate THẬT -> GIẢ
            mutated_raw = call_llm(
                MUTATION_SYSTEM, 
                MUTATION_PROMPTS[level].format(title=title, content=content[:3000])
            )
            if not mutated_raw: continue
            
            import json
            try:
                mutated_cleaned = mutated_raw.replace('```json', '').replace('```', '').strip()
                parsed = json.loads(mutated_cleaned)
                fake_content = parsed.get("fake_content", "")
                fabricated_claim = parsed.get("fabricated_claim", "")
            except Exception as e:
                print(f"         ⚠️ Lỗi Parse JSON Mutated: {e}")
                continue
                
            if not fake_content or not fabricated_claim:
                print("         ⚠️ Lỗi JSON trống.")
                continue
            
            # Tạo Câu hỏi hoàn chỉnh với đầy đủ bối cảnh bịa đặt
            q = call_llm(
                QUESTION_SYSTEM, 
                QUESTION_USER.format(fake_content=fake_content, fabricated_claim=fabricated_claim)
            )
            if not is_valid_question(q):
                print("         ⚠️ Câu hỏi ko hợp lệ, skip.")
                continue

            max_index += 1
            row = {fn: "" for fn in fieldnames}
            row.update({
                "index": max_index,
                "title": title,
                "question": q,
                "Link bài viết": "LLM Generated",
                "Link bài gốc": url,
                "label": "GIẢ",
                "mutation_level": level
            })
            new_rows.append(row)
            w.writerow(row)
            f.flush()
            print(f"         ✅ TẠO OK — {len(q)} ký tự\n")

    print(f"\n{'='*65}")
    print(f"✅ Hoàn thành! Đã tạo thêm {len(new_rows)} mẫu GIẢ mới.")
    print(f"📄 File lưu tại: {OUTPUT_FILE}")
    print(f"{'='*65}")

if __name__ == "__main__":
    main()