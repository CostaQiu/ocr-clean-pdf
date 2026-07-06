@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
set PYTHONUTF8=1
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
echo 启动网页界面，浏览器会自动打开(本地 localhost)。关闭本窗口即停止。
"%PY%" "C:\python_code\OCR\ui_web.py"
