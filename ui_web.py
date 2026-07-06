"""OCR 网页界面（Gradio）：选文件夹里的扫描 PDF(表格式，可排序，多选) → clean_<原名>.pdf。

在浏览器里打开(本地 localhost)。自己列目录里的 PDF(不依赖系统文件对话框)，
表格显示大小/修改日期、可排序、默认不全选。
运行：双击 run_ui.bat（用 .venv-ocr）。
"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from datetime import datetime
from pathlib import Path

import pandas as pd
import gradio as gr

import config
import run_ocr
import merge_md
import make_pdf

COLS = ["选择", "文件名", "大小", "修改日期"]
SORT_KEYS = ["文件名", "大小", "修改日期"]


def _human_size(n: int) -> str:
    x = float(n)
    for u in ["B", "KB", "MB", "GB"]:
        if x < 1024 or u == "GB":
            return f"{x:.0f} {u}" if u == "B" else f"{x:.1f} {u}"
        x /= 1024
    return f"{x:.1f} GB"


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame([], columns=COLS)


def _as_df(value) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    if not value:
        return _empty_df()
    return pd.DataFrame(value, columns=COLS)


def _build_rows(
    folder: str, names, sort_key: str, ascending: bool, selected: set
) -> pd.DataFrame:
    """按 names 读取每个文件的大小/修改时间，排序，组装表格；selected 里的名字打勾。"""
    p = Path(folder)
    items = []
    for name in names:
        f = p / name
        try:
            st = f.stat()
            size, mtime = st.st_size, st.st_mtime
        except OSError:
            size, mtime = 0, 0.0
        items.append((name, size, mtime))
    keyfn = {
        "文件名": lambda t: t[0],
        "大小": lambda t: t[1],
        "修改日期": lambda t: t[2],
    }.get(sort_key, lambda t: t[0])
    items.sort(key=keyfn, reverse=not ascending)
    rows = [
        [
            name in selected,
            name,
            _human_size(size),
            datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else "",
        ]
        for (name, size, mtime) in items
    ]
    return pd.DataFrame(rows, columns=COLS)


def _selected_from(df) -> set:
    df = _as_df(df)
    if len(df) == 0:
        return set()
    mask = df["选择"].astype(bool)
    return set(df.loc[mask, "文件名"].tolist())


def browse_folder():
    """弹出 Windows 原生文件夹选择框，返回所选路径（子进程，避开线程问题）。"""
    import os
    import subprocess

    code = (
        "import sys; sys.stdout.reconfigure(encoding='utf-8');"
        "import tkinter as tk; from tkinter import filedialog;"
        "r=tk.Tk(); r.withdraw(); r.attributes('-topmost', True);"
        "print(filedialog.askdirectory(title='选择书籍所在文件夹') or '', end='');"
        "r.destroy()"
    )
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    try:
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, timeout=300, env=env
        )
        folder = out.stdout.decode("utf-8", "replace").strip()
        return folder if folder else gr.update()
    except Exception:
        return gr.update()


def scan_folder(folder: str, sort_key: str, order: str):
    """列出文件夹里所有 PDF(大小写都认)，默认不全选；输出目录默认填该文件夹。"""
    folder = (folder or "").strip().strip('"')
    p = Path(folder)
    if not folder or not p.is_dir():
        return _empty_df(), "", "⚠ 文件夹不存在，请点「📁 浏览」选择或粘贴有效路径。"
    names = [f.name for f in p.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]
    if not names:
        return _empty_df(), folder, "该文件夹里没有 PDF。"
    df = _build_rows(folder, names, sort_key, order == "升序", selected=set())
    return (
        df,
        folder,
        f"✅ 找到 **{len(names)}** 个 PDF。勾选要转换的书（默认不选，可用下方「全选」）。",
    )


def sort_table(folder: str, df, sort_key: str, order: str):
    """按当前选择状态重排（保留已勾选）。"""
    df = _as_df(df)
    if len(df) == 0:
        return df
    names = df["文件名"].tolist()
    selected = _selected_from(df)
    return _build_rows(
        (folder or "").strip().strip('"'), names, sort_key, order == "升序", selected
    )


def set_all(df, value: bool):
    df = _as_df(df).copy()
    if len(df) == 0:
        return df
    df["选择"] = value
    return df


def convert(folder: str, df, outdir: str, progress=gr.Progress()):
    """对勾选的书依次 OCR → 合并 → 渲染 clean_<名>.pdf。

    生成器：边跑边 yield 状态到结果区(实时可见)；进度条按总页数推进。
    """
    folder = Path((folder or "").strip().strip('"'))
    selected = sorted(_selected_from(df))
    if not selected:
        yield "⚠ 请在表格「选择」列勾选至少一本书。"
        return
    outdir = Path((outdir or "").strip().strip('"') or folder)

    yield "⏳ **已开始转换**，正在检查 GPU、统计页数…"

    import time

    t0 = time.perf_counter()
    total_chars = 0

    try:
        import torch

        if not torch.cuda.is_available():
            yield "❌ 未检测到 CUDA GPU。请确认 .venv-ocr 装的是 CUDA 版 torch。"
            return
    except ImportError:
        yield "❌ 未安装 torch。"
        return

    books = [folder / n for n in selected]
    per = [run_ocr.count_pages(b) for b in books]
    grand = sum(per) or 1
    progress(0.0, desc="开始")
    yield (
        f"⏳ 共 **{len(books)}** 本、**{grand}** 页，开始 OCR。\n\n"
        f"（进度条见上方；每批约 180 页、需 1–2 分钟，批内进度条不动是正常的）"
    )

    logs = []
    offset = 0
    for idx, pdf in enumerate(books):
        name = pdf.stem
        work = outdir / "_ocr_work" / name
        done_head = ("\n\n".join(logs) + "\n\n---\n\n") if logs else ""
        yield done_head + f"⏳ 正在处理第 **{idx + 1}/{len(books)}** 本：《{name}》（{per[idx]} 页）— OCR 中…"

        def cb(done, total, bi, nb, running, _off=offset, _n=name, _i=idx):
            frac = (_off + done) / grand
            state = "处理中" if running else "完成"
            progress(
                frac, desc=f"第 {_i + 1}/{len(books)} 本《{_n}》· 批 {bi}/{nb} {state}"
            )

        result = run_ocr.run_all(
            pdf,
            work,
            config.BATCH_SIZE,
            config.BACKEND,
            config.LANG,
            config.FORMULA_ENABLE,
            config.TABLE_ENABLE,
            progress_cb=cb,
        )
        progress((offset + per[idx]) / grand, desc=f"《{name}》· 合并 + 渲染 PDF…")
        yield done_head + f"⏳ 《{name}》 OCR 完成，正在合并 + 渲染 PDF…"
        book_md = merge_md.merge(work)
        chars = len(book_md.read_text(encoding="utf-8"))
        total_chars += chars
        out_pdf = outdir / f"clean_{name}.pdf"
        make_pdf.render(work / "book.md", out_pdf)
        tail = f"（⚠ 失败批次 {result['failed']}）" if not result["ok"] else ""
        logs.append(f"✅ 《{name}》 → `{out_pdf}`  ({chars:,} 字){tail}")
        offset += per[idx]
        yield "\n\n".join(logs)

    progress(1.0, desc="完成")
    elapsed = int(time.perf_counter() - t0)
    mm, ss = divmod(elapsed, 60)
    elapsed_str = f"{mm} 分 {ss} 秒" if mm else f"{ss} 秒"
    yield (
        f"🎉 **全部完成，共 {len(books)} 本 · {grand} 页 · {total_chars:,} 字 · 耗时 {elapsed_str}**\n\n"
        + "\n\n".join(logs)
    )


def build():
    with gr.Blocks(title="扫描 PDF → 干净 PDF") as demo:
        gr.Markdown(
            "# 📖 扫描 PDF → 干净 PDF（本地 GPU OCR）\n"
            "选一个文件夹里的扫描书（可多选），本地显卡 OCR 成 **`clean_<原名>.pdf`**——"
            "重排版、可搜索、保留脚注、带目录。"
        )
        with gr.Row():
            folder = gr.Textbox(
                label="① 书籍所在文件夹",
                placeholder=r"点「📁 浏览」选文件夹，或直接粘贴路径如 D:\books",
                scale=3,
            )
            browse_btn = gr.Button("📁 浏览", scale=1)
            scan_btn = gr.Button("🔄 刷新列表", scale=1, variant="secondary")

        with gr.Row():
            sort_key = gr.Dropdown(SORT_KEYS, value="大小", label="排序依据", scale=2)
            order = gr.Radio(["升序", "降序"], value="降序", label="顺序", scale=2)
            select_all_btn = gr.Button("全选", scale=1)
            clear_btn = gr.Button("清空", scale=1)

        table = gr.Dataframe(
            headers=COLS,
            datatype=["bool", "str", "str", "str"],
            col_count=(4, "fixed"),
            column_widths=["8%", "60%", "14%", "18%"],
            interactive=True,
            wrap=True,
            label="② 选择要转换的书（勾选「选择」列；点上方排序）",
        )

        outdir = gr.Textbox(
            label="③ 输出目录（默认 = 上面的文件夹）",
            placeholder="留空则输出到源文件夹",
        )
        status = gr.Markdown()
        go = gr.Button("④ 开始转换", variant="primary")
        result = gr.Markdown()

        scan_out = [table, outdir, status]
        browse_btn.click(browse_folder, outputs=folder).then(
            scan_folder, inputs=[folder, sort_key, order], outputs=scan_out
        )
        scan_btn.click(scan_folder, inputs=[folder, sort_key, order], outputs=scan_out)
        folder.submit(scan_folder, inputs=[folder, sort_key, order], outputs=scan_out)

        sort_key.change(
            sort_table, inputs=[folder, table, sort_key, order], outputs=table
        )
        order.change(sort_table, inputs=[folder, table, sort_key, order], outputs=table)
        select_all_btn.click(lambda df: set_all(df, True), inputs=table, outputs=table)
        clear_btn.click(lambda df: set_all(df, False), inputs=table, outputs=table)

        go.click(
            lambda: gr.update(value="⏳ 转换中…请稍候", interactive=False),
            outputs=go,
        ).then(convert, inputs=[folder, table, outdir], outputs=result).then(
            lambda: gr.update(value="④ 开始转换", interactive=True), outputs=go
        )
    return demo


def main():
    import os

    demo = build().queue()
    _, local_url, _ = demo.launch(
        server_port=7860,
        inbrowser=False,
        theme=gr.themes.Soft(),
        prevent_thread_lock=True,
    )
    url = local_url or "http://127.0.0.1:7860"
    print(
        f"\n{'=' * 50}\n  界面已启动：{url}\n"
        f"  浏览器应已自动打开；若没有，手动访问上面的地址。\n{'=' * 50}\n",
        flush=True,
    )
    try:
        os.startfile(url)
    except Exception as e:
        print(f"（自动打开浏览器失败，请手动访问上面的地址）{e}", flush=True)
    demo.block_thread()


if __name__ == "__main__":
    main()
