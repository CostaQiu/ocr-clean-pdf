@echo off
chcp 65001 >nul
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
"%PY%" -c "import merge_md, config; merge_md.merge(config.OUTPUT_DIR)"
"%PY%" "C:\python_code\OCR\make_pdf.py"
pause
