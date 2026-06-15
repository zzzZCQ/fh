@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo   安装发货通知系统服务
echo ==============================================
echo.

set "SCRIPT_DIR=%~dp0"
set "SERVICE_NAME=FHNotificationService"
set "STARTUP_SCRIPT=%SCRIPT_DIR%start_server.vbs"

echo 检查 Python 环境...
for %%x in (pythonw.exe) do (set PYTHON_PATH=%%~$PATH:x)

if not defined PYTHON_PATH (
    echo ERROR: 未找到 pythonw.exe，请将 Python 添加到系统 PATH
    pause
    exit /b 1
)

echo 已找到 Python: !PYTHON_PATH!
echo.

echo 检查启动脚本...
if not exist "%STARTUP_SCRIPT%" (
    echo ERROR: 启动脚本不存在: %STARTUP_SCRIPT%
    pause
    exit /b 1
)

echo 启动脚本存在: %STARTUP_SCRIPT%
echo.

echo 创建任务计划程序任务...
powershell.exe -ExecutionPolicy Bypass -Command ^
"$taskName = '%SERVICE_NAME%'; ^
$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '\"%STARTUP_SCRIPT%\"'; ^
$trigger = New-ScheduledTaskTrigger -AtLogOn; ^
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest; ^
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -Hidden; ^
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings; ^
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force"

if %errorlevel% equ 0 (
    echo 任务计划程序任务创建成功
    echo.
    
    echo 立即启动服务...
    powershell.exe -ExecutionPolicy Bypass -Command "Start-ScheduledTask -TaskName '%SERVICE_NAME%'"
    
    if %errorlevel% equ 0 (
        echo 服务已启动
        echo.
        echo ==============================================
        echo   安装完成!
        echo ==============================================
        echo 服务已配置为开机自启
        echo 服务名称: %SERVICE_NAME%
        echo 日志文件: %SCRIPT_DIR%server.log
        echo.
        echo 卸载服务请运行: uninstall_service.bat
        echo ==============================================
    ) else (
        echo 警告: 服务启动失败，请手动检查任务计划程序
    )
) else (
    echo ERROR: 创建任务计划程序任务失败
    echo 请以管理员身份运行此脚本
    pause
    exit /b 1
)