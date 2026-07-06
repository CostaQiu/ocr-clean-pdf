@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
echo 后台启动全书 OCR，完成后看 output\ocr.done.flag ...
start "ocr" /b "%PY%" "C:\python_code\OCR\run_ocr.py"
echo 已在后台运行。可关闭本窗口，任务继续。
