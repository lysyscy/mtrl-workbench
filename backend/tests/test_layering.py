"""分层边界守卫（`TAIL-195` 结构债）—— **上半**：`core` 不得反向依赖业务包；
**下半**：两条「环」的机器化（方案 §3.3）。

⭐ 为什么有这件：**依赖方向错了，改一侧就牵动另一侧** —— `core` 被全站依赖、`report_export` 被
   9 个业务包反过来依赖、`mod03`/`mod05` 互相直查对方的表 ⇒ 这些地方**没有一处尺子看得见**。
   本件把它们变成**每轮非过不可**的判据。

三条规则（各自带**放行名单**起步 ⇒ 拆一处、销一条，名单只许变短）：

| 规则 | 禁什么 | 依据 |
|---|---|---|
| **A（上半）** | `app/core/**` ⛔ `import app.mod*` | `core` 是内核，全站依赖它 ⇒ 反向依赖即成环（`models_registry` 已挪走，余 3 处例外） |
| **B（下半）** | `app/mod*/**` ⛔ `import app.report_export` | 方案 §3.3 第一半（`TAIL-195` 批 2 · 案②）—— 导出器**只许按名取**（`app.export_registry`，表在 `app/export_bindings.py`） |
| **B2（下半）** | `app/export_registry.py` ⛔ `import` 任何 `app.*` | 规则 B 的**反绕过**：注册表必须是**叶子**，否则环换个名字继续存在 |
| **C（下半）** | `mod03` ⛔ `import app.mod05_flow.repository`／`mod05` ⛔ `import app.mod03_notice.repository` | 计划 **§2.3**「包间只经 `service` 调用，**不得跨包直查对方表**」（方案 §3.3 第二半） |

⚠️ **判据是静态的**（只读源码 ＋ `ast` 解析，⛔ 不 import app 包）—— 所以对"**函数内延迟 import**"
   那种形态同样有效（那正是本仓跨包引用的常见写法）。
⚠️ **每条规则都带"扫到的件太少 ⇒ 判据自己坏了"的断言**（⛔ 别让"扫到空集"伪装成"没有违规"）。
⚠️ 规则 **B** 只管 `app/mod*/`；**测试**（`backend/tests/**`）直接 import `app.report_export` 是**正当的**
   （测试不在应用的依赖图里，它就该直接调被测件）。

反向灵敏度：`tools/mut/_mut_layering.py`（每条规则各一靶 ⇒ 必红）。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.acc_plugin import acc

APP = Path(__file__).resolve().parents[1] / "app"
CORE = APP / "core"
MOD03 = APP / "mod03_notice"
MOD05 = APP / "mod05_flow"

#: ── 规则 A（上半）── (相对 `app/core/` 的文件名, 被 import 的业务顶层包) → 为什么现在还留着
_ALLOW_A: dict[tuple[str, str], str] = {
    ("app_settings.py", "app.mod14_config"):
        "单点数据访问（读系统设置那一张表）；彻底去掉要引入仓储接口/依赖注入 —— 属批 1b",
    ("identity.py", "app.mod15_user"):
        "单点数据访问（按身份取 i8 绑定）；同上，属批 1b",
    ("projects.py", "app.mod01_projects"):
        "项目三小件（唯一实现）要读 `Project` 模型；同上，属批 1b",
}

#: ── 规则 B（下半）── 相对 `backend/app` 的路径 → 为什么现在还留着
#: ⭐ **2026-09-30 批 2b 已清空**（12 处全改走 `app.export_registry` 按名取）⇒ 名单只剩空表：
#:    ⛔ 别为了"加个导出调用"往里添条目 —— 业务包取导出器**只许**经注册表（表在 `app/export_bindings.py`）。
_ALLOW_B: dict[str, str] = {}

#: 注册表**必须是叶子**（业务包 import 它 ⇒ 它一旦 import 导出层，环就换个名字继续存在）
_REGISTRY = APP / "export_registry.py"

#: ── 规则 C（下半）── (相对 `backend/app` 的路径, 被禁的模块) → 为什么现在还留着
#: ⭐ **2026-09-30 批 2a 已清空**（3 处全改走对方的 `service` 包间出口）⇒ 名单只剩空表：
#:    ⛔ 别为了"加个口子"往里添条目 —— 跨包读要经对方包的 `service`（§2.3）。
_ALLOW_C: dict[tuple[str, str], str] = {}

_BAD_TOP = "app.mod"


def _import_targets(path: Path) -> list[tuple[int, tuple[str, ...]]]:
    """→ `[(行号, 这条 import 可能触到的模块路径)]`。

    ⚠️⚠️ **必须把 `from X import Y` 展开成 `X` 与 `X.Y` 两份** —— 这是本仓的**老课**：
       `from app.mod05_flow import repository as flow_repo` 的 `node.module` 只是 `app.mod05_flow`，
       只按 `node.module` 判会**漏掉那条"直查对方表"**（本判据第一版就是这么漏的）。
    ⚠️ 认 `Import` 与 `ImportFrom`（`level == 0`）；`ast.walk` 全树扫 ⇒ **函数内延迟 import 也收**。
    ⛔ 不看相对 import（本仓 `app/` 里没有那种写法）。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[int, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.append((node.lineno, tuple(a.name for a in node.names)))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.append((node.lineno, (node.module,)
                        + tuple(f"{node.module}.{a.name}" for a in node.names)))
    return out


def _count_touching(path: Path, predicate) -> int:
    """这条文件里有**几条 import 语句**触到了 `predicate` 认的模块（一条语句算一处）。"""
    return sum(1 for _, cands in _import_targets(path) if any(predicate(c) for c in cands))


def _py_files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def _mod_imports(path: Path) -> list[str]:
    """一份源码里 import 的**业务顶层包**（`app.modXXXX_*`）—— 去重保序（规则 A 用）。"""
    out: list[str] = []
    for _, cands in _import_targets(path):
        for m in cands:
            if not m.startswith(_BAD_TOP):
                continue
            top = ".".join(m.split(".")[:2])      # app.mod05_flow.repository → app.mod05_flow
            if top not in out:
                out.append(top)
    return out


# ------------------------------------------------------------------------- 规则 A


def _scan_a() -> dict[tuple[str, str], int]:
    """→ `{(文件名, 业务顶层包): 次数}`（⛔ 只扫源文件）。"""
    found: dict[tuple[str, str], int] = {}
    files = _py_files(CORE)
    assert len(files) >= 8, f"`{CORE}` 下只扫到 {len(files)} 个 `.py` —— 路径变了，规则 A 已失效"
    for p in files:
        for top in _mod_imports(p):
            found[(p.name, top)] = found.get((p.name, top), 0) + 1
    return found


@acc()
def test_A_core_不得反向依赖业务包_除放行名单():
    found = _scan_a()
    extra = sorted(k for k in found if k not in _ALLOW_A)
    assert not extra, (
        "`app/core/**` 里出现了**新的** `import app.mod*` 反向依赖（core 是内核，全站都依赖它 ⇒ "
        "反向依赖会成环、core 就没法独立理解或测试）：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in extra)
        + "\n  ⇒ 修法：改成「`core` 定义接口 ＋ 装配层注入」，或走中立件；"
          "⛔ 别把它加进 `_ALLOW_A`（那份名单只许变短）。"
    )


@acc()
def test_A_放行名单里不许留幽灵条目():
    """名单里每条**必须仍然命中** —— 某条反向依赖被去掉（如批 1b 做完）却忘了删名单 ⇒ 名单变假口径。"""
    stale = sorted(set(_ALLOW_A) - set(_scan_a()))
    assert not stale, (
        "`_ALLOW_A` 里有**已经不存在**的条目（那条反向依赖已经没了 ⇒ 名单该删没删）：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in stale)
    )


# ------------------------------------------------------------------------- 规则 B


def _is_export_layer(m: str) -> bool:
    return m == "app.report_export" or m.startswith("app.report_export.")


def _scan_b() -> dict[str, int]:
    """→ `{相对 `backend/app` 的路径: 该件里 `import app.report_export*` 的次数}`。"""
    found: dict[str, int] = {}
    mods = sorted(p for p in APP.glob("mod*") if p.is_dir())
    assert len(mods) >= 10, f"`{APP}` 下只扫到 {len(mods)} 个 `mod*` 包 —— 路径变了，规则 B 已失效"
    for d in mods:
        for p in _py_files(d):
            n = _count_touching(p, _is_export_layer)
            if n:
                found[p.relative_to(APP).as_posix()] = n
    return found


@acc()
def test_B_业务包不得直接_import_导出层_除放行名单():
    found = _scan_b()
    extra = sorted(k for k in found if k not in _ALLOW_B)
    assert not extra, (
        "业务包（`app/mod*/**`）里出现了**新的** `import app.report_export` —— 这会让"
        "「导出层 ⇄ 业务包」成环（改一侧牵动另一侧）：\n  "
        + "\n  ".join(f"{f}（{found[f]} 处）" for f in extra)
        + "\n  ⇒ 修法（方案 §3.3 案②）：导出器在**装配层注册**，业务包从注册表**按名取**（⛔ 别直接 import）；"
          "⛔ 别把它加进 `_ALLOW_B`（那份名单只许变短）。"
    )


@acc()
def test_B_放行名单里不许留幽灵条目():
    stale = sorted(set(_ALLOW_B) - set(_scan_b()))
    assert not stale, (
        "`_ALLOW_B` 里有**已经不存在**的条目（那处 import 已经没了 ⇒ 名单该删没删）：\n  "
        + "\n  ".join(stale)
    )


@acc()
def test_B2_注册表必须是叶子件():
    """`app/export_registry.py` ⛔ 不得 `import` 任何 `app.*`。

    ⭐ 为什么单立一条（它是规则 B 的**反绕过**那一半）：注册表一旦 import 了导出层，
       「业务 → 注册表 → 导出层 → 业务」就是**换了个名字的同一个环**，而规则 B 照样绿 ⇒
       那是"**绕开结构问题**"的假绿（比不立规则更坏）。⇒ 填表的事只许在 `app/export_bindings.py`。
    """
    assert _REGISTRY.exists(), f"`{_REGISTRY}` 不在 —— 规则 B 的落点没了（改路径要同批改本判据）"
    hits = [(ln, m) for ln, cands in _import_targets(_REGISTRY) for m in cands
            if m == "app" or m.startswith("app.")]
    assert not hits, (
        "`app/export_registry.py` 是**叶子件**（业务包 import 它）⇒ ⛔ 不许 import 任何 `app.*`：\n  "
        + "\n  ".join(f"L{ln}: {m}" for ln, m in hits)
        + "\n  ⇒ 要填表请改 `app/export_bindings.py`（装配层）—— 那里才是 import 导出层的地方。"
    )


#: 业务侧"按名取"的写法：`EXP.get("<名>")`（`EXP` 是各调用点给 `export_registry` 起的名）
_GET_RE = re.compile(r'\bEXP\.get\("([a-z0-9_]+)"\)')


@acc()
def test_B3_业务按名取的每个名字都必须在绑定表里():
    """规则 B 的**另一半**：业务写的名字必须与装配层那张表对得上。

    ⭐ 为什么必须有：注册表的失败是**运行期**的（某条导出端点第一次被点到才炸）⇒ 光靠
       `get()` 报错要等线上才发现。本判据把它提前到**每轮 pytest**。
    """
    from app import export_bindings as bindings

    used: set[str] = set()
    mods = sorted(p for p in APP.glob("mod*") if p.is_dir())
    assert len(mods) >= 10, f"`{APP}` 下只扫到 {len(mods)} 个 `mod*` 包 —— 规则 B3 已失效"
    for d in mods:
        for p in _py_files(d):
            used |= set(_GET_RE.findall(p.read_text(encoding="utf-8")))
    assert used, ("一个 `EXP.get(\"…\")` 都没扫到 —— 写法变了，规则 B3 已失效"
                  "（⛔ 别让它静默通过）")

    unknown = sorted(used - set(bindings.BINDINGS))
    assert not unknown, (
        "业务包按名取的这些名字**不在**装配层的绑定表里（`app/export_bindings.BINDINGS`）⇒ "
        "那条导出端点第一次被点到就会抛「没有注册」：\n  "
        + "\n  ".join(unknown)
        + "\n  ⇒ 在 `app/export_bindings.py` 的表里补上（⛔ 别在该模块里另开第二条取件路）。"
    )
    # 顺带确认那张表**填得进**注册表（`register_all` 幂等；漏填会在第一次取件时才炸）
    bindings.register_all()


# ------------------------------------------------------------------------- 规则 C


def _scan_c() -> dict[tuple[str, str], int]:
    """→ `{(相对 `backend/app` 的路径, 被禁模块): 次数}` —— 两个方向都扫。"""
    def touch(banned: str):
        return lambda m: m == banned or m.startswith(banned + ".")

    found: dict[tuple[str, str], int] = {}
    pairs = ((MOD03, "app.mod05_flow.repository"), (MOD05, "app.mod03_notice.repository"))
    for base, banned in pairs:
        files = _py_files(base)
        assert len(files) >= 8, f"`{base}` 下只扫到 {len(files)} 个 `.py` —— 路径变了，规则 C 已失效"
        for p in files:
            n = _count_touching(p, touch(banned))
            if n:
                found[(p.relative_to(APP).as_posix(), banned)] = n
    return found


@acc()
def test_C_包间不得直查对方表_只许经包间出口():
    """计划 §2.3「包间只经 `service` 调用，**不得跨包直查对方表**」的机器化（方案 §3.3 第二半）。"""
    found = _scan_c()
    extra = sorted(k for k in found if k not in _ALLOW_C)
    assert not extra, (
        "包间**直查了对方表**（`import` 对了对方的 `repository`）—— 按计划 §2.3 只许经**包间出口**：\n  "
        + "\n  ".join(f"{f} → {m}（{found[(f, m)]} 处）" for f, m in extra)
        + "\n  ⇒ 修法：改走对方包的**包间出口**（`service`／只读 `api`），把查询留在那个包里；"
          "⛔ 别复制一份查询到本包（那是第二套口径）；⛔ 别把它加进 `_ALLOW_C`。"
    )


@acc()
def test_C_放行名单里不许留幽灵条目():
    stale = sorted(set(_ALLOW_C) - set(_scan_c()))
    assert not stale, (
        "`_ALLOW_C` 里有**已经不存在**的条目（那处 import 已经没了 ⇒ 名单该删没删）：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in stale)
    )
