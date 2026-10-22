"""系统设置的**取值出口**（`MOD-14` · §7.8）—— **库（页面所设）→ `.env`**。

⭐ 本文件是「设置项清单」的**唯一定义处**（`SPECS`）：设置项 / 默认来源 / 提示语都在这里。
⚠️ 调用方一律走 `effective()`，**不得各自读 `.env`** —— 否则会出现「页面改了但没生效」。
⚠️ **单进程假设**（本工程 = 单后端进程，见《技术栈选型分析》）：进程内缓存 ＋ 保存后 `invalidate()`。
⚠️ 库不可用时**回落 `.env` 并记 warning**（不阻断启动；但**不静默**）。
⚠️⭐ **「读库里那张设置表」不由本件做**（`TAIL-195` 批 1b）：那是**数据主人** `mod14_config` 的活，
   本件只留**口**（`bind_values_loader`）—— 由装配层接上（`app/core_bindings.py`）。
   ⛔ `core` 里别 import 业务包（计划 §2.3「依赖方向一律向外」；守卫 = `backend/tests/test_layering.py` 规则 A）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# --------------------------------------------------------------- 设置项（唯一清单）

SETTING_I8_BASE_URL = "i8_base_url"
SETTING_PRINT_ID_MATERIAL = "i8_print_id_material"
SETTING_PRINT_ID_MECHANICAL = "i8_print_id_mechanical"
# ⚠️⚠️ **打印机地址不在本页**（2026-09-21 用户裁定「打印设置从 `MOD-14` 合并进 `MOD-03`」）——
#   它的**唯一入口** = 付款通知书页的「打印机设置」弹窗（`mod03_notice/settings_store.apply_printer_setting`），
#   **唯一存储** = `.env`（`PRINTER_IPP_URL` / `PRINT_MODE` / `PRINTER_NAME` 三项）。
#   ⛔ 别再把它加回 `SPECS`：加回来就是**同一件事两个入口 ＋ 两套存储** ⇒ 会重现那个坑
#   （库里有值时，弹窗改的**不生效**，而回执还说"即时生效"）。


@dataclass(frozen=True)
class SettingSpec:
    """一个设置项。`env_attr` = `core.config.Settings` 上的属性名（**默认来源**，仅作字符串名，不 import config）。"""

    key: str
    env_attr: str
    label: str
    hint: str = ""
    kind: str = "url"          # url | text —— 供页面选控件与做格式校验


SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key=SETTING_I8_BASE_URL,
        env_attr="i8_base_url",
        label="i8 服务地址",
        hint="i8 装在哪台机器上（形如 http://主机:端口）。⚠️ **四项取数的地址由它推导**，不单独配。",
        kind="url",
    ),
    SettingSpec(
        key=SETTING_PRINT_ID_MATERIAL,
        env_attr="i8_print_id_material",
        label="材料类打印版式 ID",
        hint="⚠️ ⭐ **与直觉相反**：**材料类走的是「其他支出」版式**（§4.3.3）。配反了**会印错版式**。",
        kind="text",
    ),
    SettingSpec(
        key=SETTING_PRINT_ID_MECHANICAL,
        env_attr="i8_print_id_mechanical",
        label="外租机械类打印版式 ID",
        hint="⚠️ ⭐ **与直觉相反**：**外租机械类走的是「付款通知书」版式**（§4.3.3）。",
        kind="text",
    ),
)

SPEC_BY_KEY: dict[str, SettingSpec] = {s.key: s for s in SPECS}
SETTING_KEYS: tuple[str, ...] = tuple(s.key for s in SPECS)


# ------------------------------------------------------------------- 读取与缓存

_CACHE: dict[str, str] | None = None


#: ── 取数口（**装配层注入** · `TAIL-195` 批 1b）─────────────────────────────────
#: 实现 = `mod14_config.repository.read_values`（数据主人那边那份，**唯一一份**）；
#: 装配 = `app/core_bindings.py::register_all()`（`app/main.py` ＋ `backend/tests/conftest.py` 各调一次）。
_VALUES_LOADER: Callable[[], dict[str, str]] | None = None


def bind_values_loader(fn: Callable[[], dict[str, str]]) -> None:
    """装配层接上「读库里全部设置」的实现。

    ⚠️⚠️ 必须接**转发**（`lambda: R.read_values()`）—— ⛔ 别接模块级别名（`R.read_values`）：
       那会在接的那一刻把函数对象**绑死**，测试里 `monkeypatch.setattr(…, "read_values", …)` 就再也打不着
       （`TAIL-195` 批 2c 实测过这个坑：症状是 12 条判据当场红）。
    """
    global _VALUES_LOADER
    _VALUES_LOADER = fn


def _load_from_db() -> dict[str, str]:
    """从库读**全部**设置；库不可用 / 口没接上 ⇒ 回落空表（并记 warning，**不静默**）。"""
    fn = _VALUES_LOADER
    if fn is None:
        logger.warning("系统设置的取数口没接上（回落 .env）—— 见 `app.core_bindings.register_all()`")
        return {}
    try:
        return fn()
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("读系统设置失败（回落 .env）：%s: %s", type(exc).__name__, exc)
        return {}


def _values() -> dict[str, str]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_from_db()
    return _CACHE


def invalidate() -> None:
    """**保存设置后必须调用** —— 清本模块缓存 ＋ `get_settings()` 的 `lru_cache`。"""
    global _CACHE
    _CACHE = None
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
    except Exception:                                          # noqa: BLE001
        pass


def effective(key: str, fallback: str) -> str:
    """⭐ **取值出口**：库里有值就用库，否则回落 `fallback`（调用方一般传 `.env` 的值）。"""
    stored = (_values().get(key) or "").strip()
    return stored or (fallback or "").strip()


def stored_value(key: str) -> str:
    """**库里的原值**（空串 = 未设置）—— 页面据此区分「已设置 / 未设置」。"""
    return (_values().get(key) or "").strip()


def is_overridden(key: str) -> bool:
    return bool(stored_value(key))


# ------------------------------------------------------------------- 校验


def validate(key: str, value: str) -> str | None:
    """→ 错误信息（`None` = 通过）。空值**一律合法**（= 清除，回落 `.env`）。"""
    v = (value or "").strip()
    if not v:
        return None
    spec = SPEC_BY_KEY.get(key)
    if spec is None:
        return f"未知设置项：{key}"
    if spec.kind == "url" and not (v.startswith("http://") or v.startswith("https://") or v.startswith("ipp://")):
        return f"「{spec.label}」须以 http:// 或 https:// 或 ipp:// 开头"
    if spec.kind == "url":
        try:
            parsed = urlsplit(v)
            valid = bool(parsed.hostname) and not any(c.isspace() or ord(c) < 32 for c in v)
            valid = valid and parsed.username is None and parsed.password is None and not parsed.query and not parsed.fragment
            _ = parsed.port  # Invalid and out-of-range ports must be rejected before saving.
        except ValueError:
            valid = False
        if not valid:
            return f"「{spec.label}」地址格式不完整，请核对主机和端口；不要填写账号密码、查询参数或片段"
    return None


__all__ = [
    "SettingSpec", "SPECS", "SPEC_BY_KEY", "SETTING_KEYS",
    "SETTING_I8_BASE_URL", "SETTING_PRINT_ID_MATERIAL",
    "SETTING_PRINT_ID_MECHANICAL",
    "effective", "stored_value", "is_overridden", "invalidate", "validate",
]
