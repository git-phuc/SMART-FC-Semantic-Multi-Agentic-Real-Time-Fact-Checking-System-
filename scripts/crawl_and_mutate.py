"""
Crawl bài bóc phốt từ CAND + QDND (chống diễn biến hòa bình)
→ LLM filter: chỉ giữ bài CHÍNH TRỊ / XÃ HỘI
→ LLM trích xuất luận điệu xuyên tạc gốc → biến thành câu hỏi
→ Append vào negative CSV (index 68-100)
"""
import csv, os, sys, time, random, re, requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

client = OpenAI(
    api_key=os.getenv("AGENT3_API_KEY"),
    base_url=os.getenv("AGENT3_BASE_URL", "https://api.openai.com/v1"),
)
MODEL = "gpt-4o-mini"

EVAL_DIR = os.path.join(os.path.dirname(__file__), "..", "Evaluation")
NEGATIVE_FILE = os.path.join(EVAL_DIR, "negative-news-evaluation.csv")
TARGET = 16
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
}

def safe_get(url, timeout=15, retries=2):
    """Request with retry"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.encoding = 'utf-8'
            if resp.status_code == 200:
                return resp
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                raise e
    return None

# ═══════════════════════════════════════════════════════════
# BƯỚC 1: Crawl links
# ═══════════════════════════════════════════════════════════
print("=" * 60)
print("🕷️  BƯỚC 1: Crawl links từ CAND + QDND")
print("=" * 60)

all_links = set()

# --- QDND ---
for page in range(10, 30):
    url = f"https://www.qdnd.vn/phong-chong-dien-bien-hoa-binh?trang={page}"
    try:
        resp = safe_get(url)
        if not resp:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        count = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = "https://www.qdnd.vn" + href
            if "qdnd.vn" in href and re.search(r'-\d{5,}', href):
                if href not in all_links and "/phong-chong-dien-bien-hoa-binh" not in href.rstrip('/').rsplit('/', 1)[-1]:
                    all_links.add(href)
                    count += 1
        print(f"  📂 QDND trang {page}: +{count}")
        if count == 0:
            break
        time.sleep(0.5)
    except Exception as e:
        print(f"  ❌ QDND trang {page}: {str(e)[:50]}")
        break

# --- CAND ---
for page in range(10, 30):
    url = f"https://cand.com.vn/chong-dien-bien-hoa-binh/page-{page}/"
    try:
        resp = safe_get(url)
        if not resp:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        count = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = "https://cand.com.vn" + href
            if "cand.com.vn" in href and re.search(r'i\d{5,}', href):
                if href not in all_links:
                    all_links.add(href)
                    count += 1
        print(f"  📂 CAND trang {page}: +{count}")
        if count == 0:
            break
        time.sleep(0.5)
    except Exception as e:
        print(f"  ❌ CAND trang {page}: {str(e)[:50]}")
        break

print(f"\n  📊 Tổng links: {len(all_links)}")

# ═══════════════════════════════════════════════════════════
# BƯỚC 2: Extract article content
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print("📰 BƯỚC 2: Extract bài viết")
print("=" * 60)

# Lấy titles đã có
with open(NEGATIVE_FILE, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    existing = list(reader)
existing_titles = {r["title"].strip().lower() for r in existing}

articles = []
links_list = list(all_links)
random.shuffle(links_list)

for url in tqdm(links_list, desc="Extracting"):
    if len(articles) >= TARGET * 3:  # Lấy dư để filter
        break
    
    try:
        resp = safe_get(url, timeout=15)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Title
        title = ""
        for sel in ["h1.title-detail", "h1.detail-title", "h1.title_news_detail", 
                     "h1.title-post", "h1.article-title", "h1"]:
            el = soup.select_one(sel)
            if el:
                title = el.get_text(strip=True)
                break
        
        # Content 
        content = ""
        for sel in ["div.detail-content", "div.content-detail", "article.fck_detail",
                     "div.singular-content", "div.detail-body", "div.detail__content", "article"]:
            el = soup.select_one(sel)
            if el:
                paragraphs = el.find_all("p")
                content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                break
        
        if not content:
            paragraphs = soup.find_all("p")
            content = "\n".join(p.get_text(strip=True) for p in paragraphs[:20] if p.get_text(strip=True))
        
        if not title or len(content) < 300:
            continue
        
        if title.strip().lower() in existing_titles:
            continue
        
        articles.append({"url": url, "title": title, "content": content[:4000]})
        existing_titles.add(title.strip().lower())
        
    except Exception:
        continue
    
    time.sleep(0.3)

print(f"\n  ✅ Extracted: {len(articles)} bài")

# ═══════════════════════════════════════════════════════════
# BƯỚC 3: LLM FILTER → chỉ giữ bài chính trị/xã hội
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print("🔍 BƯỚC 3: LLM Filter - chỉ giữ bài CHÍNH TRỊ / XÃ HỘI")
print("=" * 60)

FILTER_PROMPT = """Phân loại bài viết theo chủ đề. Trả về ĐÚNG 1 nhãn:

