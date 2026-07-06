import json
from pathlib import Path
import merge_md


def _write_json(path, blocks):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blocks, ensure_ascii=False), encoding="utf-8")


def test_parse_keeps_body_and_footnotes_drops_header_and_pagenum(tmp_path):
    js = tmp_path / "b_content_list.json"
    _write_json(
        js,
        [
            {"type": "text", "text": "正文一段。", "page_idx": 0},
            {"type": "header", "text": "第二章 孔子", "page_idx": 0},
            {"type": "page_footnote", "text": "①注解内容。", "page_idx": 0},
            {"type": "page_number", "text": "66", "page_idx": 0},
        ],
    )
    md = merge_md.parse_content_list(js)
    assert "正文一段。" in md
    assert "①注解内容。" in md  # 脚注保留
    assert "第二章 孔子" not in md  # 书眉丢弃
    assert "66" not in md  # 页码丢弃


def test_parse_renders_heading_by_text_level(tmp_path):
    js = tmp_path / "b_content_list.json"
    _write_json(
        js,
        [
            {"type": "text", "text": "第四节 德礼政刑", "text_level": 2, "page_idx": 0},
            {"type": "text", "text": "正文。", "page_idx": 0},
        ],
    )
    md = merge_md.parse_content_list(js)
    assert "## 第四节 德礼政刑" in md


def test_parse_footnote_separated_from_body(tmp_path):
    js = tmp_path / "b_content_list.json"
    _write_json(
        js,
        [
            {"type": "text", "text": "正文。", "page_idx": 0},
            {"type": "page_footnote", "text": "①注。", "page_idx": 0},
        ],
    )
    md = merge_md.parse_content_list(js)
    assert md.index("正文。") < md.index("①注。")  # 正文在前,脚注在后
    assert "---" in md  # 有分隔


def test_parse_skips_empty_text(tmp_path):
    js = tmp_path / "b_content_list.json"
    _write_json(
        js,
        [
            {"type": "text", "text": "", "page_idx": 0},
            {"type": "text", "text": "有内容。", "page_idx": 0},
        ],
    )
    md = merge_md.parse_content_list(js)
    assert "有内容。" in md
    assert md.strip() == "有内容。"


def test_collapse_blank_lines():
    assert merge_md.collapse_blank_lines("A\n\n\n\nB") == "A\n\nB"


def test_merge_concatenates_batches_in_order(tmp_path):
    out = tmp_path
    b1 = out / "batches" / "0000_0040"
    b2 = out / "batches" / "0040_0080"
    _write_json(
        b1 / "x_content_list.json",
        [{"type": "text", "text": "第一批。", "page_idx": 0}],
    )
    _write_json(
        b2 / "y_content_list.json",
        [{"type": "text", "text": "第二批。", "page_idx": 0}],
    )
    book = merge_md.merge(out)
    assert book == out / "book.md"
    content = book.read_text(encoding="utf-8")
    assert content.index("第一批。") < content.index("第二批。")
