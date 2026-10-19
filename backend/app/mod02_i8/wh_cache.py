"""`MOD-02` 横切：i8 **仓库名单的磁盘缓存**（唯一出口）—— 免「每次查名单都要登录一次 i8」。

## 为什么要有它
`TAIL-39`（用户 2026-09-18 口述裁定「**兜底前…应该有去仓库跑了一环这个逻辑，而且如果跑完没结果
要在界面上提醒用户**」）让链路 C 在建具体小微前**先查一次 i8 仓库名单**。
但 i8 是**单会话**：查名单**要登录**、可能**强踢**在线用户（`D9`）⇒ 每查一次就冒一次顶号风险。
把名单**落盘缓存**后：**抓不到（i8 不可用）时还能用上一次的名单接着判**，
而且在回执里**如实说明用的是几点的缓存**（⛔ 不静默、⛔ 不把旧名单说成刚抓的）。

## 三段式（照交付面素材包 `app/warehouse_sync.py` 的 `save_cache`/`load_cache`，**只借鉴形态**）
- `cache_path()` → `var/cache/i8_warehouse/list.json`（**唯一出口**）
- `load()` → `(items, fetched_at)`；`save(items, source=…)` → 写入路径
- `clear()` → 删缓存文件

## ⚠️ 三条纪律
1. **缓存是优化、不是功能** ⇒ 读 / 写 / 删**失败一律不抛**，只记 `warning`、退回「无缓存」
   （让缓存异常打断查名单，等于用"锦上添花"砸了"主流程"）。
2. **它是"上一次抓到的快照"，不是权威数据** ⇒ 用它的地方**必须**把 `fetched_at` 一起说出来
   （⛔ 不许让用户以为是刚抓的）。
3. 本模块**只做文件读写**：⛔ 不连 i8、⛔ 不判"该不该重抓"（那是调用方的事）。

## 与素材包的**两处刻意不同（并说明理由）**
1. **落点**：素材包平铺在 `var/cache/仓库列表.json`；本仓改**子目录专属命名空间**
   `var/cache/i8_warehouse/list.json`（照本仓 `cookie_store` 的同款改法：目录已表明是 i8 仓库名单）。
2. **不做"下载目录兜底"**：素材包的调用方在"匹配不到时查缓存兜底建档"，本仓**不搬**那半 ——
   见 `TAIL-39`：建档的口径是「**先查名单、没命中要人确认**」，不是"缓存里有就直接建"
   （缓存只用来**回答"名单里有没有"**，⛔ 不当作建档许可）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.config import PROJECT_ROOT
from app.core.logging import get_logger

logger = get_logger()

#: 缓存落点（**模块级常量** —— 测试用 `monkeypatch.setattr` 换到临时目录，不必碰真实盘）
CACHE_DIR: Path = PROJECT_ROOT / "var" / "cache" / "i8_warehouse"

#: 文件名（ASCII：避免工具链上的编码花样；目录名已表明是 i8 仓库名单）
CACHE_NAME = "list.json"


def cache_path() -> Path:
    """缓存文件路径 —— **唯一出口**（`load`/`save`/`clear` 都走它，⛔ 别各自拼一份）。"""
    return CACHE_DIR / CACHE_NAME


def load() -> tuple[list[dict] | None, str]:
    """读缓存 → `(items, fetched_at)`；无 / 空 / 不认 ⇒ `(None, "")`（**不抛**）。"""
    path = cache_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None, ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("i8 仓库名单缓存格式不认（{}）—— 当无缓存", path.name)
        return None, ""
    if not isinstance(data, dict):
        logger.warning("i8 仓库名单缓存结构不认（{}）—— 当无缓存", path.name)
        return None, ""
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return None, ""
    rows = [r for r in items if isinstance(r, dict)]
    if not rows:
        return None, ""
    return rows, str(data.get("fetched_at") or "")


def save(items: list[dict] | None, *, source: str = "api05") -> Path | None:
    """把名单落盘（JSON：`items` / `fetched_at` / `count` / `source`）→ 返回写入路径。

    - 空名单 ⇒ 不写、返回 `None`（⛔ 不拿空名单覆盖掉上一份）。
    - ⚠️ **写失败不抛**（缓存是优化）：只记 `warning` 并返回 `None`。
    """
    rows = [r for r in (items or []) if isinstance(r, dict)]
    if not rows:
        return None
    path = cache_path()
    payload = {
        "items": rows,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(rows),
        "source": source,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("i8 仓库名单缓存写入失败（不影响本次查名单）：{}", exc)
        return None
    return path


def clear() -> bool:
    """删缓存文件；确实删掉了 ⇒ `True`（本就不在 / 删不掉 ⇒ `False`，**不抛**）。"""
    try:
        cache_path().unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("i8 仓库名单缓存删除失败：{}", exc)
        return False


__all__ = ["CACHE_DIR", "CACHE_NAME", "cache_path", "load", "save", "clear"]
