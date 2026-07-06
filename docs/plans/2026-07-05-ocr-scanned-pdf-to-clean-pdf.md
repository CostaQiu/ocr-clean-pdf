# 扫描 PDF → 干净 PDF（本地 GPU OCR）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用本地 GPU 对扫描版中文 PDF 做 OCR，产出重新排版的、纯文字可搜索的干净 PDF。

**Architecture:** 编排器按页码范围分批调用 MinerU CLI（pipeline 后端，CUDA-torch）→ 各批 markdown 合并清理成 `book.md` → Pandoc+Typst 渲染成干净 PDF。分批可续跑，全书 OCR 后台运行 + done.flag。

**Tech Stack:** Python 3.12、MinerU（pipeline 后端 / PaddleOCR）、CUDA torch、PyMuPDF、Pandoc、Typst、pytest。

## Global Constraints

- 项目根：`C:\python_code\OCR\`，所有代码与产物在此目录内，自包含。
- OCR 引擎：MinerU **pipeline** 后端，`-m ocr -l ch`；**强制 GPU**，`torch.cuda.is_available()` 非 True 即报错退出，绝不静默回退 CPU。
- 独立虚拟环境 `.venv-ocr`（Python 3.12）；**不得**动用系统 3.12 或其他项目环境。
- 大文件不物理切分；按 MinerU 的 `-s/-e` 页范围分批，默认 40 页/批。
- 分批可续跑：已完成批次目录含 `.batch.done` 标记，重跑跳过。
- 长任务（全书 OCR）后台运行，跑完写 `output/ocr.done.flag`；**禁止** `time.sleep`+轮询。
- 脚注**保留**，作为独立块（MinerU 版面检测已分离脚注与正文）。
- 渲染：Pandoc + Typst，CJK 字体（Windows 自带 `SimSun` 宋体）。
- 输入默认 PDF：`C:\python_code\OCR\中国政治思想史 (萧公权) (Z-Library).pdf`。
- 命令用 `python`/`pip`（非 python3）；路径用 `pathlib.Path`。
- 本项目**非** git 仓库；git 为可选。每个任务以"运行测试/验收输出"作为收尾检查点，不强制 commit（Costa 约定：只在明确要求时才 commit）。

---

### Task 1: 项目脚手架与隔离环境

**Files:**
- Create: `C:\python_code\OCR\config.py`
- Create: `C:\python_code\OCR\requirements.txt`
- Create: `C:\python_code\OCR\.gitignore`
- Create: `C:\python_code\OCR\tests\__init__.py`（空文件）

**Interfaces:**
- Produces: `config` 模块，含常量 `PROJECT_ROOT: Path`、`INPUT_PDF: Path`、`OUTPUT_DIR: Path`、`BATCH_SIZE: int`、`BACKEND: str`、`LANG: str`、`DEVICE: str`。

- [ ] **Step 1: 写 `requirements.txt`**

```
# torch 单独装（CUDA 版），不写在这里
mineru[core]
PyMuPDF
pytest
```

- [ ] **Step 2: 写 `.gitignore`**

```
.venv-ocr/
output/
output_smoke/
__pycache__/
*.pyc
.superpowers/
# 源扫描 PDF 不入库(148MB)
*.pdf
```
（注：git 仓库与此 `.gitignore` 已在执行前初始化；本步与已有内容一致即可，勿改回包含 PDF。）

- [ ] **Step 3: 写 `config.py`**

```python
"""OCR 流水线默认配置。CLI 参数可覆盖这些值。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_PDF = PROJECT_ROOT / "中国政治思想史 (萧公权) (Z-Library).pdf"
OUTPUT_DIR = PROJECT_ROOT / "output"

BATCH_SIZE = 40          # 每批页数
BACKEND = "pipeline"     # MinerU 后端；可切 "vlm-engine"
LANG = "ch"              # PaddleOCR 语言（中文模型含英文识别）
DEVICE = "cuda"          # 本期固定 GPU；缺 CUDA 报错
```

- [ ] **Step 4: 建独立 venv 并装依赖（CUDA torch 单独装）**

Run（PowerShell，逐条）：
```powershell
cd C:\python_code\OCR
C:\Users\Costa\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install --upgrade pip
.\.venv-ocr\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu124
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements.txt
```
说明：此步会下载数 GB（torch + mineru + paddle），**耗时长**，用后台执行并在完成后检查（见执行说明）。CUDA 版本按机器实际（cu121/cu124/cu126）择一。

- [ ] **Step 5: 验证环境**

Run:
```powershell
.\.venv-ocr\Scripts\python.exe -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-')"
.\.venv-ocr\Scripts\mineru.exe --version
.\.venv-ocr\Scripts\python.exe -c "import config; print(config.INPUT_PDF.exists(), config.INPUT_PDF)"
```
Expected: 第一行 `cuda True NVIDIA GeForce RTX 4080 SUPER`；第二行打印 mineru 版本号；第三行 `True <路径>`。

---

### Task 2: 分批与续跑逻辑（纯函数，TDD）

**Files:**
- Create: `C:\python_code\OCR\batching.py`
- Test: `C:\python_code\OCR\tests\test_batching.py`

**Interfaces:**
- Produces:
  - `make_batches(total_pages: int, batch_size: int) -> list[tuple[int, int]]`（0 基、end 不含）
  - `batch_dir(output_dir: Path, start: int, end: int) -> Path`
  - `is_batch_done(output_dir: Path, start: int, end: int) -> bool`
  - `mark_batch_done(output_dir: Path, start: int, end: int) -> None`

- [ ] **Step 1: 写失败测试 `tests/test_batching.py`**

```python
from pathlib import Path
import pytest
from batching import make_batches, batch_dir, is_batch_done, mark_batch_done


def test_make_batches_covers_all_pages_without_overlap():
    batches = make_batches(700, 40)
    assert batches[0] == (0, 40)
    assert batches[-1] == (680, 700)
    assert len(batches) == 18
    # 覆盖且不重叠
    covered = []
    for s, e in batches:
        covered.extend(range(s, e))
    assert covered == list(range(700))


def test_make_batches_exact_multiple():
    assert make_batches(80, 40) == [(0, 40), (40, 80)]


def test_make_batches_empty_and_bad_input():
    assert make_batches(0, 40) == []
    with pytest.raises(ValueError):
        make_batches(100, 0)


def test_batch_dir_zero_padded_name(tmp_path):
    d = batch_dir(tmp_path, 40, 80)
    assert d == tmp_path / "batches" / "0040_0080"


def test_is_batch_done_and_mark(tmp_path):
    assert is_batch_done(tmp_path, 0, 40) is False
    mark_batch_done(tmp_path, 0, 40)
    assert is_batch_done(tmp_path, 0, 40) is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv-ocr\Scripts\python.exe -m pytest tests/test_batching.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'batching'`）。

- [ ] **Step 3: 写 `batching.py`**

```python
"""页范围分批 + 续跑标记（纯逻辑，无副作用除写标记）。"""
from pathlib import Path


def make_batches(total_pages: int, batch_size: int) -> list[tuple[int, int]]:
    """返回 [(start, end), ...]，0 基、end 不含，覆盖 [0, total_pages)。"""
    if batch_size <= 0:
        raise ValueError("batch_size 必须为正")
    if total_pages <= 0:
        return []
    return [(s, min(s + batch_size, total_pages))
            for s in range(0, total_pages, batch_size)]


def batch_dir(output_dir: Path, start: int, end: int) -> Path:
    """该批的输出目录，名字零填充保证字典序 == 页序。"""
    return output_dir / "batches" / f"{start:04d}_{end:04d}"


def is_batch_done(output_dir: Path, start: int, end: int) -> bool:
    return (batch_dir(output_dir, start, end) / ".batch.done").exists()


def mark_batch_done(output_dir: Path, start: int, end: int) -> None:
    d = batch_dir(output_dir, start, end)
    d.mkdir(parents=True, exist_ok=True)
    (d / ".batch.done").write_text("ok", encoding="utf-8")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv-ocr\Scripts\python.exe -m pytest tests/test_batching.py -v`
Expected: 5 passed。

---

### Task 3: OCR 编排器 `run_ocr.py`（CUDA 自检 + 分批 + 续跑 + flag）

**Files:**
- Create: `C:\python_code\OCR\run_ocr.py`
- Test: `C:\python_code\OCR\tests\test_run_ocr.py`

**Interfaces:**
- Consumes: `batching.make_batches / batch_dir / is_batch_done / mark_batch_done`；`config`。
- Produces:
  - `assert_cuda() -> None`（无 CUDA 抛 `SystemExit`）
  - `count_pages(pdf: Path) -> int`
  - `build_mineru_cmd(pdf: Path, out: Path, start: int, end_exclusive: int, backend: str, lang: str) -> list[str]`
  - `run_all(pdf, output_dir, batch_size, backend, lang) -> dict`（返回 `{"ok": bool, "pages": int, "failed": list, "elapsed_s": float}`）
  - `main()`（argparse 入口）

- [ ] **Step 1: 写失败测试 `tests/test_run_ocr.py`**

```python
from pathlib import Path
import run_ocr


def test_build_mineru_cmd_uses_inclusive_end_and_flags():
    # 我们的批是 end 不含；MinerU 的 -e 是含端点，故应传 end_exclusive-1
    cmd = run_ocr.build_mineru_cmd(
        Path("book.pdf"), Path("out"), start=40, end_exclusive=80,
        backend="pipeline", lang="ch",
    )
    assert "mineru" in cmd[0]
    assert "-s" in cmd and "40" in cmd
    assert "-e" in cmd and "79" in cmd          # 80 不含 → 含端点 79
    assert "-b" in cmd and "pipeline" in cmd
    assert "-m" in cmd and "ocr" in cmd
    assert "-l" in cmd and "ch" in cmd


def test_run_all_skips_done_batches(tmp_path, monkeypatch):
    calls = []

    def fake_run_one(pdf, out, s, e, backend, lang):
        calls.append((s, e))
        return True  # 假装成功

    monkeypatch.setattr(run_ocr, "_run_one_batch", fake_run_one)
    monkeypatch.setattr(run_ocr, "count_pages", lambda p: 80)
    # 预先把第一批标记为已完成
    from batching import mark_batch_done
    mark_batch_done(tmp_path, 0, 40)

    result = run_ocr.run_all(
        pdf=tmp_path / "x.pdf", output_dir=tmp_path,
        batch_size=40, backend="pipeline", lang="ch",
    )
    assert (0, 40) not in calls        # 已完成的批被跳过
    assert (40, 80) in calls           # 未完成的批被执行
    assert result["ok"] is True
    assert result["pages"] == 80
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv-ocr\Scripts\python.exe -m pytest tests/test_run_ocr.py -v`
Expected: FAIL（`AttributeError`/`ModuleNotFoundError`）。

- [ ] **Step 3: 写 `run_ocr.py`**

```python
"""OCR 编排器：CUDA 自检 → 按页范围分批调 MinerU → 可续跑 → 写 done.flag。

