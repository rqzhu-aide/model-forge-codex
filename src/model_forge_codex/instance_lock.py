"""One writable backend process owns a local data directory at a time."""
from contextlib import contextmanager
import os
from pathlib import Path


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
