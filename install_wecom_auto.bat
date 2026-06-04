@echo off
chcp 65001
echo ==========================================
echo 企业微信自动化营销功能 - 快速安装
echo ==========================================
echo.

echo [1/3] 安装Python依赖包...
pip install -r requirements_wecom_auto.txt
if errorlevel 1 (
    echo 依赖包安装失败！
    pause
    exit /b 1
)
echo 依赖包安装成功！
echo.

echo [2/3] 安装Playwright浏览器...
playwright install chromium
if errorlevel 1 (
    echo 浏览器安装失败！
    pause
    exit /b 1
)
echo 浏览器安装成功！
echo.

echo [3/3] 初始化数据目录...
if not exist "wecom_data" mkdir wecom_data
echo 数据目录准备完成！
echo.

echo ==========================================
echo 安装完成！
echo ==========================================
echo.
echo 下一步：
echo 1. 运行 python app.py 启动系统
echo 2. 访问 http://你的服务器:5000/admin/wecom-auto/
echo 3. 点击"测试登录"进行企业微信扫码登录
echo.
echo 详细说明请查看 README_WECOM_AUTO.md
echo.
pause
