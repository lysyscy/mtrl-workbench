"""**pytest 选测范围**（`TAIL-241` 第 1 批）—— 「本轮该跑哪些测试件」的**单一出口**。

⭐ **为什么要有它**：收工闸门末尾那把 pytest 是每轮固定成本里最大的一块。
全跑 ⇒ 改一行文档也付全额。

⚠️⚠️ **第一原则：漏跑比慢跑严重得多**（票面原话）⇒一切拿不准的地方
**一律退回全跑**，并打一行「算不出 ⇒ 全跑」。宁可慢，不许静默漏。

**三档判定**（判据 = 测试件**实际读什么**，⛔ 不按文件名猜）：
  ① **全仓敏感**（`REPO_WIDE`）：扫 `app/**` 的文本/AST ⇒ 只要 `backend/app` 动过就必跑；
  ② **包敏感**：靠 `import` 闭包算（改一个模块 ⇒ 传递依赖它的那些测试件必跑）；
  ③ **够不着**（`SELF_ONLY`）：只读自己 / 工具 / 守则 ⇒ 不随包触发，**逐支带理由**。

**机器眼**（`TAIL-239` 同族）：`cover_gap()` 双向查 ——
  · **缺口**：盘上每个 `test_*.py` 必须够得着（在 `REPO_WIDE`、或 import 得到 `app.*`、或在 `SELF_ONLY`）；
  · **陈旧**：三张名单里登记的件必须真在盘上。
⇒ 新加一个测试件而没落进任何一档 ⇒ 当场报红（否则它永远不被跑，且没有任何痕迹）。

跑法：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_pytestscope.py --cover-only
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_pytestscope.py --explain -- backend/app/mod09_fee/router.py

⚠️ **不拆的理由**（`T5` 黄档：本件超了行数线 —— 数字以 `ops/阈值表.md` 为准，⛔ 别抄）：
三张名单 ＋ 闭包 ＋ 自检 ＋ CLI 是**同一件事的四个面**，
拆开就得再定一个「名单在哪个件」的指针 ⇒ 多一处能漂的地方（同 `_doc_downgrade` 先例：命令与它的自测同件）。

⚠️⚠️ **本件的件名不许含「`test` + 下划线」那段**（2026-10-06 当场踩到）：
`test_wiring_guards` 的正则 `test_[\\w]+\\.py` 会把**件名里那一段**当成"引用了一个测试件"
⇒ 报「幽灵判据」。`TAIL-241` 首版的名字里夹了「test + 下划线」⇒ 每轮闸门都红一条
⇒ 改名去掉那段。**教训**：新件的**名字**也是判据的输入面（`T8` 扫字面、`test_wiring_guards` 扫名字）。
"""
from __future__ import annotations

import ast
import pathlib
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

#: ① **全仓敏感清单**（单一出口 · ⛔ 别在别处再写一份）—— 判据 = 它**读 `app/**` 的文本/AST**，
#: 所以「改了哪个模块」与它无关：**只要 `backend/app` 动过就必须跑**。
#: ⚠️ 头号慢件 `test_ux_text.py` **故意在这张表里**（票面铁律：⛔ 不许把它按范围裁掉
#: —— 裁它等于裁掉「用户可见串不许拼异常原文」那张网）。
REPO_WIDE: tuple[tuple[str, str], ...] = (
    ("test_ux_text.py", "扫 app/** 的用户可见串（不许拼异常原文/工程代号）· 票面点名不许裁"),
    ("test_layering.py", "分层边界十一靶（扫全部 mod* 目录）"),
    ("test_deps_declared.py", "依赖清单不许漏登记（AST 扫 app/**）"),
    ("test_dup_guards.py", "防扩散墓碑（扫 app/** 的守卫定义）"),
    ("test_schema_drift.py", "models 漂移（扫 mod*/models.py 全集）"),
    ("test_theme.py", "主题变量不许自造（扫 app/**）"),
    ("test_wiring_guards.py", "注释里引用的测试件必须真存在（扫 app/tests/tools 三处）"),
    # —— 壳接线守卫：它们 import 不到 `app.*`（只读壳的 js 与段注册表）⇒ 闭包带不到。
    #    ⛔ **不许因此把它们判成「够不着」** —— 真改了一个路由，坏的是壳与它对不上，
    #    那样就得靠这类件喊。⚠️ 实测这批**很便宜**（秒级），所以进必跑清单而不是「按触发跑」。
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
    ("test_wired_m03_pick.py", "m03 选择器的壳接线"),
    ("test_wired_m03_print.py", "m03 打印的壳接线"),
    ("test_wired_m04.py", "m04 流程的壳接线"),
    ("test_wired_m05.py", "m05 额度的壳接线"),
    ("test_wired_m06.py", "m06 机械源的壳接线"),
    ("test_wired_m11.py", "m11 集采的壳接线"),
    ("test_wired_own_wh.py", "兜底前先查 i8 仓库名单（壳侧）"),
)

#: ② **pytest 在 `backend/` 之外会读的落点**（目录级前缀 · 单一出口）—— 动了它们，pytest 照样会红
#: ⇒ **判据不能只看 `backend/`**（本票第 0 批若照抄「backend 没动就跳过」，就会在这些件上漏跑）。
#: ⭐ **为什么是目录级、而不是逐个文件**（`/code-review` 2026-10-06 抓出）：首版逐个登记了
#: 八个具体文件，**下一个**被读到的新文件就会漏（实测当场漏掉三处：`ops/README.md` ·
#: 一个 `tools/probe/` 下的件 · 一处 `tools/**/*.py` 的通配扫描）⇒ 改成「目录级触发 ＋
#: **跑哪些由扫描器现算**」（`outside_readers()`）⇒ **要登记的东西变成 0**。
OUTSIDE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("tools/", "尺子与探针：好几件测试 import 它、还有一件**通配扫** `tools/**/*.py`"),
    ("ops/", "工程侧底账：设计守则 / 架构 / pip 镜像 / 配置主人表"),
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


