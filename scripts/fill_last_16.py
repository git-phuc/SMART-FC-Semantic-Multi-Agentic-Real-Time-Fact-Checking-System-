"""
Fill last 16 remaining negative samples (index 85-100) 
Using positive-news-evaluation.csv [1-16]
"""
import csv, os, sys, time, random
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
POSITIVE_FILE = os.path.join(EVAL_DIR, "Data", "posetive-news-evaluation.csv")

TARGET_AMOUNT = 16

# ═══════════════════════════════════════════════════════════
print("=" * 60)
print(f"🔄 MUTATION 16 SAMPLES CUỐI TỪ POSITIVE")
print("=" * 60)

with open(NEGATIVE_FILE, "r", encoding="utf-8-sig") as f:
    neg_rows = list(csv.DictReader(f))
    fieldnames = csv.DictReader(open(NEGATIVE_FILE, "r", encoding="utf-8-sig")).fieldnames

current_len = len(neg_rows)
print(f"Hiện rại: {current_len}/100 samples")

if current_len >= 100:
    print("Đã đủ 100 samples!")
    sys.exit(0)

need = 100 - current_len

with open(POSITIVE_FILE, "r", encoding="utf-8-sig") as f:
    pos_rows = list(csv.DictReader(f))

# Take the first 'need' rows from POSITIVE (they were not used, we only used 51-100)
pos_subset = pos_rows[:need]

MUTATION_PROMPT = """Bạn là chuyên gia nghiên cứu an ninh mạng, chuyên về phân tích tin giả chống phá chính quyền. 
Nhiệm vụ: biến tin THẬT thành tin GIẢ mang tính chất chống phá/xuyên tạc cho bộ dữ liệu fact-checking.

## Cách biến đổi:
1. Giữ nguyên sự kiện/nhân vật/tổ chức THẬT trong bài, nhưng xuyên tạc ĐỘNG CƠ hoặc kết quả.
2. Thêm các cụm từ điển hình: "sự thật đằng sau", "bưng bít thông tin", "che giấu", "thực chất là để trục lợi"

## Yêu cầu Output:
Viết 1 câu hỏi kiểm chứng 150-250 từ bằng tiếng Việt (như một người dân lo ngại hỏi).
Bắt đầu bằng: "Tôi nghe/đọc thấy thông tin rằng..."
Kết thúc bằng: "Xin xác minh thông tin này THẬT hay GIẢ."

CHỈ TRẢ VỀ CÂU HỎI. KHÔNG GIẢI THÍCH."""

levels = [1]*5 + [2]*6 + [3]*5
random.shuffle(levels)

LEVEL_DESC = {
    1: "CẤP 1 (DỄ): Xuyên tạc trắng trợn, kích động mạnh.",
    2: "CẤP 2 (TRUNG BÌNH): Lồng ghép thận trọng 70% thật + 30% giả.",
    3: "CẤP 3 (KHÓ): Xuyên tạc rất tinh vi, thay đổi đúng 1 chi tiết quan trọng nhất.",
}

new_rows = []
next_idx = current_len + 1

for i, pos_row in enumerate(tqdm(pos_subset, desc="Mutating")):
    title = pos_row.get("title", "")
    question = pos_row.get("question", "")
    link = pos_row.get("Link bài viết", "")
    level = levels[i] if i < len(levels) else 2
    
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": MUTATION_PROMPT},
                {"role": "user", "content": (
                    f"{LEVEL_DESC[level]}\n\n"
                    f"BÀI TIN THẬT:\n"
                    f"Tiêu đề: {title}\n"
                    f"Nội dung: {question[:3000]}\n\n"
                    f"Hãy biến thành tin GIẢ xuyên tạc và viết câu hỏi kiểm chứng (150-250 từ)."
                )},
            ],
            max_tokens=800,
            temperature=0.8,
        )
        mutated_q = resp.choices[0].message.content.strip()
        if mutated_q.startswith('"') and mutated_q.endswith('"'):
            mutated_q = mutated_q[1:-1].strip()
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        continue
    
    new_row = {fn: "" for fn in fieldnames}
    new_row.update({
        "index": next_idx,
        "title": title,
        "question": mutated_q,
        "Link bài viết": "",
        "Link bài gốc": link,
        "label": "GIẢ",
        "mutation_level": level,
    })
    new_rows.append(new_row)
    next_idx += 1
    time.sleep(0.3)

if new_rows:
    try:
        with open(NEGATIVE_FILE, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerows(new_rows)
        print(f"\n✅ Đã ghép xong {len(new_rows)} bài vào file! Đạt mốc 100 mẫu.")
    except Exception as e:
        print(f"Lỗi ghi file: {e}")