用法（通常后台运行）：
    python run_ocr.py                     # 用 config 默认值跑全书
    python run_ocr.py -s 0 -e 2           # 只跑前 2 页（冒烟）
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import config
from batching import make_batches, batch_dir, is_batch_done, mark_batch_done


def assert_cuda() -> None:
    """无可用 CUDA GPU 时明确报错退出，绝不回退 CPU。"""
    try:
        import torch
    except ImportError:
        sys.exit("错误：未安装 torch。请在 .venv-ocr 里装 CUDA 版 torch。")
    if not torch.cuda.is_available():
        sys.exit(
            "错误：未检测到 CUDA GPU（torch.cuda.is_available()==False）。\n"
            "可能 torch 装成了 CPU 版。请重装：\n"
            "  pip install torch --index-url https://download.pytorch.org/whl/cu124"
        )
    print(f"[cuda] {torch.cuda.get_device_name(0)}")


def count_pages(pdf: Path) -> int:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf)
    try:
        return doc.page_count
    finally:
        doc.close()


def build_mineru_cmd(pdf: Path, out: Path, start: int, end_exclusive: int,
                     backend: str, lang: str) -> list[str]:
    """MinerU 的 -e 含端点；我们的批 end 不含，故传 end_exclusive-1。"""
    mineru = str(Path(sys.executable).with_name("mineru.exe"))
    return [
        mineru,
        "-p", str(pdf),
        "-o", str(out),
        "-b", backend,
        "-m", "ocr",
        "-l", lang,
        "-s", str(start),
        "-e", str(end_exclusive - 1),
    ]


