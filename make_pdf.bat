@echo off
chcp 65001 >nul
set PY=%~dp0.venv-ocr\Scripts\python.exe
"%PY%" -c "import merge_md, config; merge_md.merge(config.OUTPUT_DIR)"
"%PY%" "%~dp0make_pdf.py"
pause
