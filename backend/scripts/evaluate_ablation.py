"""
Script Đánh giá Độc lập (Standalone Evaluation).
Script này chạy TÁCH BIỆT hoàn toàn với Core Project, không làm ảnh hưởng đến code chính.
Mục tiêu: So sánh Cấu hình Single-Agent (Dùng 1 LLM) vs Multi-Agent (Hệ thống của bạn).
"""

import time
import pandas as pd
import json
import os
import sys

# Đảm bảo import được các module từ thư mục gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import get_llm_for_agent
from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore[import-untyped]
from graph.workflow import create_workflow

# ==========================================
# CẤU HÌNH 1.A: SINGLE-AGENT BASELINE
# Một LLM ôm đồm rác: Tự search, tự đọc, tự phán
# ==========================================
def run_single_agent_baseline(claim: str):
    """
    Giả lập một LLM làm duy nhất mọi việc.
    Để công bằng, ta lấy nội dung từ Web Search (cào đại 3 bài báo)
    nhúng thẳng vào prompt cho LLM.
    """
    start_time = time.time()
    
    # 1. Khởi tạo con LLM (Dùng Groq cho nhanh)
    llm = get_llm_for_agent("AGENT1") 
    
    # 2. Dùng WebSearch lấy tài liệu (tượng trưng)
    from tools.web_search import web_search
    results = web_search.invoke({"query": claim})
    raw_context = json.dumps(results[:3], ensure_ascii=False)
    
    system_prompt = "Bạn là một AI kiểm chứng tin giả. Hãy đọc context và đưa ra phán quyết THẬT hay GIẢ chứa trong field `verdict` của JSON."
    user_prompt = f"Claim: {claim}\nContext: {raw_context}\nTrả về JSON có field 'verdict' là THẬT hoặc GIẢ."
    
    try:
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        result_text = str(response.content)
        if "THẬT" in result_text:
            verdict = "THẬT"
        elif "GIẢ" in result_text:
            verdict = "GIẢ"
        else:
            verdict = "CHƯA XÁC ĐỊNH"
    except Exception as e:
        verdict = f"ERROR: Rate Limit"
        
    latency = time.time() - start_time
    return verdict, latency


# ==========================================
# CẤU HÌNH 1.C: MULTI-AGENT MIX-LLM (YOUR SYSTEM)
# Chạy qua luồng LangGraph hoàn chỉnh
# ==========================================
def run_multi_agent_mix(claim: str):
    start_time = time.time()
    
    # Khởi tạo Graph Của bạn
    app = create_workflow()
    
    # Bơm Data
    initial_state = {
        "user_input": claim,
        "agent_logs": [],
    }
    
    try:
        # Chạy pipeline (không stream)
        final_state = app.invoke(initial_state)
        verdict_dict = final_state.get("verdict", {})
        verdict = verdict_dict.get("verdict", "CHƯA XÁC ĐỊNH")
    except Exception as e:
        verdict = f"ERROR"
        
    latency = time.time() - start_time
    return verdict, latency


if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    csv_path = os.path.join(base_dir, "data", "evaluation_sample.csv")
    out_path = os.path.join(base_dir, "data", "ablation_results.csv")
    
    if not os.path.exists(csv_path):
        print(f"File {csv_path} không tồn tại.")
        sys.exit(1)
        
    df = pd.read_csv(csv_path)
    
    results = []
    
    print("🚀 BẮT ĐẦU CHẠY ĐÁNH GIÁ (ABLATION STUDY)...\n")
    
    for _, row in df.iterrows():
        claim = row['claim']
        truth = row['ground_truth']
        
        print(f"🔄 Đang test câu: {claim[:50]}...")
        
        # Test A: Single Agent
        verd_a, time_a = run_single_agent_baseline(claim)
        
        # Test C: Multi Agent
        verd_c, time_c = run_multi_agent_mix(claim)
        
        results.append({
            "Claim": claim,
            "Ground_Truth": truth,
            "Single_Agent_Verdict": verd_a,
            "Single_Agent_Time(s)": round(time_a, 2),
            "Multi_Agent_Verdict": verd_c,
            "Multi_Agent_Time(s)": round(time_c, 2)
        })
        
    # Lưu kết quả
    out_df = pd.DataFrame(results)
    out_df.to_csv(out_path, index=False)
    
    print(f"\n✅ ĐÁNH GIÁ THÀNH CÔNG! Đã lưu kết quả tại {out_path}")
