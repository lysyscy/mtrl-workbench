"""分层边界守卫（`TAIL-195` 结构债）—— **上半**：`app/core/**` 不得反向依赖业务包。

⭐ 为什么有这件：`core/` 是**内核**（配置 / DB / 金额口径 / 时间口径 / 日志 / 鉴权 / 统一报错），
   它被**全站**依赖 ⇒ 它若反过来 import 业务模块，就成**环**，`core` 再也没法独立理解或测试。
   ⚠️ 实测（2026-09-30 · `TAIL-195` 批 1）：`core` 里有 **4 个件**反向依赖业务包 ——
   `models_registry`（12 处 · 装配点，**已挪出 `core`** → `app/models_registry.py`）＋
   `app_settings` / `identity` / `projects`（各 1 处，都是"单点数据访问"）。
   ⇒ 本半把「**不再新增**」钉住：除 **放行名单**外，`core` 里不许出现 `app.mod*`。

⭐ `_ALLOW` 是 **(文件, 被 import 的业务顶层包)** 对 —— ⛔ 不是"整个文件放行"：
   按文件放行的话，往 `projects.py` 里**再塞一条** `from app.mod05_flow import …` 也会绿
   （而"悄悄多一条反向依赖"正是本守卫要拦的事）。
⭐ 名单里每条**必须仍然命中**（见第二条断言）⇒ 名单只许变短、⛔ 不许留幽灵条目
   （批 1b 把那 3 处改成"`core` 定义接口 ＋ 装配层注入"之后，名单清空）。

⚠️ **判据是静态的**（只读源码 ＋ `ast` 解析，⛔ 不 import app 包）—— 所以对"**函数内延迟 import**"
   那种形态同样有效（那正是本仓反向依赖的常见写法）。
⚠️ **下半**（`app/mod*` 不得 `import app.report_export`）属 `TAIL-195` **批 2**，届时在本件追加。

反向灵敏度：`tools/mut/_mut_layering.py`（往一个不在名单里的 `core` 件塞业务 import ⇒ 必红）。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.acc_plugin import acc

CORE = Path(__file__).resolve().parents[1] / "app" / "core"

#: ⭐ 放行名单：(相对 `app/core/` 的**文件名**, 被 import 的业务**顶层包**) → 为什么现在还留着。
_ALLOW: dict[tuple[str, str], str] = {
    ("app_settings.py", "app.mod14_config"):
        "单点数据访问（读系统设置那一张表）；彻底去掉要引入仓储接口/依赖注入 —— 属批 1b",
    ("identity.py", "app.mod15_user"):
        "单点数据访问（按身份取 i8 绑定）；同上，属批 1b",
    ("projects.py", "app.mod01_projects"):
        "项目三小件（唯一实现）要读 `Project` 模型；同上，属批 1b",
}

_BAD_TOP = "app.mod"


def _mod_imports(path: Path) -> list[str]:
    """一份源码里 import 的**业务顶层包**（`app.modXXXX_*`）—— 去重保序。

    ⚠️ 认 `Import` 与 `ImportFrom`（`level == 0`）；⛔ 不看相对 import（`core` 里没有那种写法）。
    ⚠️ 顶层包取**前两段**（`app.mod05_flow.repository` → `app.mod05_flow`）—— 名单按包粒度，不按件。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods = [node.module]
        else:
            continue
        for m in mods:
            if not m.startswith(_BAD_TOP):
                continue
            top = ".".join(m.split(".")[:2])
            if top not in out:
                out.append(top)
    return out


def _scan() -> dict[tuple[str, str], int]:
    """→ `{(文件名, 业务顶层包): 该件里出现它的次数}`（⛔ 只扫源文件，不碰 `__pycache__`）。"""
    found: dict[tuple[str, str], int] = {}
    files = sorted(p for p in CORE.rglob("*.py") if "__pycache__" not in p.parts)
    assert files, f"`{CORE}` 下一个 `.py` 都没扫到 —— 路径变了，本守卫已失效"
    for p in files:
        for top in _mod_imports(p):
            found[(p.name, top)] = found.get((p.name, top), 0) + 1
    return found


@acc()
def test_core_不得反向依赖业务包_除放行名单():
    found = _scan()
    extra = sorted(k for k in found if k not in _ALLOW)
    assert not extra, (
        "`app/core/**` 里出现了**新的** `import app.mod*` 反向依赖（core 是内核，全站都依赖它 ⇒ "
        "反向依赖会成环、core 就没法独立理解或测试）：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in extra)
        + "\n  ⇒ 修法：改成「`core` 定义接口 ＋ 装配层注入」，或走中立件；"
          "⛔ 别把它加进 `_ALLOW`（那份名单只许变短）。"
    )


@acc()
def test_放行名单里不许留幽灵条目():
    """名单里每条**必须仍然命中** —— 某条反向依赖被去掉（如批 1b 做完）却忘了删名单 ⇒ 名单变假口径。"""
    found = _scan()
    stale = sorted(set(_ALLOW) - set(found))
    assert not stale, (
        "`test_layering` 的放行名单里有**已经不存在**的条目（那条反向依赖已经没了 ⇒ "
        "名单该删没删，留着会让人以为 `core` 还在依赖它）：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in stale)
    )
