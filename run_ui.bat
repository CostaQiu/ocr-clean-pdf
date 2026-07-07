@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
set PYTHONUTF8=1
set PY=%~dp0.venv-ocr\Scripts\python.exe
echo ==================================================
echo   Starting OCR web UI ... (first launch: wait 10-20s)
echo   Browser opens automatically. If not, open:
echo   http://127.0.0.1:7860
echo   Keep this window OPEN = server is running.
echo ==================================================
"%PY%" -u "%~dp0ui_web.py"
echo.
echo Server stopped. Press any key to close.
pause >nul
