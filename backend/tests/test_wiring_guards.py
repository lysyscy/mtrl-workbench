"""工程守卫自检：**「防回归」断言必须真的被调用**。

⚠️ 为什么有这个文件（2026-09-17，`tools/wiring_audit.py` 抓出来的）：
    `assert_single_external_source()`（`mod02_i8/fetch_task.py`）docstring 自称
    「**防回归**：外部数据源只能是 i8」，但**生产与测试都没人调用它** ⇒ **守卫失效**
    （防了个寂寞：真有人接第二个数据源，它也不会响）。

⭐ 这是「**写好的口径没人接**」的又一种形态 —— 与 `ensure_batch_settled` 同类，
   区别只在：那个是**业务判定**没接进链路，这个是**守卫**没人调用。

⚠️ 本文件是**工程自检**（`@acc()` 显式不绑定）—— 它绿 ≠ 判据点绿；
   它守的是「守卫本身还有人调」这件事。
"""

import builtins
import dis
import importlib
import pkgutil
import types

from app.mod02_i8.fetch_task import EXTERNAL_SOURCES, assert_single_external_source
from tests.acc_plugin import acc


@acc()
def test_外部数据源只能是i8这个守卫真的被调用():
    """`assert_single_external_source` 必须**真的被调用**，否则它是无效守卫。

    ⚠️ 变异验证：把本测试里的 `assert_single_external_source()` 去掉 ⇒
       `tools/wiring_audit.py` 的 `W1` 必须重新报红。
    """
    assert EXTERNAL_SOURCES == ("i8",), (
        "外部数据源被改动了 —— i8 是唯一外部数据源（《说明书》§6.1.2 / NG-13 / DEV-J-05）"
    )
    assert_single_external_source()          # 不抛异常 = 守卫在位


def _codes(root) -> list:
    """函数 ＋ 它内部**所有嵌套函数/推导式**的 code 对象。

    ⚠️ 必须递归：`notice_executors._exec` 就住在 `get_batch_executor` **内部**（藏在 `co_consts` 里）
       —— 只扫外层等于**正好漏掉出事的那个**。
    """
    stack, out = [root.__code__], []
    while stack:
        c = stack.pop()
        out.append(c)
        for const in c.co_consts:
            if isinstance(const, types.CodeType):
                stack.append(const)
    return out


def _undefined_globals(module) -> list[str]:
    """模块里**本模块定义**的函数/方法，引用到的、既不在它 `__globals__`、也不在内建的名字。

    ⚠️ **只看 `LOAD_GLOBAL`**：属性名（`.close` / `.strip`）走 `LOAD_ATTR` ⇒ 用 `co_names`
       会把它们全算进来，造出几十条误报。
    ⚠️ 判据用**函数自己的 `__globals__`**（⛔ 不是模块的 `vars()`）：`@dataclass` 生成的 `__repr__`
       用的是 `reprlib.get_ident`、`@contextmanager` 的包装函数用的是 `contextlib._GeneratorContextManager`
       —— 它们的 globals 在**别的模块**；按模块判会误报（实测 v1 报出 44 条，真凶只有 3 条）。
    """
    bad: list[str] = []

    def check(fn, label: str) -> None:
        g = fn.__globals__
        for code in _codes(fn):
            for ins in dis.get_instructions(code):
                if ins.opname != "LOAD_GLOBAL":
                    continue
                n = str(ins.argval)
                if n not in g and not hasattr(builtins, n):
                    bad.append(f"{label} 用了未定义的 `{n}`")

    here = vars(module)
    for name, obj in list(here.items()):
        if isinstance(obj, types.FunctionType) and obj.__globals__ is here:
            check(obj, f"{module.__name__}::{name}")
        elif isinstance(obj, type) and obj.__module__ == module.__name__:
            for mname, m in list(vars(obj).items()):
                # ⚠️ 只查**本模块定义**的方法：`@dataclass` 生成的 `__repr__` 等来自别处
                if isinstance(m, types.FunctionType) and m.__globals__ is here:
                    check(m, f"{module.__name__}::{name}.{mname}")
    return bad


@acc()
def test_全仓没有一个未定义的名字_拆件漏import():
    """⚠️⚠️ 把「**拆件漏 import**」从**运行时**提前到**测试期**。

    ⭐ 2026-09-20 用户实测报「只导出 PDF 没能完成」揪出来的 —— 同一次拆件（09-19）留下**三处**：

    | 位置 | 症状 |
    |---|---|
    | `notice_executors._exec` 用 `get_notices_by_ids` 没 import | 每次点「批量打印 / 只导出 PDF」都炸 |
    | `notice_executors.get_fetch_executor` 用 `MustReportError` 没 import | 抓付款通知书时炸（**把一句能指路的中文换成一句 `NameError`**） |
    | `mod11_jc.fetch_service.default_since` 用 `logger` 没定义 | 合同日期不合法时炸（**本意是"保守回落全量 + 留个印子"**） |

    ⚠️⚠️ **为什么测试全绿也没拦住**：这些链路的测试**一律用 `dependency_overrides` 注入假执行器**
       ⇒ **真实现从不被调用** ⇒ `NameError` 根本不发生。这是"**假绿的另一种形态**"：
       不是断言写松了，而是**被测的那条路测试根本不走**。
    ⇒ 这条断言不看行为、**只看字节码**：静态走一遍，找 `LOAD_GLOBAL` 到一个
      既不在本模块 `__globals__`、也不在内建里的名字。
    """
    import app

    mods = sorted({m.name for m in pkgutil.walk_packages(app.__path__, "app.")})
    assert len(mods) > 100, f"扫到的模块太少（{len(mods)}）—— 路径或包结构变了，本守卫已失效"

    bad: list[str] = []
    for mn in mods:
        try:
            mod = importlib.import_module(mn)
        except Exception:                       # noqa: BLE001
            # ⚠️ import 不进来的模块**跳过**：它的问题会在别处以别的形态暴露；
            #    在这里把"import 失败"当成"未定义名"会把两件事混成一件。
            continue
        bad.extend(_undefined_globals(mod))

    assert not bad, (
        "有名字**没定义也没 import** ⇒ 运行时必 `NameError`（拆件漏 import 的典型）：\n  "
        + "\n  ".join(sorted(set(bad)))
    )
