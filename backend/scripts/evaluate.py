"""
Script đánh giá tự động hệ thống SMART-FC (Multi-Agentic RAG).
Chạy toàn bộ dataset qua hệ thống, so sánh với nhãn gốc (ground_truth),
và tính toán các chỉ số phân loại (Classification Metrics).
"""

import time
import pandas as pd
import json
import os
import sys

# Đảm bảo import được các module từ thư mục gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph.workflow import run_verification_with_cache as run_verification

try:
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ Cảnh báo: Không tìm thấy thư viện scikit-learn. Đang chuyển sang tính điểm thủ công...")

def evaluate_claim(claim: str):
    """
    Chạy hệ thống kiểm chứng cho một claim.
    """
    start_time = time.time()
    try:
        final_state = run_verification(claim)
        
        # Trích xuất kết quả
        verdict_data = final_state.get("verdict", {})
        verdict = verdict_data.get("verdict", "CHƯA XÁC ĐỊNH")
        confidence = verdict_data.get("confidence_score", 0.0)
        from_cache = final_state.get("from_cache", False)

        # Chẩn hóa nhãn (uppercase)
        verdict = verdict.strip().upper()
        if "THẬT" in verdict:
            verdict = "THẬT"
        elif "GIẢ" in verdict:
            verdict = "GIẢ"
        else:
            verdict = "CHƯA XÁC ĐỊNH"

    except Exception as e:
        verdict = "ERROR"
        confidence = 0.0
        from_cache = False
        print(f"❌ Lỗi khi xử lý claim: {claim}\nChi tiết: {e}")

    latency = time.time() - start_time
    return verdict, confidence, latency, from_cache


if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    csv_path = os.path.join(base_dir, "data", "evaluation_sample.csv")
    out_path = os.path.join(base_dir, "data", "eval_results.csv")
    
    if not os.path.exists(csv_path):
        print(f"❌ File dữ liệu {csv_path} không tồn tại!")
        print("Vui lòng tạo file CSV gồm các cột: id, claim, ground_truth")
        sys.exit(1)
        
    df = pd.read_csv(csv_path)
    
    # Kiểm tra cột bắt buộc
    required_columns = {'claim', 'ground_truth'}
    if not required_columns.issubset(df.columns):
        print(f"❌ File CSV phải có các cột: {required_columns}")
        sys.exit(1)

    print(f"🚀 BẮT ĐẦU ĐÁNH GIÁ HỆ THỐNG SMART-FC ({len(df)} mẫu)...\n")
    
    results = []
    
    for index, row in df.iterrows():
        claim = row['claim']
        ground_truth = str(row['ground_truth']).strip().upper()
        
        print(f"🔄 [{index+1}/{len(df)}] Đang test: {claim[:50]}...")
        
        pred_verdict, confidence, latency, from_cache = evaluate_claim(claim)
        
        is_correct = (pred_verdict == ground_truth)
        
        results.append({
            "id": row.get('id', index + 1),
            "claim": claim,
            "ground_truth": ground_truth,
            "predicted_verdict": pred_verdict,
            "confidence_score": confidence,
            "is_correct": is_correct,
            "latency_secs": round(latency, 2),
            "cache_hit": from_cache
        })
        
    print("\n✅ HOÀN THÀNH QUÁ TRÌNH TEST!")
    
    # Lưu kết quả
    out_df = pd.DataFrame(results)
    out_df.to_csv(out_path, index=False)
    print(f"💾 Đã lưu file kết quả chi tiết tại: {out_path}\n")

    # Tính toán Metrics
    print("📋 BẢNG TÓM TẮT ĐÁNH GIÁ (EVALUATION METRICS):")
    print("-" * 50)
    
    y_true = out_df['ground_truth'].tolist()
    y_pred = out_df['predicted_verdict'].tolist()
    
    # Lọc ra những case ERROR để bóc tách khỏi metrics
    valid_indices = [i for i, v in enumerate(y_pred) if v != "ERROR"]
    y_true_valid = [y_true[i] for i in valid_indices]
    y_pred_valid = [y_pred[i] for i in valid_indices]

    total = len(y_true)
    errors = total - len(valid_indices)
    corrects = sum([1 for i in range(len(y_true_valid)) if y_true_valid[i] == y_pred_valid[i]])
    
    avg_latency = out_df['latency_secs'].mean()
    cache_hits = out_df['cache_hit'].sum()
    
    print(f"Tổng số mẫu: {total}")
    print(f"Xử lý lỗi (API/Timeout): {errors}")
    print(f"Truy xuất từ Cache (Hit): {cache_hits}")
    print(f"Thời gian phản hồi TB: {avg_latency:.2f}s")
    print(f"Đoán đúng: {corrects}/{len(valid_indices)}")
    
    if len(valid_indices) > 0:
        if SKLEARN_AVAILABLE:
            print("\n" + classification_report(y_true_valid, y_pred_valid, zero_division=0))
            
            print("\nConfusion Matrix:")
            labels = list(set(y_true_valid + y_pred_valid))
            cm = confusion_matrix(y_true_valid, y_pred_valid, labels=labels)
            cm_df = pd.DataFrame(cm, index=[f"True_{l}" for l in labels], columns=[f"Pred_{l}" for l in labels])
            print(cm_df.to_string())
        else:
            acc = corrects / len(valid_indices)
            print(f"\nAccuracy (Thủ công): {acc:.2%}")
    print("-" * 50)
