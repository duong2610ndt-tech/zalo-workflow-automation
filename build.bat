@echo off
chcp 65001 >nul
echo ========================================================
echo        DONG GOI ZALO AUTO MESSENGER THANH FILE .EXE
echo ========================================================
echo.

echo [1/3] Kiem tra moi truong Python & PyInstaller...
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Chua cai dat PyInstaller. Dang tien hanh cai dat...
    python -m pip install pyinstaller
)

echo.
echo [2/3] Dang tien hanh build file .exe (Vui long cho 1-2 phut)...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "ZaloAuto" --collect-all customtkinter --collect-all selenium app.py

if %errorlevel% neq 0 (
    echo.
    echo [X] Co loi xay ra trong qua trinh dong goi!
    pause
    exit /b %errorlevel%
)

echo.
echo [3/3] Dang copy file ZaloAuto.exe ra thu muc goc...
if exist "dist\ZaloAuto.exe" (
    copy /y "dist\ZaloAuto.exe" ".\ZaloAuto.exe"
    echo [OK] Da tao thanh cong file ZaloAuto.exe o thu muc hien tai!
)

echo.
echo ========================================================
echo   HOAN TAT! Ban co the chay truc tiep file ZaloAuto.exe
echo ========================================================
pause
