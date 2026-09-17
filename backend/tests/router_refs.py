"""**路由静态引用自检**的公共件 —— 扫路由里的 `别名.属性` 是否**真实存在**。

⚠️ 它守的是一类**离线断言天生看不见**的错：路由里写 `别名.出口`，若那个出口其实住在**另一个模块**，
   而所有断言都是**直接调函数**（不走 HTTP）⇒ 全部照绿，只有**真机请求**才会 500。
   （2026-09-17 活动大表实测一次：`parse_state` 住在 `big_service`，router 里写成了 `big_domain.parse_state`。）

⚠️ **按 glob 发现路由**（⛔ 不逐份列清单）—— 逐份列会让**新加的路由文件漏网不被查**。
"""

from __future__ import annotations

import importlib
import pathlib
import re
from types import ModuleType

# `from X import a, b as c` / `from X import (a, b as c)` 两类都吃
_FROM_RE = re.compile(r"^from ([\w.]+) import (.*)$", re.M)
_IMPORT_AS_RE = re.compile(r"^import ([\w.]+) as (\w+)$", re.M)

#: 行文里提到文件名（`importer.py`）时的"伪属性"
FILE_SUFFIXES: frozenset[str] = frozenset(
    {"py", "md", "json", "html", "css", "js", "txt", "xlsx", "xls", "csv", "ini", "sql",
     "log", "png", "pdf", "ps1", "bat"}
)


def app_dir() -> pathlib.Path:
    return pathlib.Path(importlib.import_module("app").__file__).resolve().parent


def router_modules() -> list[tuple[str, ModuleType]]:
    """全站路由件：`(相对路径, 模块)` —— 文件名**含 `router`** 的都算（`import_router.py` 等分件也在内）。"""
    root = app_dir()
    out: list[tuple[str, ModuleType]] = []
    for path in sorted(root.glob("**/*router*.py")):
        rel = path.relative_to(root.parent).with_suffix("")
        name = ".".join(rel.parts)
        out.append((str(path.relative_to(root.parent)), importlib.import_module(name)))
    return out


def _alias_pairs(src: str) -> list[tuple[str, str, str]]:
    """源码 → `[(来源模块, 原名, 引用名)]`。

    ⚠️ **没写 `as` 的也要查** —— 实测踩到：`from app.mod06_proc import importer, mech_ui, repository as repo`
    里只有 `repo` 带别名，而**出错的恰恰是不带别名的那两个**（`mech_ui.normalize_ym` 根本不存在）。
    ⇒ 引用名默认 = 导入名本身。
    """
    pairs: list[tuple[str, str, str]] = []
    for module_path, names in _FROM_RE.findall(src):
        for item in names.split(","):
            item = item.strip().strip("()").strip()
            if not item:
                continue
            if " as " in item:
                name, _, alias = item.partition(" as ")
            else:
                name, alias = item, item
            pairs.append((module_path.strip(), name.strip(), alias.strip()))
    for module_path, alias in _IMPORT_AS_RE.findall(src):
        pairs.append((module_path, module_path.split(".")[-1], alias))
    return pairs


def _code_only(src: str) -> str:
    """去掉行内注释 —— 注释里写 `importer.py` 会被正则当成 `importer.py` 这个属性（实测误报一次）。"""
    return "\n".join(re.sub(r"(?<![:'\"])#.*$", "", line) for line in src.splitlines())


def broken_refs(module: ModuleType) -> list[str]:
    """该路由件里**引用了但不存在**的 `引用名.属性`（空 = 没问题）。"""
    src = _code_only(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    bad: list[str] = []
    for module_path, name, alias in _alias_pairs(src):
        if not alias or not re.match(r"^[A-Za-z_]\w*$", alias):
            continue
        obj = getattr(importlib.import_module(module_path), name, None)
        if obj is None:
            bad.append(f"`{module_path}.{name}` 导入失败（引用名 `{alias}`）")
            continue
        for attr in sorted(set(re.findall(rf"\b{re.escape(alias)}\.([A-Za-z_]\w*)", src))):
            if attr in FILE_SUFFIXES:                  # 文里提到 `xxx.py` 不算属性访问
                continue
            if not hasattr(obj, attr):
                bad.append(f"`{alias}.{attr}`（= `{module_path}.{name}`）不存在")
    return bad


__all__ = ["app_dir", "router_modules", "broken_refs"]
