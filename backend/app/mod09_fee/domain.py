"""`MOD-09` 特殊费用月报表 · **域内核**（纯函数：不连库、不写路由）。

口径主人（**只引用、不复述取值**）：
- 《说明书》**§5.5** —— 本表 = **1 个自动项 ＋ N 个手填项**（可增项、项名可改）；
  **自动项与手填项都只统计所选项目**；手填项**按「核算年月 ＋ 项目」各存一份**；
  取值判据 = 手填项**只拦「非数字」，允许 0 与负数**（§8.4 三档中的**最宽松**一档）。
- **§2.7.4** —— 项目**候选键 = 仓库名**（比较 / 分桶 / 归集一律用它）；**写库仍按档案 id**。
- **§9.2** —— 材料报表类默认年月 = **北京时间上月**；本页**只开放「按月」**。
- **§5.7.2** —— 「上次值带入」**只属活动大表**（`MOD-07`）⇒ 本表**不带入**，未录的月就是空。
- `DEV-R-04` —— 本表是**独立新报表**，不是库存单据的第 3 张透视。

⚠️ **自动项的取数用「核算年月」（`inv_detail.ym`），不用单据日期前缀** ——
   原型演示数据没有核算月列、拿单据日期前缀代替；口径要的是**核算年月**（§5.5 / §9.2）。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.period import default_period
from app.core.money import amount_text

# ---------------------------------------------------------------- 口径常量（唯一出口）

#: 自动项 = **唯一**的系统生成项：安全文明施工费（**按 CBS 分类**取数）
AUTO_NAME_MAIN = "安全文明施工费"
AUTO_NAME_NOTE = "按 CBS 分类"
AUTO_NAME = f"{AUTO_NAME_MAIN}（{AUTO_NAME_NOTE}）"

#: 取数点（§5.5）：库存单据明细里 CBS = 本类目、且方向 = 出库的金额
CBS_AWF = "CBS-安文费"
DIRECTION_OUT = "出库"

#: 新增手填项的初值（原型同款：「名称可改、金额可填」）
DEFAULT_ITEM_NAME = "新项"
ZERO = Decimal("0.00")

SOURCE_AUTO = "系统生成（唯一自动项）"
SOURCE_MANUAL = "手填"
NOTE_AUTO_READONLY = "自动项不可改"

#: 表头（5 列，与原型 `AWF_THEAD` **同名同序**）—— 视图**不写字面量**
AWF_COLUMNS: tuple[dict[str, Any], ...] = (
    {"key": "item", "label": "数据项", "type": "text"},
    {"key": "source", "label": "来源", "type": "text"},
    {"key": "amount", "label": "金额", "type": "num"},
    {"key": "share", "label": "占合计", "type": "text"},
    {"key": "ops", "label": "操作", "type": "text"},
)

#: 「操作」列（按钮 / 表单 HTML）**只在页面上成立** ⇒ `/api/*` 导出必须剔除
PAGE_ONLY_KEYS: tuple[str, ...] = ("ops",)

#: 合计行只求这一列（「占合计」是派生比例，不求和）
SUM_KEYS: tuple[str, ...] = ("amount",)

#: 空态提示行的**跨列数**由表头列数派生（不写死）
EMPTY_COLSPAN = len(AWF_COLUMNS)

MSG_BAD_AMOUNT = "金额不合法：请填数字（2 位小数，允许 0 与负数），已保留原值"
#: 删除反馈里项名为空时的显示（原型同款：`r[0] || '未命名'`）——**不强制项名非空**（§5.5 没这条）
UNNAMED = "未命名"

#: 页面标题栏那句固定说明（口径在 §5.5/§7.1，此处只写事实）
EXPORT_NOTE = "随「逐月欠款台账」导出（工作表：辅材欠款 / 机械欠款 / 特殊费用月报表）"
EXPORT_BOUNDARY = "本页**不设单独的导出按钮**（§7.1 / §5.5）"


# ---------------------------------------------------------------- 时间 / 金额（纯函数）


def default_ym(now=None) -> str:
    """本页默认核算年月 —— **材料报表类 = 北京时间上月**（§9.2，唯一出口 = `core.period`）。"""
    return default_period("fee", now)


def parse_ym(raw) -> str | None:
    """核算年月：**只接受 `YYYY-MM`**（本页只开放「按月」，跨月 / 整年 / 全部一律不认）。"""
    v = str(raw if raw is not None else "").strip()
    if len(v) != 7 or v[4] != "-":
        return None
    if not (v[:4].isdigit() and v[5:].isdigit()):
        return None
    return v if 1 <= int(v[5:]) <= 12 else None


def parse_amount(raw) -> Decimal:
    """手填金额（§5.5 / §8.4 第 ③ 档）：**只拦「非数字」，允许 0 与负数**；空 ⇒ 0。"""
    text = amount_text(raw)
    if not text:
        return ZERO
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ArithmeticError, ValueError) as exc:
        raise ValueError(MSG_BAD_AMOUNT) from exc


def amount_problem(raw) -> str | None:
    """金额判据出口 → `None` = 合法；否则返回**要显式报出**的消息（must-report）。"""
    try:
        parse_amount(raw)
    except ValueError as exc:
        return str(exc)
    return None


def money_text(value) -> str:
    """金额显示（千分位 · 2 位小数）；空值 ⇒ 空串（**不臆造 0**）。"""
    if value in (None, ""):
        return ""
    try:
        return f"{Decimal(str(value)):,.2f}"
    except Exception:  # noqa: BLE001 - 非金额一律原样
        return str(value)


# ---------------------------------------------------------------- 取数（自动项 / 手填项）


def auto_amount(inv_rows: list[dict], *, ym: str, project_key: str) -> Decimal:
    """**自动项** = 所选「核算年月 ＋ 项目」下 `CBS-安文费` 的**出库**金额之和（§5.5）。

    ⚠️ 项目比较一律用**仓库名**（§2.7.4）；合计**不臆造 0** ⇒ 无命中就是 0.00（金额口径容差 0）。
    """
    total = ZERO
    for r in inv_rows or ():
        if str(r.get("ym") or "") != str(ym or ""):
            continue
        if str(r.get("warehouse") or "") != str(project_key or ""):
            continue
        if str(r.get("cbs") or "") != CBS_AWF or str(r.get("direction") or "") != DIRECTION_OUT:
            continue
        total += Decimal(str(r.get("amount") or 0))
    return total.quantize(Decimal("0.01"))


def sum_items(items: list[dict] | None) -> Decimal:
    """Σ 手填项（**该月 · 该项目那一份**的项，不跨月不跨项目）。"""
    total = ZERO
    for it in items or ():
        total += Decimal(str(it.get("amount") or 0))
    return total.quantize(Decimal("0.01"))


def total_amount(inv_rows: list[dict], items: list[dict] | None, *, ym: str, project_key: str) -> Decimal:
    """合计 = **该月 · 该项目**的自动项 ＋ Σ 该月 · 该项目手填项（§5.5）。"""
    return (auto_amount(inv_rows, ym=ym, project_key=project_key) + sum_items(items)).quantize(
        Decimal("0.01")
    )


def annual_rows(*, year: str, project_key: str, items: list[dict], inv_rows: list[dict]) -> dict:
    """按原始项名汇总；空月与真实零分开，累计只加往年及所选年。"""
    rows = {AUTO_NAME: {"item": AUTO_NAME, "manual": False, "prior": ZERO,
                        "months": [ZERO for _ in range(12)], "periods": set()}}

    def add(name, ym, amount, manual):
        if not parse_ym(ym) or ym > f"{year}-12":
            return
        row = rows.setdefault(name, {"item": name, "manual": True, "prior": None,
                                    "months": [None for _ in range(12)], "periods": set()})
        row["manual"] = row["manual"] or manual
        row["periods"].add(ym)
        value = Decimal(str(amount or 0))
        if ym < f"{year}-01":
            row["prior"] = (row["prior"] or ZERO) + value
        else:
            month = int(ym[5:]) - 1
            row["months"][month] = (row["months"][month] or ZERO) + value

    for r in inv_rows:
        if r.get("warehouse") == project_key and r.get("cbs") == CBS_AWF and r.get("direction") == DIRECTION_OUT:
            add(AUTO_NAME, str(r.get("ym") or ""), r.get("amount"), False)
    for r in items:
        add(str(r.get("name") or ""), str(r.get("ym") or ""), r.get("amount"), True)
    result = []
    for row in rows.values():
        row["total"] = (row["prior"] or ZERO) + sum((v or ZERO for v in row["months"]), ZERO)
        row["periods"] = sorted(row["periods"])
        result.append(row)
    return {"rows": result, "prior": sum((r["prior"] or ZERO for r in result), ZERO),
            "months": [sum((r["months"][i] or ZERO for r in result), ZERO) for i in range(12)],
            "total": sum((r["total"] for r in result), ZERO)}


def share_text(part, total) -> str:
    """「占合计」= 该项 / 合计；**合计 ≤ 0 ⇒ 「—」**（不是 `NaN%`、也不是 0.0%）。"""
    t = Decimal(str(total or 0))
    if t <= 0:
        return "—"
    return f"{(Decimal(str(part or 0)) / t * 100):.1f}%"


# ---------------------------------------------------------------- 行装配（视图只取值）


def auto_row(*, auto, total) -> dict:
    """自动项那一行（**只读、不可改**，恒在第一条数据行）。"""
    return {
        "kind": "auto",
        "item": AUTO_NAME,
        "source": SOURCE_AUTO,
        "amount": auto,
        "share": share_text(auto, total),
        "ops": NOTE_AUTO_READONLY,
    }


def manual_rows(items: list[dict] | None, *, total) -> list[dict]:
    """手填行（按录入顺序 = 该份内的下标；项名可改、金额可填、可删）。"""
    return [
        {
            "kind": "manual",
            "index": i,
            "id": it.get("id"),
            "item": str(it.get("name") or ""),
            "source": SOURCE_MANUAL,
            "amount": Decimal(str(it.get("amount") or 0)),
            "share": share_text(it.get("amount") or 0, total),
        }
        for i, it in enumerate(items or ())
    ]


def summary_row(*, total) -> dict:
    """合计行（「数据项」格写「合计」，被钉在表尾）。"""
    out = {c["key"]: "" for c in AWF_COLUMNS}
    out[AWF_COLUMNS[0]["key"]] = "合计"
    out["amount"] = money_text(total)
    out["share"] = share_text(total, total)
    return out


__all__ = [
    "AUTO_NAME", "AUTO_NAME_MAIN", "AUTO_NAME_NOTE", "CBS_AWF", "DIRECTION_OUT",
    "DEFAULT_ITEM_NAME", "SOURCE_AUTO", "SOURCE_MANUAL", "NOTE_AUTO_READONLY",
    "AWF_COLUMNS", "PAGE_ONLY_KEYS", "SUM_KEYS", "EMPTY_COLSPAN",
    "MSG_BAD_AMOUNT", "UNNAMED", "EXPORT_NOTE", "EXPORT_BOUNDARY",
    "default_ym", "parse_ym", "parse_amount", "amount_problem", "money_text",
    "auto_amount", "sum_items", "total_amount", "share_text",
    "auto_row", "manual_rows", "summary_row",
]
