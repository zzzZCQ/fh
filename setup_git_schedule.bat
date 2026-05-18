@echo off
chcp 65001 >nul
echo ========================================
echo   Git Auto Commit - Setting up schedule
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Checking git status...
git status >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Not a git repository!
    echo Please run init_git.py first.
    pause
    exit /b 1
)

echo [OK] Git repository found
echo.

echo [2/3] Creating auto-commit script...
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%~dp0"
echo echo [%%date%% %%time%%] Checking for changes...
echo git add -A
echo git commit -m "Auto commit: %%date%% %%time%%"
echo git push origin master
) > auto_commit.bat

echo [OK] auto_commit.bat created
echo.

echo [3/3] Setting up scheduled task...
schtasks /create /tn "FH_AutoCommit" /tr "\"%%~dp0auto_commit.bat\"" /sc daily /st 23:00 /f

if errorlevel 1 (
    echo [WARNING] Could not create scheduled task automatically.
    echo Please run this command as Administrator:
    echo   schtasks /create /tn "FH_AutoCommit" /tr "\"%%~dp0auto_commit.bat\"" /sc daily /st 23:00 /f
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Task: FH_AutoCommit
echo Schedule: Daily at 23:00
echo.
echo You can also run auto_commit.bat manually anytime.
echo.
pause
