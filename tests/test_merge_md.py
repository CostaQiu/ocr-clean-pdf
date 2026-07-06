from pathlib import Path
import merge_md


def test_strip_page_numbers_removes_isolated_numbers():
    text = "正文第一段。\n123\n正文第二段。\n— 45 —\n结尾。"
    out = merge_md.strip_page_numbers(text)
    assert "123" not in out
    assert "45" not in out
    assert "正文第一段。" in out
    assert "正文第二段。" in out
    assert "结尾。" in out


def test_strip_page_numbers_keeps_numbers_inside_text():
    text = "公元 1949 年是重要节点。"
    assert merge_md.strip_page_numbers(text) == text


def test_collapse_blank_lines():
    text = "A\n\n\n\nB"
    assert merge_md.collapse_blank_lines(text) == "A\n\nB"


def test_find_batch_markdown(tmp_path):
    assert merge_md.find_batch_markdown(tmp_path) is None
    sub = tmp_path / "x" / "ocr"
    sub.mkdir(parents=True)
    md = sub / "x.md"
    md.write_text("hi", encoding="utf-8")
    assert merge_md.find_batch_markdown(tmp_path) == md


def test_merge_concatenates_in_page_order(tmp_path):
    batches = tmp_path / "batches"
    for name, body in [("0000_0040", "第一批正文。"), ("0040_0080", "第二批正文。")]:
        d = batches / name / "ocr"
        d.mkdir(parents=True)
        (d / "a.md").write_text(body, encoding="utf-8")
    out = merge_md.merge(tmp_path)
    assert out == tmp_path / "book.md"
    content = out.read_text(encoding="utf-8")
    assert content.index("第一批正文。") < content.index("第二批正文。")
