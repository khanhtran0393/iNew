@echo off
chcp 65001 >nul
title Khởi Chạy Ứng Dụng 1-Click - REA Runtime Launcher
echo ======================================================================
echo    KHỞI CHẠY ỨNG DỤNG TÁI CẤU TRÚC (REA 1-CLICK LAUNCHER)
echo ======================================================================
echo.

cd /d "%~dp0"

REM 1. Kiểm tra cấu hình .env
if exist ".\.env.example" (
    if not exist ".\.env" (
        echo [*] Đang tự động sao chép .env.example sang .env...
        copy ".\.env.example" ".\.env" >nul
    )
)

REM 2. Thiết lập môi trường Python venv
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [*] Sử dụng môi trường ảo .venv cục bộ.
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    echo [*] Sử dụng môi trường ảo venv cục bộ.
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
    echo [*] Sử dụng môi trường ảo venv cha.
)

REM 3. Khởi chạy Ứng dụng iNew qua app.launcher
echo [*] Đang khởi chạy iNew Launcher trên cổng 8000...
"%PYTHON_EXE%" -m app.launcher

echo.
echo [*] Ứng dụng đã đóng. Đang dọn dẹp tiến trình backend trên cổng 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo [✓] Đã hoàn tất.
