"""OCR 网页界面（Gradio）：选文件夹里的扫描 PDF(可多选) → clean_<原名>.pdf。

在浏览器里打开(本地 localhost)。相比 Tkinter 更现代，且自己列目录里的 PDF，
不依赖系统文件对话框，保证目录里的书全列出来。
运行：双击 run_ui.bat（用 .venv-ocr）。
"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from pathlib import Path

import gradio as gr

import config
import run_ocr
import merge_md
import make_pdf


def browse_folder():
    """弹出 Windows 原生文件夹选择框，返回所选路径。

    用子进程跑 tkinter 对话框，避开 Gradio 工作线程里直接用 tkinter 的问题。
    """
    import os
    import subprocess
    import sys

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


def scan_folder(folder: str):
    """列出文件夹里所有 PDF(大小写都认)，默认全选；输出目录默认填该文件夹。"""
    folder = (folder or "").strip().strip('"')
    p = Path(folder)
    if not folder or not p.is_dir():
        return (
            gr.update(choices=[], value=[]),
            "",
            "⚠ 文件夹不存在，请粘贴有效路径（如 `D:\\books`）。",
        )
    pdfs = sorted(
        f.name for f in p.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"
    )
    if not pdfs:
        return gr.update(choices=[], value=[]), folder, "该文件夹里没有 PDF。"
    return (
        gr.update(choices=pdfs, value=pdfs),
        folder,
        f"✅ 找到 **{len(pdfs)}** 个 PDF（默认全选，可取消不需要的）。",
    )


def convert(folder: str, selected, outdir: str, progress=gr.Progress()):
    """对选中的书依次 OCR → 合并 → 渲染 clean_<名>.pdf。进度条按总页数推进。"""
    if not selected:
        return "⚠ 请至少勾选一本书。"
    folder = Path((folder or "").strip().strip('"'))
    outdir = Path((outdir or "").strip().strip('"') or folder)

    try:
        import torch

        if not torch.cuda.is_available():
            return "❌ 未检测到 CUDA GPU。请确认 .venv-ocr 装的是 CUDA 版 torch。"
    except ImportError:
        return "❌ 未安装 torch。"

    books = [folder / n for n in selected]
    per = [run_ocr.count_pages(b) for b in books]
    grand = sum(per) or 1
    logs = []
    offset = 0

    for idx, pdf in enumerate(books):
        name = pdf.stem
        work = outdir / "_ocr_work" / name

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
        merge_md.merge(work)
        out_pdf = outdir / f"clean_{name}.pdf"
        make_pdf.render(work / "book.md", out_pdf)
        tail = f"（⚠ 失败批次 {result['failed']}）" if not result["ok"] else ""
        logs.append(f"✅ 《{name}》 → `{out_pdf}` {tail}")
        offset += per[idx]

    progress(1.0, desc="完成")
    return f"🎉 全部完成，共 {len(books)} 本：\n\n" + "\n\n".join(logs)


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
                placeholder=r"点「浏览」选文件夹，或直接粘贴路径如 D:\books",
                scale=3,
            )
            browse_btn = gr.Button("📁 浏览", scale=1)
            scan_btn = gr.Button("扫描 PDF", scale=1, variant="secondary")
        files = gr.CheckboxGroup(label="② 选择要转换的书（默认全选）", choices=[])
        outdir = gr.Textbox(
            label="③ 输出目录（默认 = 上面的文件夹）",
            placeholder="留空则输出到源文件夹",
        )
        status = gr.Markdown()
        go = gr.Button("④ 开始转换", variant="primary")
        result = gr.Markdown()

        # 浏览 → 填路径 → 自动扫描列出 PDF
        browse_btn.click(browse_folder, outputs=folder).then(
            scan_folder, inputs=folder, outputs=[files, outdir, status]
        )
        scan_btn.click(scan_folder, inputs=folder, outputs=[files, outdir, status])
        folder.submit(scan_folder, inputs=folder, outputs=[files, outdir, status])
        go.click(convert, inputs=[folder, files, outdir], outputs=result)
    return demo


def main():
    import os

    demo = build().queue()
    # prevent_thread_lock 让 launch 立即返回,拿到本地地址后我们自己开浏览器
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
        os.startfile(url)  # Windows 最可靠的开默认浏览器方式
    except Exception as e:
        print(f"（自动打开浏览器失败，请手动访问上面的地址）{e}", flush=True)
    demo.block_thread()  # 保持服务运行


if __name__ == "__main__":
    main()
