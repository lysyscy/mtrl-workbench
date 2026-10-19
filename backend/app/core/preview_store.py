"""导入预览的共享暂存：确认前不写业务库，token校验阻止路径穿越。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.core.errors import MustReportError

ROOT = Path(__file__).resolve().parents[3]      # ⚠️ 本文件在 `backend/app/core/` ⇒ 上溯 3 层才是**工程根**
PREVIEW_DIR = ROOT / "var" / "state" / "import_preview"

EXPIRE_TIP = "预览已过期（临时文件不在了）—— 请重新上传文件解析一次。"


def path_of(token: str) -> Path:
    """token 对应的暂存文件路径（**只认十六进制 token**，防路径穿越）。"""
    text = str(token or "").strip()
    if not text or any(c not in "0123456789abcdef" for c in text):
        raise MustReportError(EXPIRE_TIP)
    return PREVIEW_DIR / f"{text}.json"


def save(payload: dict) -> str:
    """写一份预览结果 → 返回 token（确认时凭它取回；**不落库**）。"""
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    (PREVIEW_DIR / f"{token}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return token


def load(token: str) -> dict:
    """凭 token 取回预览结果；**取不到 ⇒ 显式报错**（不回落成空）。"""
    path = path_of(token)
    if not path.exists():
        raise MustReportError(EXPIRE_TIP)
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = ["ROOT", "PREVIEW_DIR", "EXPIRE_TIP", "path_of", "save", "load"]
