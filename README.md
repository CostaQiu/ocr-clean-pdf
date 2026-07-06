# 扫描 PDF → 干净 PDF（本地 GPU OCR）

用 MinerU（pipeline 后端，PaddleOCR）在本地显卡对扫描版中文 PDF 做 OCR，
产出重新排版、纯文字、可搜索的干净 PDF。中英混排、**保留脚注**。

## 环境要求
- Windows + NVIDIA GPU + CUDA
- Python 3.12
- Pandoc（≥3.x）、Typst

## 安装
```powershell
cd C:\python_code\OCR
py -3.12 -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install --upgrade pip
# 先装 mineru，再装 CUDA torch（顺序重要：mineru 会拉一个 CPU 版 torch，最后覆盖回 CUDA 版）
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-ocr\Scripts\python.exe -m pip install --force-reinstall --no-deps torch torchvision --index-url https://download.pytorch.org/whl/cu124
winget install --id JohnMacFarlane.Pandoc -e
winget install --id Typst.Typst -e
```
验证 CUDA：`.\.venv-ocr\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"` 应为 `True`。

## 用法（图形界面，推荐）
双击 **`run_ui.bat`** 打开界面：
1. 「选择 PDF（可多选）」——可一次选同目录多本书。
2. 「输出目录」默认 = 源 PDF 所在目录，可改。
3. 「开始转换」——进度条按总页数推进，多本依次跑。
4. 成品为 **`clean_<原名>.pdf`**，放在输出目录；中间文件在 `<输出目录>\_ocr_work\<书名>\`（含 `book.md`，可喂 TTS；支持续跑）。

## 用法（命令行）
1. 改 `config.py` 的 `INPUT_PDF`（或用 `run_ocr.py -p 路径 -o 输出目录`）。
2. 双击 `run.bat`（后台 OCR，全书要一阵；首次会下模型）。
3. 看 `output\ocr.done.flag` 出现且 `status: ok`。
4. 双击 `make_pdf.bat`，在 `output\` 得到最终 PDF。

## 工作原理
- `run_ocr.py`：CUDA 自检 → 按页范围分批调 MinerU（可续跑）→ 写 `ocr.done.flag`。
- `merge_md.py`：解析各批 `content_list.json` 组装 markdown。正文/标题保留，
  书眉与页码丢弃，**脚注按页作为独立块附在正文后**。
- `make_pdf.py`：Pandoc 用 Typst 引擎把 markdown 渲染成 CJK PDF（字体 SimSun）。

## 参数
- 分批大小、后端、语言见 `config.py`；`run_ocr.py -h` 看 CLI。
- 换高精度 VLM 后端：`run_ocr.py -b vlm-engine`（Windows 上依赖 vLLM，可能需 WSL2）。

## 续跑
中断后重跑 `run.bat` 会跳过 `output\batches\` 里已带 `.batch.done` 的批次。
