@echo off
chcp 65001 >nul
echo ========================================
echo Building Windows Notification Client (OPTIMIZED)
echo ========================================
echo.

REM Check for Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python first
    pause
    exit /b 1
)

REM Clean old builds
echo [1/5] Cleaning old builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
echo Done.

echo.
echo [2/5] Installing dependencies (optimized)...
pip install -r requirements-optimized.txt -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo Done.

echo.
echo [3/5] Installing PyInstaller and UPX...
pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)
echo Done.

echo.
echo [4/5] Building executable (optimized)...
pyinstaller --clean NotificationClient-optimized.spec

if not exist "dist\NotificationClient.exe" (
    echo.
    echo [ERROR] Build failed! EXE not found
    pause
    exit /b 1
)
echo Done.

echo.
echo [5/5] Signing EXE...
if exist "sign.bat" (
    if exist "signing-cert.pfx" (
        call sign.bat
    ) else (
        echo [SKIP] No certificate found: signing-cert.pfx
        echo See SIGNING_GUIDE.md for details
    )
) else (
    echo [SKIP] No sign script found
)

echo.
echo ========================================
echo Build SUCCESS! (OPTIMIZED)
echo.

REM Show file size
for %%I in (dist\NotificationClient.exe) do (
    set SIZE=%%~zI
    set /a SIZE_MB=!SIZE!/1048576
    echo File size: !SIZE_MB! MB
)

echo.
echo Output files:
echo   - dist\NotificationClient.exe     [Main EXE]
echo   - start_with_watchdog.bat         [Auto-restart launcher]
echo   - watchdog.py                     [Python watchdog script]
echo ========================================
echo.
echo Optimizations applied:
echo   [X] Removed EasyOCR/pytesseract
echo   [X] Excluded unused modules
echo   [X] UPX compression enabled
echo   [X] Debug symbols stripped
echo   [X] Bytecode optimization
echo.
echo Features enabled:
echo   [X] Silent mode (no window on startup)
echo   [X] System tray support
echo   [X] Auto-reconnect on disconnect
echo   [X] Auto-start with Windows (configurable in settings)
echo   [X] Click close button to minimize to tray
echo   [X] Wework call monitoring with multiple screenshot methods
echo.
echo Usage:
echo   - Run dist\NotificationClient.exe directly
echo   - Or use start_with_watchdog.bat for auto-restart
echo   - Or use watchdog.py for detailed monitoring
echo.
echo Note: First run may trigger SmartScreen warning
echo       Reference SIGNING_GUIDE.md for code signing
echo.
pause
