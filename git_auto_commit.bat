@echo off
chcp 65001 >nul
echo ========================================
echo 自动Git提交脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] 检查Git状态...
git status
if %errorlevel% neq 0 (
    echo 错误：Git命令执行失败，请确保Git已安装并在PATH中
    pause
    exit /b 1
)

echo.
echo [2/4] 添加变更的文件...
git add .

echo.
echo [3/4] 创建提交...
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set year=%datetime:~0,4%
set month=%datetime:~4,2%
set day=%datetime:~6,2%
set hour=%datetime:~8,2%
set minute=%datetime:~10,2%

set commit_msg=自动提交: %year%-%month%-%day% %hour%:%minute%
git commit -m "%commit_msg%"

if %errorlevel% neq 0 (
    echo 提示：没有变更需要提交，或提交失败
) else (
    echo.
    echo [4/4] 推送到远程仓库...
    git push
    if %errorlevel% neq 0 (
        echo 警告：推送到远程仓库失败，请检查网络或仓库配置
    ) else (
        echo 成功：代码已提交并推送！
    )
)

echo.
echo ========================================
echo 完成
echo ========================================
timeout /t 3
