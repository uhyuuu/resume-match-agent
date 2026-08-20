@echo off
setlocal
chcp 65001 >nul
title Resume Match Agent
cd /d "%~dp0"

echo ==========================================
echo   智能简历匹配 Agent - 启动器
echo ==========================================
echo.
echo 启动中，预计 5-10 秒后页面会自动打开...
echo 若浏览器未弹出，请手动访问 http://localhost:8501
echo.
echo 注意：请保持本窗口开启
echo ==========================================
echo.

start "" "http://localhost:8501"

venv\Scripts\python.exe -m streamlit run app.py ^
    --server.port 8501 ^
    --server.address 0.0.0.0 ^
    --browser.gatherUsageStats false ^
    > streamlit_log.txt 2>&1

echo.
echo 程序已退出
echo 日志已保存到 streamlit_log.txt
pause >nul
