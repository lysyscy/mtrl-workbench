"""`import_kit.staging` —— 「预览不写库」的暂存出口。

⚠️ **只许一份载具** = `app/core.preview_store`（本件是它的**门面**，不是第二份实现 ——
   `test_router_refs` 的「暂存载具是同一份」守卫盯着这件事）。
"""

from __future__ import annotations

from app.core import preview_store


def save_preview(payload: dict) -> str:
    """暂存一份预览结果 → token（确认时凭它取回；**一个字节都不写库**）。"""
    return preview_store.save(payload)


def load_preview(token: str) -> dict:
    """凭 token 取回预览结果；不存在 / 过期 ⇒ **显式报错**（⛔ 不静默当成空导入）。"""
    return preview_store.load(token)


__all__ = ["load_preview", "save_preview"]
