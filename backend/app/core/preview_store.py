"""导入预览的共享暂存：确认前不写业务库，token校验阻止路径穿越。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid

from app.core.errors import MustReportError

ROOT = Path(__file__).resolve().parents[3]
PREVIEW_DIR = ROOT / "var" / "state" / "import_preview"

EXPIRE_TIP = "预览已过期（临时文件不在了）—— 请重新上传文件解析一次。"
PREVIEW_TTL_SECONDS = 7 * 24 * 60 * 60
PREVIEW_MAX_FILES = 500
_PREVIEW_FILENAME = re.compile(r"[0-9a-f]{32}\.json")


def path_of(token: str) -> Path:
    """token 对应的暂存文件路径（**只认十六进制 token**，防路径穿越）。"""
    text = str(token or "").strip()
    if not text or any(c not in "0123456789abcdef" for c in text):
        raise MustReportError(EXPIRE_TIP)
    return PREVIEW_DIR / f"{text}.json"


def _unlink_unchanged(path: Path, info: os.stat_result) -> None:
    try:
        if path.lstat() == info:
            path.unlink()
    except OSError:
        pass


def _prune_files() -> None:
    cutoff = time.time() - PREVIEW_TTL_SECONDS
    fresh = []
    for path in PREVIEW_DIR.iterdir():
        if not _PREVIEW_FILENAME.fullmatch(path.name):
            continue
        try:
            info = path.lstat()
        except OSError:
            continue
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            continue
        if info.st_mtime <= cutoff:
            _unlink_unchanged(path, info)
        else:
            fresh.append((path, info))
    fresh.sort(key=lambda entry: (entry[1].st_mtime_ns, entry[0].name))
    for path, info in fresh[:max(0, len(fresh) - PREVIEW_MAX_FILES)]:
        _unlink_unchanged(path, info)


def prune() -> None:
    """按写入时间清理过期和超量的预览。锁由进程退出或关闭文件时释放。"""
    try:
        if not PREVIEW_DIR.is_dir() or PREVIEW_DIR.is_symlink() or PREVIEW_DIR.is_junction():
            return
        lock_path = PREVIEW_DIR.with_name(f".{PREVIEW_DIR.name}.lock")
        with lock_path.open("a+b") as lock:
            if sys.platform == "win32":
                import msvcrt
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            _prune_files()
    except OSError:
        # 另一个读写进程持有文件时留给下一次清理。
        pass


def save(payload: dict) -> str:
    """写一份预览结果 → 返回 token（确认时凭它取回；**不落库**）。"""
    data = json.dumps(payload, ensure_ascii=False, indent=1)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    path = path_of(token)
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(data, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    prune()
    return token


def load(token: str) -> dict:
    """凭 token 读取仍在保留期内的预览。"""
    try:
        with path_of(token).open(encoding="utf-8") as handle:
            if os.fstat(handle.fileno()).st_mtime <= time.time() - PREVIEW_TTL_SECONDS:
                raise MustReportError(EXPIRE_TIP)
            return json.load(handle)
    except FileNotFoundError:
        raise MustReportError(EXPIRE_TIP) from None


__all__ = ["ROOT", "PREVIEW_DIR", "EXPIRE_TIP", "path_of", "save", "load", "prune"]
