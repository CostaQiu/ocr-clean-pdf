"""OCR 网页界面（Gradio）：选文件夹里的扫描 PDF → clean_<原名>.pdf。

现代风格界面，黄色/琥珀色主色调。
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

# ── 琥珀/黄色现代主题 ──
THEME = gr.themes.Soft(
    primary_hue=gr.themes.Color(
        c50="#FFFBEB",
        c100="#FEF3C7",
        c200="#FDE68A",
        c300="#FCD34D",
        c400="#FBBF24",
        c500="#F59E0B",  # 主色：琥珀金
        c600="#D97706",
        c700="#B45309",
        c800="#92400E",
        c900="#78350F",
        c950="#451A03",
    ),
    secondary_hue=gr.themes.Color(
        c50="#FFFBEB",
        c100="#FEF3C7",
        c200="#FDE68A",
        c300="#FCD34D",
        c400="#FBBF24",
        c500="#F59E0B",
        c600="#D97706",
        c700="#B45309",
        c800="#92400E",
        c900="#78350F",
        c950="#451A03",
    ),
    neutral_hue=gr.themes.Color(
        c50="#F8FAFC",
        c100="#F1F5F9",
        c200="#E2E8F0",
        c300="#CBD5E1",
        c400="#94A3B8",
        c500="#64748B",
        c600="#475569",
        c700="#334155",
        c800="#1E293B",
        c900="#0F172A",
        c950="#020617",
    ),
    spacing_size=gr.themes.sizes.spacing_lg,
    radius_size=gr.themes.sizes.radius_md,
    text_size=gr.themes.sizes.text_lg,
)

CUSTOM_CSS = """
/* ── 全局 ── */
.gradio-container { max-width: 1100px !important; margin: 2rem auto !important; }
body { background: #FFFBEB !important; }

/* ── 头部卡片 ── */
.app-header {
    background: linear-gradient(135deg, #F59E0B 0%, #D97706 50%, #B45309 100%);
    color: white; border-radius: 16px; padding: 2rem 2.5rem;
    margin-bottom: 2rem; box-shadow: 0 8px 24px rgba(245,158,11,0.25);
}
.app-header h1 { font-size: 1.75rem; font-weight: 700; margin: 0 0 0.4rem 0; color: white; letter-spacing: -0.01em; }
.app-header p { font-size: 0.95rem; margin: 0; opacity: 0.9; line-height: 1.5; }

/* ── 卡片容器 ── */
.card {
    background: white; border-radius: 14px; padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    border: 1px solid #FDE68A;
    margin-bottom: 1.25rem;
}

/* ── 按钮 ── */
button.primary, .gr-button.primary {
    background: linear-gradient(135deg, #F59E0B, #D97706) !important;
    border: none !important; color: white !important; font-weight: 600 !important;
    border-radius: 10px !important; padding: 0.6rem 1.8rem !important;
    transition: all 0.2s ease !important; box-shadow: 0 2px 8px rgba(245,158,11,0.3) !important;
}
button.primary:hover, .gr-button.primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(245,158,11,0.4) !important;
}

button.secondary, .gr-button.secondary {
    background: #FFFBEB !important;
    border: 1px solid #FDE68A !important;
    color: #92400E !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
button.secondary:hover, .gr-button.secondary:hover {
    background: #FEF3C7 !important;
    border-color: #FCD34D !important;
}

/* ── 输入框 ── */
.gr-box, .gr-input, .gr-text-input, input[type="text"], input[type="search"], textarea {
    border-radius: 10px !important;
    border: 1.5px solid #FDE68A !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.gr-box:focus, .gr-input:focus, input:focus, textarea:focus {
    border-color: #F59E0B !important;
    box-shadow: 0 0 0 3px rgba(245,158,11,0.15) !important;
}

/* ── 下拉 / 单选框 ── */
.gr-dropdown, .gr-radio {
    border-radius: 10px !important;
}

/* ── 数据表格 ── */
table.dataframe {
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid #FDE68A !important;
}
table.dataframe thead {
    background: linear-gradient(135deg, #FFFBEB, #FEF3C7) !important;
}
table.dataframe th {
    color: #92400E !important;
    font-weight: 600 !important;
    padding: 0.6rem 0.8rem !important;
    border-bottom: 2px solid #FDE68A !important;
}
table.dataframe td {
    padding: 0.5rem 0.8rem !important;
    border-bottom: 1px solid #FEF3C7 !important;
}
table.dataframe tr:hover td {
    background: #FFFBEB !important;
}

/* ── 进度条 ── */
.gr-progress .progress-bar {
    background: linear-gradient(90deg, #FCD34D, #F59E0B, #D97706) !important;
    border-radius: 100px !important;
    height: 8px !important;
}
.gr-progress {
    background: #FEF3C7 !important;
    border-radius: 100px !important;
    height: 8px !important;
    overflow: hidden;
}

/* ── Markdown 输出 ── */
.gr-markdown { line-height: 1.7; }
.gr-markdown h3 { color: #92400E; margin-top: 1rem; }

/* ── 复选框 ── */
.gr-checkbox input:checked {
    accent-color: #F59E0B !important;
}
"""


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
    folder = (folder or "").strip().strip('"')
    p = Path(folder)
    if not folder or not p.is_dir():
        return _empty_df(), "", "⚠ 文件夹不存在，请选择或粘贴有效路径。"
    names = [f.name for f in p.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]
    if not names:
        return _empty_df(), folder, "该文件夹里没有 PDF。"
    df = _build_rows(folder, names, sort_key, order == "升序", selected=set())
    return (
        df,
        folder,
        f"找到 **{len(names)}** 个 PDF。勾选要转换的书，点击下方开始。",
    )


def sort_table(folder: str, df, sort_key: str, order: str):
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


def convert(folder: str, df, outdir: str, force: bool = True, progress=gr.Progress()):
    import shutil

    folder = Path((folder or "").strip().strip('"'))
    selected = sorted(_selected_from(df))
    if not selected:
        yield "⚠ 请在表格中勾选至少一本书。"
        return
    outdir = Path((outdir or "").strip().strip('"') or folder)

    yield "⏳ 正在检查 GPU、统计页数…"

    import time

    t0 = time.perf_counter()
    total_chars = 0

    try:
        import torch

        if not torch.cuda.is_available():
            yield "❌ 未检测到 CUDA GPU。请确认安装的是 CUDA 版 torch。"
            return
    except ImportError:
        yield "❌ 未安装 torch。"
        return

    books = [folder / n for n in selected]
    per = [run_ocr.count_pages(b) for b in books]
    grand = sum(per) or 1
    progress(0.0, desc="开始")
    yield (
        f"共 **{len(books)}** 本、**{grand}** 页，开始 OCR。\n\n"
        f"每批约 180 页、需 1–2 分钟，批内进度条不动属正常现象。"
    )

    logs = []
    offset = 0
    for idx, pdf in enumerate(books):
        name = pdf.stem
        work = outdir / "_ocr_work" / name
        if force:
            shutil.rmtree(work, ignore_errors=True)
        done_head = ("\n\n".join(logs) + "\n\n---\n\n") if logs else ""
        yield done_head + f"⏳ 第 **{idx + 1}/{len(books)}** 本：《{name}》（{per[idx]} 页）— OCR 中…"

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
        f"🎉 **全部完成 · {len(books)} 本 · {grand} 页 · {total_chars:,} 字 · 耗时 {elapsed_str}**\n\n"
        + "\n\n".join(logs)
    )


def build():
    with gr.Blocks(
        theme=THEME, title="扫描 PDF → 干净 PDF", css=CUSTOM_CSS, head=None
    ) as demo:
        # ── 顶部横幅 ──
        gr.HTML(
            """<div class="app-header">
                <h1>OCR 智能转换</h1>
                <p>扫描版 PDF → 可搜索的干净 PDF · 本地 GPU 加速 · 保留脚注与目录</p>
            </div>"""
        )

        # ── 步骤 1：选择文件夹 ──
        with gr.Group(elem_classes="card"):
            gr.Markdown("### 📂 选择书籍文件夹")
            with gr.Row():
                folder = gr.Textbox(
                    label="文件夹路径",
                    placeholder="点「浏览」选文件夹，或直接粘贴路径",
                    scale=4,
                )
                browse_btn = gr.Button("浏览", scale=1, elem_classes="secondary")
                scan_btn = gr.Button("刷新列表", scale=1, elem_classes="secondary")

        # ── 步骤 2：筛选与选择 ──
        with gr.Group(elem_classes="card"):
            gr.Markdown("### 📋 选择要转换的 PDF")
            with gr.Row():
                sort_key = gr.Dropdown(SORT_KEYS, value="大小", label="排序依据", scale=2)
                order = gr.Radio(["升序", "降序"], value="降序", label="顺序", scale=2)
                select_all_btn = gr.Button("全选", scale=1, elem_classes="secondary")
                clear_btn = gr.Button("清空选择", scale=1, elem_classes="secondary")

            table = gr.Dataframe(
                headers=COLS,
                datatype=["bool", "str", "str", "str"],
                col_count=(4, "fixed"),
                column_widths=["8%", "60%", "14%", "18%"],
                interactive=True,
                wrap=True,
                label="勾选「选择」列来标记要转换的书籍",
            )

        # ── 步骤 3：输出设置 ──
        with gr.Group(elem_classes="card"):
            gr.Markdown("### ⚙️ 输出设置")
            outdir = gr.Textbox(
                label="输出目录",
                placeholder="留空则输出到源文件夹",
            )
            force = gr.Checkbox(
                value=True,
                label="强制重新扫描（覆盖缓存）— 取消勾选可续跑中断的任务",
            )

        # ── 步骤 4：执行 ──
        status = gr.Markdown()
        go = gr.Button("开始转换", variant="primary", size="lg")
        result = gr.Markdown()

        # ── 事件绑定 ──
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
        ).then(convert, inputs=[folder, table, outdir, force], outputs=result).then(
            lambda: gr.update(value="开始转换", interactive=True), outputs=go
        )
    return demo


def main():
    import os

    demo = build().queue()
    _, local_url, _ = demo.launch(
        server_port=7860,
        inbrowser=False,
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