def plan(changed) -> Plan:
    """`changed` = 工作区 vs `HEAD` 的改动路径（**已含未跟踪新件**）→ 这一轮跑什么。

    ⛔ **拿不准就全跑**：壳（`web/`）、非 `.py` 的 backend 件、被删掉的模块、
    **pytest 自动加载的件**（`AUTO_LOADED`，它们没有 import 边可依赖）、
    以及 **`changed` 本身算不出来**（`None`）⇒ 一律全跑，并在理由里写明是哪一条。
    """
    if changed is None:
        return Plan(True, "算不出改了哪些（git 失败）⇒ 全跑")
    changed = sorted({p.replace("\\", "/") for p in changed})
    inside = [p for p in changed if p.startswith("backend/")]
    outside = _outside_hit([p for p in changed if not p.startswith("backend/")])
    if outside:
        # ⭐ 动了仓外部位 ⇒ 跑「读那些落点的测试件」＋必跑清单（**不是全跑**）：
        #   读哪些由 `outside_readers()` **现算**，⛔ 不必手工登记（首版手工登记，当场漏了三处）。
        hit = {pref for pref, _ in OUTSIDE_PREFIXES
               if any(p.startswith(pref) for p in outside)}
        readers = outside_readers()
        picked = {n for n, prefs in readers.items() if prefs & hit}
        picked |= {n for n, _ in REPO_WIDE}
        files = {p.name for p in TESTS.glob("test_*.py")}
        picked = {n for n in picked if n in files}
        if not picked:
            return Plan(True, "动了仓外部位却算不出谁读它 ⇒ 全跑")
        return Plan(True, "动了 pytest 在 backend/ 之外也读的落点（%d 处：%s）⇒ 跑读它的 %d 件"
                    % (len(outside), "、".join(outside[:3]), len(picked)), picked)
    if not inside:
        return Plan(False, "本轮既没动 backend/，也没动 pytest 读的仓外部位")
    auto = [p for p in inside if p in {a for a, _ in AUTO_LOADED}]
    if auto:
        return Plan(True, "动了 pytest **自动加载**的件（%s）⇒ 它没有 import 边、算不出 ⇒ 全跑"
                    % "、".join(auto))
    shell = [p for p in inside if p.startswith("backend/app/web/")]
    if shell:
        return Plan(True, "动了壳（backend/app/web/ · %d 处）⇒ 读壳文本的测试件一律全跑" % len(shell))
    odd = [p for p in inside if not p.endswith(".py")]
    if odd:
        return Plan(True, "动了 backend/ 下的非 .py 件（%d 处）⇒ 算不出依赖 ⇒ 全跑" % len(odd))
    mods, files = build_graph()
    seeds = []
    for p in inside:
        m = p[len("backend/"):-3].replace("/", ".")
        if m.endswith(".__init__"):
            m = m[: -len(".__init__")]
        if m not in mods:
            return Plan(True, "改动里有算不出模块的一件（%s）⇒ 全跑" % p)
        seeds.append(m)
    rev: dict = {}
    for m, imps in mods.items():
        for i in imps:
            rev.setdefault(i, set()).add(m)
    aff = set()
    for s in seeds:
        aff |= _impacted(mods, rev, s)
    picked = {n for n, m in files.items() if _reach(mods, m) & aff}
    picked |= {n for n, _ in REPO_WIDE}
    picked = {n for n in picked if n in files}
    if not picked:
        return Plan(True, "选测集算出来是空的 ⇒ 全跑")
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
    首版重拼 `Path(...) / "ops" / "README.md"`，遇到 `Path(__file__).resolve().parents[2]` 就断了
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

    · **缺口**：① 盘上每个 `test_*.py` 都够得着（在 `REPO_WIDE`、或 import 得到 `app.*`、或在 `SELF_ONLY`）；
      ② `OUTSIDE_PREFIXES` 里的落点真在盘上；③ 盘上每个 pytest **自动加载**的件都在 `AUTO_LOADED` 里
      （`conftest.py` 这类件**没有 import 边** ⇒ 漏了它就等于漏跑一大片）。
    · **陈旧**：名单里登记的测试件仍在盘上、且分类还成立。
    """
    mods, files = build_graph()
    reach = {n: _reach(mods, m) for n, m in files.items()}
    wide = {n for n, _ in REPO_WIDE}
    selfonly = {n for n, _ in SELF_ONLY}
    gets_app = {n: any(m.startswith("app.") for m in reach[n]) for n in files}
    readers = set(outside_readers())
    gaps = []
    for n in sorted(files):
        if n in wide or n in readers:
            continue                      # 必跑清单／仓外触发面会带它跑
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
              for n, _ in SELF_ONLY if n in readers]
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
    args = sys.argv[1:]
    if "--cover-only" in args:
        return report_cover()[0]
    if "--explain" in args:
        rest = [a for a in args if a != "--explain"]
        pl = plan(rest[1:] if rest and rest[0] == "--" else changed_paths())
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
