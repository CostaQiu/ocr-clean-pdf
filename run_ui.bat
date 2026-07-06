@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
set PYTHONUTF8=1
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
echo ==================================================
echo   正在启动 OCR 网页界面，首次要等 10-20 秒加载...
echo   启动后浏览器会自动打开；若没有，手动访问：
echo   http://127.0.0.1:7860
echo   （本窗口保持打开 = 服务运行中，关掉即停止）
echo ==================================================
"%PY%" -u "C:\python_code\OCR\ui_web.py"
echo.
echo 服务已停止。按任意键关闭本窗口。
pause >nul
