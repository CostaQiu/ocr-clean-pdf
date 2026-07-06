from pathlib import Path
import run_ocr


def test_build_mineru_cmd_uses_inclusive_end_and_flags():
    # 我们的批是 end 不含；MinerU 的 -e 是含端点，故应传 end_exclusive-1
    cmd = run_ocr.build_mineru_cmd(
        Path("book.pdf"),
        Path("out"),
        start=40,
        end_exclusive=80,
        backend="pipeline",
        lang="ch",
    )
    assert "mineru" in cmd[0]
    assert "-s" in cmd and "40" in cmd
    assert "-e" in cmd and "79" in cmd  # 80 不含 → 含端点 79
    assert "-b" in cmd and "pipeline" in cmd
    assert "-m" in cmd and "ocr" in cmd
    assert "-l" in cmd and "ch" in cmd


def test_run_all_skips_done_batches(tmp_path, monkeypatch):
    calls = []

    def fake_run_one(pdf, out, s, e, backend, lang):
        calls.append((s, e))
        return True  # 假装成功

    monkeypatch.setattr(run_ocr, "_run_one_batch", fake_run_one)
    monkeypatch.setattr(run_ocr, "count_pages", lambda p: 80)
    # 预先把第一批标记为已完成
    from batching import mark_batch_done

    mark_batch_done(tmp_path, 0, 40)

    result = run_ocr.run_all(
        pdf=tmp_path / "x.pdf",
        output_dir=tmp_path,
        batch_size=40,
        backend="pipeline",
        lang="ch",
    )
    assert (0, 40) not in calls  # 已完成的批被跳过
    assert (40, 80) in calls  # 未完成的批被执行
    assert result["ok"] is True
    assert result["pages"] == 80
