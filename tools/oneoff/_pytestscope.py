"""pytest影响范围：按实际import闭包、文本读取和目录扫描选择使用者。

工具共享模块采用传递使用者；已删除件保留反向依赖。无法确定依赖由入口显式调查。
跨文件用途清单按对应输入触发；局部结果不刷新权威四态。
自检和CLI与登记同处，登记覆盖仍双向检查。
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TESTS = BACKEND / "tests"
APP_PREFIX = "backend/app/"

#: ⚠️⚠️ **pytest 会自动加载、因而没有 import 边可依赖的件**（`/code-review` 2026-10-06 抓出，
#: 那是**真的漏跑**：改 `conftest.py` 时闭包带不出任何测试件 ⇒ 只剩必跑清单那几件在跑）。
#: ⛔ 判据算不出 ⇒ 一律**全跑**（票面铁律：漏跑比慢跑严重得多）。
#: `cover_gap()` 会核对「盘上每个 `conftest.py` 都在这张表里」（新增一个自动加载件 ⇒ 报红）。
AUTO_LOADED: tuple[tuple[str, str], ...] = (
    ("backend/tests/conftest.py", "pytest 自动加载（熔断 ＋ 注册插件）· 无 import 边 ⇒ 改了必须全跑"),
    ("backend/tests/acc_plugin.py", "四态插件（由 conftest 注册）· 同上"),
)

# 跨文件扫描与壳接线用途清单；按被改输入触发，不再随局部后端修改全部附带。
REPO_WIDE: tuple[tuple[str, str], ...] = (
    ("test_ux_text.py", "扫 app/** 的用户可见串（不许拼异常原文/工程代号）"),
    ("test_layering.py", "分层边界十一靶（扫全部 mod* 目录）"),
    ("test_deps_declared.py", "pyproject 运行依赖不许漏登记（AST 扫 app/**）"),
    ("test_dup_guards.py", "防扩散墓碑（扫 app/** 的守卫定义）"),
    ("test_schema_drift.py", "models 漂移（扫 mod*/models.py 全集）"),
    ("test_theme.py", "主题变量不许自造（扫 app/**）"),
    ("test_wiring_guards.py", "注释里引用的测试件必须真存在（扫 app/tests/tools 三处）"),
    # 壳接线按对应路由或壳输入变化触发；纯领域逻辑不会改变它们读的壳文本。
    ("test_acc_jc_shell.py", "集采的壳接线（壳段 vs 后端路由）"),
    ("test_acc_x_exp.py", "导出入口的壳接线"),
    ("test_ux_buttons.py", "按钮动作必须都有归属（壳侧）"),
    ("test_shell_render.py", "壳的渲染面（只读壳、不 import 后端）· 列在这儿是为了让它有明确归处"),
    ("test_ux_deadcode.py", "壳不许有死控件（对照 tools 侧词表）"),
    ("test_ux_errors.py", "报错提示的壳侧形态"),
    ("test_ux_numbers.py", "数字呈现的壳侧规则"),
    ("test_ux_pages.py", "各页壳面（含真机那段）"),
    ("test_ux_states.py", "空态/错态的壳面"),
    ("test_wired_boot.py", "性能分组并行 / 页级按需取数（壳侧）"),
    ("test_wired_m01_type.py", "m01 项目面板的壳接线"),
    ("test_wired_m02.py", "m02 台账的壳接线"),
    ("test_wired_m03_action.py", "m03 动作的壳接线"),
    ("test_wired_m03_own.py", "m03 归属弹窗的壳接线"),
    ("test_wired_m03_print.py", "m03 打印的壳接线"),
    ("test_wired_m05.py", "m05 额度的壳接线"),
    ("test_wired_m06.py", "m06 机械源的壳接线"),
    ("test_wired_m11.py", "m11 集采的壳接线"),
    ("test_wired_own_wh.py", "兜底前先查 i8 仓库名单（壳侧）"),
)

#: ② **pytest 在 `backend/` 之外会读的落点**（目录级前缀 · 单一出口）—— 动了它们，pytest 照样会红
#: ⇒ **判据不能只看 `backend/`**（本票第 0 批若照抄「backend 没动就跳过」，就会在这些件上漏跑）。
#: ⭐ **为什么是目录级、而不是逐个文件**（`/code-review` 2026-10-06 抓出）：首版逐个登记了
#: 八个具体文件，**下一个**被读到的新文件就会漏（实测当场漏掉三处：`docs/guides/operations.md` ·
#: 一个 `tools/probe/` 下的件 · 一处 `tools/**/*.py` 的通配扫描）⇒ 改成「目录级触发 ＋
#: **跑哪些由扫描器现算**」（`outside_readers()`）⇒ **要登记的东西变成 0**。
OUTSIDE_PREFIXES: tuple[tuple[str, str], ...] = (
    (".scratch/", "活动任务与票仓的真实读取者"),
    ("tools/", "尺子与探针：好几件测试 import 它、还有一件**通配扫** `tools/**/*.py`"),
    ("docs/", "现行工程文档：设计守则、架构、核验与参考正文"),
    ("ops/", "运维脚本与配置：pip 镜像 / 配置主人表"),
    (".env", "配置"),
    (".env.example", "配置样例（逐行对账）"),
)

#: ③ **真·自证件**：既够不着 `app.*`、也够不着仓外部位（只读自己测试代码）的件 —— **逐支带理由**。
#: ⛔ 理由不许写「不重要」—— 那等于没写（本仓吃过「靠回忆 ⇒ 静默失效」的亏）。
#: ⭐ **2026-10-06 首轮量出来的结论：一件都没有**（原先登记的八件全都读仓外部位 ⇒ 已由那一档带跑）
#: ⇒ **这张表现在是空的，是留给下一个「纯自证件」的登记册**：`cover_gap()` 会把新出现的那个点名。
SELF_ONLY: tuple[tuple[str, str], ...] = ()

#: ⛔ **有意排除的落点**（**逐条带理由** · 别让它变成"悄悄不检查"）：被扫出来却**故意不登记**
#: 进 `OUTSIDE_PREFIXES` 的那些。
IGNORED_READS: tuple[tuple[str, str], ...] = (
    ("artifacts/", "产物档：`acc_plugin` 只**写**它（四态档的出口），不是读入 ⇒ "
                   "登记它会让 pytest 自己触发自己（每轮都白跑一遍）"),
)


# --------------------------------------------------------------- 仓内 import 闭包
def local_scanners(paths) -> set[str]:
    """扫描测试按实际输入面触发；路由与组装仍保留壳接线覆盖。"""
    picked = set()
    app = [p for p in paths if p.startswith(APP_PREFIX) and p.endswith('.py')]
    if app:
        picked |= {'test_ux_text.py', 'test_layering.py', 'test_deps_declared.py', 'test_dup_guards.py'}
    if any(p.endswith('/models.py') or p in {'backend/app/models_registry.py', 'backend/app/core/db.py'}
           or p.startswith('backend/alembic/') for p in paths):
        picked.add('test_schema_drift.py')
    if any(p.startswith(('backend/app/', 'backend/tests/', 'tools/')) and p.endswith('.py') for p in paths):
        picked.add('test_wiring_guards.py')
    dependency_files = {'backend/pyproject.toml', 'backend/uv.lock'}
    if any(p in dependency_files for p in paths):
        picked |= {'test_deps_declared.py', 'test_pipini_single_source.py'}
    wide = {n for n, _ in REPO_WIDE}
    if any(p in {'backend/app/main.py', 'backend/app/core_bindings.py', 'backend/app/export_bindings.py'} for p in paths):
        picked |= wide
    for p in app:
        name = pathlib.Path(p).name
        if name == 'page.py':
            picked |= {'test_theme.py', 'test_ux_pages.py', 'test_ux_states.py'}
        if name.endswith('router.py') or name == 'api.py':
            module = next((part for part in p.split('/') if re.match(r'mod\d\d_', part)), '')
            if module:
                prefix = 'test_wired_m'+module[3:5]
                picked |= {p.name for p in TESTS.glob(prefix+'*.py')}
                picked |= {'test_acc_x_exp.py', 'test_acc_jc_shell.py'}
    return picked


def local_selftest():
    """直接查询真实消费图：相关金额/身份保留，无关UI减少，路由与自动加载不漏。"""
    money = plan(['backend/app/core/money.py'])
    assert 'test_core_money.py' in money.files and 'test_amount_text_parity.py' in money.files
    assert 'test_ux_numbers.py' not in money.files
    # 集采浏览器用例经mod11_jc.domain实际依赖金额模块，必须保留。
    assert 'test_shell_ui_workflow.py' in money.files
    identity = plan(['backend/app/core/identity.py'])
    assert 'test_session_identity.py' in identity.files
    routed = local_scanners(['backend/app/mod03_notice/notice_api_router.py'])
    assert 'test_wired_m03_pay.py' in routed and 'test_wired_m09.py' not in routed
    assert 'test_schema_drift.py' in local_scanners(['backend/app/mod03_notice/models.py'])
    assert plan(['backend/tests/conftest.py']).run_all
    assert not plan(['backend/tests/test_core_money.py']).run_all
    print('自测 局部金额/身份、路由接线、模型与自动加载选集通过')


def _mod_name(p: pathlib.Path) -> str:
    parts = list(p.relative_to(BACKEND).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(p: pathlib.Path) -> set:
    """模块直接 import 的**仓内**模块名（`app.*` / `tests.*`）。⛔ 语法错 ⇒ 空集（调用方会兜底）。"""
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    out: set = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
            out.update(n.module + "." + a.name for a in n.names)
    return {x for x in out if x.split(".")[0] in ("app", "tests")}


def build_graph() -> tuple:
    """→ (`模块 → 直接 import`, `测试件名 → 模块名`)。**每次现算**（⛔ 不缓存到文件＝不引状态）。"""
    mods: dict = {}
    files: dict = {}
    for p in sorted(BACKEND.rglob("*.py")):
        if "__pycache__" in p.parts or ".venv" in p.parts:
            continue
        m = _mod_name(p)
        mods[m] = _imports(p)
        if p.parent == TESTS and p.name.startswith("test_"):
            files[p.name] = m
    return mods, files


def _reach(mods: dict, start: str) -> set:
    """从 `start` 出发**传递**能到达的模块（含自己）。"""
    seen, stack = {start}, [start]
    while stack:
        for i in mods.get(stack.pop(), ()):
            if i in mods and i not in seen:
                seen.add(i)
                stack.append(i)
    return seen


def _impacted(mods: dict, rev: dict, start: str) -> set:
    """谁**传递依赖** `start`（含它自己）—— 动了它，这些都得重测。"""
    seen, stack = {start}, [start]
    while stack:
        for r in rev.get(stack.pop(), ()):
            if r not in seen:
                seen.add(r)
                stack.append(r)
    return seen


class Plan:
    """一次选测的结论（⛔ 零状态：全部由当轮 `git diff` 现算）。"""

    def __init__(self, run: bool, reason: str, files=()):
        self.run = run                  #: 该不该跑 pytest
        self.reason = reason            #: 人话一句（⛔ 静默跳过 = 另一种假绿）
        self.files = list(files)        #: 具体件名（`run_all` 时为空 ⇒ 跑全套）

    @property
    def run_all(self) -> bool:
        return self.run and not self.files

    def argv(self) -> list:
        """给 pytest 的件名参数（全套时为空列表）。"""
        return ["tests/" + n for n in sorted(self.files)]


def _outside_hit(paths: list) -> list:
    out = []
    for p in paths:
        for pref, _why in OUTSIDE_PREFIXES:
            if p == pref or p.startswith(pref):
                out.append(p)
                break
    return sorted(set(out))


def outside_tests(paths) -> set[str]:
    """仓外读入的直接及共享helper使用者；不把helper当测试，也不补无关全仓名单。"""
    prefixes = {pref for pref, _ in OUTSIDE_PREFIXES if any(p.startswith(pref) for p in paths)}
    mods, files = build_graph()
    graph = dict(mods)
    source_files = {_mod_name(p): p for folder in ('app', 'tests') for p in (BACKEND/folder).rglob('*.py')}
    source_files.update({p.relative_to(ROOT).with_suffix('').as_posix().replace('/', '.'): p
                         for p in (ROOT/'tools').rglob('*.py') if not any(x.startswith('_归档') for x in p.parts)})
    aliases = {}
    for module in source_files:
        aliases.setdefault(module.rsplit('.', 1)[-1], set()).add(module)
    data_readers = set()
    for module, p in source_files.items():
        tree = ast.parse(p.read_text(encoding='utf-8'))
        docstrings = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)
                      and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
        literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                    and isinstance(n.value, str) and id(n) not in docstrings]
        edges = set(graph.get(module, ()))
        for n in ast.walk(tree):
            imports = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or '', *[(n.module+'.'+a.name) if n.module else a.name for a in n.names]] if isinstance(n, ast.ImportFrom) else []
            for name in imports:
                if name in source_files: edges.add(name)
                if '.' not in name: edges |= aliases.get(name, set())
        graph[module] = edges
        # 具体文档/脚本输入；只要无法收窄的目录遍历或动态载入，就保守覆盖该前缀。
        local_prefixes = {_outside_prefix_of(v) for v in literals} - {''}
        opaque = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr in {'glob', 'rglob', 'walk', 'iterdir', 'spec_from_file_location', 'import_module'} for n in ast.walk(tree))
        named = any(path in v or pathlib.Path(path).name in v for path in paths for v in literals)
        if named or (opaque and local_prefixes & prefixes): data_readers.add(module)
    changed_modules = {p[:-3].replace('/', '.') for p in paths if p.startswith('tools/') and p.endswith('.py')}
    sources = changed_modules | data_readers
    return {n for n, module in files.items() if _reach(graph, module) & sources}


# 旧/retro计数为历史输入；本轮真实计数与ROI回TAIL-289 Comments。
# 首批仅认可FL/NT常量内修改及完整具名读点；无法证明仍保留旧选集。
def _shell_api():
    """复用现行具名段解析口，不另建JS解析器。"""
    audit = str(ROOT/'tools/audit')
    if audit not in sys.path:
        sys.path.insert(0, audit)
    import shell_api
    return shell_api


def _constant_change(changes):
    """只证明proj中FL/NT单句修改；句外任何字节变化均回退旧选择。"""
    path = 'backend/app/web/shell/proj.js'
    if not changes or set(changes) != {path}:
        return None
    old, new = changes[path]
    if old is None or new is None or old == new or (ROOT/path).read_bytes() != new:
        return None
    api = _shell_api()
    before, after = old.decode('utf-8'), new.decode('utf-8')
    for name in ('FL_THEAD', 'NT_THEAD'):
        pattern = rf'(?m)^const\s+{name}\s*='
        if any(len(re.findall(pattern, api.blank_comments(s))) != 1 for s in (before, after)):
            continue
        left, right = [api.const_src(name, source=s) for s in (before, after)]
        if not left.endswith(';') or not right.endswith(';'):
            continue
        if before.count(left) != 1 or after.count(right) != 1:
            continue
        if before.split(left) != after.split(right):
            continue
        import shell_source
        parts = shell_source.part_paths()
        if parts.count(ROOT/path) != 1:
            return None
        texts = [p.read_text(encoding='utf-8') for p in parts]
        i = parts.index(ROOT/path)
        texts[i] = before.replace('\r\n', '\n')
        full_old = '\n'.join(texts)
        texts[i] = after.replace('\r\n', '\n')
        full_new = '\n'.join(texts)
        if any(len(re.findall(pattern, api.blank_comments(s, html=True))) != 1
               for s in (full_old, full_new)):
            return None
        return full_old, full_new
    return None


def _pure_shell_points(tree, known_modules=()):
    """只接纳完整、直接、字面量具名调用；别名/动态/其他读法不能算空集。"""
    allowed = {'const_src', 'func_body', 'act_entry', 'page_slice'}
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'tests.shell_src':
            if node.level or any(a.asname or a.name not in allowed for a in node.names):
                return None
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(('tests', 'tools')) and node.module != 'tests.acc_plugin':
            return None
        elif isinstance(node, ast.Import) and any(a.name.startswith(('tests', 'tools')) for a in node.names):
            return None
    if not imported:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in imported:
            return None
        if isinstance(node, ast.arg) and node.arg in imported:
            return None
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == 'tests.shell_src':
                continue
            if any((a.asname or a.name.split('.')[0]) in imported for a in node.names):
                return None
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
            # 来源不在标准库/已解析仓库图中的helper不能证明没有整壳依赖。
            if any(m.split('.')[0] not in sys.stdlib_module_names and m not in known_modules
                   for m in modules):
                return None
            if any(m.split('.')[0] in {'playwright', 'requests', 'httpx', 'urllib', 'importlib'} for m in modules):
                return None
            if any(m == 'subprocess' for m in modules) and (isinstance(node, ast.ImportFrom) or any(a.asname for a in node.names)):
                return None
    calls, points = set(), set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id in {'eval', 'exec', 'getattr', 'globals', 'locals', 'vars', '__import__', 'open'}:
                return None
            if node.func.id in imported:
                if len(node.args) != 1 or node.keywords or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                    return None
                calls.add(id(node.func))
                points.add((node.func.id, node.args[0].value))
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess':
                if node.func.attr != 'run' or not node.args or not isinstance(node.args[0], ast.List) or \
                        len(node.args[0].elts) != 1 or not isinstance(node.args[0].elts[0], ast.Constant) or \
                        node.args[0].elts[0].value != 'node' or any(k.arg == 'shell' for k in node.keywords):
                    return None
            if node.func.attr in {'glob', 'rglob', 'walk', 'iterdir', 'import_module', 'spec_from_file_location'}:
                return None
            if node.func.attr in {'read_text', 'read_bytes', 'open'}:
                # 首批允许样板已有的后端.py直读；动态路径仍保守。
                path = node.func.value
                if not isinstance(path, ast.BinOp) or not isinstance(path.op, ast.Div) or \
                        not isinstance(path.right, ast.Constant) or not isinstance(path.right.value, str) or \
                        not path.right.value.endswith('.py'):
                    return None
    if any(isinstance(n, ast.Name) and n.id in imported and id(n) not in calls for n in ast.walk(tree)):
        return None
    return points or None


def _points_unchanged(points, sources):
    """比较测试实际取出的源码，不把页/函数内引用的常量当成运行时依赖图。"""
    api = _shell_api()
    for kind, name in points:
        if kind == 'page_slice':
            values = ['\n'.join(api.slices_of_lines(s.split('\n'))[name]) for s in sources]
        else:
            values = [getattr(api, kind)(name, source=s) for s in sources]
        if values[0] != values[1]:
            return False
    return True


def shell_plan(changes=None) -> Plan:
    """沿源码读入、浏览器访问与import闭包选择壳使用者，不隐式执行全套。"""
    try:
        mods, files = build_graph()
        readers = set()
        sources = {_mod_name(p): p for p in TESTS.glob('*.py')}
        sources.update({p.relative_to(ROOT).with_suffix('').as_posix().replace('/', '.'): p
                        for folder in ('audit', 'probe') for p in (ROOT/'tools'/folder).glob('*.py')})
        aliases = {}
        for module in sources:
            aliases.setdefault(module.rsplit('.', 1)[-1], set()).add(module)
        trees = {}
        for module, p in sorted(sources.items()):
            tree = ast.parse(p.read_text(encoding='utf-8'))
            trees[module] = tree
            edges = set(mods.get(module, ()))
            for node in ast.walk(tree):
                imports = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '', *[(node.module+'.'+a.name) if node.module else a.name for a in node.names]] if isinstance(node, ast.ImportFrom) else []
                for name in imports:
                    if name in sources: edges.add(name)
                    if '.' not in name: edges |= aliases.get(name, set())
            mods[module] = edges
            docs = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)
                    and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
            literals = [n.value.replace('\\', '/') for n in ast.walk(tree)
                        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
            if any(v in {'web', 'shell', '/app'} or 'app/web' in v or
                   'index.html' in v or re.search(r'\.js\b', v) or 'shell_' in v for v in literals):
                readers.add(module)
        picked = {n for n, m in files.items() if _reach(mods, m) & readers}
        if not picked:
            return Plan(False, '待查：未发现壳源码或浏览器使用者')
        # ⭐ 2026-10-11（`/retro` 报告面）：把"为什么是这么多件"直接打出来 ——
        #    自有壳字面量（直接读者）vs 只经 import 闭包被带入。看到 61 与 79 的来历，
        #    ⛔ 不必再去猜"这 140 件是不是白跑"（量测结论见上面 `shell_plan` 前那段）。
        direct = sum(1 for n, m in files.items() if n in picked and m in readers)
        closed = len(picked) - direct
        removed = set()
        try:
            named = _constant_change(changes)
        except (OSError, UnicodeError, LookupError, ValueError):
            named = None
        if named:
            # 去掉唯一认可的读点门；任何另一条整壳helper路径都禁止排除。
            graph = {m: set(edges)-{'tests.shell_src'} for m, edges in mods.items()}
            wide = {n for n, _ in REPO_WIDE}
            for n in picked-wide:
                m = files[n]
                points = _pure_shell_points(trees[m], mods) if m in trees else None
                if not points or _reach(graph, m) & readers:
                    continue
                try:
                    if _points_unchanged(points, named):
                        removed.add(n)
                except (LookupError, KeyError, ValueError):
                    pass
            picked -= removed
        if not picked:
            return Plan(False, '具名常量改动与全部已证读点不交集')
        return Plan(True, '壳源码/浏览器及共享helper使用者：%d / %d件（自有壳字面量 %d · 闭包带入 %d）'
                    % (len(picked), len(files), direct, closed) + '；已证不交集排除 %d件'%len(removed), picked)
    except (OSError, SyntaxError, UnicodeError) as exc:
        return Plan(False, '待查：壳使用者读取失败：'+type(exc).__name__)


def shell_selftest():
    """独立夹具证壳直接/传递/浏览器使用者、无关排除及未知不扩成全套。"""
    import tempfile
    from unittest.mock import patch
    _shell_api()  # 在切到夹具ROOT前加载仓库的真实解析器。
    module = sys.modules[__name__]
    with tempfile.TemporaryDirectory() as folder:
        root = pathlib.Path(folder)
        tests = root/'backend/tests'; tests.mkdir(parents=True)
        prefix = 'test' + '_'
        (tests/'reader.py').write_text("text='index.html'", encoding='utf-8')
        (tests/(prefix+'direct.py')).write_text("text='core.js'", encoding='utf-8')
        (tests/(prefix+'shared.py')).write_text('from tests import reader', encoding='utf-8')
        (tests/(prefix+'browser.py')).write_text("url='/app'", encoding='utf-8')
        (tests/'plugin.py').write_text("output='results.json'", encoding='utf-8')
        (tests/(prefix+'other.py')).write_text('from tests import plugin', encoding='utf-8')
        audit=root/'tools/audit'; audit.mkdir(parents=True)
        (audit/'shell_source.py').write_text("path='backend/app/web'", encoding='utf-8')
        (tests/'wrapped.py').write_text('from tools.audit import shell_source', encoding='utf-8')
        (tests/(prefix+'tool.py')).write_text('from tests import wrapped', encoding='utf-8')
        with patch.object(module, 'ROOT', root), patch.object(module, 'BACKEND', root/'backend'), patch.object(module, 'TESTS', tests):
            selected = plan(['backend/app/web/shell/core.js'])
            assert selected.run and not selected.run_all
            assert set(selected.files) == {prefix+n for n in ('direct.py', 'shared.py', 'browser.py', 'tool.py')}
            (tests/'shell_src.py').write_text("path='index.html'", encoding='utf-8')
            for label, body in {
                'fl': "from tests.shell_src import const_src\nx=const_src('FL_THEAD')",
                'nt': "from tests.shell_src import const_src\nx=const_src('NT_THEAD')",
                'whole': "from tests.shell_src import SHELL\nx=SHELL",
                'dynamic': "from tests.shell_src import const_src\nx=const_src(name)",
                'alias': "from tests.shell_src import const_src as read\nx=read('NT_THEAD')",
                'mixed': "from tests.shell_src import const_src\nfrom tests import reader\nx=const_src('NT_THEAD')",
                'wide': "from tests.shell_src import const_src\nx=const_src('NT_THEAD')",
                'unknown': "from tests.shell_src import custom\nx=custom('NT_THEAD')",
                'shadow': "from tests.shell_src import const_src\ndef f(const_src):\n    return const_src('NT_THEAD')",
                'outside': "from tests.shell_src import const_src\nx=const_src('NT_THEAD')\ny=Path(name).read_text()",
                'opaque': "from tests.shell_src import const_src\nfrom opaque_helper import read\nx=const_src('NT_THEAD')\nassert read()",
            }.items():
                (tests/(prefix+label+'.py')).write_text(body, encoding='utf-8')
            path = 'backend/app/web/shell/proj.js'
            proj = root/path; proj.parent.mkdir(parents=True)
            index = proj.parent.parent/'index.html'
            index.write_text('<script src="/static/shell/proj.js"></script>', encoding='utf-8')
            old = b"const FL_THEAD='old';\nconst NT_THEAD='old';\n"
            import shell_source
            with patch.object(shell_source, 'part_paths', return_value=[index, proj]), \
                    patch.object(module, 'REPO_WIDE', ((prefix+'wide.py', 'fixture'),)):
                def check(name):
                    new = old.replace((name+"='old'").encode(), (name+"='new'").encode())
                    proj.write_bytes(new)
                    legacy = plan([path])
                    narrowed = plan([path], changes={path: (old, new)})
                    wanted = prefix+('fl' if name == 'FL_THEAD' else 'nt')+'.py'
                    skipped = prefix+('nt' if name == 'FL_THEAD' else 'fl')+'.py'
                    assert wanted in narrowed.files, '匹配读点被错误排除'
                    assert skipped not in narrowed.files, '同文件不交集没有真正排除'
                    assert set(legacy.files)-set(narrowed.files) == {skipped}
                    print(name, len(legacy.files), '->', len(narrowed.files), '排除', skipped)
                    return new
                new = check('FL_THEAD')
                check('NT_THEAD')
                # 错误排除通过真实plan出口发生，正例断言必须真的报红。
                original = module.shell_plan
                def omit(*args, **kwargs):
                    result = original(*args, **kwargs)
                    result.files = [n for n in result.files if n != prefix+'fl.py']
                    return result
                with patch.object(module, 'shell_plan', side_effect=omit):
                    try:
                        check('FL_THEAD')
                    except AssertionError as exc:
                        assert str(exc) == '匹配读点被错误排除'
                    else:
                        raise AssertionError('故意漏选未能报红')
                for pair in [(None, new), (old, None), (old, new+b'// extra\n'),
                             (old, new+b"const FL_THEAD='duplicate';\n"),
                             (old, new.replace(b"'new';", b"'new'"))]:
                    proj.write_bytes(pair[1] or b'')
                    assert set(plan([path], changes={path: pair}).files) == set(plan([path]).files)
                proj.write_bytes(new)
                gaps, _ = cover_gap()
                assert not any(prefix+'direct.py' in gap for gap in gaps), '实际壳使用者被误报覆盖缺口'
                assert any(prefix+'other.py' in gap for gap in gaps), '真正无使用者的测试不能被盖住'
                with patch.object(module, 'shell_plan', return_value=Plan(False, 'fixture')):
                    assert any(prefix+'direct.py' in gap for gap in cover_gap()[0]), '壳选择证明丢失时覆盖检查必须报缺口'
                mixed = plan([path, 'backend/tests/'+prefix+'nt.py'], changes={path: (old, new)})
                assert prefix+'nt.py' in mixed.files, '测试自身改动不能被壳收窄排除'
                assert set(plan([path, 'tools/oneoff/unread.py'], changes={path: (old, new)}).files) == \
                    set(plan([path], changes={path: (old, new)}).files), '无pytest使用者的仓外改动不能吞掉壳使用者'
                assert set(plan([path, 'backend/app/web/index.html'], changes={path: (old, new)}).files) == set(plan([path]).files)
            (tests/'reader.py').write_text('bad syntax !', encoding='utf-8')
            unknown = plan(['backend/app/web/index.html'])
            assert not unknown.run and unknown.reason.startswith('待查：')
    print('壳选集自证：直接/传递/浏览器选中，无关排除，未知待查')


def plan(changed, *, changes=None) -> Plan:
    """按使用者选测；未知依赖返回待查，自动加载共享输入才扩大。"""
    if changed is None:
        return Plan(False, "待查：git失败，未确定实际输入")
    changed = sorted({p.replace("\\", "/") for p in changed})
    inside = [p for p in changed if p.startswith("backend/")]
    outside = _outside_hit([p for p in changed if not p.startswith("backend/")])
    if outside:
        # ⭐ 动了仓外部位 ⇒ 跑「读那些落点的测试件」＋必跑清单（**不是全跑**）：
        #   读哪些由 `outside_readers()` **现算**，⛔ 不必手工登记（首版手工登记，当场漏了三处）。
        picked = outside_tests(outside)
        files = {p.name for p in TESTS.glob("test_*.py")}
        picked = {n for n in picked if n in files}
        if inside:
            inner = plan(inside, changes=changes)
            if inner.reason.startswith('待查：'):
                return inner
            if inner.run_all:
                return inner
            picked |= set(inner.files)
        if not picked:
            return Plan(False, "实际import和文本消费图未发现pytest使用者；对应工具检查仍由入口执行")
        return Plan(True, "仓外读入及共享helper依赖（%d处）⇒ %d件测试" % (len(outside), len(picked)), picked)
    if not inside:
        return Plan(False, "本轮既没动 backend/，也没动 pytest 读的仓外部位")
    auto = [p for p in inside if p in {a for a, _ in AUTO_LOADED}]
    if auto:
        return Plan(True, "动了 pytest **自动加载**的件（%s）⇒ 全套pytest共享自动加载输入 ⇒ 全跑"
                    % "、".join(auto))
    shell = [p for p in inside if p.startswith("backend/app/web/")]
    if shell:
        selected = shell_plan({p: changes[p] for p in shell if changes and p in changes}
                              if changes and all(p in changes for p in shell) else None)
        remaining = [p for p in inside if p not in shell]
        if remaining and not selected.reason.startswith('待查：'):
            other = plan(remaining, changes=changes)
            if other.reason.startswith('待查：') or other.run_all:
                return other
            selected.files = sorted(set(selected.files) | set(other.files))
            selected.run = selected.run or other.run
        return selected
    dependency_files = {'backend/pyproject.toml', 'backend/uv.lock'}
    if set(inside) <= dependency_files:
        return Plan(True, 'uv依赖配置变化：核依赖声明与索引配置；运行兼容按所变依赖选测',
                    ['test_deps_declared.py', 'test_pipini_single_source.py'])
    odd = [p for p in inside if not p.endswith(".py") and p not in dependency_files]
    if odd:
        return Plan(False, "待查：后端非Python输入的实际消费（%d处）" % len(odd))
    mods, files = build_graph()
    seeds = []
    for p in inside:
        if p in dependency_files:
            continue
        source = ROOT/p
        if source.is_file():
            try:
                ast.parse(source.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeError):
                return Plan(False, '待查：模块语法或编码无法证明：'+p)
        m = p[len("backend/"):-3].replace("/", ".")
        if m.endswith(".__init__"):
            m = m[: -len(".__init__")]
        if m not in mods and (BACKEND / p[len('backend/'):]).exists():
            return Plan(False, "待查：模块语法或载入无法证明：%s" % p)
        seeds.append(m)
    rev: dict = {}
    for m, imps in mods.items():
        for i in imps:
            rev.setdefault(i, set()).add(m)
    aff = set()
    for s in seeds:
        aff |= _impacted(mods, rev, s)
    picked = {n for n, m in files.items() if _reach(mods, m) & aff}
    picked |= local_scanners(changed)
    picked = {n for n in picked if n in files}
    if not picked:
        return Plan(False, "待查：运行模块没有已发现的回归使用者")
    return Plan(True, "改动 %d 处 ⇒ 选 %d / %d 件（其余够不着）"
                % (len(inside), len(picked), len(files)), picked)


# --------------------------------------------------------------- 选集的机器眼
def _code_of(p: pathlib.Path) -> str:
    """⛔ 粗去行注释：`#` 之后不算「真读到」。"""
    return "\n".join(ln.split("#")[0] for ln in
                     p.read_text(encoding="utf-8", errors="replace").splitlines())


def _outside_prefix_of(text: str) -> str:
    """一个字面量落在仓外哪个前缀下（`tools/…` / `ops/…` / `.env…`）⇒ 前缀；不属于 ⇒ `""`。

    ⭐ **为什么扫「字符串字面量」而不是重拼路径**（`/code-review` 2026-10-06 抓出）：
    首版重拼 `Path(...) / "docs" / "guides" / "operations.md"`，遇到 `Path(__file__).resolve().parents[2]` 就断了
    ⇒ **当场漏掉三处真实落点**。字面量扫法对「拼出来的」「通配的」「直接写的」一视同仁。
    """
    t = text.strip().replace("\\", "/")
    for pref, _ in OUTSIDE_PREFIXES:
        if t == pref.rstrip("/") or t.startswith(pref):
            return pref
    return ""


def outside_readers() -> dict:
    """`{测试件名: 它读到的仓外前缀集合}` —— **跑哪些由这里现算**，⛔ 不必手工登记。

    ⚠️ **宁可多算一件**（多跑几件只是慢），⛔ 不可漏算（漏＝静默不跑）。
    """
    out: dict = {}
    for p in sorted(TESTS.rglob("*.py")):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        found = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                pref = _outside_prefix_of(n.value)
                if pref:
                    found.add(pref)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                mods = ([a.name for a in n.names] if isinstance(n, ast.Import)
                        else [n.module or ""])
                for m in mods:
                    pref = _outside_prefix_of(m.replace(".", "/"))
                    if pref:
                        found.add(pref)
        if found:
            out[p.name] = found
    return out


def cover_gap() -> tuple:
    """**选集的机器眼** → `(缺口说明, 陈旧说明)`。两个方向都造得出红（见随票的证伪件）。

    · **缺口**：① 盘上每个 `test_*.py` 都够得着（在 `REPO_WIDE`、或 import 得到 `app.*`、或仓外/壳选择器会带跑、或在 `SELF_ONLY`）；
      ② `OUTSIDE_PREFIXES` 里的落点真在盘上；③ 盘上每个 pytest **自动加载**的件都在 `AUTO_LOADED` 里
      （`conftest.py` 这类件**没有 import 边** ⇒ 漏了它就等于漏跑一大片）。
    · **陈旧**：名单里登记的测试件仍在盘上、且分类还成立。
    """
    mods, files = build_graph()
    reach = {n: _reach(mods, m) for n, m in files.items()}
    wide = {n for n, _ in REPO_WIDE}
    selfonly = {n for n, _ in SELF_ONLY}
    gets_app = {n: any(m.startswith("app.") for m in reach[n]) for n in files}
    outside = set(outside_readers())
    # 壳读者已有真实选测出口；不另登记一份名单，也不误报为永远跑不到。
    readers = outside | set(shell_plan().files)
    gaps = []
    for n in sorted(files):
        if n in wide or n in readers:
            continue                      # 必跑清单／仓外或壳触发面会带它跑
        if gets_app[n] and n not in selfonly:
            continue                      # 自动够得着（import 闭包会带它跑）
        if not gets_app[n] and n not in selfonly:
            gaps.append("%s —— 够不着 `app.*`（闭包带不到它）也不读仓外部位 ⇒ "
                        "要么写清理由登记进 `SELF_ONLY`，要么确认它该被某处带跑" % n)
    for pref, _why in OUTSIDE_PREFIXES:
        if not (ROOT / pref.rstrip("/")).exists():
            gaps.append("OUTSIDE_PREFIXES 里的 `%s` **不在盘上**（路径写错了？）" % pref)
    listed_auto = {a for a, _ in AUTO_LOADED}
    for p in BACKEND.rglob("conftest.py"):
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if ".venv" in rel:
            continue                      # ⛔ 第三方库自带的（改它们不属本仓的活）
        if rel not in listed_auto:
            gaps.append("`%s` 是 pytest **自动加载**的件却不在 `AUTO_LOADED` 里 ⇒ "
                        "改它时闭包算不出 ⇒ 会静默漏跑" % rel)
    stale = ["REPO_WIDE 里的 `%s` 不在盘上" % n for n, _ in REPO_WIDE if n not in files]
    stale += ["SELF_ONLY 里的 `%s` 不在盘上" % n for n, _ in SELF_ONLY if n not in files]
    stale += ["SELF_ONLY 里的 `%s` 其实 import 得到 `app.*` ⇒ 它会被闭包带跑，登记已过期"
              % n for n, _ in SELF_ONLY if n in files and gets_app[n]]
    stale += ["`SELF_ONLY` 里的 `%s` 现在被 `outside_readers()` 认成读仓外部位 ⇒ "
              "它已由那一档带跑，登记已过期" % n
              for n, _ in SELF_ONLY if n in outside]
    return gaps, stale


def report_cover() -> tuple:
    """打印选集自检并给 `(rc, 结论一句)` —— ⛔ 结论**只在这里写一次**，调用方只许转发。"""
    gaps, stale = cover_gap()
    for g in gaps:
        print("⛔ **选集有缺口**：%s" % g)
    if gaps:
        print("   ⇒ 它**不会被任何一轮跑到**，而没有任何痕迹说明它被跳过"
              "（`TAIL-239` 同族：本仓已 5 次「加了判据却没人跑」）")
        print("   ⇒ 两选一：① 它该跑 ⇒ 确认它 import 得到 `app.*` 或把理由写进 `SELF_ONLY`；"
              "② 它该被带跑 ⇒ 加进 `REPO_WIDE` 并写清它读的是哪一面")
    for s in stale:
        print("⛔ **名单陈旧**：%s（改名/删件 ⇒ 本件要跟改）" % s)
    if not gaps and not stale:
        on_disk = len(build_graph()[1])
        readers = outside_readers()
        print("✅ 选集一致：`REPO_WIDE` %d 件 ∪ `SELF_ONLY` %d 件 ∪ import 得着 app 的其余 %d 件"
              "（⛔ 件数别抄在别处）"
              % (len(REPO_WIDE), len(SELF_ONLY), on_disk - len(REPO_WIDE) - len(SELF_ONLY)))
        print("   仓外触发面：%d 个前缀 ⇒ 现算出的读取者 %d 件（⛔ 件数别抄在别处）"
              % (len(OUTSIDE_PREFIXES), len(readers)))
        print("   ⛔ 有意排除的落点 %d 处（理由见 `IGNORED_READS`）：%s"
              % (len(IGNORED_READS), "、".join(p for p, _ in IGNORED_READS)))
        return 0, "✅ 选集一致（三张名单 ＋ 闭包盖住 backend/tests 全集）"
    return 1, "⛔ 选集有缺口/陈旧 %d 条（上面逐条列了）" % (len(gaps) + len(stale))


def acc_path(pl) -> pathlib.Path:
    """本轮 pytest 的四态档**落点**（**单一出口**）：全套 ⇒ 权威档；子集 ⇒ 局部档。

    ⛔⛔ **权威四态档只许由「全套」刷新**（`TAIL-241` 当场踩到）：本件让 pytest 开始跑子集，
    而闸门当时**无条件**把 `ACC_RESULTS_PATH` 指向权威档 ⇒ 子集跑完，权威档里只剩那几十件的结果
    （实测：绿 138 · 未绑定 506）⇒ **下一轮** `doc_audit` 的 `T4` 立刻报红 ⇒ **闸门自己污染自己**
    （与「变异件跑子集冲权威档」同族，机理一模一样）。
    """
    return ROOT / "artifacts" / ("acc_results.json" if pl.run_all else "_partial_acc_results.json")


def acc_note(pl) -> str:
    """闸门打印的那一句（⛔ 措辞只此一处 · 闸门那边只转发，不许再写一遍）。"""
    if pl.run_all:
        return "%s（权威档 · 本轮会刷新四态）" % acc_path(pl).name
    return "%s（⛔ 局部档 · 本轮⛔不刷新四态）" % acc_path(pl).name


def pytest_env(pl) -> dict:
    """给 pytest 子进程的环境变量（**单一出口**）—— 落点路径由 `acc_path` 独家给。"""
    out = {"PLAYWRIGHT_BROWSERS_PATH": r"C:\ProgramData\ms-playwright",
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    out["ACC_RESULTS_PATH"] = str(acc_path(pl))
    return out

# --------------------------------------------------------------- git 改动面
def _porcelain() -> list:
    """git status --porcelain 的每行（只 rstrip —— `strip()` 会把状态码那两列的前导空格也去掉）。"""
    q = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return [] if q.returncode else [x.rstrip() for x in (q.stdout or "").splitlines() if x.strip()]


def fake_dirty() -> list:
    """**假改动**：`git status` 说改了、`git diff HEAD` 说没改的那几件（未跟踪不算）。

    ⛔ **它不影响选测**：本件的 `changed_paths()` 读的是 `git diff --name-only HEAD`
    （不是 `status`）。受影响的只有**人读 `git status` 时被带偏**。
    """
    said = {ln[3:].strip().replace("\\", "/") for ln in _porcelain()
            if ln[:2] != "??" and ln[3:].strip()}
    return sorted(said - set(changed_paths() or []))


def fake_dirty_note() -> str:
    """门间打印那一句（⛔ 措辞只此一处）。"""
    bad = fake_dirty()
    if not bad:
        return "✅ 无（status 与 diff HEAD 说的是同一批件）"
    return "⚠️ 无 %d 件（内容与 HEAD 逐字节相同，仅 mtime 脏）：%s" % (
        len(bad), "、".join(x.split("/")[-1] for x in bad[:4]))


def changed_paths():
    """工作区 vs `HEAD` 的改动路径（**含未跟踪新件**）—— ⛔ 零状态（提交后自然归零）。

    ⚠️⚠️ **git 本身失败 ⇒ 返回 `None`，不许返回空清单** ——
    「空清单」在语义上等于「本轮什么都没动」⇒ 闸门会静默跳过 pytest（**假绿**）。
    判据算不出来时的正确做法是**全跑**（票面铁律）。
    """
    def git(*args):
        p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode:
            return None
        return [x.strip().replace("\\", "/") for x in (p.stdout or "").splitlines() if x.strip()]
    tracked = git("diff", "--name-only", "HEAD")
    untracked = git("ls-files", "--others", "--exclude-standard")
    if tracked is None or untracked is None:
        return None
    return sorted(set(tracked + untracked))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--cover-only', action='store_true', help='检查选集登记覆盖')
    modes.add_argument('--explain', action='store_true', help='说明选集；指定路径用 --explain -- PATH...')
    parser.add_argument('paths', nargs='*', metavar='PATH')
    args = parser.parse_args()
    explicit_paths = '--' in sys.argv[1:]
    if (args.paths or explicit_paths) and not (args.explain and explicit_paths):
        parser.error('指定路径请使用 --explain -- PATH...')
    if args.cover_only:
        return report_cover()[0]
    if args.explain:
        pl = plan(args.paths if explicit_paths else changed_paths())
        print("跑 pytest：%s" % ("是" if pl.run else "否"))
        print("理由：%s" % pl.reason)
        print("件名（%d）：%s" % (len(pl.files), " ".join(sorted(pl.files)) or "（全套）"))
        return 0
    pl = plan(changed_paths())
    print("pytest=%s｜%s" % ("跑" if pl.run else "跳过", pl.reason))
    print("pytest-files=%s" % " ".join(pl.argv()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
# 全套pytest成功产生的真实读入证据；不是手工镜像测试清单。
_INPUT_FILES = set()
_INPUT_SHARED = set()
_INPUT_NODE = None
_INPUT_OUTPUT = None


def _input_audit(event, args):
    """只记录壳源码读入及调用者模块；不记录数据内容、口令或数据库值。"""
    # 子进程/远程请求可在本进程之外读壳，不能只记录本地open而漏掉它们。
    if event == 'open':
        if not args or not isinstance(args[0], (str, bytes)):
            return
        try:
            path = pathlib.Path(args[0]).resolve()
            path.relative_to(ROOT/'backend/app/web')
        except (ValueError, OSError, TypeError):
            return
    elif event not in {'subprocess.Popen', 'socket.connect', 'http.client.connect'}:
        return
    if _INPUT_NODE:
        _INPUT_FILES.add(_INPUT_NODE)
    found = False
    frame = sys._getframe(1)
    while frame:
        name = frame.f_globals.get('__file__')
        if name:
            try:
                module_path = pathlib.Path(name).resolve()
                module_path.relative_to(BACKEND)
                _INPUT_SHARED.add(_mod_name(module_path))
                found = True
            except (ValueError, OSError):
                pass
        frame = frame.f_back
    if not found and not _INPUT_NODE:
        _INPUT_SHARED.add('@unknown')


def pytest_runtest_setup(item):
    """测试上下文从setup覆盖fixture、call及teardown；共享读入另沿模块依赖扩散。"""
    global _INPUT_NODE
    _INPUT_NODE = item.path.name


def pytest_runtest_logfinish(nodeid, location):
    global _INPUT_NODE
    _INPUT_NODE = None


def pytest_sessionfinish(session, exitstatus):
    """完整成功才保存读取证据；失败先清掉，不能供下一次局部选择复用。"""
    if _INPUT_OUTPUT is None:
        return
    import json
    output = pathlib.Path(_INPUT_OUTPUT)
    if exitstatus:
        output.unlink(missing_ok=True)
        return
    data = {'version': 1, 'files': sorted(_INPUT_FILES), 'shared': sorted(_INPUT_SHARED),
            'tests': sorted(p.name for p in TESTS.glob('test_*.py'))}
    output.write_text(json.dumps(data, sort_keys=True), encoding='utf-8', newline='\n')


def text_plan(data) -> Plan:
    """从已验证完整运行的真实壳读入选测试；缺证、坏档、无法传递均全跑。"""
    if not isinstance(data, dict) or data.get('version') != 1:
        return Plan(True, '壳读入证据缺失/版本未知')
    names = {p.name for p in TESTS.glob('test_*.py')}
    if any(not isinstance(data.get(k), list) or not all(isinstance(v, str) for v in data[k])
           for k in ('files', 'shared', 'tests')) or set(data['tests']) != names:
        return Plan(True, '壳读入证据损坏或测试名字空间变化')
    picked = set(data['files'])
    if not picked <= names:
        return Plan(True, '读取证据选到清单外')
    mods, tests = build_graph()
    for shared in data['shared']:
        if shared in {p[len('backend/'):-3].replace('/', '.') for p, _ in AUTO_LOADED}:
            return Plan(True, 'pytest自动加载输入读取壳，影响全套')
        users = {n for n, m in tests.items() if shared in _reach(mods, m)}
        if not users:
            return Plan(True, '共享壳读入无法传递到测试：'+shared)
        picked |= users
    if not picked:
        return Plan(True, '壳读取证据为空，不能无证跳过')
    return Plan(True, '完整运行实际读取壳的测试及共享读入依赖', picked)


def input_selftest():
    """真实输入链与坏元数据的兜底，不按预设测试名单比相等。"""
    names = sorted(p.name for p in TESTS.glob('test_*.py'))
    for data in [None, {}, {'version': 1, 'files': [], 'shared': [], 'tests': names},
                 {'version': 1, 'files': ['outside.py'], 'shared': [], 'tests': names},
                 {'version': 1, 'files': [], 'shared': ['@unknown'], 'tests': names}]:
        assert text_plan(data).run_all, '未知/坏/空/越界读取证据必须全跑'
    # 明确的实际读取者只要求被选；不钉住全套名单形状。
    sample = names[0]
    assert sample in text_plan({'version': 1, 'files': [sample], 'shared': [], 'tests': names}).files
    import os, tempfile
    with tempfile.TemporaryDirectory() as temp:
        e = dict(os.environ, PYTEST_INPUTS_PATH=str(pathlib.Path(temp)/'inputs.json'),
                 PYTHONPATH=str(ROOT/'tools/oneoff'))
        code = "import _pytestscope as s; s._INPUT_NODE='" + sample + "'; s._INPUT_FILES.clear(); (s.ROOT/'backend/app/web/index.html').read_bytes(); assert s._INPUT_NODE in s._INPUT_FILES, '真实open未被接入输入证据'"
        result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], env=e, capture_output=True, text=True, encoding='utf-8')
        assert result.returncode == 0, result.stderr
        # Exercise actual pytest plugin discovery and setup/call/finish hooks.
        probe = pathlib.Path(temp)/sample
        probe.write_text('def test_read():\n    from pathlib import Path\n    Path('+repr(str(ROOT/'backend/app/web/index.html'))+').read_bytes()\n', encoding='utf-8')
        e['ACC_RESULTS_PATH'] = str(pathlib.Path(temp)/'partial.json')
        result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'pytest', '-q', '-p', '_pytestscope', str(probe)], cwd=temp, env=e, capture_output=True, text=True, encoding='utf-8')
        assert result.returncode == 0, result.stdout + result.stderr
        import json
        observed = json.loads((pathlib.Path(temp)/'inputs.json').read_text(encoding='utf-8'))
        assert sample in observed['files'], 'pytest真实读入未被记录'
    print('自测 壳真实读入选测、真实pytest插件接线、未知共享输入、空证据与越界兜底通过')


import os as _input_os
if _input_os.environ.get('PYTEST_INPUTS_PATH'):
    # Existing public environment helper is not a pytest hook.
    # Mark it optional so pytest plugin discovery preserves the CLI API.
    setattr(pytest_env, 'pytest_impl', {'optionalhook': True})
    _INPUT_OUTPUT = _input_os.environ['PYTEST_INPUTS_PATH']
    pathlib.Path(_INPUT_OUTPUT).unlink(missing_ok=True)
    sys.addaudithook(_input_audit)
