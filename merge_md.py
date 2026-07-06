"""从 MinerU 的 content_list.json 组装干净 markdown。

MinerU 默认 .md 会丢弃脚注(page_footnote)。本模块改从 content_list.json
按块类型组装:正文/标题/图片(按原阅读顺序位置)保留,书眉(header)、页脚
(footer)、页码(page_number)丢弃,脚注(page_footnote)按页作为独立块附在
正文后 —— 满足"保留脚注 + 保留图片"。图片用绝对路径引用,渲染时嵌入。
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


def _blocks_to_markdown(blocks: list, base_dir: Path) -> str:
    """按页组装:正文/标题/图片按原顺序保留,脚注附每页末,书眉/页脚/页码丢弃。

    base_dir 是该 content_list.json 所在目录,用于把相对 img_path 解析成绝对路径。
    """
    parts = []
    for _page_idx, page_blocks in groupby(blocks, key=lambda b: b.get("page_idx")):
        body = []
        foots = []
        for b in page_blocks:
            t = b.get("type")
            if t == "text":
                txt = (b.get("text") or "").strip()
                if not txt:
                    continue
                lvl = b.get("text_level")
                body.append(("#" * int(lvl) + " " + txt) if lvl else txt)
            elif t == "image":
                img = b.get("img_path")
                if not img:
                    continue
                ap = (base_dir / img).resolve()
                if ap.exists():
                    body.append(f"![]({ap.as_posix()})")
                    cap = " ".join(
                        c for c in (b.get("image_caption") or []) if c
                    ).strip()
                    if cap:
                        body.append(f"*{cap}*")
            elif t == "page_footnote":
                txt = (b.get("text") or "").strip()
                if txt:
                    foots.append(txt)
            # header / footer / page_number / 其它 → 丢弃
        page_md = "\n\n".join(body)
        if foots:
            page_md += FOOTNOTE_SEP + "\n\n".join(foots)
        if page_md.strip():
            parts.append(page_md)
    return "\n\n".join(parts)


def parse_content_list(json_path: Path) -> str:
    blocks = json.loads(json_path.read_text(encoding="utf-8"))
    return _blocks_to_markdown(blocks, json_path.parent)


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
