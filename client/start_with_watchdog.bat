@echo off
chcp 65001 >nul
echo ========================================
echo Notification Client Launcher
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%dist\NotificationClient.exe"
set "RESTART_DELAY=3"
set "MAX_RESTARTS=100"
set "restart_count=0"

echo Starting Notification Client...
echo.

:start
if exist "%EXE_PATH%" (
    start "" "%EXE_PATH%"
    echo [%date% %time%] Client started (attempt: %restart_count%)
) else (
    echo [ERROR] EXE not found: %EXE_PATH%
    echo Please run build.bat first to create the EXE
    pause
    exit /b 1
)

:wait
timeout /t 2 /nobreak >nul
tasklist /fi "IMAGENAME eq NotificationClient.exe" 2>nul | find /i "NotificationClient.exe" >nul
if %errorlevel% neq 0 (
    set /a restart_count+=1
    if %restart_count% lss %MAX_RESTARTS% (
        echo [%date% %time%] Client closed, restarting in %RESTART_DELAY% seconds...
        timeout /t %RESTART_DELAY% /nobreak >nul
        goto :start
    ) else (
        echo [%date% %time%] Max restarts reached (%MAX_RESTARTS%), exiting
        echo You can manually restart the launcher
        pause
        exit /b 0
    )
)
goto :wait
