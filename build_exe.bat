@echo off
CHCP 65001 > NUL
title بناء البرنامج كملف تنفيذي (GUI)

echo --------------------------------------------------
echo جاري تثبيت PyInstaller والمكتبات اللازمة...
echo --------------------------------------------------
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo.
echo --------------------------------------------------
echo جاري تحويل البرنامج إلى ملف تنفيذي (exe)...
echo --------------------------------------------------
pyinstaller --noconfirm --onedir --windowed --name "TelegramUploader" --icon NONE ^
  gui.py

if %errorlevel% neq 0 (
    echo [X] حدث خطأ أثناء البناء.
) else (
    echo [V] تم بناء البرنامج بنجاح.
    echo يمكنك العثور على البرنامج في مجلد dist/TelegramUploader
)

echo.
pause
