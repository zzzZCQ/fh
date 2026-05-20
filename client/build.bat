@echo off
chcp 65001 >nul
echo ========================================
echo Building Windows Notification Client
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
if exist "*.spec" del /q "*.spec"
echo Done.

echo.
echo [2/5] Installing dependencies...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo Done.

echo.
echo [3/5] Installing PyInstaller...
pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install PyInstaller
    pause
    exit /b 1
)
echo Done.

echo.
echo [4/5] Building executable...
REM Add --noconfirm to auto-overwrite
pyinstaller --onefile --windowed --name="NotificationClient" --noconfirm main.py

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
echo Build SUCCESS!
echo.
echo Output files:
echo   - dist\NotificationClient.exe     [Main EXE]
echo   - start_with_watchdog.bat         [Auto-restart launcher]
echo   - watchdog.py                     [Python watchdog script]
echo ========================================
echo.
echo Features enabled:
echo   [X] Silent mode (no window on startup)
echo   [X] System tray support
echo   [X] Auto-reconnect on disconnect
echo   [X] Auto-start with Windows (configurable in settings)
echo   [X] Click close button to minimize to tray
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
