import csv
import os

def reindex_csv(filepath):
    print(f"Đang xử lý: {filepath}")
    
    # Kiểm tra xem file có tồn tại không
    if not os.path.exists(filepath):
        print("Lỗi: File không tồn tại!")
        return
        
    # Đọc file CSV
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
        
    print(f"Đã đọc {len(rows)} dòng dữ liệu.")
    
    # Đánh lại index từ 1 đến hết
    for i, row in enumerate(rows):
        if 'index' in row:
            row['index'] = i + 1
            
    # Ghi đè lại vào file CSV
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"✅ Đã đánh lại index (1 -> {len(rows)}) và lưu file thành công!\n")

if __name__ == "__main__":
    # Cập nhật index cho cả 2 file để dữ liệu đồng bộ
    CSV_1 = r"E:\Research\Code\NCKH\Multi-Agentic\Evaluation\eval-results-filled.csv"
    CSV_2 = r"E:\Research\Code\NCKH\Multi-Agentic\Evaluation\eval-true-results -- backup.csv"
    
    try:
        reindex_csv(CSV_1)
        reindex_csv(CSV_2)
    except PermissionError:
        print("❌ LỖI: Không thể lưu file vì file đang được mở. Hãy ĐÓNG file trên Excel/VS Code và chạy lại lệnh.")
    except Exception as e:
        print(f"❌ LỖI KHÁC: {e}")