def _run_one_batch(pdf: Path, out_dir: Path, start: int, end_exclusive: int,
                   backend: str, lang: str) -> bool:
    """跑单批，成功（返回码 0 且产出 markdown）返回 True。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_mineru_cmd(pdf, out_dir, start, end_exclusive, backend, lang)
    print(f"[batch {start:04d}-{end_exclusive:04d}] {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print(f"[batch {start:04d}-{end_exclusive:04d}] MinerU 返回码 {proc.returncode}")
        return False
    if not list(out_dir.rglob("*.md")):
        print(f"[batch {start:04d}-{end_exclusive:04d}] 未产出 markdown")
        return False
    return True


def run_all(pdf: Path, output_dir: Path, batch_size: int,
            backend: str, lang: str) -> dict:
    t0 = time.perf_counter()
    total = count_pages(pdf)
    batches = make_batches(total, batch_size)
    failed = []
    for start, end in batches:
        if is_batch_done(output_dir, start, end):
            print(f"[batch {start:04d}-{end:04d}] 已完成，跳过")
            continue
        ok = _run_one_batch(pdf, batch_dir(output_dir, start, end),
                            start, end, backend, lang)
        if ok:
            mark_batch_done(output_dir, start, end)
        else:
            failed.append([start, end])
    elapsed = time.perf_counter() - t0
    return {"ok": not failed, "pages": total,
            "failed": failed, "elapsed_s": round(elapsed, 1)}


def _write_flag(output_dir: Path, result: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    status = "ok" if result["ok"] else "fail"
    lines = [
        f"status: {status}",
        f"pages: {result['pages']}",
        f"elapsed_s: {result['elapsed_s']}",
        f"failed_batches: {result['failed']}",
    ]
    (output_dir / "ocr.done.flag").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="扫描 PDF 分批 OCR（MinerU pipeline，GPU）")
    ap.add_argument("-p", "--pdf", type=Path, default=config.INPUT_PDF)
    ap.add_argument("-o", "--output", type=Path, default=config.OUTPUT_DIR)
    ap.add_argument("--batch-size", type=int, default=config.BATCH_SIZE)
    ap.add_argument("-b", "--backend", default=config.BACKEND)
    ap.add_argument("-l", "--lang", default=config.LANG)
    args = ap.parse_args()

    assert_cuda()
    if not args.pdf.exists():
        sys.exit(f"错误：找不到输入 PDF：{args.pdf}")

    print(f"[start] {args.pdf.name} → {args.output}")
    result = run_all(args.pdf, args.output, args.batch_size,
                     args.backend, args.lang)
    _write_flag(args.output, result)
    print(f"[done] {result}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv-ocr\Scripts\python.exe -m pytest tests/test_run_ocr.py -v`
Expected: 2 passed。

- [ ] **Step 5: 前 2 页 OCR 冒烟（真实 GPU）**

Run:
```powershell
$env:MINERU_MODEL_SOURCE="modelscope"   # 国内下模型更快
.\.venv-ocr\Scripts\python.exe run_ocr.py -s 0 -e 2 --output output_smoke
```
说明：首次运行会下载 MinerU 模型（数百 MB～GB），耗时长，用后台执行。
Expected: `output_smoke/batches/0000_0002/` 下生成 `*.md`，`output_smoke/ocr.done.flag` 内 `status: ok`。人工打开该 md，确认中文正确、中英混排完好、脚注单独成块。

---

### Task 4: 合并与清理 `merge_md.py`（TDD）

**Files:**
- Create: `C:\python_code\OCR\merge_md.py`
- Test: `C:\python_code\OCR\tests\test_merge_md.py`

**Interfaces:**
- Produces:
  - `strip_page_numbers(text: str) -> str`（删掉整行只有页码的行）
  - `collapse_blank_lines(text: str) -> str`（3+ 连续空行 → 1 个空行）
  - `find_batch_markdown(batch_dir: Path) -> Path | None`
  - `merge(output_dir: Path) -> Path`（写 `output_dir/book.md`，返回其路径）

- [ ] **Step 1: 写失败测试 `tests/test_merge_md.py`**

```python
from pathlib import Path
import merge_md


def test_strip_page_numbers_removes_isolated_numbers():
    text = "正文第一段。\n123\n正文第二段。\n— 45 —\n结尾。"
    out = merge_md.strip_page_numbers(text)
    assert "123" not in out
    assert "45" not in out
    assert "正文第一段。" in out
    assert "正文第二段。" in out
    assert "结尾。" in out


def test_strip_page_numbers_keeps_numbers_inside_text():
    text = "公元 1949 年是重要节点。"
    assert merge_md.strip_page_numbers(text) == text


def test_collapse_blank_lines():
    text = "A\n\n\n\nB"
    assert merge_md.collapse_blank_lines(text) == "A\n\nB"


def test_find_batch_markdown(tmp_path):
    assert merge_md.find_batch_markdown(tmp_path) is None
    sub = tmp_path / "x" / "ocr"
    sub.mkdir(parents=True)
    md = sub / "x.md"
    md.write_text("hi", encoding="utf-8")
    assert merge_md.find_batch_markdown(tmp_path) == md


def test_merge_concatenates_in_page_order(tmp_path):
    batches = tmp_path / "batches"
    for name, body in [("0000_0040", "第一批正文。"), ("0040_0080", "第二批正文。")]:
        d = batches / name / "ocr"
        d.mkdir(parents=True)
        (d / "a.md").write_text(body, encoding="utf-8")
    out = merge_md.merge(tmp_path)
    assert out == tmp_path / "book.md"
    content = out.read_text(encoding="utf-8")
    assert content.index("第一批正文。") < content.index("第二批正文。")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.\.venv-ocr\Scripts\python.exe -m pytest tests/test_merge_md.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'merge_md'`）。

- [ ] **Step 3: 写 `merge_md.py`**

```python
"""合并各批 MinerU markdown，并做轻量清理（去孤立页码、压缩空行）。

