@echo off
:: DD1 Workshop Tools — Build Script
:: Python ve pip kurulu olmalıdır.

setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo   DD1 Workshop Tools - Build Script
echo ============================================
echo.

:: Bağımlılıkları kur
echo [1/3] Bagimliliklar kuruluyor...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/3] EXE derleniyor...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "DD1_Workshop_Tools" ^
    --add-data "ui_interface.py;." ^
    --add-data "ai_module.py;." ^
    --add-data "vector_module.py;." ^
    --hidden-import PyQt6.QtSvgWidgets ^
    --hidden-import PyQt6.QtSvg ^
    --hidden-import vtracer ^
    --hidden-import ezdxf ^
    --hidden-import cv2 ^
    --hidden-import PIL ^
    main_app.py

echo.
echo [3/3] Tamamlandi!
echo.
echo Cikti: dist\DD1_Workshop_Tools.exe
echo.
pause
