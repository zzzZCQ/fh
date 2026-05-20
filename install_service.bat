@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo   Install Notification Service
echo ==============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=NotificationService.lnk"
set "TARGET_FILE=%SCRIPT_DIR%start_server.py"

echo Finding Python path...
for %%x in (pythonw.exe) do (set PYTHON_PATH=%%~$PATH:x)

if not defined PYTHON_PATH (
    echo ERROR: pythonw.exe not found. Please add Python to your system PATH.
    pause
    exit /b 1
)

echo Found Python: !PYTHON_PATH!
echo.

echo Creating shortcut in Startup folder...
powershell.exe -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('!STARTUP_DIR!\!SHORTCUT_NAME!'); $sc.TargetPath = '!PYTHON_PATH!'; $sc.Arguments = '\"!TARGET_FILE!\"'; $sc.WorkingDirectory = '!SCRIPT_DIR!'; $sc.WindowStyle = 7; $sc.Save();"

if exist "!STARTUP_DIR!\!SHORTCUT_NAME!" (
    echo Shortcut created successfully.
    echo.
    echo ==============================================
    echo   Installation Complete!
    echo ==============================================
    echo Service will start automatically on next boot.
    echo To start immediately, run: start_server.vbs
    echo To uninstall, run: uninstall_service.bat
    echo ==============================================
) else (
    echo ERROR: Failed to create shortcut.
    pause
    exit /b 1
)