MinerU 版面检测通常已丢弃 running header/footer，故清理保持克制，
只做低风险处理，避免误删正文。
"""
import re
from pathlib import Path

# 整行只含页码（可带前后破折号），如 "123"、"— 45 —"、"- 12 -"
PAGE_NUM_RE = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")


def strip_page_numbers(text: str) -> str:
    kept = [ln for ln in text.split("\n") if not PAGE_NUM_RE.match(ln)]
    return "\n".join(kept)


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def find_batch_markdown(batch_dir: Path) -> Path | None:
    mds = sorted(batch_dir.rglob("*.md"))
    return mds[0] if mds else None


def merge(output_dir: Path) -> Path:
    batches_dir = output_dir / "batches"
    # 目录名零填充，字典序 == 页序
    batch_dirs = sorted(p for p in batches_dir.iterdir() if p.is_dir())
    parts = []
    for bd in batch_dirs:
        md = find_batch_markdown(bd)
        if md is not None:
            parts.append(md.read_text(encoding="utf-8"))
    merged = "\n\n".join(parts)
    merged = strip_page_numbers(merged)
    merged = collapse_blank_lines(merged)
    out = output_dir / "book.md"
    out.write_text(merged, encoding="utf-8")
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.\.venv-ocr\Scripts\python.exe -m pytest tests/test_merge_md.py -v`
Expected: 5 passed。

---

### Task 5: 渲染 `make_pdf.py`（Pandoc + Typst）+ 冒烟验收

**Files:**
- Create: `C:\python_code\OCR\make_pdf.py`
- Test: `C:\python_code\OCR\tests\test_make_pdf.py`

**Interfaces:**
- Consumes: `output/book.md`。
- Produces:
  - `check_tools() -> None`（缺 pandoc/typst 时打印安装提示并退出）
  - `build_pandoc_cmd(book_md: Path, out_pdf: Path, font: str) -> list[str]`
  - `main()`

- [ ] **Step 1: 装 Pandoc 与 Typst**

Run（PowerShell）：
```powershell
winget install --id JohnMacFarlane.Pandoc -e
winget install --id Typst.Typst -e
```
验证：`pandoc --version`（需 ≥3.x，含 typst 引擎）、`typst --version`。装完可能需重开终端刷新 PATH。

- [ ] **Step 2: 写失败测试 `tests/test_make_pdf.py`**

```python
from pathlib import Path
import make_pdf


def test_build_pandoc_cmd_uses_typst_engine_and_cjk_font():
    cmd = make_pdf.build_pandoc_cmd(
        Path("output/book.md"), Path("output/book.pdf"), font="SimSun",
    )
    assert cmd[0] == "pandoc"
    assert "--pdf-engine=typst" in cmd
    joined = " ".join(cmd)
    assert "mainfont=SimSun" in joined
    assert str(Path("output/book.md")) in cmd
    assert "-o" in cmd
```

- [ ] **Step 3: 跑测试确认失败**

Run: `.\.venv-ocr\Scripts\python.exe -m pytest tests/test_make_pdf.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'make_pdf'`）。

- [ ] **Step 4: 写 `make_pdf.py`**

```python
"""book.md → 干净可搜索 PDF：Pandoc 用 Typst 引擎渲染，CJK 字体。

