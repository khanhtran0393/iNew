@echo off
chcp 65001 >nul
title iNew - Hệ Thống Tin Tức Đa Nền Tảng
cd /d "%~dp0"

echo ==========================================================
echo   iNew - Hệ Thống Tin Tức Đa Nền Tảng (Reconstructed)
echo ==========================================================
echo.
echo [*] Đang khởi động iNew...
python start_app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [-] Khởi động thất bại. Hãy đảm bảo bạn đã cài đặt Python và chạy:
    echo     pip install -r requirements.txt
    pause
)
