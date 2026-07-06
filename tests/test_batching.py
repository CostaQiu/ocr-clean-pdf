from pathlib import Path
import pytest
from batching import make_batches, batch_dir, is_batch_done, mark_batch_done


def test_make_batches_covers_all_pages_without_overlap():
    batches = make_batches(700, 40)
    assert batches[0] == (0, 40)
    assert batches[-1] == (680, 700)
    assert len(batches) == 18
    # 覆盖且不重叠
    covered = []
    for s, e in batches:
        covered.extend(range(s, e))
    assert covered == list(range(700))


def test_make_batches_exact_multiple():
    assert make_batches(80, 40) == [(0, 40), (40, 80)]


def test_make_batches_empty_and_bad_input():
    assert make_batches(0, 40) == []
    with pytest.raises(ValueError):
        make_batches(100, 0)


def test_batch_dir_zero_padded_name(tmp_path):
    d = batch_dir(tmp_path, 40, 80)
    assert d == tmp_path / "batches" / "0040_0080"


def test_is_batch_done_and_mark(tmp_path):
    assert is_batch_done(tmp_path, 0, 40) is False
    mark_batch_done(tmp_path, 0, 40)
    assert is_batch_done(tmp_path, 0, 40) is True
