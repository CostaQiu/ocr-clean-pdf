# 扫描版 PDF → 干净可搜索 PDF(本地 GPU OCR)设计文档

- 日期:2026-07-05
- 项目位置:`C:\python_code\OCR\`(独立项目,整目录可拷给他人)
- 首个目标文件:`C:\python_code\OCR\中国政治思想史 (萧公权) (Z-Library).pdf`(148 MB,扫描版,约 700 页,中英混排印刷体)——已拷入项目内,自包含
- 成品:重新排版的、纯文字、可搜索的干净 PDF(**非**扫描图),便于塞进读书软件 + 喂 TTS

## 1. 目标与非目标

**目标**
- 用本地显卡(RTX 4080 SUPER 16GB)对扫描 PDF 做 OCR,提取干净正文。
- 输出一份重新排版的、文字型、可搜索的 PDF(CJK 字体),体积远小于原扫描件。
- 大文件按页码范围分批处理,可续跑(中途中断后重跑跳过已完成批次)。
- 作为独立通用工具:接受任意 PDF 路径为输入,不绑定某一本书。

**非目标**
- 不保留扫描图原始版面外观(那是"可搜索 PDF 叠加文字层"路线,已否决)。
- 不做 CPU 回退(本期只做 GPU 版,YAGNI;缺 CUDA 直接报错)。
- 不追求复杂表格/公式的完美还原(本书版面规整,pipeline 后端足够;个别页可后续用 vlm 补跑)。

## 2. 关键决策(含理由)

| 决策点 | 选择 | 理由 |
|---|---|---|
| OCR 工具 | **MinerU** | CJK 版面识别专家,直出 markdown + 版面信息 |
| OCR 后端 | **`pipeline`**(PaddleOCR + 版面检测) | 原生 Windows + CUDA-torch 稳定;`vlm` 后端依赖 vLLM,Windows 装不上。本书版面规整,pipeline 质量足够 |
| 算力 | **本地 GPU,强制 CUDA** | `torch.cuda.is_available()` 非 True 直接报错,绝不静默回退 CPU |
| 大文件处理 | **按页码范围分批(`-s/-e`)** | 不物理切分 148MB 文件;MinerU 原生支持页范围。分批 = 内存有界 + 可续跑 |
| 语言 | **`-l ch`** | PaddleOCR 中文模型内置英文/数字/标点识别,中英混排同行可一起认出,无需分两遍 |
| md → PDF | **Pandoc + Typst** | 两个自包含二进制,原生 CJK,排版干净;避开 LaTeX/MiKTeX 与 WeasyPrint/GTK 的 Windows 安装坑 |
| 环境隔离 | **独立 venv `.venv-ocr`(Py 3.12)** | MinerU 拖入自己的 torch/paddle;独立环境,不碰用户其他项目 |
| 长任务 | **后台运行 + `ocr.done.flag`** | 700 页 OCR 远超 2 分钟,遵循长任务铁律:不 sleep 轮询,后台跑完写 flag |

## 3. 流水线

```
输入扫描 PDF   (例:148 MB, ~700 页)
  │
  1. probe: PyMuPDF 读总页数
  │
  2. OCR(分批, 每批 N 页, 默认 N=40):
  │     for 每个页范围 [s, e):
  │        若该批 done-marker 存在 → 跳过(可续跑)
  │        mineru -p <pdf> -o output/batches/<s>_<e> -b pipeline -m ocr -l ch -s s -e e-1
  │        写该批 done-marker
  │
  3. merge: 按页序拼接各批 markdown → output/book.md
  │
  4. cleanup: 去掉 running header/footer 与页码, 重接被切断的行
  │
  5. render: book.md --(Pandoc)--> Typst --(typst compile)--> output/<书名>.pdf
```

## 4. 目录结构

```
C:\python_code\OCR\           # 项目根 = 工具本身
├── README.md                 # 安装(CUDA torch / pandoc / typst)+ 运行说明
├── requirements.txt          # mineru[core] 等(不含 torch,torch 单独按 CUDA 装)
├── config.py                 # 默认参数:输入路径、批大小、后端、设备、输出目录
├── run_ocr.py                # 编排器:CUDA 自检 → 分批调 mineru → 可续跑 → 写 ocr.done.flag
├── merge_md.py               # 合并各批 markdown + 清理页眉页脚页码 + 重接断行
├── make_pdf.py               # markdown → Pandoc → Typst → 干净 PDF
├── run.bat                   # 一键:激活 .venv-ocr 后台跑 run_ocr.py,立即退出
├── docs/specs/               # 本设计文档所在
├── tests/                    # pytest 单元测试
├── .venv-ocr/                # 独立虚拟环境(不提交)
└── output/
    ├── batches/<s>_<e>/      # 各批 MinerU 原始产物(markdown + images + done-marker)
    ├── book.md               # 合并清理后的全书 markdown
    ├── ocr.done.flag         # ok/fail + 已处理页数 + 耗时摘要
    └── <书名>.pdf            # 最终成品
