"""One writable backend process owns a local data directory at a time."""
from contextlib import contextmanager
import os
from pathlib import Path
import threading
import hashlib
import tempfile


_catalog_locks: dict[str, threading.RLock] = {}
_catalog_locks_guard = threading.Lock()
_catalog_lock_depth = threading.local()


@contextmanager
def writable_instance(data_root: Path):
    """Hold an OS lock until service cleanup finishes; never unlink its inode."""
    data_root.mkdir(parents=True, exist_ok=True)
    handle = (data_root / ".writer.lock").open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(f"Another writable Model Forge instance already uses {data_root}.") from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(f"Another writable Model Forge instance already uses {data_root}.") from exc
        locked = True
        yield
    finally:
        try:
            if locked:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


@contextmanager
def catalog_access(project_dir: Path):
    """Serialize a project's catalog swap, recovery and synchronous readers.

    The service's writer lock still governs research writes. This narrower OS
    lock also covers readers in another process, and is reentrant for Catalog
    calls made while an upgrade is validating its prepared directories.
    """
    key = os.path.normcase(str(project_dir.resolve()))
    with _catalog_locks_guard:
        lock = _catalog_locks.setdefault(key, threading.RLock())
    with lock:
        depths = getattr(_catalog_lock_depth, "paths", None)
        if depths is None:
            depths = _catalog_lock_depth.paths = set()
        if key in depths:
            yield
            return
        # A read-only viewer must not need write access to research files.
        user_scope = "-" + str(os.getuid()) if hasattr(os, "getuid") else ""
        lock_dir = Path(tempfile.gettempdir()) / ("model-forge-catalog-locks" + user_scope)
        lock_dir.mkdir(mode=0o700, exist_ok=True)
        lock_path = lock_dir / (hashlib.sha256(key.encode()).hexdigest() + ".lock")
        with lock_path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            depths.add(key)
            try:
                yield
            finally:
                depths.remove(key)
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
