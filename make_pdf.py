"""book.md → 干净可搜索 PDF：Pandoc 用 Typst 引擎渲染，CJK 字体。

用法：
    python make_pdf.py                       # 用 config 默认输出目录
    python make_pdf.py --md output/book.md --pdf output/书名.pdf
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import config

DEFAULT_FONT = "SimSun"  # Windows 自带宋体，覆盖 CJK

# winget 装完常见位置，PATH 未刷新时用作回退
_FALLBACK_DIRS = {
    "pandoc": Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc",
    "typst": Path(os.environ.get("LOCALAPPDATA", ""))
    / "Microsoft"
    / "WinGet"
    / "Links",
}


def _ensure_on_path(tool: str) -> bool:
    """tool 在 PATH 上返回 True；否则尝试已知安装目录补进 PATH。"""
    if shutil.which(tool) is not None:
        return True
    fallback_dir = _FALLBACK_DIRS.get(tool)
    if fallback_dir and (fallback_dir / f"{tool}.exe").exists():
        os.environ["PATH"] = str(fallback_dir) + os.pathsep + os.environ.get("PATH", "")
        return True
    return False


def check_tools() -> None:
    missing = [t for t in ("pandoc", "typst") if not _ensure_on_path(t)]
    if missing:
        sys.exit(
            f"错误：找不到 {', '.join(missing)}。请安装：\n"
            "  winget install --id JohnMacFarlane.Pandoc -e\n"
            "  winget install --id Typst.Typst -e\n"
            "装完重开终端以刷新 PATH。"
        )


def build_pandoc_cmd(book_md: Path, out_pdf: Path, font: str) -> list[str]:
    return [
        "pandoc",
        str(book_md),
        "-o",
        str(out_pdf),
        "--pdf-engine=typst",
        "-V",
        f"mainfont={font}",
        "-V",
        "fontsize=12pt",
        "--toc",  # 依 markdown 标题生成目录
    ]


def render(md_path: Path, pdf_path: Path, font: str = DEFAULT_FONT) -> Path:
    """把 markdown 渲染成 PDF。缺工具/缺输入/渲染失败均抛异常。返回 pdf_path。"""
    check_tools()
    if not md_path.exists():
        raise FileNotFoundError(f"找不到 {md_path}，请先跑 OCR + merge。")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_pandoc_cmd(md_path, pdf_path, font)
    print("[render]", " ".join(cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"渲染失败，pandoc 返回码 {proc.returncode}")
    print(f"[ok] 生成 {pdf_path}")
    return pdf_path


def main() -> None:
    ap = argparse.ArgumentParser(description="book.md → 干净 PDF（Pandoc+Typst）")
    ap.add_argument("--md", type=Path, default=config.OUTPUT_DIR / "book.md")
    ap.add_argument(
        "--pdf", type=Path, default=config.OUTPUT_DIR / "中国政治思想史.pdf"
    )
    ap.add_argument("--font", default=DEFAULT_FONT)
    args = ap.parse_args()

    try:
        render(args.md, args.pdf, args.font)
    except (FileNotFoundError, RuntimeError, SystemExit) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
