@echo off
chcp 65001 >nul
echo ========================================
echo Using OSSLSignCode (Open Source Tool)
echo ========================================
echo.

echo [1/3] Checking OpenSSL...
where openssl >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] OpenSSL not found
    echo Please install OpenSSL first
    pause
    exit /b 1
)

echo.
echo [2/3] Downloading osslsigncode...
if not exist "osslsigncode.exe" (
    echo Downloading...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/mtroelper/osslsigncode/releases/download/v1.7.1/osslsigncode-windows.exe' -OutFile 'osslsigncode.exe'"
)

echo.
echo [3/3] Signing EXE...
set /p CERT=Enter certificate file path: 
set /p KEY=Enter private key file path: 
set /p PASSWORD=Enter private key password: 

osslsigncode sign -c %CERT% -k %KEY% -p %PASSWORD% -t http://timestamp.digicert.com dist\NotificationClient.exe

echo.
echo Done!
pause
