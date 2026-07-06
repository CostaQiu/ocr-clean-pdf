@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
rem 可选提速(默认关):放开下一行会把 GPU 批量翻倍(batch_ratio 8->16)。
rem 注意:这是对 16G 卡"谎报"32G 显存,有 OOM 风险,GPU 本非瓶颈,建议先不开。
rem set MINERU_VIRTUAL_VRAM_SIZE=32
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
echo 后台启动全书 OCR，完成后看 output\ocr.done.flag ...
start "ocr" /b "%PY%" "C:\python_code\OCR\run_ocr.py"
echo 已在后台运行。可关闭本窗口，任务继续。
