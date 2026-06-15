@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo   卸载发货通知系统服务
echo ==============================================
echo.

set "SERVICE_NAME=FHNotificationService"

echo 停止并删除任务计划程序任务...
powershell.exe -ExecutionPolicy Bypass -Command ^
"$taskName = '%SERVICE_NAME%'; ^
try { Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue; } catch {}; ^
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false"

if %errorlevel% equ 0 (
    echo 任务计划程序任务已删除
    echo.
    echo ==============================================
    echo   卸载完成!
    echo ==============================================
    echo 服务已从开机自启中移除
    echo ==============================================
) else (
    echo ERROR: 删除任务计划程序任务失败
    echo 请以管理员身份运行此脚本
    pause
    exit /b 1
)