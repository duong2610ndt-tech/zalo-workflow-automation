"""
Zalo Auto Messenger Entry Point
Khởi chạy giao diện đồ họa (GUI) mặc định, hoặc chế độ dòng lệnh (CLI).
"""

import sys
import os

# Thêm thư mục hiện tại vào sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import engine

if __name__ == "__main__":
    if "--cli" in sys.argv:
        print("🚀 Khởi chạy ở chế độ Dòng lệnh (CLI)...")
        worker = engine.ZaloAutoWorker()
        worker.start()
        try:
            while worker.is_running():
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            worker.stop()
            print("\n🛑 Đã dừng theo yêu cầu người dùng.")
    else:
        # Chạy giao diện đồ họa GUI
        from app import ZaloAutoApp
        app = ZaloAutoApp()
        app.mainloop()