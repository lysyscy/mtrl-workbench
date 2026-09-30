"""`TAIL-102` 的两条守卫：**模型注册表要全** ＋ **元数据与库不许分叉**。

⭐ 为什么必须加机器的守卫（不是"记得跑 `alembic check`"）：
   `alembic check` 是"迁移三连"的第三连 —— 可它**只在有人想起来时才跑**。实测它**从未通过**：
   报 `remove_table user_account` ＋ 两条 `modify_default`（`payment_flow.created_by` / `user_account.account`）
   ＋ `remove_constraint`（`uq_user_account`），而**没有任何尺子看得见**（`TAIL-102` 的原话）。
   ⇒ 下一个人跑 `alembic revision --autogenerate` 就会顺手生成一条**删表 / 删唯一约束**的迁移。
   ⭐ 那种事故的代价不是"build 红"，是**静默把线上数据结构的门拆掉**（本仓最忌的一类）。

两条守卫各守一半：

1. **登记完整**（纯静态）：`app/mod*/models.py` 的**每一个**都必须在 `app/models_registry.py` 里 import。
   漏一个 ⇒ `autogenerate` **看不见**它 ⇒ 反过来判成"**要删掉这张表**"。
   ⚠️ 本次事故的直接原因就是它：`mod15_user` 那行**一直是注释**，而登录/账号体系**早就在跑**
   （`main.py` 挂了它的路由、`core/identity.py` 靠它取"当前登录用户"）⇒ 两处说法不一致，没人发现。
   ⭐ 本件不连库、不跑 alembic ⇒ **库连不上时它照样能救你**。

2. **与库一致**：拿**测试库**（`conftest` 已把 `DATABASE_URL` 指过去 ⇒ 断言天然打在测试库上）
   跑一次 autogenerate 的比对，断言 **0 条差异**。判据与 `alembic check` **同源**
   （`compare_type` / `compare_server_default` 与 `alembic/env.py` 逐字一致）。
   ⚠️ 分叉时**⛔ 不许**用"把库里的东西删掉"来对齐（那要动线上库）：**先判哪边是对的** ——
      多数情况是**模型漏声明了库里早已存在的**默认值/约束 ⇒ **补模型**（声明它 = 零 DDL、零风险）；
      真属库错，才**新写一条迁移**（⛔ 绝不改已应用的迁移）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.acc_plugin import acc

APP = Path(__file__).resolve().parents[1] / "app"
#: ⭐ 2026-09-30（`TAIL-195` 批 1）：登记表**已从 `core/` 挪到装配层**（`app/` 顶层，与 `main.py` 同级）
#:   —— 它的性质是"把全部业务 models 装配进 metadata"，那是装配层的活，不是内核的活。
REGISTRY = APP / "models_registry.py"


def _code_lines(path: Path) -> list[str]:
    """去掉**注释**后的代码行（`#` 前必须有行首或空白 —— ⛔ 别把字符串里的 `#` 也当注释）。

    ⚠️ 这一条是本件能抓到 `TAIL-102` 那个事故的关键：那行导入**是注释**，
       按"文件里搜得到 `mod15_user` 吗"去判 ⇒ **恒为真**（正是本仓最忌的"永远为真的守卫"）。
    """
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        ln = re.sub(r"(^|\s)#.*$", "", raw).strip()
        if ln:
            out.append(ln)
    return out


@acc()
def test_每一个_models_模块都登记进了模型注册表():
    """⭐ 漏登记一个 ⇒ `alembic autogenerate` 判成"**要删掉这张表**"（破坏性、且没人拦）。

    对照（真实事故 · 2026-09-26 `TAIL-102`）：`mod15_user` 漏登记 ⇒ `alembic check` 报
    `remove_table user_account`；而登录体系一直在跑 ⇒ 一份模型、一份库，**两处说法不一致**。
    """
    mods = sorted(p.parent.name for p in APP.glob("mod*/models.py"))
    assert mods, "一条 `app/mod*/models.py` 都没扫到 —— 是测试自己坏了（路径变了？）"
    code = "\n".join(_code_lines(REGISTRY))
    missing = [m for m in mods if f"from app.{m} import models" not in code]
    assert not missing, (
        "这些模块的模型**没登记**进 `app/models_registry.py`："
        + "、".join(f"`{m}`" for m in missing)
        +         "。\n  ⇒ `alembic autogenerate` 看不见它们，会把库里**已有的表判成「要删除」**"
          "（下一个人跑 `--autogenerate` 就会生成删表迁移）。\n"
          "  ⇒ 修法：在 `models_registry.py` 里**取消注释/补上** `from app.<mod> import models as _x  # noqa: F401`，"
          "然后跑一次 `alembic check` 确认元数据与库对得上。"
    )


@acc()
def test_注册表里的导入都指向真实存在的模块():
    """反向那一半：登记表里**不许留有幽灵**（模块被删/改名后忘了改这一行 ⇒ 启动期才炸）。"""
    for ln in _code_lines(REGISTRY):
        m = re.match(r"from (app\.[\w.]+) import models", ln)
        if not m:
            continue
        target = APP.parent / Path(*m.group(1).split(".")) / "models.py"
        assert target.exists(), f"`models_registry.py` 里这行指向的模块已不存在：{ln}"


@acc()
def test_元数据与测试库没有分叉():
    """⭐ 判据与 `alembic check` **同源**（同两个开关）—— 差异必须为 **0**。

    ⚠️ 断言打在**测试库**上（`conftest._point_tests_at_test_db()` 已把 `DATABASE_URL` 换过去，
       且那条熔断保证"解析到的不是测试库就直接失败"）。
    ⚠️ 失败信息里**逐条列出**差异 —— 别只报一句"有差异"（那样下一个人还得自己跑一遍才知道差在哪）。
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    import app.models_registry  # noqa: F401  ← 必须先注册全表（与 `alembic/env.py` 同源）
    from app.core.config import get_settings
    from app.core.db import Base

    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        mc = MigrationContext.configure(
            conn, opts={"compare_type": True, "compare_server_default": True}
        )
        raw = compare_metadata(mc, Base.metadata)

    # ⚠️⚠️ `compare_metadata` 的条目**形态不一致**（实测踩到）：多数是 `(kind, …)` 的平铺元组，
    #   而 `modify_default` 那种是 `((kind, schema, table, col, …),)`（**再套一层**）——
    #   直接拿 `d[0]` 当 `kind` 会得到**一个含 dict 的元组**（`{d[0] for d in diffs}` 当场
    #   `TypeError: unhashable type: 'dict'`，把"报差异"变成"报崩溃"）。⇒ 先归一。
    def _op(d):
        """差异条目 → **操作元组**（`(kind, …)`）。"""
        return d[0] if (d and isinstance(d[0], tuple)) else d

    ops = [_op(d) for d in raw]
    kinds = sorted({str(o[0]) for o in ops})
    if ops:
        lines = []
        for o in ops[:12]:
            kind = o[0]
            if kind == "remove_table":
                lines.append(f"  · remove_table  表 `{o[1].name}`（库有、元数据没有 ⇒ 多半是模型没登记）")
            elif kind == "modify_default":
                lines.append(f"  · modify_default  `{o[2]}.{o[3]}`（库与模型的默认值不一致）")
            elif kind == "remove_constraint":
                name = getattr(o[1], "name", None) or repr(o[1])[:60]
                lines.append(
                    f"  · remove_constraint  `{name}`（库有、模型没声明 ⇒ 会生成「删约束」的迁移）")
            else:
                lines.append(f"  · {kind} {o[1:]}")
        pytest.fail(
            f"元数据与**测试库**分叉（{len(ops)} 条：{'、'.join(kinds)}）—— "
            "`alembic autogenerate` 会据此生成**破坏性迁移**（删表/删约束/改默认值）：\n"
            + "\n".join(lines)
            + "\n  ⇒ 先判**哪边是对的**：多数情况是**模型漏声明了库里早已有的**默认值/约束 ⇒ **补模型**"
              "（零 DDL、零风险）；真属库错才**新写一条迁移**（⛔ 绝不改已应用的迁移）。\n"
              "  ⇒ 若测试库自己落后（少了别人新加的迁移）：把 `.env` 的 `TEST_DATABASE_URL` 那个库"
              " `alembic upgrade head` 补上（两个库都要到 head）。"
        )
