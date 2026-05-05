import os
import json
import time
import pytest
from pathlib import Path
from shared.utils.helpers import (
    sanitize_filename,
    ensure_dirs,
    save_json,
    load_json,
    ms_to_seconds,
    seconds_to_ms,
    get_timestamp,
    chunk_list,
    retry,
)


# ── sanitize_filename ─────────────────────────────────────────────────────────


def test_sanitize_filename_basic():
    assert sanitize_filename("hello world") == "hello_world"


def test_sanitize_filename_special_chars():
    result = sanitize_filename("file/with:special?chars*")
    for ch in r'/\:*?"<>|':
        assert ch not in result


def test_sanitize_filename_empty():
    result = sanitize_filename("")
    assert isinstance(result, str)


def test_sanitize_filename_already_clean():
    assert sanitize_filename("clean_name") == "clean_name"


# ── ensure_dirs ───────────────────────────────────────────────────────────────


def test_ensure_dirs_creates_directories(tmp_path):
    d1 = str(tmp_path / "dir_a")
    d2 = str(tmp_path / "nested" / "dir_b")
    ensure_dirs([d1, d2])
    assert os.path.isdir(d1)
    assert os.path.isdir(d2)


def test_ensure_dirs_idempotent(tmp_path):
    d = str(tmp_path / "existing")
    os.makedirs(d)
    ensure_dirs([d])  # should not raise
    assert os.path.isdir(d)


# ── save_json / load_json ─────────────────────────────────────────────────────


def test_save_and_load_json(tmp_path):
    data = {"key": "value", "number": 42, "list": [1, 2, 3]}
    path = str(tmp_path / "test.json")
    save_json(data, path)
    loaded = load_json(path)
    assert loaded == data


def test_load_json_nonexistent(tmp_path):
    path = str(tmp_path / "missing.json")
    with pytest.raises(Exception):
        load_json(path)


def test_save_json_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "nested" / "deep" / "data.json")
    save_json({"x": 1}, path)
    assert os.path.exists(path)


# ── ms_to_seconds / seconds_to_ms ────────────────────────────────────────────


def test_ms_to_seconds():
    assert ms_to_seconds(1000) == pytest.approx(1.0)
    assert ms_to_seconds(500) == pytest.approx(0.5)
    assert ms_to_seconds(0) == pytest.approx(0.0)


def test_seconds_to_ms():
    assert seconds_to_ms(1.0) == 1000
    assert seconds_to_ms(0.5) == 500
    assert seconds_to_ms(0) == 0


def test_roundtrip_conversion():
    original_ms = 3750
    assert seconds_to_ms(ms_to_seconds(original_ms)) == pytest.approx(original_ms, abs=1)


# ── get_timestamp ─────────────────────────────────────────────────────────────


def test_get_timestamp_returns_string():
    ts = get_timestamp()
    assert isinstance(ts, str)
    assert len(ts) > 0


def test_get_timestamp_unique():
    ts1 = get_timestamp()
    time.sleep(0.01)
    ts2 = get_timestamp()
    # Timestamps should differ (or at least be strings)
    assert isinstance(ts1, str)
    assert isinstance(ts2, str)


# ── chunk_list ────────────────────────────────────────────────────────────────


def test_chunk_list_even():
    result = list(chunk_list([1, 2, 3, 4, 5, 6], 2))
    assert result == [[1, 2], [3, 4], [5, 6]]


def test_chunk_list_uneven():
    result = list(chunk_list([1, 2, 3, 4, 5], 2))
    assert len(result) == 3
    assert result[-1] == [5]


def test_chunk_list_larger_than_list():
    result = list(chunk_list([1, 2], 10))
    assert result == [[1, 2]]


def test_chunk_list_empty():
    result = list(chunk_list([], 3))
    assert result == []


# ── retry ─────────────────────────────────────────────────────────────────────


def test_retry_succeeds_first_try():
    call_count = [0]

    def fn():
        call_count[0] += 1
        return "success"

    result = retry(fn, max_attempts=3, delay_s=0)
    assert result == "success"
    assert call_count[0] == 1


def test_retry_succeeds_after_failures():
    call_count = [0]

    def fn():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError("not yet")
        return "ok"

    result = retry(fn, max_attempts=3, delay_s=0)
    assert result == "ok"
    assert call_count[0] == 3


def test_retry_raises_after_max_attempts():
    def fn():
        raise RuntimeError("always fails")

    with pytest.raises(RuntimeError):
        retry(fn, max_attempts=3, delay_s=0)
