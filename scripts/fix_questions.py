"""
Script chạy lại việc gen câu hỏi cho Index 83 và 90.
Sử dụng GPT-4o-mini với prompt được tối ưu hóa.
"""

import os
import csv
import sys
import time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# 1. Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
load_dotenv(BACKEND_DIR / ".env")

CRAWL_FILE = BASE_DIR / "Evaluation" / "vnexpress_crawled.csv"
EVAL_FILE = BASE_DIR / "Evaluation" / "eval-questions-generated.csv"

# 2. Config OpenAI
OPENAI_API_KEY = os.getenv("AGENT3_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """Bạn là chuyên gia Fact-checker cao cấp. 
Nhiệm vụ: Chuyển đổi nội dung tin tức thành một câu hỏi kiểm chứng có ĐỘ CHI TIẾT CỰC CAO (180-280 từ).
- Luôn giữ lại tên người, chức vụ, con số, địa điểm, thời gian chính xác.
- Câu hỏi phải mang tính nghi vấn, yêu cầu xác minh sự thật.
- Chỉ trả về duy nhất nội dung đoạn văn, không tiêu đề, không lời dẫn."""

def generate_better_question(title, content):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Title: {title}\nContent: {content}\n\nHãy tạo câu hỏi kiểm chứng chi tiết."}
            ],
            temperature=0.8
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Lỗi khi gọi GPT: {e}")
        return None

def main():
    # Đọc dữ liệu gốc để lấy content của 5 và 12
    # Lưu ý: Index 5 của crawled -> 83 của Eval, Index 12 của crawled -> 90 của Eval
    content_map = {}
    with open(CRAWL_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["index"] in ["5", "12"]:
                content_map[row["index"]] = row

    if "5" not in content_map or "12" not in content_map:
        print("❌ Không tìm thấy article 5 hoặc 12 trong vnexpress_crawled.csv")
        return

    # Sinh câu hỏi mới
    print("🔄 Đang sinh câu hỏi mới cho index 83 (Policy)...")
    q83 = generate_better_question(content_map["5"]["title"], content_map["5"]["nội dung"])
    
    print("🔄 Đang sinh câu hỏi mới cho index 90 (Fire)...")
    q90 = generate_better_question(content_map["12"]["title"], content_map["12"]["nội dung"])

    if not q83 or not q90:
        print("❌ Lỗi sinh câu hỏi.")
        return

    # Đọc file Eval và cập nhật
    rows = []
    with open(EVAL_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row["index"] == "83":
                row["question"] = q83
                # Reset luôn kết quả cũ nếu có để Runner chạy lại
                for k in ["Decision", "output_1", "link_1", "output_2", "link_2", "output_3", "link_3", "label_model"]:
                    if k in row: row[k] = ""
                print("✅ Cập nhật Index 83")
            elif row["index"] == "90":
                row["question"] = q90
                for k in ["Decision", "output_1", "link_1", "output_2", "link_2", "output_3", "link_3", "label_model"]:
                    if k in row: row[k] = ""
                print("✅ Cập nhật Index 90")
            rows.append(row)

    # Ghi lại file
    with open(EVAL_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("🎉 Hoàn thành cập nhật!")

if __name__ == "__main__":
    main()
