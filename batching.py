"""页范围分批 + 续跑标记（纯逻辑，无副作用除写标记）。"""

from pathlib import Path


def make_batches(total_pages: int, batch_size: int) -> list[tuple[int, int]]:
    """返回 [(start, end), ...]，0 基、end 不含，覆盖 [0, total_pages)。"""
    if batch_size <= 0:
        raise ValueError("batch_size 必须为正")
    if total_pages <= 0:
        return []
    return [
        (s, min(s + batch_size, total_pages)) for s in range(0, total_pages, batch_size)
    ]


def batch_dir(output_dir: Path, start: int, end: int) -> Path:
    """该批的输出目录，名字零填充保证字典序 == 页序。"""
    return output_dir / "batches" / f"{start:04d}_{end:04d}"


def is_batch_done(output_dir: Path, start: int, end: int) -> bool:
    return (batch_dir(output_dir, start, end) / ".batch.done").exists()


def mark_batch_done(output_dir: Path, start: int, end: int) -> None:
    d = batch_dir(output_dir, start, end)
    d.mkdir(parents=True, exist_ok=True)
    (d / ".batch.done").write_text("ok", encoding="utf-8")
