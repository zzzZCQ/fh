@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo   Uninstall Notification Service
echo ==============================================
echo.

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=NotificationService.lnk"

echo Removing startup shortcut...
if exist "!STARTUP_DIR!\!SHORTCUT_NAME!" (
    del "!STARTUP_DIR!\!SHORTCUT_NAME!"
    echo Shortcut removed successfully.
    echo.
    echo ==============================================
    echo   Uninstallation Complete!
    echo ==============================================
    echo Service will NOT start on next boot.
    echo ==============================================
) else (
    echo Shortcut not found. May already be uninstalled.
)

pause