"""`import_kit.profile_store` —— **映射记忆**（`TAIL-75` B1 · 设计 §六）。

⭐ 用户 2026-09-22 裁定：**记忆按「表头指纹」**（同名表换项目也能命中）。

规则：
1. 指纹 = 归一化表头序列的 `sha1`（同表同指纹 ⇒ 直接命中，**预填**，界面照旧显示「来自记忆 · 可改」）；
2. 指纹不中时按**表头集合的 Jaccard** 找最近的一条：**≥ 0.60 才用**（表变了别拿旧映射硬套），
   否则**不用记忆**（宁可空白让人选 —— 与"永不静默猜"同一条精神）；
3. 落盘是**原子写**（临时文件 ＋ `replace`），⛔ 不做半截文件。

⚠️ 存的是**归一化后的表头**（不是原文）—— 足够算相似度，也避免把业务原文写进记忆件。
⛔ 本件**不判业务**（哪个字段对哪列由域给），只负责"记住/取回"。
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass, field

from app.import_kit.mapping import normalize

#: 命中门槛：表头集合相似度低于它 ⇒ **不用**旧映射
MIN_JACCARD = 0.60

#: 工程根（`backend/app/import_kit/profile_store.py` 上溯 3 层 ⇒ 与 `app.core.config.PROJECT_ROOT`
#: 同一算法；⚠️ 这里**自算**而不 import `config` —— 本件是纯逻辑件，不该把"读 `.env` 的配置模块"拖进来）。
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: ⚠️⚠️ 2026-09-24 修（**产物落点唯一**）：此前这里是**相对路径** `"artifacts/import_profiles.json"`
#:   ⇒ 落点跟着 **cwd** 走 —— 而 NSSM 服务的 `AppDirectory = backend/`（见 `ops/nssm_install.ps1`）
#:   ⇒ **服务写的记忆落到 `backend/artifacts/import_profiles.json`**，而工具 / pytest（cwd = 仓根）
#:   读写**根** `artifacts/import_profiles.json` ⇒ **同一份「导入映射记忆」分裂成两份**
#:   （2026-09-24 实测：两个文件都在、都 608 字节、mtime 差 9 小时）。
#:   ⇒ 一律挂**工程根**（与 `cookie_store` / `preview_store` / `wh_cache` 同款）。
_DEFAULT_REL = _PROJECT_ROOT / "var" / "data" / "import_profiles.json"


def fingerprint(headers) -> str:
    """归一化表头序列 → `sha1`（同表同指纹）。"""
    keys = "|".join(normalize(h) for h in headers)
    return hashlib.sha1(keys.encode("utf-8")).hexdigest()[:16]


def jaccard(headers_a, headers_b) -> float:
    """两组表头的**集合** Jaccard（顺序、列增减都能容忍）。"""
    a = {normalize(h) for h in headers_a if normalize(h)}
    b = {normalize(h) for h in headers_b if normalize(h)}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Saved:
    """一条记忆：`domain` ＋ 归一化表头 ＋ `{源列原文: 字段 label | IGNORE}` ＋ 来源标签。"""

    domain: str
    headers: list[str]
    mapping: dict[str, str] = field(default_factory=dict)
    source_label: str = ""
    updated_at: str = ""

    @property
    def fp(self) -> str:
        return fingerprint(self.headers)


class ProfileStore:
    """JSON 文件版记忆（路径由调用方给 ⇒ 可测；默认 `var/data/import_profiles.json`）。"""

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self.path = pathlib.Path(path or _DEFAULT_REL)
        self._items: dict[str, Saved] = {}
        self.reload()

    # ------------------------------------------------------------ 落盘
    def reload(self) -> None:
        self._items = {}
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return                      # 坏了就当空 —— ⛔ 不让记忆件把导入卡死
        for fp, raw in (data.get("items") or {}).items():
            self._items[fp] = Saved(
                domain=raw.get("domain", ""), headers=list(raw.get("headers") or []),
                mapping=dict(raw.get("mapping") or {}), source_label=raw.get("source_label", ""),
                updated_at=raw.get("updated_at", ""),
            )

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"_note": "import_kit 映射记忆（归一化表头 → 映射）；键 = 表头指纹",
                   "items": {fp: {"domain": s.domain, "headers": s.headers, "mapping": s.mapping,
                                  "source_label": s.source_label, "updated_at": s.updated_at}
                             for fp, s in self._items.items()}}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)      # ⭐ 原子写：要么旧、要么新，⛔ 不做半截

    # ------------------------------------------------------------ 读写
    def save(self, domain: str, headers, mapping: dict, *, source_label: str = "",
             now: str = "") -> Saved:
        """存一条记忆（同指纹覆盖）。`mapping` 的键用**源列原文**（取回时按原文回填）。"""
        norm_headers = [normalize(h) for h in headers]
        item = Saved(domain=domain, headers=norm_headers, mapping=dict(mapping),
                     source_label=source_label, updated_at=now)
        self._items[item.fp] = item
        self._flush()
        return item

    def find(self, domain: str, headers) -> tuple[Saved, float, str] | None:
        """取记忆 ⇒ `(条目, 相似度, 命中方式)`；`命中方式 ∈ {指纹, 相似}`；够不着 ⇒ `None`。

        ⚠️ **两条路都要校验域** —— 指纹相同但域不同（如 `m04` 与 `m11` 恰好都有「项目/付款时间」两列）
        时**不许跨域套用**（自测抓到过：指纹路原先漏了这一步）。
        """
        target = [normalize(h) for h in headers]
        fp = fingerprint(target)
        hit = self._items.get(fp)
        if hit is not None and hit.domain == domain:
            return hit, 1.0, "指纹"
        best: tuple[Saved, float] | None = None
        for s in self._items.values():
            if s.domain != domain:
                continue
            sim = jaccard(s.headers, target)
            if best is None or sim > best[1]:
                best = (s, sim)
        if best and best[1] >= MIN_JACCARD:
            return best[0], round(best[1], 3), "相似"
        return None

    def prefill(self, domain: str, headers) -> tuple[dict, str, float] | None:
        """给界面用：命中的话 ⇒ `(预填映射, 说明, 相似度)` —— 说明会显示成「来自记忆（…）· 可改」。"""
        hit = self.find(domain, headers)
        if not hit:
            return None
        item, sim, how = hit
        label = item.source_label or item.domain
        return dict(item.mapping), f"来自记忆（{how}命中：{label}）· 可改", sim

    def drop(self, domain: str, headers) -> bool:
        """删一条（表变了/用户点「忘记这套」时用）。"""
        fp = fingerprint([normalize(h) for h in headers])
        if fp in self._items:
            del self._items[fp]
            self._flush()
            return True
        return False

    def count(self, domain: str | None = None) -> int:
        return len([s for s in self._items.values() if domain is None or s.domain == domain])


__all__ = ["MIN_JACCARD", "ProfileStore", "Saved", "fingerprint", "jaccard"]
