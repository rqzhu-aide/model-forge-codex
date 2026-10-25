"""Atomic JSON commits tolerate a short-lived Windows reader handle."""
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from model_forge_codex import storage


def test_atomic_replace_retries_prepared_bytes_without_rewriting(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    storage.write_json_atomic(path, {"revision": 1})
    replace, calls, delays = storage.os.replace, [], []
    prepared = []
    def sharing_violation(source, destination):
        calls.append((source, destination))
        prepared.append(source.read_bytes())
        assert storage.read_json(destination) == {"revision": 1}
        if len(calls) < 3:
            raise PermissionError("fixture reader")
        return replace(source, destination)
    monkeypatch.setattr(storage, "_JSON_REPLACE_RETRY_DELAYS", (0.001, 0.002))
    monkeypatch.setattr(storage.os, "replace", sharing_violation)
    monkeypatch.setattr(storage.time, "sleep", delays.append)
    storage.write_json_atomic(path, {"revision": 2})
    assert delays == [0.001, 0.002]
    assert calls == [(path.with_name("state.json.tmp"), path)] * 3
    assert prepared == [b'{\n  "revision": 2\n}\n'] * 3
    assert storage.read_json(path) == {"revision": 2}
    assert not path.with_name("state.json.tmp").exists()


def test_atomic_replace_exhaustion_preserves_prior_target_and_original_error(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    storage.write_json_atomic(path, {"revision": 1})
    error, calls, delays = PermissionError("fixture held reader"), [], []
    def sharing_violation(source, destination):
        calls.append((source, destination))
        raise error
    monkeypatch.setattr(storage, "_JSON_REPLACE_RETRY_DELAYS", (0.001, 0.002))
    monkeypatch.setattr(storage.os, "replace", sharing_violation)
    monkeypatch.setattr(storage.time, "sleep", delays.append)
    with pytest.raises(PermissionError) as caught:
        storage.write_json_atomic(path, {"revision": 2})
    assert caught.value is error
    assert len(calls) == 3 and delays == [0.001, 0.002]
    assert storage.read_json(path) == {"revision": 1}
    assert storage.read_json(path.with_name("state.json.tmp")) == {"revision": 2}


def test_atomic_replace_does_not_retry_other_errors(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    error, calls, delays = OSError("fixture disk failure"), [], []
    def fail(source, destination):
        calls.append((source, destination))
        raise error
    monkeypatch.setattr(storage.os, "replace", fail)
    monkeypatch.setattr(storage.time, "sleep", delays.append)
    with pytest.raises(OSError) as caught:
        storage.write_json_atomic(path, {"revision": 2})
    assert caught.value is error
    assert len(calls) == 1 and delays == []


@pytest.mark.skipif(os.name != "nt", reason="Windows reader sharing semantics")
def test_actual_windows_reader_release_allows_atomic_commit(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    storage.write_json_atomic(path, {"revision": 1})
    replace, denied, calls = storage.os.replace, threading.Event(), []
    def observed_replace(source, destination):
        calls.append((source, destination))
        try:
            return replace(source, destination)
        except PermissionError:
            denied.set()
            raise
    monkeypatch.setattr(storage.os, "replace", observed_replace)
    with ThreadPoolExecutor(max_workers=1) as workers:
        with path.open("rb") as reader:
            future = workers.submit(storage.write_json_atomic, path, {"revision": 2})
            assert denied.wait(2), "The real open reader should deny the first replace"
            assert reader.read() == b'{\n  "revision": 1\n}\n'
        future.result(timeout=2)
    assert len(calls) >= 2
    assert storage.read_json(path) == {"revision": 2}
