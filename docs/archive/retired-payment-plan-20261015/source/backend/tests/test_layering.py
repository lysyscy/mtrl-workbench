"""分层边界守卫（`TAIL-195` 结构债）—— **上半**：`core` 不得反向依赖业务包；
**下半**：两条「环」的机器化（方案 §3.3）。

⭐ 为什么有这件：**依赖方向错了，改一侧就牵动另一侧** —— `core` 被全站依赖、`report_export` 被
   9 个业务包反过来依赖、`mod03`/`mod05` 互相直查对方的表 ⇒ 这些地方**没有一处尺子看得见**。
   本件把它们变成**每轮非过不可**的判据。

分层规则（各自带**放行名单**起步 ⇒ 拆一处、销一条，名单只许变短）：

| 规则 | 禁什么 | 依据 |
|---|---|---|
| **A（上半）** | `app/core/**` ⛔ `import app.mod*` | `core` 是内核，全站依赖它 ⇒ 反向依赖即成环（**名单已清空**：`models_registry` 挪走 ＋ 另 3 处改成"口 ＋ 装配层注入"） |
| **B（下半）** | `app/mod*/**` ⛔ `import app.report_export` | 方案 §3.3 第一半（`TAIL-195` 批 2 · 案②）—— 导出器**只许按名取**（`app.export_registry`，表在 `app/export_bindings.py`） |
| **B2（下半）** | `app/export_registry.py` ⛔ `import` 任何 `app.*` | 规则 B 的**反绕过**：注册表必须是**叶子**，否则环换个名字继续存在 |
| **C（一般式 · `TAIL-218`）** | **任一 `app/mod*/**` ⛔ `import` **别包**的 `repository`（⛔ 自己包的随便用） | 计划 **§2.3**「包间只经 `service` 调用，**不得跨包直查对方表**」——⭐ **2026-10-02 起升一般式**：原先只罩 `mod03`↔`mod05` **两条边**，实测另有 **17 处 / 13 件**没人管（其中 **11 处同族指向 `mod01_projects`**，而它**当时根本没有 `service.py`** —— ⭐ 批 2 已补上，那 11 处全清）⇒ ⭐ **批 3 后全仓已无待清项**（只剩 1 处**按设计的例外**）⇒ 施工图 = `work/10-designs/设计-分层门禁一般式-20261002.md` · 尾巴 = `TAIL-218` |
| **D（下半）** | `app/report_export/**` ⛔ `import app.mod*.repository` | 同上（`TAIL-195` 批 2c）—— 导出层只许用业务包的 `domain` / `models` / `service` |
| **C2（TAIL-299）** | `app/mod*/**` 不得把别包models的类或列当查询目标 | 五形态；typing/domain/join条件放行。待清与按设计例外分表登记，全部条目必须仍命中 |

⭐ **规则 C 有两张名单**（⛔ **性质不同，别混**）：`_ALLOW_C_PENDING`（**待清** · 只许变短）/ `_ALLOW_C_BY_DESIGN`（**按设计的例外** · 看理由、不看数量）。
⭐ **出口那一层的约定全仓一致**（`mod03_notice` / `mod05_flow` / `mod06_proc` / `mod09_fee` 的 `service.py` 里都写着「⚠️⚠️ 跨包调用**只许经这一层**」）⇒ 别为单个调用者单开一层"只会转手的窗口"（用户 2026-10-02 明确否过那种形式主义）。

⚠️ **判据是静态的**（只读源码 ＋ `ast` 解析，⛔ 不 import app 包）—— 所以对"**函数内延迟 import**"
   那种形态同样有效（那正是本仓跨包引用的常见写法）。
⚠️ **每条规则都带"扫到的件太少 ⇒ 判据自己坏了"的断言**（⛔ 别让"扫到空集"伪装成"没有违规"）。
⚠️ 规则 **B** 只管 `app/mod*/`；**测试**（`backend/tests/**`）直接 import `app.report_export` 是**正当的**
   （测试不在应用的依赖图里，它就该直接调被测件）。

反向灵敏度：`tools/mut/_mut_layering.py`（每条规则各一靶 ⇒ 必红）。
"""