- "CHÍNH TRỊ" - xuyên tạc đường lối Đảng, Nhà nước, chế độ, lãnh đạo, sáp nhập, bầu cử, chính sách
- "XÃ HỘI" - kích động bất mãn xã hội, chia rẽ dân tộc, tôn giáo, biểu tình, bạo lực
- "AN NINH" - xuyên tạc quân đội, công an, quốc phòng, an ninh mạng
- "KHÁC" - lừa đảo tài chính, quảng cáo, công nghệ, bình luận chung chung không cụ thể

CHỈ TRẢ VỀ MỘT NHÃN DUY NHẤT."""

filtered = []
for art in tqdm(articles, desc="Filtering"):
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": FILTER_PROMPT},
                {"role": "user", "content": f"Tiêu đề: {art['title']}\n\nTóm tắt: {art['content'][:500]}"},
            ],
            max_tokens=10,
            temperature=0,
        )
        label = resp.choices[0].message.content.strip().upper()
        
        if any(k in label for k in ["CHÍNH TRỊ", "XÃ HỘI", "AN NINH"]):
            filtered.append(art)
            status = f"✅ {label}"
        else:
            status = f"⬚ {label}"
        
        if len(filtered) % 5 == 0 or "KHÁC" not in label:
            tqdm.write(f"  {status} | {art['title'][:55]}")
            
    except Exception as e:
        tqdm.write(f"  ❌ {str(e)[:40]}")
    
    time.sleep(0.2)

print(f"\n  📊 Sau filter: {len(filtered)}/{len(articles)} bài (giữ {len(filtered)})")

# ═══════════════════════════════════════════════════════════
# BƯỚC 4: LLM Mutation → câu hỏi tin giả
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"🔄 BƯỚC 4: LLM Mutation ({min(TARGET, len(filtered))} bài)")
print("=" * 60)

MUTATE_PROMPT = """Bạn là chuyên gia nghiên cứu an ninh thông tin, chuyên phân tích các chiến dịch tuyên truyền chống phá nhà nước Việt Nam.

## Nhiệm vụ:
Bài viết dưới đây là bài BÓC PHỐT/PHẢN BÁC tin giả từ báo chính thống.
Hãy ĐỌC KỸ → tìm LUẬN ĐIỆU XUYÊN TẠC GỐC mà bài đang phản bác → viết lại luận điệu đó thành CÂU HỎI KIỂM CHỨNG, như thể đó là lời một người dân bình thường đọc được trên Facebook/TikTok/Zalo.

## Kỹ thuật tái tạo luận điệu (chọn 1-2):
1. **Bịa số liệu cụ thể**: thêm con số giả nhưng nghe hợp lý ("hơn 500 người bị...", "mất 3000 tỷ đồng...")
2. **Gán động cơ xấu cho lãnh đạo**: "thực chất là để trục lợi cá nhân", "che giấu tham nhũng"  
3. **Suy diễn cực đoan**: biến 1 sự kiện nhỏ thành "sụp đổ", "khủng hoảng", "biểu tình"
4. **Lồng sự kiện thật + bình luận xuyên tạc**: giữ 70% thông tin đúng, xuyên tạc 30% quan trọng
5. **Giọng điệu "thức tỉnh"**: "sự thật đằng sau", "điều báo chí không dám nói", "chính quyền che giấu"
6. **Kích động bất mãn**: liên hệ đến đời sống khó khăn, bất công xã hội, dân bị bỏ rơi

