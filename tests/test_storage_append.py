"""JSONL append retries must not replay writes or hide persistent failures."""

import ctypes
import errno
import json
import os
from pathlib import Path

import pytest

from model_forge_codex import storage


@pytest.fixture
def retry_delays(monkeypatch):
    delays = (0.05, 0.1, 0.2, 0.4)
    monkeypatch.setattr(storage, "_JSONL_OPEN_RETRY_DELAYS", delays)
    sleeps = []
    monkeypatch.setattr(storage.time, "sleep", sleeps.append)
    return delays, sleeps


def test_transient_open_denial_appends_one_complete_record(tmp_path, monkeypatch, retry_delays):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"existing": true}\n')
    original_open = Path.open
    calls = []

    def transient_open(target, *args, **kwargs):
        calls.append((target, args, kwargs))
        if len(calls) <= 2:
            raise PermissionError(errno.EACCES, "sharing violation", str(target))
        return original_open(target, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", transient_open)
        storage.append_jsonl(path, {"type": "thread.rotated", "message": "已保存"})

    assert len(calls) == 3
    assert retry_delays[1] == list(retry_delays[0][:2])
    assert path.read_bytes() == '{"existing": true}\n{"type": "thread.rotated", "message": "已保存"}\n'.encode("utf-8")


def test_persistent_open_denial_remains_an_error(tmp_path, monkeypatch, retry_delays):
    path = tmp_path / "events.jsonl"
    failure = PermissionError(errno.EACCES, "persistent denial", str(path))
    calls = []

    def denied_open(*args, **kwargs):
        calls.append(args)
        raise failure

    monkeypatch.setattr(Path, "open", denied_open)
    with pytest.raises(PermissionError) as caught:
        storage.append_jsonl(path, {"type": "heartbeat"})

    assert caught.value is failure
    assert len(calls) == len(retry_delays[0]) + 1
    assert retry_delays[1] == list(retry_delays[0])
    assert not path.exists()


@pytest.mark.parametrize("failure_at", ["write", "close"])
def test_write_or_close_denial_does_not_replay_record(tmp_path, monkeypatch, retry_delays, failure_at):
    path = tmp_path / "events.jsonl"
    original_open = Path.open
    failure = PermissionError(errno.EACCES, "write or flush denied", str(path))
    opens = []

    class FailingHandle:
        def __enter__(self):
            self.handle = original_open(path, "a", encoding="utf-8", newline="\n")
            return self

        def write(self, line):
            self.handle.write(line)
            self.handle.flush()
            if failure_at == "write":
                raise failure

        def __exit__(self, *exc):
            self.handle.close()
            if failure_at == "close":
                raise failure

    def failing_open(*args, **kwargs):
        opens.append(args)
        return FailingHandle()

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", failing_open)
        with pytest.raises(PermissionError) as caught:
            storage.append_jsonl(path, {"type": "heartbeat"})

    assert caught.value is failure
    assert len(opens) == 1
    assert retry_delays[1] == []
    assert path.read_text(encoding="utf-8") == '{"type": "heartbeat"}\n'


def test_other_open_errors_are_not_retried(tmp_path, monkeypatch, retry_delays):
    failure = OSError(errno.ENOSPC, "disk full")
    opens = []

    def failed_open(*args, **kwargs):
        opens.append(args)
        raise failure

    monkeypatch.setattr(Path, "open", failed_open)
    with pytest.raises(OSError) as caught:
        storage.append_jsonl(tmp_path / "events.jsonl", {"type": "heartbeat"})

    assert caught.value is failure
    assert len(opens) == 1
    assert retry_delays[1] == []


def test_no_retry_without_windows_delay_policy(tmp_path, monkeypatch, retry_delays):
    monkeypatch.setattr(storage, "_JSONL_OPEN_RETRY_DELAYS", ())
    failure = PermissionError(errno.EACCES, "access denied")
    opens = []

    def denied_open(*args, **kwargs):
        opens.append(args)
        raise failure

    monkeypatch.setattr(Path, "open", denied_open)
    with pytest.raises(PermissionError) as caught:
        storage.append_jsonl(tmp_path / "events.jsonl", {"type": "heartbeat"})

    assert caught.value is failure
    assert len(opens) == 1
    assert retry_delays[1] == []


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing semantics")
def test_windows_reader_releasing_write_denial_allows_append(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"existing": true}\n')
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    # GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING: reader denies writes.
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value
    released = False
    sleeps = []

    def release_reader(delay):
        nonlocal released
        sleeps.append(delay)
        assert kernel.CloseHandle(handle)
        released = True

    monkeypatch.setattr(storage.time, "sleep", release_reader)
    try:
        storage.append_jsonl(path, {"type": "thread.rotated"})
    finally:
        if not released:
            kernel.CloseHandle(handle)

    assert sleeps == [storage._JSONL_OPEN_RETRY_DELAYS[0]]
    assert [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] == [
        {"existing": True}, {"type": "thread.rotated"},
    ]
