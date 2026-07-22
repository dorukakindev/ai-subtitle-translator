import json
import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path


STATE_DIR_ENV = "SUBTITLE_TRANSLATOR_STATE_DIR"
_fallback_lock = threading.RLock()


def state_dir(anchor_file) -> Path:
    override = os.environ.get(STATE_DIR_ENV, "").strip()
    return Path(override) if override else Path(anchor_file).resolve().parent


def state_path(anchor_file, name: str) -> Path:
    return state_dir(anchor_file) / name


def atomic_write_text(path, text: str, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding=encoding)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_write_json(path, data) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


@contextmanager
def _interprocess_lock(path):
    lock_path = Path(path).with_name(Path(path).name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _fallback_lock:
        with open(lock_path, "a+b") as handle:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def mutate_batch_ids(path, *, add=(), remove=(), replace=None) -> list[str]:
    path = Path(path)
    with _interprocess_lock(path):
        current = []
        if replace is None and path.exists():
            try:
                current = path.read_text(encoding="utf-8").splitlines()
            except Exception:
                current = []
        source = replace if replace is not None else current
        removed = {str(x).strip() for x in remove if str(x).strip()}
        result = []
        seen = set()
        for value in list(source or []) + list(add or []):
            bid = str(value).strip()
            if not bid or bid in removed or bid in seen:
                continue
            seen.add(bid)
            result.append(bid)
        if result:
            atomic_write_text(path, "\n".join(result))
        else:
            path.unlink(missing_ok=True)
        return result
