"""**i8 源文件缓存**（`TAIL-58` 后续 · 2026-09-21 用户裁定「抓取导出分开」）。

## 为什么要有这一件

`m08`「含透视导出」需要 **i8 导出的源 xlsx 本身**（两张透视表是 i8 生成的 Excel 对象，
数据库里只有明细行、存不了透视）⇒ 原先**每次导出都现场登 i8**（HTTP 现导）——
与 `m07`「抓取归抓取、导出吃本地」**不一致**，且导出会突然撞"登录冲突 / 要顶号"。

⭐ 而 **抓取那一刻源文件本来就在手上**（`fetch_service.run_fetch` 的 `content`，用完即扔）⇒
把它按月存档，导出**只读缓存**：
- 抓取 = 全站唯一碰 i8 的动作（D9 确认都在抓取侧）；
- 导出 = 离线、秒出、**永不顶号**；导出的就是屏幕上那份（数据一致）；
- 缓存没有 ⇒ **显式提示先抓取**（⛔ 不静默、不回落现导）。

## 落点

`PROJECT_ROOT / artifacts / i8_source / <key> / <YYYY-MM>.xlsx`
（照 `wh_cache` 的同款改法：目录表明是 i8 的东西；`artifacts/` 已在 `.gitignore`）
"""

from __future__ import annotations

import pathlib

from app.core.config import PROJECT_ROOT

DIR = PROJECT_ROOT / "artifacts" / "i8_source"


def _path(key: str, ym: str) -> pathlib.Path:
    """`<DIR>/<key>/<YYYY-MM>.xlsx`（key 如 `inv`；ym 已由调用方校验为 `YYYY-MM`）。"""
    return DIR / str(key) / f"{str(ym).strip()}.xlsx"


def save(key: str, ym: str, content: bytes) -> pathlib.Path:
    """把一次抓取拿到的**源文件字节**按月存档（幂等：同月覆盖）。"""
    p = _path(key, ym)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def load(key: str, ym: str) -> bytes | None:
    """读当月源文件字节；**没有 ⇒ `None`**（调用方显式报"请先抓取"，⛔ 不回落现导）。"""
    p = _path(key, ym)
    return p.read_bytes() if p.exists() else None


__all__ = ["load", "save"]
