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


def build_mineru_cmd(
    pdf: Path,
    out: Path,
    start: int,
    end_exclusive: int,
    backend: str,
    lang: str,
    formula: bool = True,
    table: bool = True,
) -> list[str]:
    """MinerU 的 -e 含端点；我们的批 end 不含，故传 end_exclusive-1。

    formula/table 显式传给 MinerU 的 -f/-t（默认 True）；关掉可省 CPU 开销。
    """
    mineru = str(Path(sys.executable).with_name("mineru.exe"))
    return [
        mineru,
        "-p",
        str(pdf),
        "-o",
        str(out),
        "-b",
        backend,
        "-m",
        "ocr",
        "-l",
        lang,
        "-s",
        str(start),
        "-e",
        str(end_exclusive - 1),
        "-f",
        str(formula).lower(),
        "-t",
        str(table).lower(),
    ]


def _run_one_batch(
    pdf: Path,
    out_dir: Path,
    start: int,
    end_exclusive: int,
    backend: str,
    lang: str,
    formula: bool = True,
    table: bool = True,
) -> bool:
    """跑单批，成功（返回码 0 且产出 markdown）返回 True。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_mineru_cmd(
        pdf, out_dir, start, end_exclusive, backend, lang, formula, table
    )
    print(f"[batch {start:04d}-{end_exclusive:04d}] {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print(
            f"[batch {start:04d}-{end_exclusive:04d}] MinerU 返回码 {proc.returncode}"
        )
        return False
    if not list(out_dir.rglob("*.md")):
        print(f"[batch {start:04d}-{end_exclusive:04d}] 未产出 markdown")
        return False
    return True


def run_all(
    pdf: Path,
    output_dir: Path,
    batch_size: int,
    backend: str,
    lang: str,
    formula: bool = True,
    table: bool = True,
    progress_cb=None,
) -> dict:
    """progress_cb(pages_done, total, batch_index, num_batches, running) 可选：
    running=True 表示该批开始处理，running=False 表示该批已完成。"""
    t0 = time.perf_counter()
    total = count_pages(pdf)
    batches = make_batches(total, batch_size)
    nb = len(batches)
    failed = []
    for i, (start, end) in enumerate(batches):
        if progress_cb:
            progress_cb(start, total, i + 1, nb, True)
        if is_batch_done(output_dir, start, end):
            print(f"[batch {start:04d}-{end:04d}] 已完成，跳过")
        else:
            ok = _run_one_batch(
                pdf,
                batch_dir(output_dir, start, end),
                start,
                end,
                backend,
                lang,
                formula,
                table,
            )
            if ok:
                mark_batch_done(output_dir, start, end)
            else:
                failed.append([start, end])
        if progress_cb:
            progress_cb(end, total, i + 1, nb, False)
    elapsed = time.perf_counter() - t0
    return {
        "ok": not failed,
        "pages": total,
        "failed": failed,
        "elapsed_s": round(elapsed, 1),
    }


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
    ap = argparse.ArgumentParser(
        description="扫描 PDF 分批 OCR（MinerU pipeline，GPU）"
    )
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
    result = run_all(
        args.pdf,
        args.output,
        args.batch_size,
        args.backend,
        args.lang,
        config.FORMULA_ENABLE,
        config.TABLE_ENABLE,
    )
    _write_flag(args.output, result)
    print(f"[done] {result}")


if __name__ == "__main__":
    main()
