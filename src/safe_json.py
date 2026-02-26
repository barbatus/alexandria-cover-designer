"""Atomic JSON read/write helpers to reduce corruption risk."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import tempfile
from pathlib import Path
from typing import Any

try:  # pragma: no cover - unix-only API
    import fcntl  # type: ignore
except Exception:  # pragma: no cover - fallback for platforms without fcntl
    fcntl = None  # type: ignore


def _lock_path_for(path: Path) -> Path:
    return path.parent / f".{path.name}.lock"


@contextmanager
def _path_lock(path: Path):
    lock_path = _lock_path_for(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def _multi_path_lock(paths: list[Path]):
    ordered = sorted({Path(path) for path in paths}, key=lambda row: str(row))
    handles: list[Any] = []
    try:
        for target in ordered:
            lock_path = _lock_path_for(target)
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = lock_path.open("a+", encoding="utf-8")
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            try:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def atomic_write_json(path: Path, payload: Any) -> None:
    with _path_lock(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, indent=2, ensure_ascii=False)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        os.replace(tmp_name, path)


def atomic_write_many_json(items: list[tuple[Path, Any]]) -> None:
    """Stage-and-swap JSON writes with rollback on partial commit failure."""
    staged: list[tuple[str, Path]] = []
    backup_by_target: dict[Path, str] = {}
    target_existed: dict[Path, bool] = {}
    applied_targets: list[Path] = []
    normalized: list[tuple[Path, Any]] = []
    seen_targets: set[Path] = set()

    # Deduplicate duplicate targets in one call, keeping the last payload.
    for path, payload in reversed(items):
        target = Path(path)
        if target in seen_targets:
            continue
        seen_targets.add(target)
        normalized.append((target, payload))
    normalized.reverse()

    with _multi_path_lock([path for path, _ in normalized]):
        for path, payload in normalized:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(path.parent),
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                json.dump(payload, tmp, indent=2, ensure_ascii=False)
                tmp.write("\n")
                tmp.flush()
                os.fsync(tmp.fileno())
                staged.append((tmp.name, path))

        for _, path in staged:
            existed = path.exists()
            target_existed[path] = existed
            if not existed:
                continue
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=str(path.parent),
                prefix=f".{path.name}.",
                suffix=".bak",
                delete=False,
            ) as backup:
                backup.write(path.read_bytes())
                backup.flush()
                os.fsync(backup.fileno())
                backup_by_target[path] = backup.name

        try:
            for tmp_name, path in staged:
                os.replace(tmp_name, path)
                applied_targets.append(path)
        except Exception:
            for target in reversed(applied_targets):
                backup_path = backup_by_target.get(target)
                if backup_path and os.path.exists(backup_path):
                    os.replace(backup_path, target)
                    backup_by_target.pop(target, None)
                    continue
                if not target_existed.get(target, False) and target.exists():
                    try:
                        os.remove(target)
                    except OSError:
                        pass
            raise
        finally:
            for tmp_name, _ in staged:
                if os.path.exists(tmp_name):
                    try:
                        os.remove(tmp_name)
                    except OSError:
                        pass
            for backup_path in backup_by_target.values():
                if os.path.exists(backup_path):
                    try:
                        os.remove(backup_path)
                    except OSError:
                        pass


def update_json(path: Path, mutator: Any, default: Any) -> Any:
    current = load_json(path, default)
    updated = mutator(current)
    atomic_write_json(path, updated)
    return updated