用法：
    python make_pdf.py                       # 用 config 默认输出目录
    python make_pdf.py --md output/book.md --pdf output/书名.pdf
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import config

DEFAULT_FONT = "SimSun"   # Windows 自带宋体，覆盖 CJK


def check_tools() -> None:
    for tool in ("pandoc", "typst"):
        if shutil.which(tool) is None:
            sys.exit(
                f"错误：找不到 {tool}。请安装：\n"
                "  winget install --id JohnMacFarlane.Pandoc -e\n"
                "  winget install --id Typst.Typst -e\n"
                "装完重开终端以刷新 PATH。"
            )


def build_pandoc_cmd(book_md: Path, out_pdf: Path, font: str) -> list[str]:
    return [
        "pandoc",
        str(book_md),
        "-o", str(out_pdf),
        "--pdf-engine=typst",
        "-V", f"mainfont={font}",
        "-V", "fontsize=12pt",
        "--toc",                 # 依 markdown 标题生成目录
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description="book.md → 干净 PDF（Pandoc+Typst）")
    ap.add_argument("--md", type=Path, default=config.OUTPUT_DIR / "book.md")
    ap.add_argument("--pdf", type=Path,
                    default=config.OUTPUT_DIR / "中国政治思想史.pdf")
    ap.add_argument("--font", default=DEFAULT_FONT)
    args = ap.parse_args()

    check_tools()
    if not args.md.exists():
        sys.exit(f"错误：找不到 {args.md}，请先跑 run_ocr.py + merge_md.py。")

    cmd = build_pandoc_cmd(args.md, args.pdf, args.font)
    print("[render]", " ".join(cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        sys.exit(f"渲染失败，pandoc 返回码 {proc.returncode}")
    print(f"[ok] 生成 {args.pdf}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 跑测试确认通过**

Run: `.\.venv-ocr\Scripts\python.exe -m pytest tests/test_make_pdf.py -v`
Expected: 1 passed。

- [ ] **Step 6: 前 2 页端到端出 PDF 验收**

Run:
```powershell
.\.venv-ocr\Scripts\python.exe -c "import merge_md; from pathlib import Path; print(merge_md.merge(Path('output_smoke')))"
.\.venv-ocr\Scripts\python.exe make_pdf.py --md output_smoke\book.md --pdf output_smoke\smoke.pdf
```
Expected: 生成 `output_smoke/smoke.pdf`。人工打开：中文/英文渲染正确、可选中搜索、脚注单独成块、无乱码。**此关通过前不跑全书。**

---

### Task 6: 一键脚本 `run.bat` + `README.md`

**Files:**
- Create: `C:\python_code\OCR\run.bat`
- Create: `C:\python_code\OCR\make_pdf.bat`
- Create: `C:\python_code\OCR\README.md`

**Interfaces:**
- 无新代码接口；封装既有脚本供双击运行。

- [ ] **Step 1: 写 `run.bat`（后台跑全书 OCR）**

```bat
@echo off
chcp 65001 >nul
set MINERU_MODEL_SOURCE=modelscope
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
echo 后台启动全书 OCR，完成后看 output\ocr.done.flag ...
start "ocr" /b "%PY%" "C:\python_code\OCR\run_ocr.py"
echo 已在后台运行。可关闭本窗口，任务继续。
```

- [ ] **Step 2: 写 `make_pdf.bat`（合并 + 渲染）**

```bat
@echo off
chcp 65001 >nul
set PY=C:\python_code\OCR\.venv-ocr\Scripts\python.exe
"%PY%" -c "import merge_md; from pathlib import Path; import config; merge_md.merge(config.OUTPUT_DIR)"
"%PY%" "C:\python_code\OCR\make_pdf.py"
pause
```

- [ ] **Step 3: 写 `README.md`**

````markdown
# 扫描 PDF → 干净 PDF（本地 GPU OCR）

用 MinerU（pipeline 后端，PaddleOCR）在本地显卡对扫描版中文 PDF 做 OCR，
产出重新排版、纯文字、可搜索的干净 PDF。中英混排、保留脚注。

## 环境要求
- Windows + NVIDIA GPU + CUDA
- Python 3.12
- Pandoc（≥3.x）、Typst

## 安装
```powershell
cd C:\python_code\OCR
py -3.12 -m venv .venv-ocr
.\.venv-ocr\Scripts\python.exe -m pip install --upgrade pip
.\.venv-ocr\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu124
.\.venv-ocr\Scripts\python.exe -m pip install -r requirements.txt
winget install --id JohnMacFarlane.Pandoc -e
winget install --id Typst.Typst -e
```

## 用法
1. 把要处理的 PDF 放进本目录，改 `config.py` 的 `INPUT_PDF`（或用 `-p` 传路径）。
2. 双击 `run.bat`（后台 OCR，全书要一阵；首次会下模型）。
3. 看 `output\ocr.done.flag` 出现且 `status: ok`。
4. 双击 `make_pdf.bat`，在 `output\` 得到最终 PDF。

## 参数
- 分批大小、后端、语言见 `config.py`；`run_ocr.py -h` 看 CLI。
- 换成高精度 VLM 后端：`run_ocr.py -b vlm-engine`（Windows 上依赖 vLLM，可能需 WSL2）。

## 续跑
中断后重跑 `run.bat` 会跳过 `output\batches\` 里已带 `.batch.done` 的批次。
````

- [ ] **Step 4: 校验脚本可跑**

Run: `.\.venv-ocr\Scripts\python.exe run_ocr.py -h`
Expected: 打印 argparse 帮助，无异常。

---

### Task 7: 全书正式 OCR（后台长任务）+ 出成品

**Files:** 无新文件；执行既有脚本。

- [ ] **Step 1: 后台启动全书 OCR**

Run（后台，立即退出当前 turn，不轮询）：
```powershell
$env:MINERU_MODEL_SOURCE="modelscope"
.\.venv-ocr\Scripts\python.exe run_ocr.py
```
用 `Bash(run_in_background=True)` 或 `run.bat` 启动。预计 GPU 上约 10–25 分钟。

- [ ] **Step 2: 完成后核对 flag**

下次进来读 `output\ocr.done.flag`：`status: ok`、`pages` 约 700、`failed_batches: []`。
若有失败批次，删掉对应 `output\batches\<范围>\` 后重跑 `run_ocr.py`（只补那几批）。

- [ ] **Step 3: 合并 + 渲染出最终 PDF**

Run:
```powershell
.\.venv-ocr\Scripts\python.exe -c "import merge_md, config; merge_md.merge(config.OUTPUT_DIR)"
.\.venv-ocr\Scripts\python.exe make_pdf.py
```
Expected: `output\中国政治思想史.pdf` 生成。

- [ ] **Step 4: 人工终检**

打开成品 PDF：通读抽查几章，确认文字准确、章节标题层级对、脚注保留且成块、中英混排无误、可搜索、体积远小于 148 MB。塞进读书软件试读一章。

---

## 自查（Self-Review）

- **Spec 覆盖**：目标（GPU OCR / 干净可搜索 PDF / 分批可续跑 / 自包含目录）→ Task 1-7 全覆盖；脚注保留 → merge 不拆脚注块、渲染保留；强制 CUDA → Task 3 `assert_cuda`；长任务 flag → Task 3 `_write_flag` + Task 7 后台。
- **占位符**：无 TBD/TODO；每个代码步骤含完整代码。
- **类型一致**：`make_batches/batch_dir/is_batch_done/mark_batch_done` 在 Task 2 定义，Task 3 按同名同签名消费；`merge` 返回 `output_dir/book.md`，Task 5/6/7 一致引用；`build_mineru_cmd` 的 `-e` = `end_exclusive-1` 与测试一致。
- **风险备注**：`pandoc --pdf-engine=typst` + `mainfont` 的 CJK 渲染在 Task 5 Step 6 用真实 2 页验收；若字体不生效，退路是生成中间 `.typ` 并在模板里显式 `#set text(font: "SimSun")`。
