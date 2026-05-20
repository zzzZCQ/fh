@echo off
chcp 65001 >nul
echo ========================================
echo Windows EXE Signing Tool
echo ========================================
echo.

if not exist "signing-cert.pfx" (
    echo [ERROR] Certificate not found: signing-cert.pfx
    echo.
    echo Please:
    echo 1. Get a code signing certificate
    echo 2. Export as PFX format
    echo 3. Save as signing-cert.pfx
    echo 4. Create sign-config.bat with password
    echo.
    pause
    exit /b 1
)

if exist "sign-config.bat" call sign-config.bat

if not defined SIGN_PASSWORD (
    set /p SIGN_PASSWORD=Enter certificate password: 
)

echo.
echo [1/2] Checking signtool...
where signtool >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] signtool not found
    echo Please install Windows SDK: https://developer.microsoft.com/windows/downloads/windows-sdk/
    echo.
    pause
    exit /b 1
)

echo.
echo [2/2] Signing EXE...
signtool sign /f signing-cert.pfx /p %SIGN_PASSWORD% /tr http://timestamp.digicert.com /td SHA256 /fd SHA256 dist\NotificationClient.exe

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo Signing SUCCESS!
    echo.
    echo Note: First run may still be blocked by SmartScreen
    echo Repeated runs will build reputation
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Signing FAILED! Error: %errorlevel%
    echo Check certificate and password
    echo ========================================
)

echo.
pause