from __future__ import annotations

import ast
import importlib.util
import re
from collections import Counter

from pathlib import Path

from tests.acc_plugin import acc

APP = Path(__file__).resolve().parents[1] / "app"
CORE = APP / "core"


def _query_targets(source: str, own: str, package: str | None = None) -> list[tuple[str, str, int]]:
    """C2：只识别查询目标；typing/domain/where/join 条件不算目标。

    支持类别名、models模块别名及绝对/相对import；返回(函数, 模型, 行)。
    ORM接收者认Session注解、session_scope绑定和本仓s/session约定，普通映射get放行。
    """
    tree = ast.parse(source)
    hits = []

    def dotted(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = dotted(node.value)
            return f"{base}.{node.attr}" if base else ""
        return ""

    def resolve(node, aliases):
        name = dotted(node)
        head, _, tail = name.partition('.')
        return aliases.get(head, head) + ('.' + tail if tail else '')

    def selected(node, aliases, statements):
        if isinstance(node, ast.Name):
            return node.id in statements
        if isinstance(node, ast.Call):
            if resolve(node.func, aliases) in ('sqlalchemy.select', 'sqlalchemy.sql.select', 'sqlalchemy.sql.expression.select'):
                return True
            if isinstance(node.func, ast.Attribute):
                return selected(node.func.value, aliases, statements)
        return False

    def visit(node, aliases, sessions, statements, function="<module>"):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            aliases = dict(aliases)
            sessions, statements = set(sessions), set(statements)
            if not isinstance(node, ast.Module):
                function = node.name
            # 函数调用发生在模块加载后；定义之后的模块import同样生效。
            # 各词法作用域先取自己的imports，不能把别的函数局部import混进来。
            def collect(scope):
                for child in ast.iter_child_nodes(scope):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        continue
                    if isinstance(child, ast.ImportFrom):
                        module = child.module or ''
                        if child.level:
                            module = importlib.util.resolve_name('.' * child.level + module, package or own)
                        for a in child.names:
                            aliases[a.asname or a.name] = f"{module}.{a.name}"
                    elif isinstance(child, ast.Import):
                        for a in child.names:
                            aliases[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
                    else:
                        collect(child)
            collect(node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    if arg.annotation and any(resolve(part, aliases) in ('sqlalchemy.orm.Session', 'sqlalchemy.orm.session.Session')
                                              for part in ast.walk(arg.annotation)):
                        sessions.add(arg.arg)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if dotted(node.value) in sessions:
                        sessions.add(target.id)
                    if selected(node.value, aliases, statements):
                        statements.add(target.id)
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if (isinstance(item.context_expr, ast.Call) and isinstance(item.optional_vars, ast.Name)
                        and resolve(item.context_expr.func, aliases) == 'app.core.db.session_scope'):
                    sessions.add(item.optional_vars.id)
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            resolved = resolve(node.func, aliases)
            method = node.func.attr if isinstance(node.func, ast.Attribute) else name
            is_select = resolved in ('sqlalchemy.select', 'sqlalchemy.sql.select', 'sqlalchemy.sql.expression.select')
            receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
            is_session = dotted(receiver) in sessions
            if is_select or (method in ('get', 'query') and is_session) or (method == 'select_from' and selected(receiver, aliases, statements)):
                args = node.args if is_select or method in ('query', 'select_from') else node.args[:1]
                if method == 'get' and not args:
                    args = [kw.value for kw in node.keywords if kw.arg == 'entity']
                models = set()
                for arg in args:
                    for part in ast.walk(arg):
                        ref = dotted(part)
                        first, _, rest = ref.partition('.')
                        ref = aliases.get(first, first) + ('.' + rest if rest else '')
                        match = re.match(r'^(app\.mod\d+_[a-z0-9_]+)\.models\.([A-Z]\w*)(?:\.|$)', ref)
                        if match and match[1] != own:
                            models.add(f"{match[1]}.models.{match[2]}")
                hits.extend((function, model, node.lineno) for model in sorted(models))
        for child in ast.iter_child_nodes(node):
            visit(child, aliases, sessions, statements, function)

    visit(tree, {}, {'s', 'session'}, set())
    return hits


# 按查询处登记（文件、函数、模型）；同处再多一次查询也必须报红。
# 待清项逐条归TAIL-300；按设计锁不占待清名额。起点只许变短。
_ALLOW_C2_PENDING: dict[tuple[str, str, str], str] = {}
_ALLOW_C2_BY_DESIGN: dict[tuple[str, str, str], str] = {
    ("mod05_flow/router.py", "api_revoke", "app.mod03_notice.models.PaymentNotice"):
        "撤销付款必须在付款侧同一事务内锁通知书行，从事实重读/确认到撤销流水/重算都保持锁；转手另开事务会破坏临界区",
}
_C2_PENDING_START = 16  # 原预估10；2026-10-12完整实扫补6处，按实际登记


def _scan_c2() -> Counter:
    """只扫app/mod*/**，与C同面；app顶层、home、report_export在面外。

    包数/件数下限防空扫；名单逐条命中由独立判据验证。
    可删除条件：业务包不再接触别包models，规则C足以守住全部直查入口。
    """
    pkgs = sorted(p for p in APP.glob('mod*') if p.is_dir())
    assert len(pkgs) >= 10, '规则 C2 包数不足，扫描面失效'
    files = [(d, p) for d in pkgs for p in _py_files(d)]
    assert len(files) >= 100, '规则 C2 件数不足，扫描面失效'
    found = Counter()
    for d, p in files:
        package = 'app.' + '.'.join(p.parent.relative_to(APP).parts)
        for fn, model, _ in _query_targets(p.read_text(encoding='utf-8'), f'app.{d.name}', package):
            found[(p.relative_to(APP).as_posix(), fn, model)] += 1
    return found


@acc()
def test_C2_不得把别包模型当查询目标():
    allowed = set(_ALLOW_C2_PENDING) | set(_ALLOW_C2_BY_DESIGN)
    extra = {key: n for key, n in _scan_c2().items() if key not in allowed or n != 1}
    assert not extra, f'跨包查询目标必须走主人service；新直查或同处增加查询：{extra}'


@acc()
def test_C2_名单逐条命中且待清只许变短():
    assert len(_ALLOW_C2_PENDING) <= _C2_PENDING_START, 'C2 待清名单不许变长'
    assert not set(_ALLOW_C2_PENDING) & set(_ALLOW_C2_BY_DESIGN), 'C2 两张名单不能重叠'
    stale = (set(_ALLOW_C2_PENDING) | set(_ALLOW_C2_BY_DESIGN)) - set(_scan_c2())
    assert not stale, f'C2 名单未被扫出：{stale}'

#: ── 规则 A（上半）── (相对 `app/core/` 的文件名, 被 import 的业务顶层包) → 为什么现在还留着
#: ⭐ **2026-09-30 批 1b 已清空**：三处「`core` 里的函数运行期读业务包的表」改成
#:    **口留在 `core`（`bind_*`）＋ 取数实现归数据主人 ＋ 装配层接线（`app/core_bindings.py`）** ⇒ 只剩空表。
#:    ⛔ 别为了"core 里要用一下业务包"往里添条目 —— 正确做法是**再开一个口**（`core` 里加 `bind_*`）
#:    并在 `app/core_bindings.py` 接上；`core` 只留**口**，取数归数据主人。
_ALLOW_A: dict[tuple[str, str], str] = {}

#: ── 规则 B（下半）── 相对 `backend/app` 的路径 → 为什么现在还留着
#: ⭐ **2026-09-30 批 2b 已清空**（12 处全改走 `app.export_registry` 按名取）⇒ 名单只剩空表：
#:    ⛔ 别为了"加个导出调用"往里添条目 —— 业务包取导出器**只许**经注册表（表在 `app/export_bindings.py`）。
_ALLOW_B: dict[str, str] = {}

#: 注册表**必须是叶子**（业务包 import 它 ⇒ 它一旦 import 导出层，环就换个名字继续存在）
_REGISTRY = APP / "export_registry.py"

#: ── 规则 D（下半）── (相对 `backend/app` 的路径, 被禁模块) → 为什么现在还留着
#: ⭐ **2026-09-30 批 2c 已清空**（`report_export/service.py` 那 2 处 `mod09_fee`/`mod06_proc` 的
#:    `repository` 直查，改成走对方的 `service` 包间出口）⇒ 名单只剩空表。
_ALLOW_D: dict[tuple[str, str], str] = {}

RE = APP / "report_export"
#: 「直查业务包的表」的形态：`app.modNN_xxx.repository`（含它的子模块）
_BAD_REPO_RE = re.compile(r"^app\.mod\d+_[a-z_]+\.repository($|\.)")

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


# ------------------------------------------------------------------------- 规则 C（一般式）

#: 「翻别人账本」的形态：`app.modNN_xxx.repository`（含它的子模块）
_BAD_CROSS_REPO_RE = re.compile(r"^app\.mod\d+_[a-z_]+\.repository($|\.)")

#: ── ① **待清名单**（⛔ **只许变短**）：**已清空**（起点 13 条 ⇒ 批 2 清 11 · 批 3 清 3）。
#:    ⚠️ 填法要求（日后若又长出来）：**写具体落点**（哪个出口 / 哪一批），⛔ 别只写文件名 —— 名单要能自己催自己。
#:    ⭐ **2026-10-02 批 2**：11 处指向 `mod01_projects` 的全清（`mod01_projects/service.py` 开出来）⇒ 13 → 3。
#:    ⭐ **2026-10-02 批 3**：余 3 处全清（B 组 `mod06_proc` 的出口**现成** · C 组 `mod08_inv` / `mod04_plan`
#:       各补 **1 个同型出口**）⇒ 3 → **0**。
#:    ⇒ 全仓现在只剩 **1 处按设计的例外**（见下表 —— ⛔ 那不是待清项）。
_ALLOW_C_PENDING: dict[tuple[str, str], str] = {}

#: ── ② **按设计的例外**（⭐ **看理由，不看数量** —— ⛔ 与"待清"是两码事）
#:    判它能不能进本表，只问一句：**给它加一个转手出口，结构会不会真的变好？**
#:    ⛔ 若答案只是"把手伸过去改个名字" ⇒ 进本表（并写清出处），⛔ 别进 `_ALLOW_C_PENDING`。
_ALLOW_C_BY_DESIGN: dict[tuple[str, str], str] = {
    ("mod14_config/jc_ignore_api.py", "app.mod11_jc.repository"):
        "页面在 M14 / 数据主人在集采域（本文件头三行）· 方向单向不成环 · 与付款侧 `rules_api.py` 同构；"
        "⭐ 只有 1 个调用者 ⇒ 加 4 个 `return R.xxx()` 只是「把手伸过去改个名字」（用户 2026-10-02 否掉的做法）",
}

#: ⭐ **起点条数 —— 只许往下改**（想加条目 ⇒ 先回答"为什么不走出口"；⛔ 别把这条数调大）
#:    ⚠️ 变了要同批改：施工图 `work/10-designs/设计-分层门禁一般式-20261002.md` §四 的分批进度 ＋ 计划 `§15`。
#:    ⭐ 2026-10-02 批 3 后 = **0**（全仓无待清项 ⇒ 这条现在是"⛔ 不许再长出第二条"的闸）。
_C_PENDING_START: int = 0

_LAYER_C_TABLES = (_ALLOW_C_PENDING, _ALLOW_C_BY_DESIGN)   #: 两张表（⛔ 别在别处再写一份）


def _scan_c() -> dict[tuple[str, str], int]:
    """→ `{(相对 `backend/app` 的路径, 被翻的 `repository`): 次数}`（**一般式** · 扫全部 `mod*` 包）。

    ⚠️ **自己包的 `repository` 不受影响**（翻自己的账本正当）⇒ 按"本包前缀"排除。
    ⚠️ **扫描面 = `app/mod*/**`** ⇒ `app/` 顶层（装配层 `core_bindings.py` / `export_bindings.py`）
       **天然豁免** —— 装配层**就是**干"接线"这件事的地方，⛔ 不用往名单里塞条目。
    ⚠️ 两条防"空扫"断言（⛔ 别让"扫到空集"伪装成"没有违规"）。
    """
    found: dict[tuple[str, str], int] = {}
    pkgs = sorted(p for p in APP.glob("mod*") if p.is_dir())
    assert len(pkgs) >= 10, f"`{APP}` 下只扫到 {len(pkgs)} 个 `mod*` 包 —— 路径变了，规则 C 已失效"
    scanned = 0
    for d in pkgs:
        own = f"app.{d.name}"
        for p in _py_files(d):
            scanned += 1
            for _, cands in _import_targets(p):
                for m in cands:
                    if not _BAD_CROSS_REPO_RE.match(m):
                        continue
                    target = m.split(".repository", 1)[0]        # app.mod05_flow
                    if target == own:                            # 翻自己的账本：正当
                        continue
                    key = (p.relative_to(APP).as_posix(), f"{target}.repository")
                    found[key] = found.get(key, 0) + 1
    assert scanned >= 100, (f"只扫到 {scanned} 个 `.py` —— 扫描面变了，规则 C 已失效"
                            "（⛔ 别让空扫伪装成没有违规）")
    return found


def _c_allowed() -> set[tuple[str, str]]:
    return set(_ALLOW_C_PENDING) | set(_ALLOW_C_BY_DESIGN)


@acc()
def test_C_包间不得直查对方表_只许经包间出口():
    """计划 §2.3「包间只经 `service` 调用，**不得跨包直查对方表**」—— **一般式**（`TAIL-218`）。"""
    found = _scan_c()
    extra = sorted(k for k in found if k not in _c_allowed())
    assert not extra, (
        "包间**直查了对方表**（`import` 对了对方的 `repository`）—— 按计划 §2.3 只许经**包间出口**：\n  "
        + "\n  ".join(f"{f} → {m}（{found[(f, m)]} 处）" for f, m in extra)
        + "\n  ⇒ 修法：改走对方包的**包间出口**（`service`），把查询留在那个包里；"
          "⛔ 别复制一份查询到本包（那是第二套口径）；"
          "⛔ 别把它加进 `_ALLOW_C_PENDING`（那份名单只许变短）；"
          "⭐ 若对方**没有**出口 ⇒ 给它开一个（`TAIL-218` 批 2/3 就是这么做的）。"
    )


@acc()
def test_C_待清名单只许变短():
    """⛔ **不许为了让它变绿而往待清名单里加条目** —— 加条目 = 用名单掩盖新长的病。"""
    assert len(_ALLOW_C_PENDING) <= _C_PENDING_START, (
        f"`_ALLOW_C_PENDING` 有 {len(_ALLOW_C_PENDING)} 条，超过起点 {_C_PENDING_START} —— "
        "这条名单**只许变短**：新长出来的跨包直查必须**改走出口**（或进 `_ALLOW_C_BY_DESIGN` 并写清"
        "为什么「加个转手出口也没用」）。"
    )
    print(f"\n[规则C] 待清剩 {len(_ALLOW_C_PENDING)} / 起点 {_C_PENDING_START}"
          f"（按设计的例外 {len(_ALLOW_C_BY_DESIGN)} 条）")


@acc()
def test_C_待清名单里不许留幽灵条目():
    stale = sorted(set(_ALLOW_C_PENDING) - set(_scan_c()))
    assert not stale, (
        "`_ALLOW_C_PENDING` 里有**已经不存在**的条目（那处 import 已经没了 ⇒ 名单该删没删）：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in stale)
        + "\n  ⇒ 改完一处就顺手销一条（销号 [用户] 不释放编号，同理：名单也别留旧账）。"
    )


@acc()
def test_C_按设计的例外必须带理由():
    """例外表**看理由不看数量** —— 每条必须带出处，且对象**必须还命中**。"""
    assert _ALLOW_C_BY_DESIGN, (
        "`_ALLOW_C_BY_DESIGN` 空了 —— 若确实一处都不剩，**请连本判据一起删掉**"
        "（⛔ 别留一张空表假装还在守）。"
    )
    thin = sorted(k for k, why in _ALLOW_C_BY_DESIGN.items() if len((why or "").strip()) < 12)
    assert not thin, (
        "`_ALLOW_C_BY_DESIGN` 里这些条目**没写理由（或太短）** ⇒ 例外就成了「随便放行」：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in thin)
        + "\n  ⇒ 每条写清「为什么加个转手出口也没用」＋出处（文件头 / 裁定）。"
    )
    stale = sorted(set(_ALLOW_C_BY_DESIGN) - set(_scan_c()))
    assert not stale, (
        "`_ALLOW_C_BY_DESIGN` 里有**已经不存在**的条目（那个调用点改了/没了 ⇒ 例外该销没销）：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in stale)
    )


# ------------------------------------------------------------------------- 包间出口（`TAIL-218` 批 1）

#: 包间出口的**取样表**：`(出口所在模块, 出口函数名, 它该转发到的仓储模块)`。
#: ⭐ **新增出口 ⇒ 往本表加一行**（表里每条都会被"打桩"验一次）。
_EXPORT_SMOKE: tuple[tuple[str, str, str], ...] = (
    ("app.mod06_proc.service", "load_inv_rows", "app.mod06_proc.repository"),
    ("app.mod06_proc.service", "load_mech", "app.mod06_proc.repository"),
    ("app.mod06_proc.service", "load_history", "app.mod06_proc.repository"),
    ("app.mod06_proc.service", "load_cutoff", "app.mod06_proc.repository"),
    # ⭐ `TAIL-218` 批 2：`mod01_projects` 新开的 5 个包间出口（11 处调用点改走它们）。
    ("app.mod01_projects.service", "all_projects", "app.mod01_projects.repository"),
    ("app.mod01_projects.service", "warehouse_index", "app.mod01_projects.repository"),
    ("app.mod01_projects.service", "list_projects", "app.mod01_projects.repository"),
    ("app.mod01_projects.service", "export_phids", "app.mod01_projects.repository"),
    ("app.mod01_projects.service", "create_project", "app.mod01_projects.repository"),
    ("app.mod01_projects.service", "set_keywords", "app.mod01_projects.repository"),
    # ⭐ `TAIL-218` 批 3：两个**同型出口**（C 组给 `mod08_inv` / `mod04_plan` 各补 1 个）。
    ("app.mod08_inv.service", "load_rows", "app.mod08_inv.repository"),
    ("app.mod08_inv.service", "load_original_inbound", "app.mod08_inv.repository"),
    ("app.mod04_plan.service", "list_rows", "app.mod04_plan.repository"),
)


@acc()
def test_包间出口必须真转发_打得着桩():
    """⭐ `TAIL-218` 批 1：**出口 ⛔ 不许写成模块级别名**（`load_mech = R.load_mech`）。

    为什么单立一条（本仓**踩过**）：模块级别名会在 **import 那一刻**把函数对象绑死 ⇒
    测试里 `monkeypatch.setattr(repository, "load_mech", …)` **再也打不着**、改实现也换不掉
    （2026-09-30 实测：**12 条判据当场红**，症状是 `session=None` 一路传到真查询里）。

    做法 = **打桩**：把仓储那份换成哨兵 ⇒ 出口**必须**把哨兵还回来。
    ⭐ 钉的是**"是不是真转发"这个意图**，⛔ 不是钉代码写法（出口里怎么写都行，只要换得掉）。
    """
    import importlib

    missing = [f"{m}.{n}" for m, n, _ in _EXPORT_SMOKE if not hasattr(importlib.import_module(m), n)]
    assert not missing, (
        f"`_EXPORT_SMOKE` 里这些出口**不存在**（改名 / 搬走 ⇒ 请更新那张表）：{missing}"
    )

    bad: list[str] = []
    for mod_name, fn_name, repo_name in _EXPORT_SMOKE:
        svc = importlib.import_module(mod_name)
        repo = importlib.import_module(repo_name)
        orig = getattr(repo, fn_name, None)
        assert orig is not None, f"`{repo_name}.{fn_name}` 不在 ⇒ 出口没有对标的仓储函数"
        sentinel = object()
        setattr(repo, fn_name, lambda *a, **kw: sentinel)
        try:
            got = getattr(svc, fn_name)(None)
        except Exception as exc:                      # 绑死的那种会把真函数跑起来 ⇒ 在这儿炸
            got = f"<炸了：{type(exc).__name__}>"
        finally:
            setattr(repo, fn_name, orig)              # ⭐ 打桩必须复原
        if got is not sentinel:
            bad.append(f"{mod_name}.{fn_name}")
    assert not bad, (
        "这些包间出口**没走 `repository`**（写成了模块级别名？）—— 函数对象在 import 期被绑死 ⇒ "
        "打桩打不着、改实现也换不掉：\n  " + "\n  ".join(bad)
        + "\n  ⇒ 改成函数：`def f(session, **kw): from app.<包> import repository as R; return R.f(session, **kw)`"
    )


# ------------------------------------------------------------------------- 规则 D


def _scan_d() -> dict[tuple[str, str], int]:
    """→ `{(相对 `backend/app` 的路径, 被禁模块): 次数}`（只扫导出层）。"""
    found: dict[tuple[str, str], int] = {}
    files = _py_files(RE)
    assert len(files) >= 15, f"`{RE}` 下只扫到 {len(files)} 个 `.py` —— 路径变了，规则 D 已失效"
    for p in files:
        hits = [m for _, cands in _import_targets(p) for m in cands if _BAD_REPO_RE.match(m)]
        for m in dict.fromkeys(hits):
            found[(p.relative_to(APP).as_posix(), m)] = hits.count(m)
    return found


@acc()
def test_D_导出层不得直查业务包的表():
    """`app/report_export/**` ⛔ `import app.mod*.repository`（计划 §2.3：包间只经 `service` 调用）。

    ⚠️ 导出层**允许**用的三种形态：`domain`（纯函数）/ `models`（表结构）/ `service`（包间出口）；
       ⛔ 只有**直查对方表**（`repository`）才是"改一侧牵动另一侧"的病根。
    """
    found = _scan_d()
    extra = sorted(k for k in found if k not in _ALLOW_D)
    assert not extra, (
        "导出层**直查了业务包的表**（`import app.mod*.repository`）—— 按计划 §2.3 只许经**包间出口**"
        "（对方的 `service`）：\n  "
        + "\n  ".join(f"{f} → {m}（{found[(f, m)]} 处）" for f, m in extra)
        + "\n  ⇒ 改走对方包的 `service`（可在那边**再导出** `repository` 的名字当口）；"
          "⛔ 别在本包复制一份取数（那是第二套口径）；⛔ 别把它加进 `_ALLOW_D`。"
    )


@acc()
def test_D_放行名单里不许留幽灵条目():
    stale = sorted(set(_ALLOW_D) - set(_scan_d()))
    assert not stale, (
        "`_ALLOW_D` 里有**已经不存在**的条目（那处 import 已经没了 ⇒ 名单该删没删）：\n  "
        + "\n  ".join(f"{f} → {m}" for f, m in stale)
    )
