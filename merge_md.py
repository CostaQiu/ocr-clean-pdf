"""从 MinerU 的 content_list.json 组装干净 markdown。

MinerU 默认 .md 会丢弃脚注(page_footnote)。本模块改从 content_list.json
按块类型组装:正文/标题保留,书眉(header)与页码(page_number)丢弃,
脚注(page_footnote)按页作为独立块附在正文后 —— 满足"保留脚注"。
"""

import json
import re
from itertools import groupby
from pathlib import Path

FOOTNOTE_SEP = "\n\n---\n\n"  # 脚注与正文的分隔


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def find_batch_content_json(batch_dir: Path) -> Path | None:
    js = sorted(batch_dir.rglob("*_content_list.json"))
    return js[0] if js else None


def _blocks_to_markdown(blocks: list) -> str:
    """按页组装:正文+标题保留,脚注附在每页末,书眉/页码丢弃。"""
    parts = []
    for _page_idx, page_blocks in groupby(blocks, key=lambda b: b.get("page_idx")):
        body = []
        foots = []
        for b in page_blocks:
            t = b.get("type")
            txt = (b.get("text") or "").strip()
            if not txt:
                continue
            if t == "text":
                lvl = b.get("text_level")
                if lvl:
                    body.append("#" * int(lvl) + " " + txt)
                else:
                    body.append(txt)
            elif t == "page_footnote":
                foots.append(txt)
            # header / page_number / 其它 → 丢弃
        page_md = "\n\n".join(body)
        if foots:
            page_md += FOOTNOTE_SEP + "\n\n".join(foots)
        if page_md.strip():
            parts.append(page_md)
    return "\n\n".join(parts)


def parse_content_list(json_path: Path) -> str:
    blocks = json.loads(json_path.read_text(encoding="utf-8"))
    return _blocks_to_markdown(blocks)


def merge(output_dir: Path) -> Path:
    batches_dir = output_dir / "batches"
    # 目录名零填充,字典序 == 页序
    batch_dirs = sorted(p for p in batches_dir.iterdir() if p.is_dir())
    parts = []
    for bd in batch_dirs:
        js = find_batch_content_json(bd)
        if js is not None:
            md = parse_content_list(js)
            if md.strip():
                parts.append(md)
    merged = collapse_blank_lines("\n\n".join(parts))
    out = output_dir / "book.md"
    out.write_text(merged, encoding="utf-8")
    return out
