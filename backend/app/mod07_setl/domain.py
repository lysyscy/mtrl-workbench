"""`MOD-07` 收发结存月报 —— **域内核**（纯函数：不连库、不写路由）。

口径回主人处读，本处只落形态：
- 《说明书》**§5.3.1**（用途**仅两个**：① 总公司资产处每月要 ② 会议大表里提取焊材和气体）
- 《说明书》**§5.3.2**（交付形态 = **分仓库表 + 原表加透视表**，打包 zip；金额按 2 位小数对平、**容差 0**）
- 《说明书》**§9.1**（金额：`Decimal` · `ROUND_HALF_UP` · **判定容差 0**）· **§9.2**（材料报表类默认核算年月 = 上月）
- 《技术栈选型分析》**§9.8**（`API-02`：项目参数 key = `pc`；`reportName` **需传表名**）

列结构主人 = **原型 `WH_THEAD`**（原型 = 交互规格）；`key` = 域内规范字段名 ——
视图 / 导出**一律用它**，不得在别处写列名字面量。

⚠️ 本表**没有「项目全名」列**：认项目只靠**仓库名**（§2.7.4「键 = 仓库名」）。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import is_zero, sum_money, to_money
from app.core.period import default_period, month_of

# 抓取对象名（`§3.1.1` 数据来源清单；弹窗与执行记录都用它）
CHANNEL = "收发结存表"

# 本表属**材料报表类** ⇒ 默认核算年月 = 北京时间**上月**（§9.2）
DEFAULT_TABLE = "settle"

# 交付物命名的**单位主体**（主人 =《说明书》§1「业务主体 = 河南省安装集团第四工程公司机关材料科」；
# 命名形态照原型 `zipSfjc`）—— 只此一处，改名只改这里。
ORG_NAME = "第四工程公司"


# ============================================================ 列（唯一出口）

# `type`：`text` / `num` / `state`（状态标签，不可排、不求和）
SETL_COLUMNS: tuple[dict, ...] = (
    {"key": "warehouse", "label": "仓库名", "type": "text", "sortable": True},
    {"key": "rows", "label": "行数", "type": "num", "sortable": True},
    {"key": "begin", "label": "期初金额", "type": "num", "sortable": True},
    {"key": "in", "label": "收金额", "type": "num", "sortable": True},
    {"key": "out", "label": "发金额", "type": "num", "sortable": True},
    {"key": "end", "label": "结存金额", "type": "num", "sortable": True},
    {"key": "check", "label": "校验", "type": "state", "sortable": False},
)

WAREHOUSE_KEY = "warehouse"
ROWCOUNT_KEY = "rows"
CHECK_KEY = "check"
# 明细行的稳定排序键（同仓内）；也是落库唯一键的一半（另一半 = 核算月 ＋ 仓库名）
RESOURCE_CODE_KEY = "resource_code"

# 四个金额列（**对平口径**就在它们身上）
AMOUNT_KEYS: tuple[str, ...] = ("begin", "in", "out", "end")
# 合计行求和的列（**行数也合** —— 001-01 明写「行数合计 = 各仓行数之和」）
SUM_KEYS: tuple[str, ...] = (ROWCOUNT_KEY,) + AMOUNT_KEYS

TOTAL_LABEL = "合计"
BALANCE_OK = "已对平"

# ============================================================ 硬边界（`MOD-07` §三）

# 动作 id → 依据（本页**不得**出现这些入口）
FORBIDDEN_ACTIONS: dict[str, str] = {
    "colset": "NG-01（列设置面板）",
    "colwidth": "NG-02（列宽拖动）",
    "remind": "NG-04（提醒与督办）",
}
# 页面上**不得出现**的字样（同一条硬边界，防"换个写法绕过去"）
FORBIDDEN_TEXTS: tuple[tuple[str, str], ...] = (
    ("列设置", "NG-01"), ("列宽", "NG-02"), ("提醒", "NG-04"), ("督办", "NG-04"),
)


def column_meta(key: str) -> dict | None:
    for col in SETL_COLUMNS:
        if col["key"] == key:
            return col
    return None


def column_keys() -> tuple[str, ...]:
    return tuple(c["key"] for c in SETL_COLUMNS)


def boundary_violations(*, html: str = "", action_ids=()) -> list[str]:
    """硬边界自检（空 = 合规）：**不做列设置 / 列宽拖动 / 提醒督办**（`NG-01` `NG-02` `NG-04`）。"""
    bad: list[str] = []
    for act in action_ids or ():
        ref = FORBIDDEN_ACTIONS.get(str(act).lower())
        if ref:
            bad.append(f"本页不得出现「{act}」入口（{ref}）")
    for word, ref in FORBIDDEN_TEXTS:
        if word in str(html or ""):
            bad.append(f"本页不得出现「{word}」字样（{ref}）")
    return bad


# ============================================================ 按月取数（唯一出口）

def default_month(now=None) -> str:
    """默认核算年月 = **北京时间上月**（§9.2；材料报表类）。"""
    return default_period(DEFAULT_TABLE, now)


def rows_of(all_rows, ym: str) -> list[dict]:
    """**按月取数出口**（唯一）：从全部**明细行**里取该核算年月的那一份。

    ⚠️ 行序 = **资源编码升序**（同仓内稳定；跨仓排序见 `aggregate_by_warehouse`）；
       月与月之间**互不覆盖**（换月只是换一份，不是清空）。
    """
    want = str(ym or "")
    picked = [r for r in (all_rows or ()) if str(r.get("ym") or "") == want]
    return sorted(picked, key=lambda r: str(r.get(RESOURCE_CODE_KEY) or ""))


def aggregate_by_warehouse(details) -> list[dict]:
    """**明细行 → 每仓一行**（页面的表体 / 产出物清单都吃这一份）。

    - `rows` = 该仓的**明细行数**（§5.3.2 的「行 / 仓 / 文件」三项计数里的「行」）
    - 四个金额列 = 该仓明细的**求和**（金额口径走 `core.money`，逐笔归一到 2 位小数）
    - 行序 = **仓库名升序**（本表数据来自 i8 导出，与项目档案的 `ord` 无关）

    ⚠️ 汇总**只在域内核做**（库里存的是明细，"表格汇总"与"分仓库工作簿"共用同一份明细）。
    """
    buckets: dict[str, list[dict]] = {}
    for d in details or ():
        buckets.setdefault(str(d.get(WAREHOUSE_KEY) or ""), []).append(d)
    out: list[dict] = []
    for warehouse, group in buckets.items():
        row: dict = {WAREHOUSE_KEY: warehouse, ROWCOUNT_KEY: len(group)}
        for key in AMOUNT_KEYS:
            row[key] = sum_money([g.get(key) for g in group])
        out.append(row)
    return sorted(out, key=lambda r: str(r.get(WAREHOUSE_KEY) or ""))


def warehouse_rows(all_details, ym: str) -> list[dict]:
    """**页面 / 清单的唯一取数出口** = 按月取数（`rows_of`）＋ 按仓汇总（`aggregate_by_warehouse`）。"""
    return aggregate_by_warehouse(rows_of(all_details, ym))


def row_total(rows) -> int:
    """**行数合计** = 各仓行数之和（001-01 的独立复算对象）。"""
    return sum(int(r.get(ROWCOUNT_KEY) or 0) for r in (rows or ()))


def warehouse_count(rows) -> int:
    """仓库数 = 表体行数（每仓一行）。"""
    return len(list(rows or ()))


# ============================================================ 对平（容差 0，§9.1）

def balance(row: dict) -> Decimal:
    """**对平差额** = 期初 ＋ 收 － 发 － 结存（各自归一到 2 位小数后算）。"""
    total = to_money(row.get("begin") or 0)
    total += to_money(row.get("in") or 0)
    total -= to_money(row.get("out") or 0)
    total -= to_money(row.get("end") or 0)
    return to_money(total)


def is_balanced(row: dict) -> bool:
    """对平判据 = **按 2 位小数归一后判等（容差 0）**（§9.1；不用 0.005 之类的松容差）。"""
    return is_zero(balance(row))


def check_text(row: dict) -> str:
    """校验列的文字（页面与导出**共用**这一份）。"""
    diff = balance(row)
    return BALANCE_OK if is_zero(diff) else f"差 {diff:,.2f}"


def check_level(row: dict) -> str:
    """校验列的状态档（`ok` / `dg`）—— 供视图上色，判据仍是 `is_balanced`。"""
    return "ok" if is_balanced(row) else "dg"


# ============================================================ 合计 / 计数 / 产出物

def sum_row(rows) -> dict:
    """表内**合计行**：行数与四个金额列各自求和；校验格 = **对合计值本身**再判一次（不抄各仓结论）。"""
    rows = list(rows or ())
    if not rows:
        return {}
    out: dict = {WAREHOUSE_KEY: TOTAL_LABEL, ROWCOUNT_KEY: row_total(rows)}
    for key in AMOUNT_KEYS:
        out[key] = sum_money([r.get(key) for r in rows])
    out[CHECK_KEY] = check_text(out)
    return out


def counts(rows, ym: str = "") -> dict:
    """页面「行 / 仓 / 文件」**三项计数**（001-07）—— 一律**实时算**，不得写死。"""
    n = warehouse_count(rows)
    return {"warehouses": n, "rows": row_total(rows), "files": file_count(n), "ym": str(ym or "")}


def file_count(warehouse_n: int) -> int:
    """产出物份数 = **分仓库工作簿（每仓一份）＋ 总表（1 份）**（§5.3.2）。"""
    return int(warehouse_n) + 1


def period_label(ym: str) -> str:
    """`2026-09` → `2026年9月`（成品文件名里的**期间标签**）—— ⛔ **只此一处转换**。

    ⚠️ 它与 `core.period.export_filename`（`表名-YYYY-MM` 那**另一族**命名）**不是一回事**：
       收发结存的成品名照**用户手作成品**的写法 —— 2026-09-17 真机跑通的那次产出就是
       `第四工程公司2026年9月收发结存表.zip`（`docs/reference/template-export.md` §二）。
    ⚠️ 传进来的若不是干净的 `YYYY-MM` ⇒ **原样返回**（⛔ 不抛、也不臆造一个月份）。
    """
    s = str(ym or "").strip()
    if len(s) == 7 and s[4] == "-" and s[:4].isdigit() and s[5:].isdigit():
        return f"{int(s[:4])}年{int(s[5:])}月"
    return s


def total_workbook_name(ym: str) -> str:
    return f"{ORG_NAME}{period_label(ym)}收发结存表.xlsx"


def zip_name(ym: str) -> str:
    return f"{ORG_NAME}{period_label(ym)}收发结存表.zip"


def zip_manifest(rows, ym: str) -> list[dict]:
    """**产出物清单**（001-08）：分仓库工作簿（每仓一份）＋ 总表。

    ⚠️ 份数**随仓数实时算** —— 清单里 `kind == "warehouse"` 的条数恒等于仓数。
    ⚠️ 本函数只产**清单**；文件本身走路径②（脚本改 i8 导出源文件，`demo/模板/模板清单.md` §一）。
    """
    rows = list(rows or ())
    out = [{"name": f"{r.get(WAREHOUSE_KEY)}.xlsx", "kind": "warehouse"} for r in rows]
    out.append({"name": total_workbook_name(ym), "kind": "total"})
    return out


# ============================================================ 焊材 / 气体提取（§5.3.3）
#
# ⚠️ 这一段**已拆到 `app/mod07_setl/extract.py`**（本文件超 400 行登记线，2026-09-16 纯搬代码拆出，
#    **一处逻辑未改**）。提取相关的常量 / 规则 / 取数 / 导出矩阵**一律去那里**；
#    本文件只管「收发结存月报」本条线。
#    依赖方向是**单向**的：`extract` → `domain`（用它的 `WAREHOUSE_KEY` / `TOTAL_LABEL`），
#    `domain` **不得**反向 import `extract`（会成环）。


# ============================================================ 抓取弹窗

def fetch_dialog_default(current_period: str) -> str:
    """「按月抓取」弹窗的**默认月份** = **本页当前所选核算年月**（001-06）。

    ⚠️ 抓取只允许**单月**（§9.2）⇒ 当前所选不是单月时回落到本表默认年月（上月）。
    """
    return month_of(current_period) or default_month()


# ============================================================ 空态

def empty_text(ym: str) -> str:
    """空态提示行文字（跨列数由 `render_list_page` 按表头列数派生，**不写死数字**）。"""
    label = str(ym or "")
    return f"{label} 没有收发结存数据 —— 换个「核算年月」，或点「抓取 i8」"


__all__ = [
    "CHANNEL", "DEFAULT_TABLE", "ORG_NAME",
    "SETL_COLUMNS", "WAREHOUSE_KEY", "ROWCOUNT_KEY", "CHECK_KEY", "RESOURCE_CODE_KEY",
    "AMOUNT_KEYS", "SUM_KEYS", "TOTAL_LABEL", "BALANCE_OK",
    "FORBIDDEN_ACTIONS", "FORBIDDEN_TEXTS",
    "column_meta", "column_keys", "boundary_violations",
    "default_month", "rows_of", "aggregate_by_warehouse", "warehouse_rows",
    "row_total", "warehouse_count",
    "balance", "is_balanced", "check_text", "check_level",
    "sum_row", "counts", "file_count", "period_label", "total_workbook_name", "zip_name", "zip_manifest",
    "fetch_dialog_default", "empty_text",
    # 焊材 / 气体提取（§5.3.3）的出口**不在这里** ⇒ 见 `app/mod07_setl/extract.py`
]
