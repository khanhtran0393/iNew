@echo off
chcp 65001 >nul
title Khởi Chạy Bản Tái Tạo - iNew
echo ======================================================================
echo    KHỞI CHẠY ỨNG DỤNG MỚI TÁI TẠO (REBUILT EXECUTABLE)
echo ======================================================================
echo.
echo [*] Đang khởi chạy tệp thực thi: iNew_Rebuilt.exe
cd /d "%~dp0"
start "" "iNew_Rebuilt.exe"
