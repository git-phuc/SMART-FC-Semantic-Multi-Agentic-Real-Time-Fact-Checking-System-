import sys
import os

# Thêm đường dẫn backend vào hệ thống
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import logging
from graph.workflow import run_verification_with_cache as run_verification
from utils.logger import get_logger

# Bật log cấp độ DEBUG để thấy luồng chạy chi tiết
logging.getLogger().setLevel(logging.INFO)

input_claim = "Việt Nam chính thức gia nhập tổ chức BRICS vào tháng 1 năm 2024 tại hội nghị thượng đỉnh ở Nam Phi."

print("============== BẮT ĐẦU CHẠY PIPELINE cục bộ ==============")
try:
    result = run_verification(input_claim)
    print("\n============== KẾT QUẢ ==============")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"\n❌ LỖI RỒI: {e}")
    import traceback
    traceback.print_exc()
