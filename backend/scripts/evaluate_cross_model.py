"""
Script Đánh giá Độc lập: Cross-Model Benchmarking (Ma trận 9 kết hợp).
Mục tiêu: Đổi lõi LLM của Agent 2 (3 model) và Agent 3 (3 model) để chấm điểm F1 và Runtime.
"""

import time
import pandas as pd
import json
import os
import sys

# Đảm bảo import được các module từ thư mục gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph.workflow import create_workflow

# ==========================================
# KHAI BÁO CÁC ỨNG VIÊN MODELS
# ==========================================
# Agent 1 (Query) luôn cố định là Groq (Nhanh, Rẻ)
os.environ["AGENT1_BASE_URL"] = "https://api.groq.com/openai/v1"
os.environ["AGENT1_MODEL"] = "llama-3.1-8b-instant"
# AGENT1_API_KEY lấy thẳng từ .env

AGENT2_CANDIDATES = [
    {
        "name": "Gemini-2.0-Flash", 
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", 
        "model": "gemini-2.0-flash", 
        "key_env_source": "AGENT2_API_KEY" # Lấy key Gemini từ .env
    },
    {
        "name": "Mixtral-8x7B", 
        "base_url": "https://api.groq.com/openai/v1", 
        "model": "mixtral-8x7b-32768", 
        "key_env_source": "AGENT1_API_KEY" # Lấy key Groq tái sử dụng
    },
    {
        "name": "Llama-3.3-70B", 
        "base_url": "https://api.groq.com/openai/v1", 
        "model": "llama-3.3-70b-versatile", 
        "key_env_source": "AGENT1_API_KEY" # Lấy key Groq tái sử dụng
    }
]

AGENT3_CANDIDATES = [
    {
        "name": "Qwen-72B", 
        "base_url": "https://api-inference.huggingface.co/v1/", 
        "model": "Qwen/Qwen2.5-72B-Instruct", 
        "key_env_source": "AGENT3_API_KEY" # Lấy key HF
    },
    {
        "name": "DeepSeek-R1", 
        "base_url": "https://api.groq.com/openai/v1", 
        "model": "deepseek-r1-distill-llama-70b", 
        "key_env_source": "AGENT1_API_KEY" # Lấy key Groq
    },
    {
        "name": "Llama-3.3-70B", 
        "base_url": "https://api.groq.com/openai/v1", 
        "model": "llama-3.3-70b-versatile", 
        "key_env_source": "AGENT1_API_KEY" # Lấy key Groq
    }
]

def run_evaluation():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    csv_path = os.path.join(base_dir, "data", "evaluation_sample.csv")
    out_path = os.path.join(base_dir, "data", "cross_model_results.csv")
    
    if not os.path.exists(csv_path):
        print(f"File {csv_path} không tồn tại.")
        sys.exit(1)
        
    df = pd.read_csv(csv_path)
    # Rút gọn lấy 3 câu test nhanh (do 9x3 = 27 lượt gọi LLM mất khá nhiều thời gian/tiền)
    df = df.head(3) 

    results = []
    
    from dotenv import load_dotenv
    load_dotenv(os.path.join(base_dir, ".env"))

    # Bắt đầu vòng lặp ma trận 3x3 = 9 cấu hình
    config_id = 1
    for a2 in AGENT2_CANDIDATES:
        for a3 in AGENT3_CANDIDATES:
            # Ghi đè biến môi trường để get_llm_for_agent đọc cấu hình mới
            os.environ["AGENT2_BASE_URL"] = a2["base_url"]
            os.environ["AGENT2_MODEL"] = a2["model"]
            os.environ["AGENT2_API_KEY"] = os.getenv(a2["key_env_source"], "")
            
            os.environ["AGENT3_BASE_URL"] = a3["base_url"]
            os.environ["AGENT3_MODEL"] = a3["model"]
            os.environ["AGENT3_API_KEY"] = os.getenv(a3["key_env_source"], "")
            
            combo_name = f"{a2['name']} + {a3['name']}"
            print(f"\n==============================================")
            print(f"BẮT ĐẦU TEST CẤU HÌNH {config_id}/9: {combo_name}")
            print(f"==============================================")
            
            # Khởi tạo Graph với bộ đôi mới
            try:
                app = create_workflow()
            except Exception as e:
                print(f"Lỗi khởi tạo mô hình: {e}")
                continue

            for _, row in df.iterrows():
                claim = row['claim']
                truth = row['ground_truth']
                
                print(f"  - Đang chạy câu: {claim[:30]}...")
                start_time = time.time()
                initial_state = {"user_input": claim, "agent_logs": []}
                
                try:
                    final_state = app.invoke(initial_state)
                    verdict = final_state.get("verdict", {}).get("verdict", "CHƯA XÁC ĐỊNH")
                except Exception as e:
                    verdict = f"ERROR: Rate Limit/Crash"
                    
                latency = time.time() - start_time
                
                results.append({
                    "Config_ID": config_id,
                    "Agent2_Model": a2["name"],
                    "Agent3_Model": a3["name"],
                    "Claim": claim,
                    "Ground_Truth": truth,
                    "Output_Verdict": verdict,
                    "Latency(s)": round(latency, 2)
                })
                # Nghỉ 5 giây để tránh bị văng Rate Limit
                time.sleep(5)
                
            config_id += 1
            
            # Thường xuyên lưu tạm phòng khi đứt kết nối
            out_df = pd.DataFrame(results)
            out_df.to_csv(out_path, index=False)

    print(f"\n✅ HOÀN THÀNH TEST MA TRẬN 9 MÔ HÌNH! Đã lưu kết quả tại {out_path}")

if __name__ == "__main__":
    run_evaluation()
