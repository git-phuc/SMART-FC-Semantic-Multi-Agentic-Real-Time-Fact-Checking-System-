import os
from pymongo import MongoClient
from dotenv import load_dotenv

def clean_all():
    load_dotenv(os.path.join('backend', '.env'))
    
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("LỖI: Không tìm thấy MONGODB_URI trong file .env.")
        return
        
    print("Đang kết nối tới MongoDB Atlas...")
    client = MongoClient(mongo_uri)
    db = client["FakeNewsDB"]
    collection = db["CacheLogs"]
    
    count = collection.count_documents({})
    print(f"Tổng số bản ghi hiện có trong DB: {count}")
    
    if count > 0:
        result = collection.delete_many({})
        print(f"✅ Đã xóa toàn bộ {result.deleted_count} bản ghi khỏi Collection CacheLogs.")
    else:
        print("✅ Database đã trống sẵn rồi.")

if __name__ == "__main__":
    clean_all()
