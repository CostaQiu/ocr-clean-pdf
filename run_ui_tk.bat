@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
set PYTHONUTF8=1
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
rem 旧版 Tkinter 桌面界面(备用)。日常用 run_ui.bat(网页版)。
"%PY%" "C:\python_code\OCR\ui.py"
