#!/usr/bin/env python3
# start_app.py - Cross-platform REA Application Orchestrator & PID Manager
import os
import sys
import time
import subprocess
import urllib.request
import atexit

PORT = 8000
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_SCRIPT = os.path.join(BACKEND_DIR, "app", "launcher.py")

backend_proc = None

def cleanup():
    global backend_proc
    if backend_proc and backend_proc.poll() is None:
        print("[*] Đang đóng tiến trình Backend (PID: %d)..." % backend_proc.pid)
        try:
            backend_proc.terminate()
            backend_proc.wait(timeout=3)
        except Exception:
            backend_proc.kill()
        print("[✓] Backend đã được giải phóng.")

atexit.register(cleanup)

def check_backend_alive(port, timeout=12):
    start = time.time()
    url = f"http://127.0.0.1:{port}/health/live"
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status in (200, 301, 302, 303, 404):
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    global backend_proc
    print("=" * 65)
    print("      REA APPLICATION ORCHESTRATOR & RUNTIME LAUNCHER")
    print("=" * 65)

    # 1. Tự động kiểm tra file .env
    env_example = os.path.join(BACKEND_DIR, ".env.example")
    env_file = os.path.join(BACKEND_DIR, ".env")
    if os.path.exists(env_example) and not os.path.exists(env_file):
        print("[*] Đang tự động nạp cấu hình từ .env.example sang .env...")
        with open(env_example, "r", encoding="utf-8") as f_in, open(env_file, "w", encoding="utf-8") as f_out:
            f_out.write(f_in.read())

    # 2. Khởi chạy Backend
    b_cmd = [sys.executable, "-m", "app.launcher"]
    print(f"[*] Khởi chạy iNew Launcher trên cổng {PORT}...")
    backend_proc = subprocess.Popen(b_cmd, cwd=BACKEND_DIR)

    # 3. Chờ Backend sẵn sàng
    print(f"[*] Đang thẩm định trạng thái cổng {PORT}...")
    if check_backend_alive(PORT, timeout=12):
        print(f"[✓] Backend đã kích hoạt thành công trên http://127.0.0.1:{PORT}!")
    else:
        print(f"[!] Cảnh báo: Backend chưa phản hồi sau 12s, vẫn tiến hành theo dõi tiến trình.")

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        pass

    print("[*] Phiên làm việc kết thúc.")

if __name__ == "__main__":
    main()
