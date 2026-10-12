"""查询文本的纯读取：不决定字段、默认期间、合法值或多选规则。"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class MultiValues(Protocol):
    def keys(self): ...

    def getlist(self, key: str) -> list[str]: ...


def flatten_query(params: MultiValues) -> dict:
    """保留同名参数顺序；单值为字符串，多值为列表，空值不丢弃。"""
    out: dict = {}
    for key in params.keys():
        vals = params.getlist(key)
        out[key] = vals if len(vals) > 1 else (vals[0] if vals else "")
    return out


def query_one(params: Mapping | None, name: str, default: str = "") -> str:
    """缺席用 default；列表/元组取首项；None/空列表为空，0 保留；去两端空白。"""
    value = (params or {}).get(name, default)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if value is None:
        value = ""
    return str(value).strip()
