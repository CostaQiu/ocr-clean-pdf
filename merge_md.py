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
