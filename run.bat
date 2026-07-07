@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
rem Optional speedup (off by default): the next line doubles GPU batch (ratio 8->16).
rem It fakes 32GB VRAM on a 16GB card = OOM risk, GPU is not the bottleneck. Keep off.
rem set MINERU_VIRTUAL_VRAM_SIZE=32
set PY=%~dp0.venv-ocr\Scripts\python.exe
echo Starting full-book OCR in background. Check output\ocr.done.flag when done.
start "ocr" /b "%PY%" "%~dp0run_ocr.py"
echo Running in background. You can close this window.
