"""OCR 图形界面：选扫描 PDF(可多选，同目录多本) → 输出 clean_<名>.pdf，带进度条。

后台线程跑 OCR，界面不卡死；进度条按总页数推进。
运行：双击 run_ui.bat（用 .venv-ocr）。
"""

import sys

# UTF-8 控制台，避免中文日志在 cp1252 控制台崩溃
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import queue
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import config
import run_ocr
import merge_md
import make_pdf


class OcrApp:
    def __init__(self, root):
        self.root = root
        root.title("扫描 PDF → 干净 PDF（本地 OCR）")
        root.geometry("660x540")
        self.pdfs = []
        self.q = queue.Queue()
        self.running = False

        pad = dict(padx=12, pady=6)

        # 文件选择
        top = ttk.Frame(root)
        top.pack(fill="x", **pad)
        ttk.Button(top, text="选择 PDF（可多选）", command=self.choose_pdfs).pack(
            side="left"
        )
        self.files_var = tk.StringVar(value="未选择文件")
        ttk.Label(top, textvariable=self.files_var, foreground="#555").pack(
            side="left", padx=10
        )

        # 输出目录（默认 = 源 PDF 所在目录）
        outf = ttk.Frame(root)
        outf.pack(fill="x", **pad)
        ttk.Label(outf, text="输出目录：").pack(side="left")
        self.outdir_var = tk.StringVar()
        ttk.Entry(outf, textvariable=self.outdir_var).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(outf, text="浏览", command=self.choose_outdir).pack(side="left")

        # 开始
        self.start_btn = ttk.Button(root, text="开始转换", command=self.start)
        self.start_btn.pack(**pad)

        # 进度条 + 状态
        self.bar = ttk.Progressbar(root, mode="determinate", maximum=100)
        self.bar.pack(fill="x", **pad)
        self.status_var = tk.StringVar(value="就绪。成品命名 clean_<原名>.pdf")
        ttk.Label(root, textvariable=self.status_var).pack(**pad)

        # 日志
        self.log = scrolledtext.ScrolledText(
            root, height=13, state="disabled", wrap="word"
        )
        self.log.pack(fill="both", expand=True, **pad)

        self.root.after(100, self._poll)

    # ---------- 交互 ----------
    def choose_pdfs(self):
        files = filedialog.askopenfilenames(
            title="选择扫描 PDF（可多选，同目录多本）",
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if not files:
            return
        self.pdfs = [Path(f) for f in files]
        self.files_var.set(f"已选 {len(self.pdfs)} 本")
        if not self.outdir_var.get():
            self.outdir_var.set(str(self.pdfs[0].parent))  # 默认原目录
        self._log("已选择：\n" + "\n".join(f"  · {p.name}" for p in self.pdfs))

    def choose_outdir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.outdir_var.set(d)

    def start(self):
        if self.running:
            return
        if not self.pdfs:
            messagebox.showwarning("提示", "请先选择至少一本 PDF。")
            return
        outdir = self.outdir_var.get().strip()
        if not outdir:
            messagebox.showwarning("提示", "请设置输出目录。")
            return
        try:
            import torch

            if not torch.cuda.is_available():
                messagebox.showerror(
                    "错误", "未检测到 CUDA GPU。请确认 .venv-ocr 装的是 CUDA 版 torch。"
                )
                return
        except ImportError:
            messagebox.showerror("错误", "未安装 torch。")
            return

        self.running = True
        self.start_btn.config(state="disabled")
        self.bar["value"] = 0
        threading.Thread(
            target=self._worker, args=(list(self.pdfs), Path(outdir)), daemon=True
        ).start()

    # ---------- 后台线程 ----------
    def _worker(self, pdfs, outdir):
        try:
            per = [run_ocr.count_pages(p) for p in pdfs]
            grand = sum(per) or 1
            offset = 0
            for idx, pdf in enumerate(pdfs):
                name = pdf.stem
                work = outdir / "_ocr_work" / name
                self.q.put(
                    ("status", f"第 {idx + 1}/{len(pdfs)} 本《{name}》· 开始 OCR…")
                )

                def cb(done, total, bi, nb, running, _off=offset, _n=name, _i=idx):
                    pct = (_off + done) / grand * 100
                    self.q.put(("progress", pct))
                    state = "处理中" if running else "完成"
                    self.q.put(
                        (
                            "status",
                            f"第 {_i + 1}/{len(pdfs)} 本《{_n}》· 批 {bi}/{nb} {state} · {pct:.0f}%",
                        )
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
                if not result["ok"]:
                    self.q.put(("log", f"⚠《{name}》失败批次：{result['failed']}"))

                self.q.put(("status", f"《{name}》· 合并 + 渲染 PDF…"))
                merge_md.merge(work)
                out_pdf = outdir / f"clean_{name}.pdf"
                make_pdf.render(work / "book.md", out_pdf)
                self.q.put(("log", f"✅《{name}》→ {out_pdf}"))
                offset += per[idx]

            self.q.put(("progress", 100))
            self.q.put(("done", f"全部完成，共 {len(pdfs)} 本。"))
        except Exception:
            self.q.put(("error", traceback.format_exc()))

    # ---------- 主线程刷新 ----------
    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "progress":
                    self.bar["value"] = payload
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "log":
                    self._log(payload)
                elif kind == "done":
                    self.status_var.set(payload)
                    self._log("🎉 " + payload)
                    self._finish()
                elif kind == "error":
                    self._log("❌ 出错：\n" + payload)
                    self.status_var.set("出错，见日志")
                    messagebox.showerror("转换出错", payload.strip().splitlines()[-1])
                    self._finish()
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _finish(self):
        self.running = False
        self.start_btn.config(state="normal")

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main():
    root = tk.Tk()
    OcrApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
