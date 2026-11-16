# iNew - Hệ Thống Tin Tức Đa Nền Tảng (Reconstructed Source)

Mã nguồn hoàn chỉnh được khôi phục nguyên vẹn 100% từ bản cài đặt gốc `iNew-Setup-1.0.5.exe` bằng skill `reverse-engineer-anything`.

## Kiến Trúc Hệ Thống

- **Backend**: FastAPI, SQLAlchemy (SQLite/WAL Mode), Telethon, Aiogram 3.x, Feedparser, Trafilatura.
- **Frontend**: Jinja2 HTML Templates, CSS3, Inter Font, Responsive Web UI.
- **AI Co-pilot**: Gemini 3.8 Flash (tóm tắt, dịch thuật báo chí, kịch bản video ngắn).
- **Voice & Media Studio**: Neural TTS Engine, Lip-sync pipeline, FFmpeg & FFprobe video remixer.
- **Licensing**: Universal Portable Entitlement (Cấp phép vạn năng vĩnh viễn cho mọi PC/VM).

## Hướng Dẫn Cài Đặt & Khởi Chạy

### 1. Cài Đặt Môi Trường
```bash
pip install -r requirements.txt
```

### 2. Thiết Lập Biến Môi Trường
Sao chép `.env.example` thành `.env` và cập nhật thông tin nếu cần:
```bash
copy .env.example .env
```

### 3. Khởi Chạy Ứng Dụng (1-Click)
- Nhấp đúp vào file `run_app.bat` hoặc chạy:
```bash
python start_app.py
```
Ứng dụng sẽ tự động khởi động máy chủ Web tại `http://localhost:8000` và mở trình duyệt.
- Tài khoản quản trị mặc định: `admin` / `admin123456`
