@echo off
chcp 65001 >nul
cd /d "D:\fh\"
echo [%date% %time%] Checking for changes...
git add -A
git commit -m "Auto commit: %date% %time%"
git push origin master