```

## 5. 各模块接口与职责

### `config.py`
集中默认值,供 CLI 覆盖:
- `input_pdf: Path`(默认 `C:\python_code\OCR\中国政治思想史 (萧公权) (Z-Library).pdf`)、`output_dir: Path`
- `batch_size: int = 40`
- `backend: str = "pipeline"`(可切 `vlm-engine`)
- `lang: str = "ch"`
- `device: str = "cuda"`(本期固定;缺 CUDA 报错)

### `run_ocr.py`(编排器,后台运行)
- **启动即自检**:`import torch; assert torch.cuda.is_available()`,否则打印明确错误并 `sys.exit(1)`。
- 用 PyMuPDF 读总页数,生成页范围批次列表。
- 逐批以子进程调用 `mineru` CLI(`subprocess.run`);每批输出独立目录。
- **可续跑**:每批成功后在其目录写 `.batch.done`;重跑时若存在则跳过。
- 全部批次完成后写 `output/ocr.done.flag`,内容含 `ok/fail`、总页数、总耗时、失败批次列表。
- 输入:CLI 参数(input/output/batch-size/backend/start/end)。依赖:`torch`、`fitz`(PyMuPDF)、`mineru` CLI、`config`。

### `merge_md.py`
- 输入:`output/batches/*/` 下各批 markdown(按页范围排序)。
- 输出:`output/book.md`。
- 清理规则:剥离每页重复出现的页眉/页脚行与孤立页码;把跨页/跨块被硬换行切断的句子重新接上;保留章节标题层级。
- **脚注策略:保留**。MinerU 版面检测已将脚注区与正文分离;保留脚注内容,在 markdown/PDF 中作为独立的脚注块呈现(不与正文混排),使日后 TTS 可选择性跳过。
- 职责单一:只做"合并 + 文本清理",不碰 OCR、不碰渲染。

### `make_pdf.py`
- 输入:`output/book.md`。
- 输出:`output/<书名>.pdf`。
- 步骤:`pandoc book.md -o book.typ`(生成 Typst)→ 注入一个带 CJK 字体(如"宋体/微软雅黑")与合理页边距、行距的 Typst 模板 → `typst compile book.typ 最终.pdf`。
- 启动检查:`pandoc`、`typst` 二进制在 PATH,否则给出安装提示并退出。

### `run.bat`
- 硬编码 `.venv-ocr` 的 python 路径。
- 后台方式启动 `run_ocr.py`(遵循长任务约定,不阻塞、不轮询),立即返回;用户稍后凭 `ocr.done.flag` 判断状态,再手动跑 `merge_md.py` + `make_pdf.py`(或 `make_pdf.bat`)。

## 6. 错误处理

- **无 CUDA**:`run_ocr.py` 启动自检失败 → 明确报错("未检测到 CUDA GPU / torch 可能装成了 CPU 版")→ 退出,不跑。
- **单批 MinerU 失败**:记录该批为 fail,继续后续批次(不让一批坏页拖垮整本);最终 `ocr.done.flag` 汇总失败批次列表,便于定点重跑。
- **缺 pandoc/typst**:`make_pdf.py` 启动即检测,缺则打印安装命令并退出。
- **续跑安全**:写 done-marker 前确认 MinerU 返回码为 0 且输出目录有 markdown。

## 7. 测试

- **单元测试**(pytest,`tests/`):
  - 页范围分批逻辑:给定总页数与批大小,生成的批次覆盖且不重叠。
  - 续跑跳过逻辑:存在 done-marker 的批次被跳过。
  - `merge_md` 清理:构造含页眉/页码/断行的样例 markdown,断言清理后正确。
- **冒烟测试**:对原书**前 2 页**跑完整流水线(OCR → merge → PDF),人工看输出 PDF 文字是否正确、中英混排是否完好。全书正式跑之前必过这一关。
- CUDA 自检、subprocess 调 mineru 等用 mock 或小页范围验证。

## 8. 交付顺序(供实现计划参考)

1. 建 `C:\python_code\OCR\` + `.venv-ocr` + 装 CUDA torch + `mineru[core]`,`mineru --version` 通。
2. `config.py` + `run_ocr.py`(自检 + 分批 + 续跑 + flag),前 2 页冒烟。
3. `merge_md.py` + 清理规则 + 单测。
4. 装 pandoc + typst,`make_pdf.py` + CJK 模板,前 2 页出 PDF 验收。
5. `run.bat` + README。
6. 全书后台正式跑(后台 + flag,退出当前 turn)。

## 已确认

- **脚注策略**:保留(作为独立脚注块,与正文分离)。
- **批大小**:默认 40 页/批,可调。
