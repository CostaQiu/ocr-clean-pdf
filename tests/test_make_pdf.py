from pathlib import Path
import make_pdf


def test_build_pandoc_cmd_uses_typst_engine_and_cjk_font():
    cmd = make_pdf.build_pandoc_cmd(
        Path("output/book.md"),
        Path("output/book.pdf"),
        font="SimSun",
    )
    assert cmd[0] == "pandoc"
    assert "--pdf-engine=typst" in cmd
    joined = " ".join(cmd)
    assert "mainfont=SimSun" in joined
    assert str(Path("output/book.md")) in cmd
    assert "-o" in cmd
