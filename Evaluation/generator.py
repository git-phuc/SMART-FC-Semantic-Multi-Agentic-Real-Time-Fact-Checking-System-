import csv
import os
import time
import re
from huggingface_hub import InferenceClient
from tqdm import tqdm

# Configuration: Optimized for Fact-Checking Research
# google/gemma-2-9b-it is free, stable and great for Vietnamese reasoning.
MODEL_ID = "google/gemma-2-9b-it"

KEYS_FILE = "e:/Research/Code/NCKH/Evaluation/hf"
INPUT_FILE = "e:/Research/Code/NCKH/Evaluation/dataset.csv"
# USING A NEW FILENAME TO AVOID PERMISSION ERRORS AND START FRESH
OUTPUT_FILE = "e:/Research/Code/NCKH/Evaluation/dataset_fact_check.csv"

def get_clean_keys(file_path):
    keys = []
    if not os.path.exists(file_path):
        return keys
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            match = re.search(r'(hf_[a-zA-Z0-9]+)', line)
            if match:
                keys.append(match.group(1))
    return keys

KEYS = get_clean_keys(KEYS_FILE)

def generate_fact_check_question(client, content):
    system_prompt = """
<role>
Bạn là chuyên gia phân tích và xác minh tin tức (Fact-checker) lão luyện. 
</role>
<context>
Bạn đang xây dựng một bộ dữ liệu kiểm thử (Evaluation Dataset) để đánh giá khả năng nhận diện tin giả của một hệ thống AI khác. 
Nhiệm vụ: Chuyển đổi mẩu tin được cung cấp thành một CÂU HỎI thảo luận mang tính chất "thử thách xác minh" (Fact-checking Challenge).
</context>
<constraints>
1. Trả về DUY NHẤT một câu hỏi dài hoàn chỉnh (từ 100-200 từ).
2. Câu hỏi PHẢI mô tả cụ thể các chi tiết từ tin tức (như tên người, địa danh, thời gian, sự kiện) để người trả lời có đầy đủ dữ kiện để đối soát.
3. Câu hỏi CẦN được đặt dưới góc nhìn của một người đang tìm hiểu sự thật, bày tỏ sự nghi ngờ về tính xác thực của thông tin này và yêu cầu hệ thống AI phải phân tích các nguồn tin, đối chiếu bối cảnh để kết luận đây là "TIN THẬT" hay "TIN GIẢ".
4. Ngôn ngữ: Tiếng Việt chuẩn mực, chuyên nghiệp.
5. Tuyệt đối KHÔNG có lời dẫn (không: "Dưới đây là...", "Câu hỏi là..."). Chỉ trả về lời văn của câu hỏi.
</constraints>
"""
    
    user_prompt = f"""
<news_content>
{content[:4000]}
</news_content>
<task>
Sử dụng nội dung trong <news_content> để viết một câu hỏi dài khoảng 150 từ nhằm yêu cầu một hệ thống AI khác tiến hành xác minh tính đúng sai của thông tin này. Hãy lồng ghép các chi tiết cụ thể để làm tăng độ khó cho quá trình xác minh.
</task>
"""

    try:
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=600,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        if "503" in str(e) or "overloaded" in str(e).lower():
            time.sleep(10)
        return None

def main():
    if not os.path.exists(INPUT_FILE):
        return

    # Fresh start or resume for the NEW file
    processed_indices = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            processed_indices = {row['index'] for row in reader}

    with open(INPUT_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    rows_to_process = [row for row in all_rows if row['index'] not in processed_indices]
    print(f"Total samples to process with Fact-Checking prompt: {len(rows_to_process)}")

    mode = 'a' if os.path.exists(OUTPUT_FILE) else 'w'
    key_idx = 0

    with open(OUTPUT_FILE, mode, newline='', encoding='utf-8-sig') as f:
        # User requested to keep all original columns and only update 'question'
        # Original columns: index, title, nội dung, Link bài viết, label
        # The 'nội dung' in input maps to 'original_content' in my logic? 
        # Actually the user said "chỉ cần sửa lại cột question thôi các cột khác giữ nguyên". 
        # So I will map input columns exactly.
        fieldnames = ["index", "title", "nội dung", "Link bài viết", "label", "question"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == 'w':
            writer.writeheader()
        
        for row in tqdm(rows_to_process):
            content = row.get("nội dung", "")
            if len(content) < 100:
                continue
                
            question = None
            client = InferenceClient(model=MODEL_ID, token=KEYS[key_idx % len(KEYS)])
            
            # Retry mechanism
            for attempt in range(len(KEYS) * 2):
                client.token = KEYS[key_idx % len(KEYS)]
                question = generate_fact_check_question(client, content)
                if question:
                    break
                else:
                    key_idx += 1
                    time.sleep(3)
            
            if question:
                output_row = row.copy()
                output_row["question"] = question
                writer.writerow(output_row)
                f.flush()
            else:
                print(f"FAILED for index {row['index']}")
            
            time.sleep(1.5)

if __name__ == "__main__":
    main()
