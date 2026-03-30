import os
import sys
import time

# Trỏ path để nạp thư viện backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_next_gemini_key, load_dotenv, env_path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

print("Đang test Xoay vòng key Gemini...")
print("================================")

for i in range(4):
    key = get_next_gemini_key()
    if not key:
        print("Không tìm thấy key trong .env!")
        break
        
    print(f"\n[Lần {i+1}] Lấy Key xoay vòng: {key[:15]}... (ẩn bớt để bảo mật)")
    llm = ChatOpenAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        max_tokens=20,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=key
    )
    
    try:
        start = time.time()
        res = llm.invoke([HumanMessage(content="Say the word 'OK' only.")])
        elapsed = time.time() - start
        print(f"✅ Hoạt động tốt! Trả lời mất {elapsed:.1f}s: {res.content.strip()}")
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg:
            print("❌ BỊ RATE LIMIT (429) - Key này đã cạn Quota hoặc Google đang chặn IP!")
            # Trích xuất số giây retry
            import re
            m = re.search(r'retry in (\d+\.?\d*)s', error_msg)
            if m:
                print(f"   -> Lời nhắn của Google: Phải đợi {m.group(1)}s mới thả.")
        else:
            print(f"❌ LỖI KHÁC: {error_msg[:100]}...")
            
    # Chờ 1 giây để sang vòng tiếp
    time.sleep(1)

print("\nKết thúc test.")
