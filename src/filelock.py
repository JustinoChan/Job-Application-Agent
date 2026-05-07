from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Iterator

from src import config

_LOCAL_LOCK = RLock()


@contextmanager
def _portalock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import portalocker
    except ImportError:
        with _LOCAL_LOCK:
            yield
        return

    with _LOCAL_LOCK:
        with path.open("a+", encoding="utf-8") as lock_file:
            portalocker.lock(lock_file, portalocker.LOCK_EX)
            try:
                yield
            finally:
                portalocker.unlock(lock_file)


@contextmanager
def tracker_lock() -> Iterator[None]:
    """Exclusive lock for tracker.csv operations."""
    with _portalock(config.JOBS_DIR / ".tracker.lock"):
        yield


@contextmanager
def version_lock(job_id: str) -> Iterator[None]:
    """Exclusive lock for resume version creation and artifact writes."""
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_id)
    with _portalock(config.RESUMES_DIR / f".{safe_name}.version.lock"):
        yield