## Ví dụ THAM KHẢO:
- Bài bóc phốt: "Sai sự thật thông tin Đà Lạt bạo động"
  → "Tôi đọc trên Facebook rằng tại Đà Lạt đã xảy ra bạo động quy mô lớn, hàng trăm người dân xuống đường phản đối chính quyền cưỡng chế đất đai, công an đã sử dụng vũ lực đàn áp, nhiều người bị thương. Trang tin còn đăng ảnh đám đông và khói lửa, cho rằng chính quyền đang bưng bít thông tin, không có báo chí nào được phép đưa tin. Xin xác minh thông tin này THẬT hay GIẢ."

- Bài bóc phốt: "Xuyên tạc chính sách sáp nhập tỉnh"
  → "Tôi nghe thấy trên mạng xã hội rằng việc sáp nhập tỉnh thực chất là âm mưu của một nhóm lợi ích nhằm chiếm đoạt đất đai và tài sản công, hàng nghìn cán bộ công chức sẽ bị sa thải không được bồi thường, người dân ở các tỉnh bị sáp nhập sẽ mất quyền lợi về đất đai và hộ khẩu. Có người còn nói rằng đây là bước đầu để xóa bỏ chính quyền địa phương, tập trung quyền lực vào một nhóm nhỏ... Xin xác minh thông tin này THẬT hay GIẢ."

## Yêu cầu output:
- 150-300 từ, tiếng Việt tự nhiên
- PHẢI có chi tiết cụ thể (tên người, địa danh, tổ chức, con số) lấy từ bài gốc
- Bắt đầu: "Tôi đọc/nghe thấy trên mạng xã hội/Facebook/Zalo rằng..."
- Kết thúc: "Xin xác minh thông tin này THẬT hay GIẢ."
- QUAN TRỌNG: câu hỏi phải nghe ĐÁNG TIN, không được quá lố

## Nếu bài KHÔNG chứa xuyên tạc cụ thể nào → trả về "SKIP"

CHỈ TRẢ VỀ CÂU HỎI HOẶC "SKIP". KHÔNG GIẢI THÍCH."""

next_idx = len(existing) + 1
new_rows = []
skipped = 0

for art in tqdm(filtered[:TARGET + 10], desc="Mutating"):
    if len(new_rows) >= TARGET:
        break
    
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": MUTATE_PROMPT},
                {"role": "user", "content": f"Tiêu đề: {art['title']}\n\nNội dung:\n{art['content'][:3000]}"},
            ],
            max_tokens=800,
            temperature=0.8,
        )
        result = resp.choices[0].message.content.strip()
        
        if result.upper() == "SKIP" or len(result) < 50:
            skipped += 1
            continue
        
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1].strip()
        
    except Exception as e:
        tqdm.write(f"  ❌ {str(e)[:50]}")
        continue
    
    new_row = {fn: "" for fn in fieldnames}
    new_row.update({
        "index": next_idx,
        "title": art["title"],
        "question": result,
        "Link bài viết": "",
        "Link bài gốc": art["url"],
        "label": "GIẢ",
        "mutation_level": 2,
    })
    new_rows.append(new_row)
    tqdm.write(f"  ✅ [{next_idx}] {art['title'][:55]}...")
    next_idx += 1
    time.sleep(0.3)

# ═══════════════════════════════════════════════════════════
# BƯỚC 5: Ghi CSV
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"📝 BƯỚC 5: Ghi vào CSV")
print("=" * 60)
print(f"  Skipped: {skipped}")
print(f"  Mới:     {len(new_rows)}")

if new_rows:
    try:
        with open(NEGATIVE_FILE, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerows(new_rows)
        
        with open(NEGATIVE_FILE, "r", encoding="utf-8-sig") as f:
            total = len(list(csv.DictReader(f)))
        
        print(f"  TỔNG: {total}/100")
        print(f"\n  ✅ Thành công!")
    except PermissionError:
        tmp = NEGATIVE_FILE + ".append.csv"
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(new_rows)
        print(f"  ⚠️ File lock → {tmp}")

print(f"\n{'='*60}")
print("🏁 HOÀN THÀNH!")
print(f"{'='*60}")
