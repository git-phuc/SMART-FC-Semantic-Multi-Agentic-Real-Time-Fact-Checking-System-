"""
Script xóa các bản ghi 'GIẢ' và 'CHƯA XÁC ĐỊNH' khỏi MongoDB Cache.
Dùng để dọn dẹp các cache không mong muốn khi test hệ thống.
"""

import os
import sys
from pathlib import Path
from pymongo import MongoClient
from dotenv import load_dotenv

# 1. Xác định đường dẫn .env
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
ENV_PATH = BACKEND_DIR / ".env"

if not ENV_PATH.exists():
    print(f"❌ Không tìm thấy file .env tại: {ENV_PATH}")
    sys.exit(1)

load_dotenv(ENV_PATH)

# 2. Cấu hình MongoDB
MONGO_URI = os.getenv("MONGODB_URI")
DB_NAME = "FakeNewsDB"
COLLECTION_NAME = "CacheLogs"

if not MONGO_URI:
    print("❌ MONGODB_URI không tồn tại trong .env")
    sys.exit(1)

def main():
    try:
        # Kết nối
        print(f"🔄 Đang kết nối tới MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Danh sách cần xóa
        target_labels = ["GIẢ", "CHƯA XÁC ĐỊNH"]
        
        # Kiểm tra trước
        query = {"full_response.verdict": {"$in": target_labels}}
        count_before = collection.count_documents(query)
        
        if count_before == 0:
            print("✨ Không tìm thấy bản ghi nào cần xóa.")
            return

        print(f"⚠️  Tìm thấy {count_before} bản ghi {target_labels}. Đang dọn dẹp...")
        
        # Thực hiện xóa
        result = collection.delete_many(query)
        
        print(f"✅ Đã xóa thành công {result.deleted_count} bản ghi.")
        print(f"📊 Tổng số bản ghi còn lại trong cache: {collection.count_documents({})}")

    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
