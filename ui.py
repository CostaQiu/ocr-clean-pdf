"""OCR 图形界面 — 现代黄色主题版。

选扫描 PDF(可多选，同目录多本) → 输出 clean_<名>.pdf，带进度条。
后台线程跑 OCR，界面不卡死。
"""

import sys

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

# ── 黄色主题色板 ──
YELLOW_BG = "#FFFBEB"          # 暖白背景
YELLOW_CARD = "#FFFFFF"        # 卡片白
YELLOW_BORDER = "#FDE68A"      # 浅金边框
YELLOW_PRIMARY = "#F59E0B"     # 琥珀金主色
YELLOW_DARK = "#D97706"        # 深琥珀
YELLOW_LIGHT = "#FEF3C7"       # 浅琥珀底
YELLOW_TEXT = "#92400E"        # 棕色文字
YELLOW_GRADIENT_FROM = "#F59E0B"
YELLOW_GRADIENT_TO = "#B45309"
FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Ubuntu"


def _setup_style():
    """为 ttk 控件注册黄色主题样式。"""
    style = ttk.Style()
    # 尝试用 'clam' 主题（支持自定义色）
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", font=(FONT_FAMILY, 10))
    style.configure(
        "TFrame", background=YELLOW_BG
    )
    style.configure(
        "Card.TFrame", background=YELLOW_CARD, relief="solid", borderwidth=1
    )

    # 按钮
    style.configure(
        "Accent.TButton",
        background=YELLOW_PRIMARY,
        foreground="white",
        borderwidth=0,
        focusthickness=3,
        focuscolor="none",
        font=(FONT_FAMILY, 10, "bold"),
        padding=(20, 8),
        relief="flat",
    )
    style.map(
        "Accent.TButton",
        background=[("active", YELLOW_DARK), ("disabled", "#D1D5DB")],
        foreground=[("disabled", "#9CA3AF")],
    )

    style.configure(
        "Secondary.TButton",
        background=YELLOW_LIGHT,
        foreground=YELLOW_TEXT,
        borderwidth=1,
        focusthickness=0,
        font=(FONT_FAMILY, 9),
        padding=(14, 6),
        relief="solid",
    )
    style.map(
        "Secondary.TButton",
        background=[("active", "#FDE68A")],
    )

    # 标签
    style.configure(
        "TLabel",
        background=YELLOW_BG,
        foreground="#334155",
        font=(FONT_FAMILY, 10),
    )
    style.configure(
        "Accent.TLabel",
        background=YELLOW_BG,
        foreground=YELLOW_TEXT,
        font=(FONT_FAMILY, 10, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=YELLOW_BG,
        foreground="#475569",
        font=(FONT_FAMILY, 9),
    )

    # 进度条
    style.configure(
        "Yellow.Horizontal.TProgressbar",
        background=YELLOW_PRIMARY,
        troughcolor=YELLOW_LIGHT,
        bordercolor=YELLOW_BORDER,
        lightcolor=YELLOW_DARK,
        darkcolor=YELLOW_DARK,
        thickness=10,
    )

    # Entry
    style.configure(
        "TEntry",
        fieldbackground="white",
        borderwidth=1,
        bordercolor=YELLOW_BORDER,
        padding=(8, 4),
        font=(FONT_FAMILY, 10),
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", YELLOW_PRIMARY)],
    )


def _draw_header(canvas, width):
    """在 Canvas 上画渐变色头部横幅。"""
    canvas.delete("all")
    h = 72
    canvas.config(width=width, height=h, highlightthickness=0)
    # 近似渐变：画叠色矩形
    for i in range(80):
        ratio = i / 80
        r = int(0xF5 - (0xF5 - 0xB4) * ratio)
        g = int(0x9E - (0x9E - 0x53) * ratio)
        b = int(0x0B - (0x0B - 0x09) * ratio)
        color = f"#{r:02x}{g:02x}{b:02x}"
        x0 = int(width * ratio / 80 * i)
        x1 = int(width * (ratio + 1 / 80))
        canvas.create_rectangle(x0, 0, x1, h, fill=color, outline="")
    canvas.create_text(
        width // 2,
        28,
        text="OCR 智能转换",
        fill="white",
        font=(FONT_FAMILY, 18, "bold"),
    )
    canvas.create_text(
        width // 2,
        52,
        text="扫描 PDF → 可搜索的干净 PDF",
        fill="white",
        font=(FONT_FAMILY, 10),
    )


class OcrApp:
    def __init__(self, root):
        self.root = root
        root.title("扫描 PDF → 干净 PDF（本地 OCR）")
        root.geometry("680x580")
        root.configure(bg=YELLOW_BG)
        self.pdfs = []
        self.q = queue.Queue()
        self.running = False

        _setup_style()
        pad = dict(padx=16, pady=5)

        # ── 顶部横幅 ──
        self.header_canvas = tk.Canvas(root, bg=YELLOW_BG, highlightthickness=0)
        self.header_canvas.pack(fill="x", padx=0, pady=(0, 8))
        self.header_canvas.bind("<Configure>", self._on_resize_header)

        # ── 文件选择 ──
        card1 = tk.Frame(root, bg=YELLOW_CARD, highlightbackground=YELLOW_BORDER, highlightthickness=1)
        card1.pack(fill="x", **pad)
        card1.pack_propagate(False)

        row1 = tk.Frame(card1, bg=YELLOW_CARD)
        row1.pack(fill="x", pady=8, padx=12)

        ttk.Button(
            row1, text="选择 PDF（可多选）", style="Accent.TButton",
            command=self.choose_pdfs,
        ).pack(side="left")

        self.files_var = tk.StringVar(value="未选择文件")
        tk.Label(
            row1, textvariable=self.files_var, fg=YELLOW_TEXT,
            bg=YELLOW_CARD, font=(FONT_FAMILY, 10),
        ).pack(side="left", padx=12)

        # ── 输出目录 ──
        card2 = tk.Frame(root, bg=YELLOW_CARD, highlightbackground=YELLOW_BORDER, highlightthickness=1)
        card2.pack(fill="x", **pad)
        card2.pack_propagate(False)

        row2 = tk.Frame(card2, bg=YELLOW_CARD)
        row2.pack(fill="x", pady=8, padx=12)

        tk.Label(
            row2, text="输出目录：", fg="#334155", bg=YELLOW_CARD,
            font=(FONT_FAMILY, 10),
        ).pack(side="left")
        self.outdir_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.outdir_var, font=(FONT_FAMILY, 10)).pack(
            side="left", fill="x", expand=True, padx=8
        )
        ttk.Button(
            row2, text="浏览", style="Secondary.TButton",
            command=self.choose_outdir,
        ).pack(side="left")

        # ── 开始按钮 ──
        btn_frame = tk.Frame(root, bg=YELLOW_BG)
        btn_frame.pack(fill="x", **pad)
        self.start_btn = ttk.Button(
            btn_frame, text="开始转换", style="Accent.TButton",
            command=self.start,
        )
        self.start_btn.pack(pady=4)

        # ── 进度条 ──
        self.bar = ttk.Progressbar(
            root, style="Yellow.Horizontal.TProgressbar", mode="determinate", maximum=100
        )
        self.bar.pack(fill="x", **pad)

        self.status_var = tk.StringVar(value="就绪。成品命名 clean_<原名>.pdf")
        ttk.Label(root, textvariable=self.status_var, style="Status.TLabel").pack(**pad)

        # ── 日志 ──
        self.log = scrolledtext.ScrolledText(
            root, height=11, state="disabled", wrap="word",
            bg="white", fg="#1E293B",
            font=("Consolas", 9) if sys.platform == "win32" else ("Ubuntu Mono", 9),
            relief="solid", borderwidth=1,
        )
        self.log.pack(fill="both", expand=True, **pad)

        self.root.after(100, self._poll)

    def _on_resize_header(self, event):
        _draw_header(self.header_canvas, event.width)

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
            self.outdir_var.set(str(self.pdfs[0].parent))
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
