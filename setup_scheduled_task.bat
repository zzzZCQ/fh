@echo off
chcp 65001 >nul
echo ========================================
echo 设置Git自动提交定时任务
echo ========================================
echo.

cd /d "%~dp0"

set TASK_NAME=GitAutoCommit_FHScript
set SCRIPT_PATH=%~dp0git_auto_commit.bat
set START_TIME=23:00

echo 任务名称: %TASK_NAME%
echo 脚本路径: %SCRIPT_PATH%
echo 执行时间: 每天 %START_TIME%
echo.

echo [1/2] 删除已存在的同名任务（如果有）...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

echo [2/2] 创建定时任务...
schtasks /create /tn "%TASK_NAME%" /tr "\"%SCRIPT_PATH%\"" /sc daily /st %START_TIME% /ru SYSTEM /rl highest /f

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo 成功！定时任务已创建
    echo ========================================
    echo.
    echo 您可以通过以下命令管理任务：
    echo   查看任务: schtasks /query /tn "%TASK_NAME%"
    echo   运行任务: schtasks /run /tn "%TASK_NAME%"
    echo   删除任务: schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo 创建任务失败，请以管理员身份运行此脚本
)

echo.
pause
