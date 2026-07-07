@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
set PYTHONUTF8=1
set PY=%~dp0.venv-ocr\Scripts\python.exe
rem Old Tkinter desktop UI (fallback). Use run_ui.bat for the web UI.
"%PY%" "%~dp0ui.py"
pause >nul
