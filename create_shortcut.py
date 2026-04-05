import os

desktop_path = r"c:\Users\DDSOUND\Desktop\DD1_GARAJ_BASLAT.bat"

bat_content = """@echo off
chcp 65001 >nul
title DD1 GARAGE - Web Arayuz Baslatici
color 0b

echo ========================================================
echo        DDSOUND GARAJ - MOTORLAR ATESLENIYOR...
echo ========================================================
echo.

echo [1/2] DD1 Backend (Ses Ustasi Zekasi) Baslatiliyor...
cd /d "c:\\Users\\DDSOUND\\Desktop\\exemiz\\dd1_sound"
start cmd /k "title DD1_BACKEND_SERVER && python main.py"

echo Arka plan servislerinin ayaga kalkmasi bekleniyor...
timeout /t 3 /nobreak >nul

echo [2/2] Kuantum Web Arayuzu Aciliyor...
start http://127.0.0.1:9000

echo.
echo Islem tamam! Bu pencereyi kapatabilirsiniz.
timeout /t 2 >nul
exit
"""

with open(desktop_path, "w", encoding="utf-8") as f:
    f.write(bat_content)

print(f"Successfully created shortcut at {desktop_path}")
