@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
set PYTHONUTF8=1
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
"%PY%" "C:\python_code\OCR\ui.py"
