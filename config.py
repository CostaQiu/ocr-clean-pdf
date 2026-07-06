"""OCR 流水线默认配置。CLI 参数可覆盖这些值。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
INPUT_PDF = PROJECT_ROOT / "中国政治思想史 (萧公权) (Z-Library).pdf"
OUTPUT_DIR = PROJECT_ROOT / "output"

BATCH_SIZE = 180  # 每批页数(大批 → 更少子进程启动开销,提速关键)
BACKEND = "pipeline"  # MinerU 后端；可切 "vlm-engine"
LANG = "ch"  # PaddleOCR 语言(中文模型含英文识别)
DEVICE = "cuda"  # 本期固定 GPU；缺 CUDA 报错

# 表格/公式检测：默认开,换取广泛适用(带表格/公式的书也能处理)。
# 速度已足够(批量 180 的提速足以覆盖这点开销)。纯文字书想再快可手动设 False。
FORMULA_ENABLE = True  # 公式检测(开)
TABLE_ENABLE = True  # 表格检测(开)

# 可选提速(默认不启用)：设环境变量 MINERU_VIRTUAL_VRAM_SIZE=32 会把 GPU 批量
# 从 batch_ratio=8 翻到 16。但这是对 16G 卡"谎报"32G 显存,有 OOM 风险,且 GPU
# 本非瓶颈,故默认不设。想试就在 run.bat 里放开那一行。
