"""`MOD-09` 特殊费用月报表验收断言的离线桩（**不连库**）。

⚠️ 为什么不用 `m04_helpers.FakeSession`：它**忽略 `where`**（按模型类型整表返回）
   ⇒ 本用例的核心判据「增 / 改 / 删**只落在那一份**（核算年月 ＋ 项目）」就**看不出区别** ——
   那正是「断言看着有、其实没区分力」的温床。本桩**honor 简单等值过滤**（`col == 值` 的 AND）。
⚠️ 认不出的 where 形态 ⇒ **直接报错**，**不静默不过滤**（宁报错，不假绿）。
⚠️ 不处理 `order_by` —— 行按**添加顺序**保存，与真实库的自增 id 顺序一致。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList

from app.mod01_projects.models import Project
from app.mod08_inv.models import InvDetail
from app.mod09_fee.models import FeeManualItem
from tests.m04_helpers import make_project


class _Result:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list:
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        """⚠️ 桩件**补缺**（2026-09-18）：`repository._next_ord` 走 `select(func.max(Project.ord))`
        ⇒ 真库那边返回 NULL ⇒ `None`；不实现它本桩会抛 `AttributeError`（同 `m08_helpers` 那次）。
        """
        if not self._rows:
            return None
        if len(self._rows) > 1:
            raise AssertionError(f"scalar_one_or_none 收到 {len(self._rows)} 条（桩只认 0 / 1 条）")
        return self._rows[0]


def _terms(where) -> list[tuple[str, object]]:
    """从 where 子句里抽 `(列名, 值)`；只认 `==`。

    ⚠️ 判等号要用 `operator.__name__ == "eq"` —— `str(operators.eq)` 得到的是
       `<built-in function eq>`（不是 `"="`），**用字符串比会永远不命中**（2026-09-17 实测踩到）。
    """
    out: list[tuple[str, object]] = []
    stack = [where] if where is not None else []
    while stack:
        node = stack.pop()
        if isinstance(node, BooleanClauseList):
            stack.extend(node.get_children())
            continue
        if isinstance(node, BinaryExpression) and getattr(node.operator, "__name__", "") == "eq":
            col = getattr(node.left, "key", None)
            if col is not None:
                out.append((col, getattr(node.right, "value", None)))
                continue
        raise AssertionError(f"桩不支持这个 where 形态：{node!r} —— 请扩桩，别让它静默不过滤")
    return out


class M09Session:
    """按模型类型分发 ＋ **honor 等值过滤**的最小会话桩。"""

    def __init__(self, by_model: dict | None = None) -> None:
        self.by_model: dict = dict(by_model or {})
        self.added: list = []

    def execute(self, stmt):  # noqa: ANN001
        entity = stmt.column_descriptions[0]["entity"]
        rows = list(self.by_model.get(entity, []))
        for col, want in _terms(stmt.whereclause):
            rows = [r for r in rows if getattr(r, col, None) == want]
        return _Result(rows)

    def get(self, model, ident):  # noqa: ANN001
        return next((r for r in self.by_model.get(model, []) if r.id == ident), None)

    def add(self, row) -> None:  # noqa: ANN001
        rows = self.by_model.setdefault(type(row), [])
        if getattr(row, "id", None) is None:
            row.id = max((getattr(r, "id", 0) or 0) for r in rows) + 1 if rows else 1
        rows.append(row)
        self.added.append(row)

    def delete(self, row) -> None:  # noqa: ANN001
        rows = self.by_model.get(type(row), [])
        if row in rows:
            rows.remove(row)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


# ---------------------------------------------------------------- 样本数据（口径自洽）

YM_NOW = "2026-08"          # 已录的月
YM_OTHER = "2026-07"        # 未录的月（判「不带入」用）
WH_A, WH_B = "甲仓库", "乙仓库"


def make_inv(ym: str, warehouse: str, direction: str, cbs: str, amount: str, *, rid: int = 0) -> InvDetail:
    return InvDetail(id=rid or abs(hash((ym, warehouse, direction, cbs, amount))) % 10**6 + 1,
                     ym=ym, warehouse_name=warehouse, direction=direction, cbs_name=cbs,
                     amount=Decimal(amount))


def make_item(iid: int, ym: str, project_id: int, name: str, amount: str) -> FeeManualItem:
    return FeeManualItem(id=iid, ym=ym, project_id=project_id, item_name=name,
                         amount=Decimal(amount))


def session() -> M09Session:
    """一份自洽样本：

    - 自动项只认 **该月 · 该仓库 · `CBS-安文费` · 出库** —— 故意埋四类"不该算"的行（入库 / 别 CBS /
      别仓库 / 别月），用来钉住取数条件。
    - 手填项只有 **(2026-08, 甲仓库)** 那一份（两项）；(2026-07, 甲仓库) 与 (2026-08, 乙仓库) 都是"未录"。
    - 项目档案：甲 / 乙（有仓库）＋ 一个**壳**（无仓库 ⇒ 不该进候选）。
    """
    projects = [
        make_project(11, WH_A, "甲公司项目"),
        make_project(12, WH_B, "乙公司项目"),
        Project(id=13, project_type="shell", name_full="某壳项目", warehouse_name=None, disp="某壳"),
    ]
    inv = [
        make_inv(YM_NOW, WH_A, "出库", "CBS-安文费", "1000.00", rid=101),   # ✅ 算
        make_inv(YM_NOW, WH_A, "入库", "CBS-安文费", "500.00", rid=102),    # ✗ 非出库
        make_inv(YM_NOW, WH_A, "出库", "CBS-其他", "700.00", rid=103),      # ✗ 别的 CBS
        make_inv(YM_NOW, WH_B, "出库", "CBS-安文费", "2000.00", rid=104),   # ✗ 别的仓库
        make_inv(YM_OTHER, WH_A, "出库", "CBS-安文费", "3000.00", rid=105), # ✗ 别的月
    ]
    items = [
        make_item(201, YM_NOW, 11, "油卡使用", "100.00"),
        make_item(202, YM_NOW, 11, "运费", "200.00"),
    ]
    return M09Session({Project: projects, InvDetail: inv, FeeManualItem: items})


__all__ = ["M09Session", "session", "make_inv", "make_item", "YM_NOW", "YM_OTHER", "WH_A", "WH_B"]
