import pandas as pd
import sys
import os
import time
import gc

# Thêm đường dẫn backend vào bộ nhớ để import các module
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.append(backend_path)

# Import từ workflow - Dùng bản không cache để đảm bảo quét lại thực tế
from graph.workflow import run_verification

INPUT_FILE = "e:/Research/Code/NCKH/Multi-Agentic/Evaluation/eval-true-results.csv"
OUTPUT_FILE = "e:/Research/Code/NCKH/Multi-Agentic/Evaluation/eval-results-PHUC-NCKH.csv"

def run_eval():
    print("\n" + "="*50)
    print("🚀 MULTI-LLM EVALUATION SYSTEM - SAFE MODE")
    print("="*50)
    
    # 1. Đọc dữ liệu ban đầu
    if os.path.exists(OUTPUT_FILE):
        df = pd.read_csv(OUTPUT_FILE)
        print(f"🔄 Đang tiếp tục từ file đã có: {OUTPUT_FILE}")
    else:
        df = pd.read_csv(INPUT_FILE)
        # Fix: Đôi khi file CSV ban đầu chưa có đủ cột
        cols_to_ensure = ['Decision', 'label_module', 'AC_1', 'link_paper_1', 'AC_2', 'link_paper_2', 'AC_3', 'link_paper_3']
        for col in cols_to_ensure:
            if col not in df.columns:
                df[col] = None
        print(f"📄 Bắt đầu mới từ dữ liệu gốc.")

    total = len(df)
    processed_this_session = 0

    # 2. Vòng lặp xử lý từng dòng
    for i in range(0, total):
        # Bỏ qua dòng 1 (vị trí 0) vì là dòng mẫu của user
        if i == 0:
            continue
            
        # Kiểm tra nếu dòng này đã được xử lý (tránh chạy đè trừ khi anh xóa nội dung)
        if not pd.isna(df.loc[i, 'label_module']) and str(df.loc[i, 'label_module']).strip() != "":
            continue

        question = str(df.loc[i, 'question'])
        print(f"\n👉 [{i+1}/{total}] Đang xử lý claim...")
        print(f"   Nội dung: {question[:120]}...")
        
        start_time = time.time()
        try:
            # GỌI PIPELINE CHÍNH
            # Hàm này sẽ chạy qua 3 Agent sử dụng 3 LLM khác nhau (Groq, Gemini, HF)
            result_state = run_verification(question)
            verdict = result_state.get("verdict", {})
            
            # Ghi dữ liệu vào DataFrame
            df.loc[i, 'Decision'] = verdict.get('summary', '')
            df.loc[i, 'label_module'] = verdict.get('verdict', 'CHƯA XÁC ĐỊNH')
            
            # Phân bổ luận điểm (Mỗi claim thường có 2-3 AC)
            args = verdict.get('arguments', [])
            for j in range(1, 4):
                if len(args) >= j:
                    content = args[j-1].get('content', '')
                    url = args[j-1].get('source_url', '')
                    df.loc[i, f'AC_{j}'] = content
                    df.loc[i, f'link_paper_{j}'] = url
            
            # 3. LƯU CHECKPOINT NGAY LẬP TỨC (Rất an toàn)
            df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
            
            duration = time.time() - start_time
            print(f"✅ THÀNH CÔNG: [{verdict.get('verdict')}] trong {duration:.1f} giây.")
            
            processed_this_session += 1
            
            # Giải phóng bộ nhớ tạm thời của Python
            gc.collect()
            
            # Nghỉ 1.5s để hệ thống ổn định và tránh bị các API khóa do request quá nhanh
            time.sleep(1.5)

        except KeyboardInterrupt:
            print("\n⚠️ Đang dừng theo yêu cầu người dùng...")
            break
        except Exception as e:
            print(f"❌ LỖI tại dòng {i+1}: {str(e)}")
            # Tự động lưu lỗi vào file để có thể xem lại sau
            df.loc[i, 'label_module'] = f"ERROR: {str(e)[:40]}..."
            df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
            # Nghỉ lâu hơn nếu bị lỗi (thường là lỗi mạng hoặc API limit)
            time.sleep(10)
            continue

    print("\n" + "="*50)
    print(f"🏆 KẾT THÚC: Đã xử lý {processed_this_session} mẫu tin mới.")
    print(f"📂 Kết quả được lưu tại: {OUTPUT_FILE}")
    print("="*50)

if __name__ == "__main__":
    run_eval()
